#!/usr/bin/env python3
"""Incremental Bronze exception closure ledger for the 6,358 frozen v0.93->v0.97 exceptions.
Read prior V4 source receipts, TDCC A4 checkpoint statuses and existing Phase A reports.
Never mutate legacy raw/Bronze assets; NEVER call any Silver/Gold code.
"""
import os,json
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,upsert,put_once
from scripts.v097_phase_a_disposition import evaluate,V4_RUN,EXPECTED
RUN=os.getenv("GITHUB_RUN_ID","manual")
TDCC_PREFIX="v097_TDCC_A4_V3"
def main():
 api=service();_,c,q,_=common(api)
 states=Counter();per_source=Counter();detail=[];seen=set();missing_checkpoint=0
 for lane in range(6):
  f=match(api,q,"v097_BF_REPAIR_V4_%s_L%02d.json"%(V4_RUN,lane))
  if not f:raise RuntimeError("MISSING_FROZEN_V4_EVIDENCE_L%02d"%lane)
  rows=load_json(api,f["id"])["rows"]
  t=match(api,c,"%s_CK_L%02d.json"%(TDCC_PREFIX,lane))
  tdone=load_json(api,t["id"]).get("done",{}) if t else {}
  for r in rows:
   fid=r["file_id"]
   if fid in seen:raise RuntimeError("DUPLICATE_ORIGINAL_FILE_ID")
   seen.add(fid)
   prior,reason=evaluate(r)
   if r["category"]=="CONTROL_METADATA":
    state="EXCLUDED_CONTROL_NOT_MARKET"
   elif prior=="REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING":
    state="HOLD_REPAIR_SEMANTIC_QA"
   elif prior=="ARCHIVE_EVIDENCE_ONLY":
    state="HOLD_ARCHIVE_CONTENT_ORIGIN"
   elif r["category"]=="TDCC_IDENTITY":
    evidence=tdone.get(fid,{})
    status=evidence.get("status","")
    if not evidence:missing_checkpoint+=1
    # TDCC's official securities-code schema supports four numeric positions plus
    # two suffix positions. A filename token alone cannot authorize exclusion.
    state="HOLD_TDCC_HISTORICAL_MARKET_AND_PROVENANCE" if status.startswith("HTML_") else "HOLD_TDCC_SOURCE_OR_CONTENT"
   else:state="HOLD_OTHER_EXCEPTION"
   states[state]+=1
   per_source[r.get("category","UNKNOWN")]+=1
   detail.append({"file_id":fid,"lane":lane,"state":state,
       "source_path":r.get("source_path"),
       "previous_status":prior,
       "tdcc_checkpoint_state":tdone.get(fid,{}).get("status"),
       "decision_reason":reason})
 if len(seen)!=EXPECTED:raise RuntimeError("FROZEN_EXCEPTION_COUNT_MISMATCH:"+str(len(seen)))
 summary={"schema":"v097_bronze_6358_scope_audit_1","run":RUN,
  "at":datetime.now(timezone.utc).isoformat(),
  "original_exception_count":EXPECTED,"unique_file_ids":len(seen),
  "states":dict(states),"source_categories":dict(per_source),
  "tdcc_checkpoint_missing":missing_checkpoint,
  "official_references":[
   "https://schema.gov.tw/lists/75",
   "https://original-www.tdcc.com.tw/portal/zh/smWeb/qryStock",
   "https://openapi.tdcc.com.tw/"],
  "rules":{"tdcc_security_code":"FIRST_4_NUMERIC_NEXT_0_TO_2_ALNUM",
   "market_scope":"Only historically verified TWSE/TPEx listed/common equity enters the trading universe",
   "non_four_digit_automatic_exclusion":False,
   "recheck_verified_74750":False,
   "silver_executed":False,"gold_executed":False},
  "remaining_blockers":["historical_market_master_asof_date",
    "original_tdcc_provenance","7_repairs_semantic_gate","2_archives_member_source_provenance"],
  "silver_ready_from_exception_cohort":0,
  "notice":"Classifies existing proof, does not fabricate independent market certification."}
 put_once(api,q,"v097_BRONZE_6358_SCOPE_ROWS_%s.json"%RUN,
  {"schema":"v097_bronze_6358_rows_1","rows":detail,"run":RUN})
 put_once(api,q,"v097_BRONZE_6358_SCOPE_SUMMARY_%s.json"%RUN,summary)
 upsert(api,c,"v097_BRONZE_6358_SCOPE_LATEST.json",summary)
 print("BRONZE_6358_AUDIT="+json.dumps(summary,ensure_ascii=False),flush=True)
def selftest():
 code=lambda x:len(x) in (4,5,6) and x[:4].isdigit() and (len(x)==4 or x[4:].isalnum())
 assert code("2330") and code("2330A") and code("2330A1")
 assert not code("YJR4") and not code("2330-") and not code("233")
 print("BRONZE_6358_SELFTEST_PASS",flush=True)
if __name__=="__main__":
 if os.getenv("BRONZE_6358_MODE")=="selftest":selftest()
 else:main()
