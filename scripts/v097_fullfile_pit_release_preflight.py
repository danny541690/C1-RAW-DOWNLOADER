#!/usr/bin/env python3
"""Seven-source full-file numeric/PIT release preflight.

This verifier NEVER equates sample witnesses, a provider landing page or parser
success to a complete file attestation. It reads frozen Bronze cohort, current
formal intake, native V2, and D stage, then joins per-source full-file numeric
evidence. Only strictly corroborated candidates are emitted to a separate
review manifest; formal Bronze READY and Silver/Gold are not silently mutated.
"""
import json,os,sys,re
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import source_api,SOURCES,READY
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_d_seven_source_gate import independently_attested
from scripts.v097_seven_native_v2_probe import checkpoint_commit
FIELDS={
 "TWSE":("trade_date","stock_id","open","high","low","close","volume","amount"),
 "TPEx":("trade_date","stock_id","open","high","low","close","volume","amount"),
 "MOPS":("company_id","filing_period","announced_at","account_code","account_value","unit","revision"),
 "TDCC":("snapshot_date","security_id","security_class","holder_tier","holders","shares","percentage"),
 "TAIFEX":("trade_date","contract","contract_month","settlement","volume","open_interest","session"),
 "NDC":("series","release_month","observation_month","value","revision"),
 "FinMind":("dataset","stock_id","date","metric","value","unit","publisher")}
VERSION="v097_full_file_pit_release_preflight_v1"
LIMIT=max(10,min(10000,int(os.getenv("PIT_GATE_BATCH","300"))))
def utc(s):
 try:
  t=datetime.fromisoformat(str(s).replace("Z","+00:00"))
  if t.tzinfo is None:return None
  return t.astimezone(timezone.utc)
 except (ValueError,TypeError):return None
def full_proof(src,row,old,native,d,e):
 if old["status"]==READY:return "READY_PRESERVED"
 if not native or native.get("bronze_sha256")!=row["sha"] or not native.get("input_bytes_sha_checked"):
  return "HOLD_ORIGINAL_SHA_OR_NATIVE"
 if native.get("status","").startswith(("HOLD_","RETRY_")):
  return "HOLD_HISTORICAL_FORMAT_SEMANTICS"
 if not d or d.get("status")!="D_CANDIDATE_FULL_THREE_WAY_ATTESTED":
  return "HOLD_D_GATE_NOT_FULLY_ATTESTED"
 if not isinstance(e,dict):return "HOLD_FULL_FILE_EVIDENCE_MISSING"
 if not independently_attested({**row,"source":src},e)[0]:return "HOLD_TRIPLE_NUMERIC_EVIDENCE_INVALID"
 if not all(e.get(x) is True for x in ("all_rows_verified","all_fields_verified","publication_pit_verified")):
  return "HOLD_PARTIAL_ROWS_FIELDS_OR_PIT"
 if e.get("source_id")!=row["source_id"] or e.get("original_sha256")!=row["sha"]:
  return "HOLD_SOURCE_ID_OR_ORIGINAL_SHA"
 if e.get("dataset")!=e.get("verified_dataset") or e.get("dataset") is None:
  return "HOLD_DATASET_IDENTITY"
 required=FIELDS[src]
 if not set(required).issubset(set(e.get("verified_fields",[]))):
  return "HOLD_REQUIRED_DATASET_COLUMNS"
 nums=[e.get("original_row_count"),e.get("official_row_count"),e.get("third_party_row_count")]
 if not all(type(x) is int and x>0 for x in nums) or len(set(nums))!=1:
  return "HOLD_ALL_RECORD_COUNT_NOT_RECONCILED"
 digests=[e.get(k) for k in ("original_row_digest","official_row_digest","third_party_row_digest")]
 if not all(isinstance(x,str) and re.fullmatch("[0-9a-f]{64}",x) for x in digests):
  return "HOLD_FULL_FILE_ROW_DIGEST_ABSENT"
 if len(set(digests))!=1:return "HOLD_FULL_FILE_VALUES_DIFFER"
 p=utc(e.get("official_published_at"))
 asof=utc(e.get("publication_pit_as_of"))
 if p is None or asof is None or p>asof:return "HOLD_PIT_PUBLISHED_AFTER_ASOF_OR_UNKNOWN"
 if not all(e.get(k) for k in ("official_fetch_receipt_id","third_party_fetch_receipt_id",
      "original_extracted_value_receipt_id","schema_version_id","source_uri_asof")):
  return "HOLD_AUDIT_RECEIPT_OR_FORMAT_VERSION_MISSING"
 # A gate candidate is not the signed release: maintain independent reviewed candidate.
 return "CANDIDATE_COMPLETE_EVIDENCE_REQUIRES_SIGNED_RELEASE"
