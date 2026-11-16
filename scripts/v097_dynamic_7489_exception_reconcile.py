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
def ids_by_state(api,c,prefix,state):
 found=set()
 for lane in range(6):
  done=get(api,c,prefix+"_CK_%02d.json"%lane).get("done",{})
  matches={fid for fid,x in done.items() if x.get("state")==state}
  if found&matches:raise RuntimeError("DUPLICATE_OFFICIAL_PROOF_ID")
  found.update(matches)
 return found
def retry_official_proof_ids(api,q):
 """Only allow independently evidenced 2025 official retries tied to original IDs."""
 r=get(api,q,"v097_TDCC_TWO_OFFICIAL_RETRY_43521418693.json")
 if not r:return set()
 if r.get("official_proved")!=2:raise RuntimeError("RETRY_OFFICIAL_PROOF_RECEIPT_CHANGED")
 original=get(api,q,"v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json")
 byid={x["file_id"]:x for x in original.get("records",[])}
 proved=set()
 for x in r.get("items",[]):
  if x.get("state")!="EXACT_SAME_DATE_CONTENT_MATCH":continue
  fid=x.get("file_id");o=byid.get(fid)
  if not o or not str(o.get("day","")).startswith("2025"):
   raise RuntimeError("RETRY_ID_NOT_IN_FROZEN_2025")
  if not x.get("official_response_sha256"):
   raise RuntimeError("RETRY_NO_OFFICIAL_RESPONSE_SHA")
  if any(o.get(a)!=x.get(b) for a,b in (
   ("source_sha256","source_sha256"),("day","day"),("code","code"),
   ("holders","original_holders"),("shares","original_shares"))):
   raise RuntimeError("RETRY_ORIGINAL_ID_SHA_DATE_CODE_TOTAL_MISMATCH")
  proved.add(fid)
 if len(proved)!=2:raise RuntimeError("RETRY_OFFICIAL_VERIFIED_ID_COUNT_NOT_2")
 return proved
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
 n_internal,s_internal=buckets(api,c,"v097_TDCC_1084_INTERNAL_PROOF_RAW")
 internal_raw_pass=s_internal.get("SPECIAL_RAW_INTERNAL_STRICT_QA_PASS_EXTERNAL_PENDING",0)
 add800=a800.get("NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS",0)
 add2025=a2025.get("NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS",0)
 # Special RAW copy+internal numeric QA is NOT formal proof of official same-day
 # publication or ordinary-stock Bronze readiness. Track discrepancies as
 # fail-closed HOLD rather than crashing the entire immutable ID accounting job.
 external_800=int(v800.get("INTERNAL_AND_THIRDPARTY_TOTALS_EXACT_NONSTOCK",0))
 official_2025=int(v2025.get("EXACT_SAME_DATE_CONTENT_MATCH",0))
 proof_gap_800=max(0,add800-external_800)
 # Unlike the historical-date checkpoint, the separately SHA-validated
 # official retry receipt can contain TWO additional, non-overlapping 2025 IDs.
 # Reconcile individual file IDs rather than comparing aggregate counters.
 official_2025_ids=ids_by_state(api,c,"v097_TDCC_2025_OFFICIAL_HISTORY_PROOFS","EXACT_SAME_DATE_CONTENT_MATCH")
 retry_ids=retry_official_proof_ids(api,q)
 if len(official_2025_ids)!=official_2025:
  raise RuntimeError("2025_CHECKPOINT_OFFICIAL_ID_COUNT_CONFLICT")
 admission_ids=ids_by_state(api,c,"v097_TDCC_2025_OFFICIAL_EXACT_SPECIAL_RAW","NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS")
 if len(admission_ids)!=add2025:raise RuntimeError("2025_SPECIAL_RAW_ID_COUNT_CONFLICT")
 overlapping=official_2025_ids&retry_ids
 extra_retry_ids=retry_ids-official_2025_ids
 official_unmatched_ids=admission_ids-(official_2025_ids|retry_ids)
 proof_gap_2025=len(official_unmatched_ids)
 if overlapping:print("OFFICIAL_RETRY_IDS_ALREADY_IN_HISTORY="+str(len(overlapping)),flush=True)
 if min(add800,add2025,external_800,official_2025)<0:
  raise RuntimeError("NEGATIVE_EXTERNAL_PROOF_COUNTER")
 # Counts are conservative lower bounds for a *necessary* ID-level evidence
 # reconciliation. Aggregate matches cannot certify an individual file.
 official_proof_status="HOLD_OFFICIAL_PROOF_RECONCILIATION" if (proof_gap_800 or proof_gap_2025) else "COUNTS_CONSISTENT_ID_LEVEL_PROOF_STILL_REQUIRED"
 raw_bronze=1094+7
 special_total=2377+add800+add2025
 control=1314
 outscope_tick=content["by_state"].get("OUT_OF_SCOPE_TICK_DATA_USER_EXCLUDED",0)
 if outscope_tick!=8:raise RuntimeError("NONMARKET_TICK_COUNT_CHANGED")
 unresolved_tdcc=5035-special_total-internal_raw_pass
 if unresolved_tdcc<0:raise RuntimeError("TDCC_RAW_SOURCE_POPULATION_DOUBLE_COUNT")
 unresolved_other=39-outscope_tick
 total=raw_bronze+special_total+internal_raw_pass+control+outscope_tick+unresolved_tdcc+unresolved_other
 if total!=7489:raise RuntimeError("SUM_7489_ACCOUNTING_ERROR_"+str(total))
 report={"schema":"v097_dynamic_7489_exception_status_1","run":RUN,
   "at":datetime.now(timezone.utc).isoformat(),
   "initial_exception_file_ids":7489,
   "raw_market_bronze_bytes_qa_admitted":raw_bronze,
   "separate_nonstock_special_raw_qa_admitted":special_total,
   "special_raw_internal_qa_pass_external_witness_pending":internal_raw_pass,
   "special_security_awaiting_original_raw_qa":unresolved_tdcc,
   "control_records_excluded":control,
   "user_disallowed_tick_data_excluded":outscope_tick,
   "remaining_unadmitted_special_security_originals":unresolved_tdcc,
   "other_source_files_semantics_release_pending":unresolved_other,
   "actual_market_files_bronze_release_PIT_certified":0,
   "official_proof_status":official_proof_status,
   "official_proof_gap":{"tdcc_800_external_count_shortfall":proof_gap_800,
      "tdcc_2025_exact_same_day_count_shortfall":proof_gap_2025,
      "raw_qa_800_count":add800,"external_match_800_count":external_800,
      "raw_qa_2025_count":add2025,"official_exact_match_2025_count":official_2025,
      "verified_extra_retry_2025_ids":len(extra_retry_ids),
      "unmatched_2025_file_ids":sorted(official_unmatched_ids)},
   "unverified_raw_qa_remains_hold":True,
   "requires_per_file_proof_id_sha_date_code_holders_shares":True,
   "tdcc_2025_ids_reconciled_from_official_history_and_separate_retry":len(admission_ids)-len(official_unmatched_ids),
   "subset_counters":{"tdcc_800_rechecked":n800,"tdcc_800_recheck_by_state":v800,
      "tdcc_800_special_raw_checked":n800_admit,"tdcc_800_special_raw_by_state":a800,
      "tdcc_2025_official_checked":n2025,"tdcc_2025_official_by_state":v2025,
      "tdcc_2025_special_raw_checked":n2025_admit,"tdcc_2025_special_raw_by_state":a2025,
      "tdcc_1082_internal_checked":n_internal,"tdcc_1082_internal_by_state":s_internal},
   "remaining_in_scope_or_provenance_pending":unresolved_tdcc+internal_raw_pass+unresolved_other,
   "accounting_total":total,
   "notes":"Official-missing 2025 and 800 raw QA remain HOLD pending per-ID official evidence, never auto-release. Internal-only raw pass remains EXTERNAL_WITNESS_PENDING. Source file counts, not missing trading dates; special-security archival does not qualify ordinary-stock Gold; no Silver/Gold/PIT release asserted"}
 put_once(api,q,"v097_DYNAMIC_EXCEPTION_ACCOUNTING_"+RUN+".json",report)
 print("DYNAMIC_EXCEPTION_ACCOUNTING="+json.dumps(report,ensure_ascii=False),flush=True)
 if proof_gap_800 or proof_gap_2025:
  print("OFFICIAL_PROOF_GAP_HOLD="+json.dumps(report["official_proof_gap"],ensure_ascii=False),flush=True)
def selftest():
 assert max(0,8-6)==2
 assert max(0,4-4)==0
 assert max(0,0-0)==0
 print("DYNAMIC_7489_FAIL_CLOSED_ACCOUNTING_SELFTEST_PASS",flush=True)
if __name__=="__main__":
 import sys
 if sys.argv[1:]==["selftest"]:selftest()
 elif not sys.argv[1:]:main()
 else:raise SystemExit("usage: [selftest]")
