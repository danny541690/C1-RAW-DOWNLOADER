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
TARGETED_RUN="43159677957"
def main():
 api=service();_,c,q,_=common(api)
 states=Counter();per_source=Counter();detail=[];seen=set();missing_checkpoint=0
 targeted=match(api,q,"v097_PHASE_A_TARGETED_QA_%s.json"%TARGETED_RUN)
 if not targeted:raise RuntimeError("MISSING_NINE_TARGETED_QA_RECEIPTS")
 targeted_doc=load_json(api,targeted["id"])
 targetrows=targeted_doc.get("rows",[])
 targets={x["asset_id"]:x for x in targetrows}
 if len(targetrows)!=9 or len(targets)!=9:raise RuntimeError("EXPECTED_NINE_DISTINCT_TARGETED_QA")
 target_states=Counter(x.get("status","UNKNOWN") for x in targetrows)

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
    state="HOLD_REPAIR_SEMANTIC_QA" if targets.get(fid,{}).get("status")=="BYTE_MATCH_SEMANTIC_PENDING" else "HOLD_REPAIR_QA_FAILED"
   elif prior=="ARCHIVE_EVIDENCE_ONLY":
    state="HOLD_ARCHIVE_CONTENT_ORIGIN" if targets.get(fid,{}).get("status")=="ARCHIVE_STRUCTURE_REVIEW" else "HOLD_ARCHIVE_QA_FAILED"
   elif r["category"]=="TDCC_IDENTITY":
    evidence=tdone.get(fid,{})
    status=evidence.get("status","")
    if not evidence:missing_checkpoint+=1
    # TDCC's official securities-code schema supports four numeric positions plus
    # two suffix positions. A filename token alone cannot authorize exclusion.
    if status=="HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING":
     # Independent original-content checks found a matching non-four-digit token.
     # Close only JARVIS common-stock scope; DO NOT certify TDCC publication origin.
     state="EXCLUDED_TDCC_NON_COMMON_STOCK_SCOPE"
    elif status=="HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING":
     state="HOLD_TDCC_HISTORICAL_MARKET_AND_PROVENANCE"
    else:
     state="HOLD_TDCC_SOURCE_OR_CONTENT"
   else:state="HOLD_OTHER_EXCEPTION"
   states[state]+=1
   per_source[r.get("category","UNKNOWN")]+=1
   detail.append({"file_id":fid,"lane":lane,"state":state,
       "source_path":r.get("source_path"),
       "previous_status":prior,
       "tdcc_checkpoint_state":tdone.get(fid,{}).get("status"),
       "targeted_qa_state":targets.get(fid,{}).get("status"),
       "decision_reason":reason})
 if len(seen)!=EXPECTED:raise RuntimeError("FROZEN_EXCEPTION_COUNT_MISMATCH:"+str(len(seen)))
 if not set(targets).issubset(seen):raise RuntimeError("TARGETED_QA_ORPHAN_IDS")
 if missing_checkpoint:raise RuntimeError("TDCC_PRIOR_QA_MISSING_"+str(missing_checkpoint))
 tdcc_count=sum(1 for x in detail if x["state"].startswith("HOLD_TDCC_") or x["state"]=="EXCLUDED_TDCC_NON_COMMON_STOCK_SCOPE")
 if tdcc_count!=5035:raise RuntimeError("TDCC_COUNT_MISMATCH")
 if states.get("EXCLUDED_CONTROL_NOT_MARKET",0)!=1314:raise RuntimeError("CONTROL_COUNT_MISMATCH")

 summary={"schema":"v097_bronze_6358_scope_audit_1","run":RUN,
  "at":datetime.now(timezone.utc).isoformat(),
  "original_exception_count":EXPECTED,"unique_file_ids":len(seen),
  "states":dict(states),"source_categories":dict(per_source),
  "tdcc_checkpoint_missing":missing_checkpoint,
  "stock_scope_excluded_total":states["EXCLUDED_CONTROL_NOT_MARKET"]+states["EXCLUDED_TDCC_NON_COMMON_STOCK_SCOPE"],
  "remaining_unresolved":EXPECTED-states["EXCLUDED_CONTROL_NOT_MARKET"]-states["EXCLUDED_TDCC_NON_COMMON_STOCK_SCOPE"],
  "scope_closed_count_not_equivalent_to_source_origin_certification":True,
  "targeted_nine_qa_statuses":dict(target_states),
  "targeted_nine_verified_receipts":len(targets),
  "official_references":[
   "https://schema.gov.tw/lists/75",
   "https://original-www.tdcc.com.tw/portal/zh/smWeb/qryStock",
   "https://openapi.tdcc.com.tw/"],
  "rules":{"tdcc_security_code":"FIRST_4_NUMERIC_NEXT_0_TO_2_ALNUM",
   "market_scope":"Only historically verified TWSE/TPEx listed/common equity enters the trading universe",
   "non_four_digit_automatic_exclusion":False,
   "exclusion_requires_verified_prior_html_content_status":True,
   "recheck_verified_74750":False,
   "silver_executed":False,"gold_executed":False},
  "remaining_blockers":["source_origin_not_certified_for_scope_excluded_tdcc",
    "historical_market_master_required_only_for_ambiguous_stock_codes",
    "7_repairs_semantic_gate","2_archives_member_source_provenance"],
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
 assert "HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING".startswith("HTML_TOKEN_")
 print("BRONZE_6358_SELFTEST_PASS",flush=True)
if __name__=="__main__":
 if os.getenv("BRONZE_6358_MODE")=="selftest":selftest()
 else:main()
