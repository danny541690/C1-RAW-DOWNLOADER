#!/usr/bin/env python3
"""JARVIS v0.97: incremental seven-source independent evidence depth work queue.

Each record receives source-specific semantic gates and an exact list of missing
external proof. The original Bronze SHA is rechecked against the actual bytes.
This tool NEVER replaces an official release, writes fabricated 3-way values,
or treats publisher documentation as a numerical observation.
"""
import hashlib,json,os,re,sys,time,socket
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from googleapiclient.errors import HttpError
from scripts.v097_bronze_autopilot import SOURCES,source_api,digest,READY
from scripts.v097_seven_deep_format_inspector import analyze
from scripts.v097_seven_historical_format_registry import period
from scripts.v097_seven_source_specific_resolvers import triage
from scripts.v097_d_seven_source_gate import independently_attested

VERSION="seven-independent-evidence-depth-v1"
BATCH=max(1,min(35,int(os.getenv("EVIDENCE_DEPTH_BATCH","12"))))
RETRIES=3
PROOF_GATES={
 "TWSE":("official_trade_day_security_and_dataset","official_value_by_stock_and_date",
         "finmind_independent_unadjusted_price","all_fields_all_rows",
         "published_asof_reconstructed"),
 "TPEx":("otc_market_membership_asof","official_historical_trade_day_and_market_scope",
         "official_value_and_third_party_comparison","all_fields_all_rows","published_asof_reconstructed"),
 "MOPS":("company_id_market_asof","reporting_period_filing_timestamp",
         "gaap_ifrs_xbrl_taxonomy_version","accounting_units_and_amendment_number",
         "official_filing_value","independent_financial_values","all_fields_all_rows"),
 "TDCC":("historical_security_class_asof","weekly_snapshot_date",
         "holder_tier_count_shares_total","official_same_code_same_date_value",
         "independent_second_source","all_fields_all_rows"),
 "TAIFEX":("csv_encoding_quote_header_and_footer","report_product_and_contract_type",
         "trading_day_and_after_hours_assignment","contract_month_vs_trade_date",
         "official_contract_row","independent_third_party_contract_row","all_fields_all_rows"),
 "NDC":("worksheet_cell_coordinate","series_methodology_effective_month",
         "revised_vs_original_publication_series","official_downloaded_numeric_cell",
         "independent_secondary_series","all_fields_all_rows"),
 "FinMind":("provider_dataset_id_and_version","unit_archive_sha_and_row_date",
         "exchange_issuer_source_value","provider_original_value",
         "third_party_is_independent_of_provider","all_fields_all_rows")}
CLASSIFIERS={
 "TWSE":{"STOCK_DAILY_OHLCV","INDEX","VALUATION","MARGIN_FINANCING","INSTITUTIONAL","LENDING","FOREIGN_HOLDING"},
 "TPEx":{"STOCK_DAILY_OHLCV","MARKET_CAPITALIZATION","INDEX","MARGIN_FINANCING","LENDING","VALUATION","FOREIGN_HOLDING"},
 "MOPS":{"MONTHLY_REVENUE","INCOME_STATEMENT","BALANCE_SHEET","CASH_FLOW","ANNOUNCEMENT"},
 "TDCC":{"SHAREHOLDING_DISTRIBUTION","SECURITY_MASTER_ASOF","NON_ORDINARY_INSTRUMENT"},
 "TAIFEX":{"FUTURES_DAILY","OPTIONS_DAILY","INSTITUTIONAL","LARGE_TRADER","CONTRACT_META"},
 "NDC":{"BUSINESS_SIGNAL","LEADING_INDEX","COINCIDENT_INDEX","LAGGING_INDEX","SERIES_COMPONENTS"},
 "FinMind":{"TaiwanStockPrice","TaiwanStockFinancialStatements","TaiwanStockInstitutionalInvestorsBuySell","TaiwanStockInfo"}}
def evidence_state(source,row,raw,native,external=None):
 """Inspect one original file and report evidence *requirements*, not proof assertions."""
 base={"source_id":row["source_id"],"source":source,"original_sha256":row["sha"],
       "source_path":row.get("source_path"),"silver_ready_promoted":False,
       "all_fields_verified":False,"all_rows_verified":False}
 if digest(raw)!=row["sha"]:
  return {**base,"status":"HOLD_ORIGINAL_SHA_MISMATCH","missing":list(PROOF_GATES[source])}
 ym=str(row["year"])+"-"+str(row["month"])
 historical=period(source,ym)
 ext=str(row.get("source_path","")).rsplit("/",1)[-1]
 report=analyze(source,ext,raw,ym+"-01")
 signatures=Counter()
 datasets=Counter()
 for m in report.get("members",[]):
  signatures[m.get("format","unknown")]+=1
  child=m.get("detail",{})
  for k,n in child.get("dataset_counts",{}).items():datasets[k]+=n
 if report.get("dataset"):datasets[str(report["dataset"])]+=1
 for k,n in report.get("detail",{}).get("dataset_counts",{}).items():datasets[k]+=n
 status="CONTENT_DEEP_INSPECTED_ORIGIN_PENDING"
 if report["status"].startswith("HOLD_"):status="HOLD_CONTENT_"+report["status"]
 if native and native.get("status","").startswith(("HOLD_","RETRY_")):
  status="HOLD_SOURCE_NATIVE_"+native["status"]
 row_info={"source":source,"source_id":row["source_id"],"sha":row["sha"]}
 external_decision=independently_attested(row_info,external)[0] if external else False
 # A single externally attested metric cannot prove every row and field.
 missing=list(PROOF_GATES[source])
 if external_decision:
  missing=[x for x in missing if x not in ("official_value_by_stock_and_date",
     "official_value_and_third_party_comparison","independent_financial_values")]
 return {**base,"status":status,"historical_version":historical["id"],
   "format_signature":report["signature"],
   "deep_status":report["status"],
   "member_signature_counts":dict(signatures),
   "dataset_fingerprints":dict(datasets),
   "source_native_status":native.get("status") if native else None,
   "original_sha_checked":True,
   "official_numeric_observations_proven":int(bool(external_decision)),
   "full_file_numeric_coverage":False,"publication_pit_verified":False,
   "required_evidence":list(PROOF_GATES[source]),
   "missing":missing,
   "next_resolution":triage(source,(native or {}).get("status","NOT_EXAMINED"))["resolver"]}
