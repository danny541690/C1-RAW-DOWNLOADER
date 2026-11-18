"""Durable R3 three-source root-cause QA handover with checked Drive receipts.

No false G2; catalog official-origin versus native-format/semantic/revision
blocks so the next G2 run repairs incrementally instead of repeating work.
"""
import json,os
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import digest,COHORT
RUN=os.getenv("GITHUB_RUN_ID","manual")
OUT="R3_G2_THREE_SOURCE_DEEP_DIAG_REUSABLE_RULES_ISOLATED"
IDS={"MOPS_all_issuer_revision_diff":"1_OwT9qEhd2AZtILmO1yCa2zGABMCNZ4M",
     "TDCC_10_native_tier_semantics":"1k-hVuOm7iAqBKflYyg9L94FVqhTauDaX",
     "TAIFEX_10_csv_native_diagnostics":"19_uAJgvVCxSJu-bXRnjjhyVrxmR6-Nmw",
     "MOPS_TDCC_exact_source_route_comparison":"1gsrV7G-7aBN5hUhdPYX5pkxhIGcZcAfw",
     "MOPS_TDCC_TAIFEX_30_manifest":"1ZdsFpd7ZghwpHabRxu_JKUjastkw2GOH",
     "prior_324_source_vintage_qa":"1l6OD1y79u6nNCKK9bPHIfJCopZxeltf6"}
