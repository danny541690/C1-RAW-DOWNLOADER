#!/usr/bin/env python3
"""JARVIS v0.97 Bronze-only evidence builder, incrementally per source_id.

Recovers existing source proof, validates ORIGINAL bytes, classifies missing
official/independent/full-file/PIT evidence and persists checkpoint receipts.
Never manufactures a historical publisher response, never modifies Bronze, and
never releases to Silver/Gold. A candidate claim is not a signed release.
"""
import hashlib,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api,digest
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_seven_native_v2_probe import checkpoint_commit
from scripts.v097_evidence_contract import safe_evidence_claim,VERSION as CONTRACT

VERSION="v097_fullfile_evidence_builder_v1"
BATCH=max(1,min(100,int(os.getenv("EVIDENCE_BUILD_BATCH","24"))))
def revision(original,native,attestation):
 payload={"sha":original["sha"],"native":native,"attestation":attestation}
 return hashlib.sha256(json.dumps(payload,sort_keys=True,default=str,
  ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
def decide(original,native,attestation,byte_sha):
 if byte_sha!=original["sha"]:
  return "HOLD_ORIGINAL_BRONZE_BYTES_SHA_MISMATCH"
 if not native or not native.get("input_bytes_sha_checked") or native.get("bronze_sha256")!=original["sha"]:
  return "HOLD_SOURCE_NATIVE_VERSION_OR_SHA_MISSING"
 if str(native.get("status","")).startswith(("HOLD_","RETRY_")):
  return "HOLD_HISTORICAL_SCHEMA_OR_DATASET_IDENTITY"
 if attestation is None:
  return "HOLD_OFFICIAL_AND_INDEPENDENT_FULL_FILE_EVIDENCE_MISSING"
 status=safe_evidence_claim(attestation,original["source_id"],original["sha"])
 if status=="REVIEW_CLAIM_ONLY_NOT_SIGNED":
  return "HOLD_REVERIFY_ALL_RECEIPT_BYTES_AND_PIT_BEFORE_SIGNING"
 return status
def build(source):
 if source not in SOURCES:raise RuntimeError("SOURCE_NOT_SUPPORTED")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inf=match(api,quality,"v097_AP_INPUT_"+source+".json")
 nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 if not inf or not nf:raise RuntimeError("MISSING_FROZEN_INPUT_OR_NATIVE_"+source)
 rows=load_json(api,inf["id"])["rows"]
 native=load_json(api,nf["id"]).get("done",{})
 rid,formal=latest_complete(api,quality,match,load_json)
 gates={r["source_id"]:r for r in formal[source]["records"]}
 byid={r["source_id"]:r for r in rows}
 if set(gates)!=set(byid):raise RuntimeError("SOURCE_FROZEN_RELEASE_CONFLICT")
 ef=match(api,quality,"v097_INDEPENDENT_TRIPLE_NUMERIC_EVIDENCE_"+source+".json")
 attest=load_json(api,ef["id"]).get("by_source_id",{}) if ef else {}
 if set(attest)-set(byid):raise RuntimeError("ATTESTATION_OUTSIDE_FROZEN_COHORT")
 name="v097_FULLFILE_EVIDENCE_BUILDER_CK_"+source+".json"
 f=match(api,control,name)
 ck=load_json(api,f["id"]) if f else {"version":VERSION,"source":source,"done":{}}
 if ck.get("version")!=VERSION or ck.get("source")!=source:
  raise RuntimeError("EVIDENCE_BUILDER_CK_VERSION_MISMATCH")
 done=ck["done"]
 if set(done)-set(byid):raise RuntimeError("EVIDENCE_BUILDER_CHECKPOINT_ORPHANS")
 # Focus on native-verified existing HOLD; skip already formal READY entirely.
 eligible=[r for r in rows if gates[r["source_id"]]["status"]!=READY
    and r["source_id"] in native
    and not str(native[r["source_id"]].get("status","")).startswith(("HOLD_","RETRY_"))]
 # First process never examined; re-run prior only if underlying evidence changed.
 pending=[r for r in eligible if done.get(r["source_id"],{}).get("revision")!=
   revision(r,native[r["source_id"]],attest.get(r["source_id"]))][:BATCH]
 states=Counter()
 for r in pending:
  sid=r["source_id"]; prior=done.get(sid,{}); rev=revision(r,native[sid],attest.get(sid))
  try:
   blob=call(lambda:api.files().get_media(fileId=r["dest_id"]))
   actual=digest(blob)
   status=decide(r,native[sid],attest.get(sid),actual)
   done[sid]={"revision":rev,"status":status,"source_id":sid,
    "original_sha256":r["sha"],"verified_original_sha256":actual,
    "bytes_readback_checked":True,"native_schema":native[sid].get("historical_version"),
    "evidence_source_receipt":ef["id"] if ef else None,
    "release_candidate":False,"silver_gold_executed":False}
  except Exception as e:
   attempts=int(prior.get("attempts",0))+1
   done[sid]={"revision":rev if attempts>=3 else None,
     "status":"HOLD_SOURCE_READ_RETRY_EXHAUSTED" if attempts>=3 else "RETRY_SOURCE_READ",
     "error_type":type(e).__name__,"source_id":sid,"attempts":attempts,
     "release_candidate":False,"silver_gold_executed":False}
  states[done[sid]["status"]]+=1
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["formal_reference_run"]=rid
 if pending:checkpoint_commit(api,control,name,ck,upsert,match,load_json)
 overall=Counter(x["status"] for x in done.values())
 out={"schema":VERSION,"run":ck["last_run"],"source":source,
   "formal_reference_run":rid,"target_hold":len(eligible),"checked":len(done),
   "this_batch":len(pending),"remaining":len(eligible)-len(set(done)&{r["source_id"] for r in eligible}),
   "statuses_this_batch":dict(states),"status_total":dict(overall),
   "source_sha_verified_this_batch":sum(x.get("bytes_readback_checked",False) for x in
    (done[r["source_id"]] for r in pending)),
   "independent_fullfile_ledger_exists":ef is not None,
   "newly_ready":0,"formal_release_mutated":False,"silver_gold_executed":False}
 if ck["last_run"]!="manual":
  put_once(api,quality,"v097_FULLFILE_EVIDENCE_BUILDER_"+source+"_"+ck["last_run"]+".json",out)
 print("FULLFILE_EVIDENCE_BUILD="+json.dumps(out,ensure_ascii=False),flush=True)
def selftest():
 r={"source_id":"x","sha":"a"*64}
 n={"bronze_sha256":"a"*64,"input_bytes_sha_checked":True,
    "status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"}
 assert decide(r,n,None,"b"*64)=="HOLD_ORIGINAL_BRONZE_BYTES_SHA_MISMATCH"
 assert decide(r,n,None,r["sha"])=="HOLD_OFFICIAL_AND_INDEPENDENT_FULL_FILE_EVIDENCE_MISSING"
 assert decide(r,{**n,"status":"HOLD_UNKNOWN_DATASET"},None,r["sha"])=="HOLD_HISTORICAL_SCHEMA_OR_DATASET_IDENTITY"
 assert decide(r,n,{},r["sha"]).startswith("HOLD")
 assert revision(r,n,None)!=revision(r,n,{"test":1})
 assert set(SOURCES)=={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind"}
 print("FULLFILE_EVIDENCE_BUILDER_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:build(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