def retries(ck):
 return {sid for sid,v in ck.items() if str(v.get("status","")).startswith("RETRY_")
   and int(v.get("attempts",0))<RETRIES}
def run(source):
 if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 native_f=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 if not inp or not native_f:raise RuntimeError("MISSING_FROZEN_INPUT_OR_NATIVE_CHECKPOINT")
 rows=load_json(api,inp["id"])["rows"]
 native=load_json(api,native_f["id"])["done"]
 # Never silently overwrite the authoritative 35467 READY set.
 from scripts.v097_seven_parser_triage import latest_complete
 rid,formal=latest_complete(api,quality,match,load_json)
 ready={x["source_id"] for x in formal[source]["records"] if x["status"]==READY}
 name="v097_SEVEN_INDEPENDENT_DEPTH_CK_"+source+".json"
 file=match(api,control,name)
 ck=load_json(api,file["id"]) if file else {"schema":VERSION,"version":VERSION,"source":source,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("EVIDENCE_CHECKPOINT_VERSION_CONFLICT")
 done=ck["done"]
 allowed={x["source_id"] for x in rows if x["source_id"] not in ready}
 if set(done)-allowed:raise RuntimeError("EVIDENCE_CHECKPOINT_ID_OUTSIDE_HOLD_COHORT")
 # Read only already-parsed HOLDs; do not trigger expensive parsing for unseen files.
 redo=retries(done)
 todo=[x for x in rows if x["source_id"] in native and
    x["source_id"] in allowed and (x["source_id"] not in done or x["source_id"] in redo)]
 redo_rows=[x for x in todo if x["source_id"] in redo][:min(3,BATCH//4)]
 new_rows=[x for x in todo if x["source_id"] not in done][:BATCH-len(redo_rows)]
 selected=redo_rows+new_rows
 batch={}
 for row in selected:
  sid=row["source_id"]
  try:
   raw=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   batch[sid]=evidence_state(source,row,raw,native.get(sid))
  except (TimeoutError,socket.timeout,ConnectionError,OSError,HttpError) as exc:
   batch[sid]={"source_id":sid,"source":source,
    "status":"RETRY_EVIDENCE_"+type(exc).__name__,
    "attempts":done.get(sid,{}).get("attempts",0)+1,
    "silver_ready_promoted":False}
  except Exception as exc:
   batch[sid]={"source_id":sid,"source":source,
    "status":"HOLD_INSPECTOR_"+type(exc).__name__,
    "silver_ready_promoted":False}
 done.update(batch)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["formal_release_run"]=rid
 if batch:
  # Existing Google Drive retry helper verifies uncertain writes by re-reading.
  from scripts.v097_seven_native_v2_probe import checkpoint_commit
  checkpoint_commit(api,control,name,ck,upsert,match,load_json)
 print("SEVEN_INDEPENDENT_DEPTH="+json.dumps({"source":source,
  "checked":len(done),"new":len(batch),
  "eligible_native_holds":len(set(native)&allowed),
  "remaining":len((set(native)&allowed)-set(done)),
  "source_statuses":dict(Counter(v["status"] for v in batch.values())),
  "newly_ready":0},ensure_ascii=False),flush=True)
def selftest():
 from scripts.v097_bronze_autopilot import digest
 assert set(PROOF_GATES)==set(CLASSIFIERS)==set(SOURCES)
 doc=json.dumps({"date":"2026-11-13","tables":[{"fields":["代號","收盤價","成交股數"],
  "data":[["2330","100","1000"]]}]},ensure_ascii=False).encode()
 for s in SOURCES:
  row={"source_id":"test","sha":digest(doc),"source_path":"2026/"+s+"/test.raw",
   "year":"2026","month":"11"}
  x=evidence_state(s,row,doc,{"status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"})
  assert x["original_sha_checked"] and not x["silver_ready_promoted"]
  assert len(x["required_evidence"])>=5 and not x["all_rows_verified"]
  assert x["official_numeric_observations_proven"]==0
  assert evidence_state(s,row,b"forged",{})["status"]=="HOLD_ORIGINAL_SHA_MISMATCH"
 assert retries({"a":{"status":"RETRY_EVIDENCE_TimeoutError","attempts":1},
                 "b":{"status":"RETRY_EVIDENCE_TimeoutError","attempts":3}})=={"a"}
 print("SEVEN_DEEP_INDEPENDENT_EVIDENCE_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
