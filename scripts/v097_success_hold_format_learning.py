#!/usr/bin/env python3
"""Seven-source successful-vs-HOLD format forensic learning, no inferred READY.

Reads 74,750 frozen formal release observations, A and V2 checkpoints; discovers
which exact, observed schema classes are common among READY and HOLD.
Produces source-scoped recovery playbook and prioritizes resolvable format
classes before expensive independent numeric checks. Preserves every exception.
"""
import json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS

FIXES={
 "TWSE":{"ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"ZIP member per-sha manifest + A05 type/edition/time slot + numeric official and third-party per row",
         "HOLD_DATASET_IDENTITY":"Dataset names and official historical table titles, never just closing price fields",
         "CONTENT_PARSED_ORIGIN_PIT_HOLD":"Original quote date+code, trade scope and published-at then full row/field reconciliation"},
 "TPEx":{"HOLD_UNKNOWN_JSON_DATASET":"Separate receipt JSON from quotes; 2003-2006 and early 2007 editions",
         "HOLD_UNRECOGNIZED_EXTENSION":"Detect magic bytes and receipt-vs-source payload, never promote a receipt as trade rows",
         "HOLD_CONTENT_PERIOD_CONFLICT":"Compare each payload trading day to archive location after ROC conversion",
         "ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"Versioned table identity, market capitalization vs OHLCV, immutable manifest"},
 "MOPS":{"ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"Per member typed financial HTML/XBRL/iXBRL and declaration receipt",
         "HOLD_UNKNOWN_JSON_DATASET":"Distinguish receipt JSON from numeric financial tables",
         "MOPS_MATRIX_RECEIPT_AND_PIT_HOLD":"Per company filing period GAAP/IFRS taxonomy, corrections, publication timestamp and currency units"},
 "TDCC":{"TDCC_HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING":"As-of code universe for warrant/ETF/security type, do not coerce unknown type",
         "TDCC_HOLD_DISTRIBUTION_TABLE_QA":"Per-tier headcount/shares/percentage + official totals with rounding policy",
         "HOLD_DATE_EVIDENCE":"Weekly last business day and archived publication proof; retention limitation"},
 "TAIFEX":{"HOLD_TAIFEX_CSV_WIDTH":"Report-specific CSV header, quoted delimiters, CP950/Big5, trailing blank vs footer",
         "HOLD_DATE_EVIDENCE":"Date in source vs futures contract month vs after-hours reporting trade date",
         "HOLD_ZIP_EXPANSION_LIMIT":"Bound and enumerate yearly ZIP members; do not silently skip",
         "HOLD_TAIFEX_MONTH_CONFLICT":"Separate contract delivery month from data collection month"},
 "NDC":{"HOLD_NDC_UNDOCUMENTED_CELL_GAP":"Keep physical Excel cell+worksheet, source revision and official documented missingness"},
 "FinMind":{"HOLD_FINMIND_ROW_PERIOD_CONFLICT":"Distinguish observation date from retrieval month, typed dataset and corrections",
         "HOLD_FINMIND_PROVIDER_OR_DATASET_PROOF":"Dataset version + official source alignment, independent provider data cannot self-verify"}}
def learn(gates,stage):
 result={}
 for src in SOURCES:
  gate=gates[src]
  formal={r["source_id"]:r for r in gate["records"]}
  accepted={sid for sid,r in formal.items() if r["status"]==READY}
  a=stage[src].get("A",{})
  v=stage[src].get("V2",{})
  states={"READY":Counter(),"HOLD":Counter()}
  examples={}
  for sid,r in a.items():
   kind="READY" if sid in accepted else "HOLD"
   status=r.get("status","UNKNOWN")
   states[kind][status]+=1
   if kind=="HOLD" and len(examples.setdefault(status,[]))<3:examples[status].append(sid)
  eras=Counter()
  v2_status=Counter()
  for sid,r in v.items():
   if sid not in accepted:
    eras[r.get("historical_version","UNCLASSIFIED")]+=1
    v2_status[r.get("status","UNKNOWN")]+=1
  work=sorted(((k,n,FIXES.get(src,{}).get(k,"Requires source-specific evidence and source schema review"))
      for k,n in states["HOLD"].items()),key=lambda z:-z[1])
  result[src]={"cohort":gate["cohort"],"ready":len(accepted),"hold":len(formal)-len(accepted),
    "observed_ready_parser_patterns":dict(states["READY"]),
    "observed_hold_parser_patterns":dict(states["HOLD"]),
    "hold_era_samples":dict(eras),"hold_v2_statuses":dict(v2_status),
    "priority_action_classes":[{"status":k,"count":n,"strategy":fix,
      "sample_ids":examples.get(k,[])} for k,n,fix in work],
    "historical_format_reference_urls":OFFICIAL_VERSIONS[src]["reference"],
    "format_windows":OFFICIAL_VERSIONS[src]["periods"],
    "official_values_verified_in_this_run":0,"promoted":0}
 return result
def run():
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 rid,gates=latest_complete(api,quality,match,load_json)
 stages={}
 for src in SOURCES:
  stages[src]={}
  for s,n in [("A",f"v097_AP_CHECKPOINT_{src}.json"),("V2",f"v097_SEVEN_FORMAT_V2_CK_{src}.json")]:
   f=match(api,control,n)
   if f:stages[src][s]=load_json(api,f["id"])["done"]
 out={"schema":"v097_success_hold_source_format_learning_v1",
  "run":os.getenv("GITHUB_RUN_ID","manual"),
  "formal_release_run":rid,
  "created_utc":datetime.now(timezone.utc).isoformat(),
  "sources":learn(gates,stages),"full_numeric_attestation_not_assumed":True}
 if out["run"]!="manual":
  put_once(api,quality,f"v097_SUCCESS_HOLD_FORMAT_LEARNING_{out['run']}.json",out)
 print("SEVEN_SUCCESS_HOLD_LEARNING="+json.dumps({
  "release_run":rid,"by_source":{s:{"ready":x["ready"],"hold":x["hold"],
   "top_hold":x["priority_action_classes"][:4]} for s,x in out["sources"].items()}},
   ensure_ascii=False),flush=True)
def selftest():
 gates={s:{"cohort":2,"records":[{"source_id":s+"1","status":READY},
           {"source_id":s+"2","status":"HOLD"}]} for s in SOURCES}
 stage={s:{"A":{s+"1":{"status":"PASS"},s+"2":{"status":"ERR"}},"V2":{}} for s in SOURCES}
 res=learn(gates,stage)
 assert set(res)==set(SOURCES)
 for s in SOURCES:
  assert res[s]["observed_ready_parser_patterns"]=={"PASS":1}
  assert res[s]["observed_hold_parser_patterns"]=={"ERR":1}
  assert res[s]["promoted"]==0
 print("SUCCESS_HOLD_FORMAT_LEARNING_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif not sys.argv[1:]:run()
 else:raise SystemExit("usage: [selftest]")