RULES={
 "MOPS":{"dataset":"MONTHLY_REVENUE_OTC_2025_02",
   "freeze_original":"Keep 857 issuer original intact",
   "official_revision_issue":{"current_issuers":861,
     "new_issuer_codes":["6938","6825","6898","2249"],
     "old_issuer_value_changes":["6474","3489"]},
   "expected_native_fields":["公司代號","公司名稱","當月營收","上月營收","去年當月營收","上月比較增減(%)","去年同月增減(%)","當月累計營收","去年累計營收","前期比較增減(%)","備註"],
   "expected_units":"千元; do not change Bronze or convert to 億 in G2",
   "first_success_path":"Find the actual original official publication version and revision-log asof for 4 added and 2 changed issuers; version the 2025 OTC report; compare every issuer before G2 PASS",
   "no_false_error":"Official 2026 snapshot differs from frozen older vintage; not confirmed corruption"},
 "TDCC":{"dataset":"SHAREHOLDING_DISTRIBUTION",
   "native_header":["序","持股/單位數分級","人數","股數/單位數","占集保庫存數比例 (%)"],
   "tier_count":15,"native_seq16":"合 計",
   "validations":["holders sum of 15 bands equals seq16 total",
     "shares sum of 15 bands equals seq16 total",
     "ratio sum allows ±0.2 percentage points",
     "do not include TOTAL as a tier",
     "effective-dated security ID including ETF/other instrument",
     "weekly source data-date and capture/publication asof independent of dropdown"],
   "native_10_files_semantic_pass":10,
   "official_api":"https://openapi.tdcc.com.tw/v1/opendata/1-5",
   "official_api_5MB_guard":"Need safe streaming/pagination or official archive with exact week/stock; current public html query is 589B placeholder",
   "first_success_path":"Bounded official matching same week/same effective security id with identical 15 tier counts and shares, independently verify format version and source vintage, then G2 cert"},
 "TAIFEX":{"dataset_categories":[
     "LARGE_TRADER_FUTURES_10_NATIVE_COLS",
     "LARGE_TRADER_OPTIONS_11_NATIVE_COLS",
     "SPREAD_ORDER","PRODUCT_ORDER","SINGLE_ORDER","COMBINATION_ORDER",
     "FUTURES_CONTRACTS_INSTITUTIONAL","OTHER_OPTION_OR_DAILY"],
   "observed_10_sample_groups":{"futures_large_trader":2,"options_large_trader":1,"other_dataset":6,"oversized_zip_hold":1},
   "futures_2013_08_rows":19194,"futures_2024_01_rows":25300,
   "options_2025_05_rows":8400,
   "native_footer_notes":3,
   "special_values":["-","0","666666","999999"],
   "first_success_path":"Use authentic TAIFEX historical data download URL, correct GET/POST route and query/session; compare every raw CSV row with the frozen monthly sample, and version trading session/call-put/dataset separately",
   "no_false_error":"Official POST ConnectionError does not imply damaged Bronze; 10 vs 11 large-trader formats are different datasets"}
}
def main():
 api,control,quality,match,load,_,_,call=source_api()
 refs={}
 for label,id in IDS.items():
  d=load(api,id)
  if not isinstance(d,dict):raise RuntimeError("REQUIRED_EVIDENCE_NOT_ACCESSIBLE:"+label)
  refs[label]={"drive_id":id,"record_schema":d.get("schema"),"sha256":digest(d),
               "remote_readback":True}
 mops=load(api,IDS["MOPS_all_issuer_revision_diff"])
 if (mops.get("unique_company_count_original")!=857 or
     mops.get("unique_company_count_official")!=861 or
     set(mops.get("only_in_official",[]))!={"6938","6825","6898","2249"} or
     set(mops.get("different_issuer_rows",[]))!={"6474","3489"}):
  raise RuntimeError("MOPS_ACTUAL_DIFFERENCES_CHANGED")
 tdcc=load(api,IDS["TDCC_10_native_tier_semantics"])
 if tdcc.get("native_format_pass_count")!=10:
  raise RuntimeError("TDCC_15_TIER_CONTRACT_NOT_STABLE")
 taifex=load(api,IDS["TAIFEX_10_csv_native_diagnostics"])
 if taifex.get("sample_real_frozen")!=10:
  raise RuntimeError("TAIFEX_ACTUAL_SAMPLE_NOT_TEN")
 prior=load(api,IDS["prior_324_source_vintage_qa"])
 if prior.get("verified_g2_source_vintage_pass")!=324:
  raise RuntimeError("PREVIOUS_G2_324_SOURCE_VINTAGE_MASTER_CHANGED")
 folder=match(api,quality,OUT)
 if not folder:folder=call(lambda:api.files().create(body={"name":OUT,
  "parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 artifact={"schema":"R3_G2_THREE_SOURCE_NATIVE_OFFICIAL_REUSABLE_RULES_AND_PROGRESS_V1",
  "run":RUN,"cohort":COHORT,"source_count":3,"actual_native_files_sha_verified":30,
  "TDCC_15_tier_native_validated":10,
  "MOPS_issuer_revision":{"archive":857,"current":861,"extra_current":4,"changed_existing":2},
  "TAIFEX_source_dataset_split":{"futures_large_trader":2,"options_large_trader":1,"other":6,"resource_guard":1},
  "new_formal_g2_pass":0,"prior_approved_g2_source_vintage":324,
  "still_unapproved_or_hold":COHORT-324,"official_historical_original_source_proof_needed":True,
  "reusable_rules":RULES,"verified_existing_receipts":refs,
  "github_run_ids":[44282067824,44282355777,44282907695,44283350941],
  "tech_report_path":"docs/V097_R3_G2_THREE_SOURCE_NATIVE_OFFICIAL_ROOT_CAUSES_20261118.md",
  "bronze_modified":False,"silver_gold_materialized":False,"no_production_master_overwrite":True}
 artifact=json.loads(json.dumps(artifact,ensure_ascii=False))
 name="r3_g2_three_source_historical_native_official_rules_master_run_"+RUN+".json"
 id=put_once(api,folder["id"],name,artifact)
 if load(api,id)!=artifact:raise RuntimeError("MISSING_DRIVE_REMOTE_PERSISTENCE")
 print("R3_G2_THREE_SOURCE_ROOT_CAUSE_SOP="+json.dumps({
  "run":RUN,"receipt_id":id,"name":name,"folder_id":folder["id"],
  "TDCC_native_15_tier_pass":10,"MOPS_additions":4,"MOPS_changed":2,
  "TAIFEX_futures_10col":2,"TAIFEX_options_11col":1,
  "new_official_G2_PASS":0,"source_vintage_prior_pass":324,
  "all_evidence_remote_readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
