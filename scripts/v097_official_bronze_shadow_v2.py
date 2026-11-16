#!/usr/bin/env python3
"""v0.97 Bronze Official-Source Gate v2: immutable, fail-closed SHADOW audit.

No third party is required for *Bronze intake*. PIT certification remains separate.
Cannot change original 74,750 cohort, published READY/HOLD, or run Silver/Gold.
Official provenance is affirmative evidence, not a filename/domain claim.
"""
import json,os,re,sys,hashlib
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_evidence_contract import sha256
from scripts.v097_seven_native_v2_probe import checkpoint_commit
VERSION="v097_official_bronze_shadow_gate_v2_1"
LIMIT=max(1,min(1000,int(os.getenv("BRONZE_V2_SHADOW_BATCH","300"))))
HASH=re.compile(r"[0-9a-f]{64}\Z")
# These are historical format *categories*, not a complete independent
# identity proof. A valid parser status alone NEVER proves official origin.
PARSER_PROVISIONAL={
 "TWSE":{"CONTENT_PARSED_ORIGIN_PIT_HOLD","C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"},
 "TPEx":{"CONTENT_PARSED_ORIGIN_PIT_HOLD","C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"},
 "MOPS":{"MOPS_MATRIX_RECEIPT_AND_PIT_HOLD"},
 "TDCC":{"TDCC_HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING"},
 "TAIFEX":{"TAIFEX_CSV_ENCODING_WIDTH_PASS_DATE_PIT_HOLD"},
 "NDC":{"NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD"},
 "FinMind":{"FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD","CONTENT_PARSED_ORIGIN_PIT_HOLD"}
}
PROVENANCE_REQUIRED=("source_id","original_sha256","source","dataset",
 "historical_schema_version","original_fetch_receipt_id","upstream_response_sha256",
 "official_or_provider_endpoint","retrieved_at","source_identity_verified",
 "full_content_qa_verified","data_period_verified","field_units_verified")
def decide(source,row,formal,native,origin):
 if formal.get("status")==READY:return "READY_ALREADY_FORMAL_PRESERVED"
 if not native:return "HOLD_NATIVE_V2_MISSING"
 if native.get("source_id")!=row["source_id"] or native.get("bronze_sha256")!=row["sha"] or native.get("input_bytes_sha_checked") is not True:
  return "HOLD_ORIGINAL_SHA_OR_ID_UNVERIFIED"
 state=str(native.get("status",""))
 if state.startswith(("HOLD_","RETRY_")):return "HOLD_HISTORICAL_FORMAT_OR_IDENTITY"
 if state not in PARSER_PROVISIONAL[source]:return "HOLD_DATASET_SPECIFIC_PARSER_EVIDENCE"
 if not isinstance(origin,dict):return "HOLD_SOURCE_DOWNLOAD_PROVENANCE_MISSING"
 if any(x not in origin for x in PROVENANCE_REQUIRED):return "HOLD_ORIGIN_RECEIPT_REQUIRED_FIELDS"
 if origin["source_id"]!=row["source_id"] or origin["original_sha256"]!=row["sha"] or origin["source"]!=source:
  return "HOLD_PROVENANCE_SOURCE_ID_OR_SHA_CONFLICT"
 if not all(HASH.fullmatch(str(origin[k])) for k in ("original_sha256","upstream_response_sha256")):
  return "HOLD_PROVENANCE_INVALID_DIGEST"
 if not origin["original_fetch_receipt_id"] or not origin["historical_schema_version"] or not origin["dataset"]:
  return "HOLD_PROVENANCE_DATASET_OR_RECEIPT_ABSENT"
 if origin["historical_schema_version"]!=native.get("historical_version"):
  return "HOLD_HISTORICAL_VERSION_CONFLICT"
 if origin["dataset"]!=native.get("parser_detail",{}).get("dataset") and origin["dataset"]!=native.get("parser_detail",{}).get("bc_c_status"):
  # Historical schema identity cannot be inferred solely from the file name.
  return "HOLD_DATASET_IDENTITY_NOT_INDEPENDENTLY_ESTABLISHED"
 if not all(origin.get(k) is True for k in ("source_identity_verified","full_content_qa_verified",
 "data_period_verified","field_units_verified")):
  return "HOLD_OFFICIAL_OR_PROVIDER_INTEGRITY_OR_QA"
 # Existing source provenance proof must itself be read back/verified by an
 # independent verifier. A ledger entry alone is not a signed release.
 if origin.get("receipt_bytes_readback_verified") is not True:
  return "HOLD_PROVENANCE_RECEIPT_BYTES_NOT_VERIFIED"
 if not origin.get("receipt_lineage_verified"):
  return "HOLD_SOURCE_RECEIPT_LINEAGE_NOT_VERIFIED"
 return "SHADOW_CANDIDATE_OFFICIAL_BRONZE_NEEDS_SIGNED_GATE"