def run(src):
 if src not in SOURCES:raise RuntimeError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inf=match(api,quality,"v097_AP_INPUT_"+src+".json")
 nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+src+".json")
 df=match(api,control,"v097_D_THREE_WAY_GATE_CK_"+src+".json")
 if not inf:raise RuntimeError("FROZEN_INPUT_ABSENT")
 rows=load_json(api,inf["id"])["rows"]
 native=load_json(api,nf["id"]).get("done",{}) if nf else {}
 d=load_json(api,df["id"]).get("done",{}) if df else {}
 rid,formal=latest_complete(api,quality,match,load_json)
 gate={r["source_id"]:r for r in formal[src]["records"]}
 if set(gate)!={x["source_id"] for x in rows}:raise RuntimeError("FORMAL_COHORT_CONFLICT")
 evidence_name="v097_INDEPENDENT_TRIPLE_NUMERIC_EVIDENCE_"+src+".json"
 ef=match(api,quality,evidence_name)
 e=load_json(api,ef["id"]).get("by_source_id",{}) if ef else {}
 if set(e)-set(gate):raise RuntimeError("EVIDENCE_ORPHANS")
 checkpoint_name="v097_FULLFILE_PIT_RELEASE_CK_"+src+".json"
 f=match(api,control,checkpoint_name)
 ck=load_json(api,f["id"]) if f else {"schema":VERSION,"source":src,"done":{}}
 if ck.get("schema")!=VERSION or ck.get("source")!=src:raise RuntimeError("CHECKPOINT_VERSION_OR_SOURCE")
 byid={x["source_id"]:x for x in rows}
 target=[x for x in rows if gate[x["source_id"]]["status"]!=READY]
 def signature(x):
  sid=x["source_id"]
  from hashlib import sha256
  b=json.dumps({"sha":x["sha"],"native":native.get(sid),"D":d.get(sid),
    "evidence":e.get(sid)},sort_keys=True,ensure_ascii=False,default=str).encode()
  return sha256(b).hexdigest()
 pending=[x for x in target if ck["done"].get(x["source_id"],{}).get("revision")!=signature(x)][:LIMIT]
 statuses=Counter()
 candidates=[]
 for row in pending:
  sid=row["source_id"]
  state=full_proof(src,row,gate[sid],native.get(sid),d.get(sid),e.get(sid))
  ck["done"][sid]={"status":state,"revision":signature(row),
    "source_sha256":row["sha"],"run":os.getenv("GITHUB_RUN_ID","manual")}
  statuses[state]+=1
  if state=="CANDIDATE_COMPLETE_EVIDENCE_REQUIRES_SIGNED_RELEASE":candidates.append(sid)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["formal_reference_run"]=rid
 if pending:checkpoint_commit(api,control,checkpoint_name,ck,upsert,match,load_json)
 total=Counter(v["status"] for v in ck["done"].values())
 report={"schema":VERSION,"source":src,"run":ck["last_run"],"formal_run":rid,
    "frozen_total":len(rows),"original_ready":len(rows)-len(target),
    "checked_hold":len(ck["done"]),"remaining_unreviewed":len(target)-len(ck["done"]),
    "batch":len(pending),"candidate_ids":candidates,
    "all_known_status_counts":dict(total),"formal_ready_promoted":0,
    "not_a_signed_release":True,"silver_gold_executed":False}
 if report["run"]!="manual":
  put_once(api,quality,"v097_FULLFILE_PIT_RELEASE_PREFLIGHT_"+src+"_"+report["run"]+".json",report)
 print("FULLFILE_PIT_RELEASE_PREFLIGHT="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
 row={"source_id":"x","sha":"a"*64}
 old={"source_id":"x","status":"HOLD","source_sha256":"a"*64}
 native={"bronze_sha256":"a"*64,"input_bytes_sha_checked":True,
         "status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"}
 d={"status":"D_CANDIDATE_FULL_THREE_WAY_ATTESTED"}
 assert full_proof("TWSE",row,old,native,d,{})=="HOLD_TRIPLE_NUMERIC_EVIDENCE_INVALID"
 assert full_proof("TWSE",row,old,native,{},None)=="HOLD_D_GATE_NOT_FULLY_ATTESTED"
 assert full_proof("TWSE",row,{**old,"status":READY},None,None,None)=="READY_PRESERVED"
 assert utc("2026-11-15T09:00:00Z")<utc("2026-11-15T10:00:00Z")
 assert set(FIELDS)==set(SOURCES)
 print("FULLFILE_PIT_RELEASE_PREFLIGHT_NEGATIVE_TESTS_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
