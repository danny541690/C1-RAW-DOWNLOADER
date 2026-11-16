#!/usr/bin/env python3
"""Three-way schema / temporal reconciliation ledger, seven sources.
COLUMNS: v0.97 observed parsed dataset, independent official published format
reference, third-party provider dataset. This is a DOCUMENT-LEVEL comparison;
no fake live numerical recheck or Silver release.
"""
import json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,source_api
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_seven_source_specific_resolvers import triage

# Only verified documented third-party dataset names or explicit "none":
THIRD_PARTY={
 "TWSE":{"provider":"FinMind","datasets":["TaiwanStockPrice","TaiwanStockPER","TaiwanStockInstitutionalInvestorsBuySell"],
  "keys":["date","stock_id"],"rules":["unadjusted price only","volume shares vs trading lots","listed vs OTC market as-of"]},
 "TPEx":{"provider":"FinMind","datasets":["TaiwanStockPrice","TaiwanStockPER","TaiwanStockMarginPurchaseShortSale"],
  "keys":["date","stock_id"],"rules":["OTC only","closing price vs market-cap ranking separate","market trading scope"]},
 "MOPS":{"provider":"FinMind","datasets":["TaiwanStockFinancialStatements","TaiwanStockBalanceSheet","TaiwanStockCashFlowsStatement","TaiwanStockMonthRevenue"],
  "keys":["stock_id","date","type"],"rules":["GAAP vs IFRS tag","accounting units","report period vs announcement/publication PIT","FinMind create_time NOT official MOPS filing time"]},
 "TDCC":{"provider":"FinMind","datasets":["TaiwanStockHoldingSharesPer"],
  "keys":["date","stock_id","HoldingSharesLevel"],"rules":["weekly distribution snapshot","security class PIT","percentage denominator and tiers"]},
 "TAIFEX":{"provider":"FinMind","datasets":["TaiwanFuturesDaily","TaiwanOptionDaily"],
  "keys":["date","contract"],"rules":["trade date vs contract maturity","after-hours attribution from 2017-05-15","contracts/lots unit"]},
 "NDC":{"provider":"FinMind","datasets":["TaiwanBusinessIndicator"],
  "keys":["date","series"],"rules":["historical signal composition versions","revision vs original publication PIT","signal components not directly comparable across methods"]},
 "FinMind":{"provider":"FinMind original v4 API (not independent third party)","datasets":["TaiwanStockPrice","TaiwanStockFinancialStatements","TaiwanStockInfo"],
  "keys":["dataset","date","stock_id"],"rules":["self-retrieval is not independent three-party verification","provider revision history","per-unit SHA and source period"]},
}
def make(source,ck):
 if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 done=ck["done"]
 fmt=Counter()
 blockers=Counter()
 eras=Counter()
 for v in done.values():
  eras[v.get("historical_version","UNCLASSIFIED")]+=1
  status=v.get("status","UNCLASSIFIED")
  blockers[status]+=1
  t=v.get("parser_detail",{})
  if isinstance(t,dict):
   for k,n in t.get("table_datasets",{}).items():fmt[k]+=int(n)
  if status.startswith("HOLD") and "resolver" not in v:raise RuntimeError("UNROUTED_HOLD")
 return {"source":source,"observed_v097_format_statuses":dict(blockers),
    "observed_dataset_fingerprints":dict(fmt),"observed_era_sample":dict(eras),
    "official_format_references":OFFICIAL_VERSIONS[source]["reference"],
    "official_release_version_windows":OFFICIAL_VERSIONS[source]["periods"],
    "official_required_proof":OFFICIAL_VERSIONS[source]["strict"],
    "third_party_schema":THIRD_PARTY[source],
    "rows_checked":len(done),"independently_fetched_official_rows":0,
    "third_party_numerical_comparisons":0,
    "schema_crosswalk_only":True,"approved_for_silver":False}
def run():
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 out={}
 for s in SOURCES:
  f=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+s+".json")
  if not f:raise RuntimeError("WAIT_SOURCE_V2_CHECKPOINT:"+s)
  out[s]=make(s,load_json(api,f["id"]))
 report={"schema":"v097_seven_threeway_schema_crosswalk_v1",
   "created_at":datetime.now(timezone.utc).isoformat(),
   "run":os.getenv("GITHUB_RUN_ID","manual"),"sources":out,
   "cannot_assert_exact_numeric_matching":True,
   "silver_gold_executed":False}
 if os.getenv("GITHUB_RUN_ID"):
  put_once(api,quality,"v097_SEVEN_3WAY_SCHEMA_CROSSWALK_"+report["run"]+".json",report)
 print("SEVEN_3WAY_CROSSWALK="+json.dumps({
  "source_counts":{s:x["rows_checked"] for s,x in out.items()},
  "official_live_rows":0,"third_party_numerical_comparisons":0,
  "silver_promoted":0,"report":"v097_SEVEN_3WAY_SCHEMA_CROSSWALK_"+report["run"]+".json"},ensure_ascii=False),flush=True)
def selftest():
 assert set(THIRD_PARTY)==set(SOURCES)
 for s in SOURCES:
  assert THIRD_PARTY[s]["datasets"] and THIRD_PARTY[s]["keys"]
  assert OFFICIAL_VERSIONS[s]["reference"]
  r=make(s,{"done":{"sample":{"status":"HOLD_UNKNOWN_JSON_DATASET",
    "historical_version":"v0","resolver":triage(s,"HOLD_UNKNOWN_JSON_DATASET")["resolver"]}}})
  assert r["rows_checked"]==1 and r["schema_crosswalk_only"] and not r["approved_for_silver"]
 assert "NOT official MOPS" not in THIRD_PARTY["MOPS"]["rules"] # informational
 print("SEVEN_3WAY_SCHEMA_CROSSWALK_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==1:run()
 else:raise SystemExit("usage: [selftest]")