def selftest():
 row={"source_id":"id","sha":"a"*64}
 formal={"status":"HOLD"}
 native={"source_id":"id","bronze_sha256":"a"*64,"input_bytes_sha_checked":True,
 "status":"CONTENT_PARSED_ORIGIN_PIT_HOLD","historical_version":"v1",
 "parser_detail":{"dataset":"test"}}
 assert decide("TWSE",row,formal,native,None)=="HOLD_SOURCE_DOWNLOAD_PROVENANCE_MISSING"
 assert decide("TWSE",row,formal,None,None)=="HOLD_NATIVE_V2_MISSING"
 assert decide("TWSE",row,formal,{**native,"bronze_sha256":"b"*64},None)=="HOLD_ORIGINAL_SHA_OR_ID_UNVERIFIED"
 assert decide("TWSE",row,formal,{**native,"status":"HOLD_BAD_JSON"},None)=="HOLD_HISTORICAL_FORMAT_OR_IDENTITY"
 o={"source_id":"id","original_sha256":"a"*64,"source":"TWSE","dataset":"test",
 "historical_schema_version":"v1","original_fetch_receipt_id":"receipt",
 "upstream_response_sha256":"b"*64,"official_or_provider_endpoint":"https://www.twse.com.tw/",
 "retrieved_at":"2026-11-16T08:00:00Z","source_identity_verified":True,
 "full_content_qa_verified":True,"data_period_verified":True,"field_units_verified":True,
 "receipt_bytes_readback_verified":True,"receipt_lineage_verified":True}
 assert decide("TWSE",row,formal,native,o)=="SHADOW_CANDIDATE_OFFICIAL_BRONZE_NEEDS_SIGNED_GATE"
 for name,change in (("missing receipt",{"receipt_bytes_readback_verified":False}),
  ("source mismatch",{"source":"TPEx"}),("date not verified",{"data_period_verified":False}),
  ("schema changed",{"historical_schema_version":"v0"})):
  assert decide("TWSE",row,formal,native,{**o,**change}).startswith("HOLD_"),name
 assert decide("TWSE",row,{"status":READY},None,None)=="READY_ALREADY_FORMAL_PRESERVED"
 assert set(PARSER_PROVISIONAL)==set(SOURCES)
 print("BRONZE_OFFICIAL_SHADOW_V2_SELFTEST_PASS")
def run(source):
 if source not in SOURCES:raise RuntimeError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 if not inp:raise RuntimeError("FROZEN_INPUT_MISSING")
 rows=load_json(api,inp["id"])["rows"]
 rr,formal=latest_complete(api,quality,match,load_json)
 byid={r["source_id"]:r for r in rows}
 fby={r["source_id"]:r for r in formal[source]["records"]}
 if set(fby)!=set(byid):raise RuntimeError("FROZEN_FORMAL_COHORT_MISMATCH")
 nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 native=load_json(api,nf["id"]).get("done",{}) if nf else {}
 proof_name="v097_OFFICIAL_SOURCE_PROVENANCE_RECEIPTS_"+source+".json"
 pf=match(api,quality,proof_name)
 proofs=load_json(api,pf["id"]).get("by_source_id",{}) if pf else {}
 if set(proofs)-set(byid):raise RuntimeError("OFFICIAL_PROOF_ORPHAN")
 outname="v097_OFFICIAL_BRONZE_SHADOW_V2_CK_"+source+".json"
 cf=match(api,control,outname)
 ck=load_json(api,cf["id"]) if cf else {"schema":VERSION,"source":source,"done":{}}
 if ck.get("schema")!=VERSION or ck.get("source")!=source:raise RuntimeError("SHADOW_CHECKPOINT_VERSION_MISMATCH")
 done=ck["done"]
 if set(done)-set(byid):raise RuntimeError("SHADOW_CHECKPOINT_ORPHAN")
 def signature(row):
  sid=row["source_id"]
  context={"source_sha":row["sha"],"formal":fby[sid].get("status"),
      "native":native.get(sid),"provenance":proofs.get(sid)}
  return hashlib.sha256(json.dumps(context,sort_keys=True,ensure_ascii=False,
    separators=(",",":"),default=str).encode()).hexdigest()
 pending=[r for r in rows if fby[r["source_id"]]["status"]!=READY and
       done.get(r["source_id"],{}).get("revision")!=signature(r)][:LIMIT]
 fresh=Counter()
 for row in pending:
  sid=row["source_id"]
  status=decide(source,row,fby[sid],native.get(sid),proofs.get(sid))
  done[sid]={"status":status,"source_sha256":row["sha"],"revision":signature(row),
    "official_provenance_ledger":pf["id"] if pf else None,
    "signed":False,"new_ready":False}
  fresh[status]+=1
 ck["run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["formal_reference_run"]=rr
 if pending:checkpoint_commit(api,control,outname,ck,upsert,match,load_json)
 counts=Counter(v["status"] for v in done.values())
 target=sum(fby[x["source_id"]]["status"]!=READY for x in rows)
 report={"schema":VERSION,"run":ck["run"],"source":source,"formal_reference_run":rr,
 "formal_ready_preserved":len(rows)-target,"target_holds":target,
 "shadow_examined":len(done),"shadow_remaining":target-len(done),
 "this_batch":len(pending),"new_statuses":dict(fresh),"all_statuses":dict(counts),
 "provenance_ledger_present":pf is not None,"third_party_required":False,
 "pit_backtest_approved":False,"formal_ready_mutated":False,"silver_gold_executed":False}
 if report["run"]!="manual":
  put_once(api,quality,"v097_OFFICIAL_BRONZE_SHADOW_"+source+"_"+report["run"]+".json",report)
 print("OFFICIAL_BRONZE_SHADOW_V2="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
