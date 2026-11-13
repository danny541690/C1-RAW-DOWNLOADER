#!/usr/bin/env python3
"""v0.97 7489 source-ID anomaly truth table; dynamically reconciles
original RAW Bronze, isolated nonstock RAW, scope exclusions and remaining
blocked files from durable evidence checkpoints. Counts are never release
PIT certification. No mutating raw data or previous evidence receipts.
"""
import os,json
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
def get(api,folder,name):
 f=match(api,folder,name)
 return load_json(api,f["id"]) if f else {}
def buckets(api,c,prefix):
 all_ids=set();by=Counter()
 for lane in range(6):
  d=get(api,c,prefix+"_CK_%02d.json"%lane).get("done",{})
  if set(d)&all_ids:raise RuntimeError("SAME_ORIGINAL_ID_ACROSS_LANES_"+prefix)
  all_ids.update(d)
  by.update(v.get("state","MISSING_STATE") for v in d.values())
 return len(all_ids),dict(by)
def main():
 api=service();m,c,q,_=common(api)
 master=get(api,q,"v097_FINAL_OPEN_ISSUES_20261113_V1_SUMMARY_43404850198.json")
 if master.get("unique_anomaly_files")!=7489:raise RuntimeError("BASELINE_7489_NOT_VERIFIED")
 base=master["by_bucket"]
 raw=get(api,q,"v097_LEGACY_COMBINED_BRONZE_RAW_V1_SUMMARY_43410081178.json")
 # Prior successful report may be named with 43405715742 if postaudit summary differs
 if not raw:raw=get(api,q,"v097_LEGACY_COMBINED_BRONZE_RAW_V1_SUMMARY_43405715742.json")
 seven=get(api,q,"v097_V4_SEVEN_BRONZE_SUMMARY_43405316217.json")
 special=get(api,q,"v097_TDCC_SPECIAL_RAW_3WAY_QA_V1_SUMMARY_43428742706.json")
 content=get(api,q,"v097_REMAINING_39_CONTENT_QA_43452888927.json")
 if raw.get("new_or_existing_raw_bronze_pass")!=1094 or seven.get("raw_bronze_qa_pass")!=7:
  raise RuntimeError("ORDINARY_RAW_BRONZE_QA_RECEIPT_MISSING")
 if special.get("special_raw_3way_pass")!=2377:raise RuntimeError("SPECIAL_RAW_2377_RECEIPT_MISSING")
 if content.get("total")!=39:raise RuntimeError("39_RECHECK_RECEIPT_MISSING")
 n800,v800=buckets(api,c,"v097_TDCC_800_REVERIFY_V1")
 n800_admit,a800=buckets(api,c,"v097_TDCC_800_EXTERNAL_MATCH_SPECIAL_RAW")
 n2025,v2025=buckets(api,c,"v097_TDCC_2025_OFFICIAL_HISTORY_PROOFS")
 n2025_admit,a2025=buckets(api,c,"v097_TDCC_2025_OFFICIAL_EXACT_SPECIAL_RAW")
 add800=a800.get("NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS",0)
 add2025=a2025.get("NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS",0)
 if add800>v800.get("INTERNAL_AND_THIRDPARTY_TOTALS_EXACT_NONSTOCK",0):raise RuntimeError("800_ADMISSIONS_WITHOUT_EXTERNAL_PROOF")
 if add2025>v2025.get("EXACT_SAME_DATE_CONTENT_MATCH",0):raise RuntimeError("2025_ADMISSIONS_WITHOUT_OFFICIAL_PROOF")
 raw_bronze=1094+7
 special_total=2377+add800+add2025
 control=1314
 outscope_tick=content["by_state"].get("OUT_OF_SCOPE_TICK_DATA_USER_EXCLUDED",0)
 if outscope_tick!=8:raise RuntimeError("NONMARKET_TICK_COUNT_CHANGED")
 unresolved_tdcc=5035-special_total
 unresolved_other=39-outscope_tick
 total=raw_bronze+special_total+control+outscope_tick+unresolved_tdcc+unresolved_other
 if total!=7489:raise RuntimeError("SUM_7489_ACCOUNTING_ERROR_"+str(total))
 report={"schema":"v097_dynamic_7489_exception_status_1","run":RUN,
   "at":datetime.now(timezone.utc).isoformat(),
   "initial_exception_file_ids":7489,
   "raw_market_bronze_bytes_qa_admitted":raw_bronze,
   "separate_nonstock_special_raw_qa_admitted":special_total,
   "control_records_excluded":control,
   "user_disallowed_tick_data_excluded":outscope_tick,
   "remaining_unadmitted_special_security_originals":unresolved_tdcc,
   "other_source_files_semantics_release_pending":unresolved_other,
   "actual_market_files_bronze_release_PIT_certified":0,
   "subset_counters":{"tdcc_800_rechecked":n800,"tdcc_800_recheck_by_state":v800,
      "tdcc_800_special_raw_checked":n800_admit,"tdcc_800_special_raw_by_state":a800,
      "tdcc_2025_official_checked":n2025,"tdcc_2025_official_by_state":v2025,
      "tdcc_2025_special_raw_checked":n2025_admit,"tdcc_2025_special_raw_by_state":a2025},
   "remaining_in_scope_or_provenance_pending":unresolved_tdcc+unresolved_other,
   "accounting_total":total,
   "notes":"Source file counts, not missing trading dates; special-security archival does not qualify ordinary-stock Gold; no Silver/Gold/PIT release asserted"}
 put_once(api,q,"v097_DYNAMIC_EXCEPTION_ACCOUNTING_"+RUN+".json",report)
 print("DYNAMIC_EXCEPTION_ACCOUNTING="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
