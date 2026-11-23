#!/usr/bin/env python3
"""JARVIS v0.98 FinMind FREE factual dataset history & schema audit.
Anonymous Free API only: no Backer token. Free candidates are parsed directly
from FinMind-MCP official registry, not assumed to equal pricing-page 45.
No Google Drive writes or Bronze mutation.
"""
import collections,csv,datetime as dt,hashlib,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error
ROOT=pathlib.Path("free_source_audit");ROOT.mkdir(exist_ok=True)
DOC="https://raw.githubusercontent.com/FinMind/FinMind-MCP/master/knowledge/datasets.md"
API="https://api.finmindtrade.com/api/v4/data"
STOP="2026-11-24"
ID_BY_DS={"TaiwanStockTotalReturnIndex":"TAIEX","CrudeOilPrices":"WTI",
 "GovernmentBondsYield":"United States 10-Year",
 "TaiwanFuturesDaily":"TX","TaiwanFuturesInstitutionalInvestors":"TX",
 "TaiwanOptionDaily":"TXO","TaiwanOptionInstitutionalInvestors":"TXO",
 "USStockPrice":"AAPL","UKStockPrice":"HSBA.L","EuropeStockPrice":"AALB.AS",
 "JapanStockPrice":"7203.T","InterestRate":"FED"}
SINGLE={"TaiwanStockNews","TaiwanStockStatisticsOfOrderBookAndTrade","TaiwanVariousIndicators5Seconds"}
# Only diagnostic samples are queried on unrestricted broad aggregate datasets.
BOUNDED={"TaiwanStockInfoWithWarrant","TaiwanStockAfterHoursFixedPriceTrading",
 "TaiwanStockTotalMarginPurchaseShortSale","TaiwanStockTotalInstitutionalInvestors",
 "TaiwanStockCapitalReductionReferencePrice","TaiwanStockDelisting","TaiwanStockSplitPrice",
 "TaiwanStockParValueChange","TaiwanFuturesDealerTradingVolumeDaily",
 "TaiwanOptionDealerTradingVolumeDaily","TaiwanExchangeRate","GoldPrice",
 "TaiwanStockTradingDate","TaiwanStockInfo","TaiwanSecuritiesTraderInfo",
 "TaiwanStockActiveETFInfo","TaiwanFutOptDailyInfo","USStockInfo","UKStockInfo",
 "EuropeStockInfo","JapanStockInfo"}
def official_registry():
 with urllib.request.urlopen(urllib.request.Request(DOC,headers={"User-Agent":"JARVIS-free-audit-v098"}),timeout=40) as f:raw=f.read()
 s=raw.decode("utf-8-sig")
 entries=[]
 for section in re.split(r"(?m)^### ",s)[1:]:
  name=section.splitlines()[0].strip()
  tier=re.search(r"(?m)^-\s*\*\*Tier:\*\*\s*(.+)$",section)
  need=re.search(r"(?m)^-\s*\*\*Required:\*\*\s*(.+)$",section)
  if not tier or not need:continue
  if tier.group(1).strip() not in ("Free","Free(w/ data_id)"):continue
  required=need.group(1).strip()
  entries.append({"dataset":name,"registry_tier":tier.group(1).strip(),"required":required})
 return entries,hashlib.sha256(raw).hexdigest()
def request(ds,params):
 req=urllib.request.Request(API+"?"+urllib.parse.urlencode(params),
     headers={"Accept":"application/json","User-Agent":"JARVIS-C1-v098-FREE-history/1.0"})
 try:
  with urllib.request.urlopen(req,timeout=46) as f:
   http=f.status;data=f.read(12000001)
  if len(data)>12000000:return {"state":"SIZE_LIMIT","http_status":http}
  obj=json.loads(data.decode("utf-8-sig"))
  if obj.get("status")!=200:return {"state":"API_REJECTED","http_status":http,"api_status":obj.get("status")}
  rows=obj.get("data")
  if not isinstance(rows,list):return {"state":"BAD_DATA_ARRAY","http_status":http}
  if not rows:return {"state":"EMPTY","rows":0,"columns":[],"http_status":http}
  if not all(isinstance(r,dict) for r in rows):return {"state":"INVALID_ROWS","http_status":http}
  cols=sorted(set().union(*(set(x) for x in rows)))
  observed=sorted({str(x.get("date") or x.get("trade_date") or x.get("datetime") or x.get("create_time"))[:10]
       for x in rows if (x.get("date") or x.get("trade_date") or x.get("datetime") or x.get("create_time"))})
  types={k:sorted({type(x[k]).__name__ for x in rows if k in x}) for k in cols}
  return {"state":"PASS","rows":len(rows),"columns":cols,"column_types":types,
    "earliest_observed_date":observed[0] if observed else None,
    "latest_observed_date":observed[-1] if observed else None,
    "date_count":len(observed),"sample_row":rows[0],"response_sha256":hashlib.sha256(data).hexdigest(),
    "http_status":http}
 except urllib.error.HTTPError as e:return {"state":"HTTP_ERROR","http_status":e.code}
 except Exception as e:return {"state":"TRANSPORT_OR_PARSE","error_type":type(e).__name__}
def main():
 candidates,sha=official_registry()
 # Source catalog snapshot is NOT pricing-plan entitlement catalog.
 results=[]
 for i,d in enumerate(candidates,1):
  ds=d["dataset"];required=d["required"]
  data_id=ID_BY_DS.get(ds,"2330") if "data_id" in required else None
  single=("single day" in required.lower()) or ds in SINGLE
  static=("start_date" not in required)
  params={"dataset":ds}
  if data_id:params["data_id"]=data_id
  if single:params["start_date"]="2024-01-02"
  elif not static:
   params["start_date"]="2024-01-01" if ds in BOUNDED else "1900-01-01"
   params["end_date"]="2024-01-31" if ds in BOUNDED else STOP
  evidence=request(ds,params);trials=[{"query":params,"result":evidence}]
  # Bounded fallback avoids huge responses and timeout. Do NOT infer earliest from bounded sample.
  if evidence["state"] in ("SIZE_LIMIT","HTTP_ERROR","TRANSPORT_OR_PARSE","API_REJECTED") and not single:
   small=dict(params)
   if not static:small.update(start_date="2024-01-01",end_date="2024-01-08")
   result=request(ds,small)
   trials.append({"query":small,"result":result})
   if result["state"]=="PASS":evidence=result
  if evidence["state"]=="EMPTY" and not static and not single:
   newer=dict(params);newer.update(start_date="2026-01-01",end_date="2026-11-20")
   result=request(ds,newer);trials.append({"query":newer,"result":result})
   if result["state"]=="PASS":evidence=result
  if evidence.get("http_status")==429:
   print("API_RATE_LIMIT_STOP",flush=True)
   results.append({**d,"data_id":data_id,"single_day":single,"static":static,"trials":trials,
        "final_state":evidence["state"]})
   break
  broad_pass=trials[0]["result"]["state"]=="PASS" and not static and not single and ds not in BOUNDED
  result={"dataset":ds,"registry_tier":d["registry_tier"],"required":required,
   "data_id_used":data_id,"single_day_query":single,"static_list":static,
   "trials":trials,"final_state":evidence["state"],"rows_observed":evidence.get("rows"),
   "earliest_observed_date":evidence.get("earliest_observed_date"),
   "latest_observed_date":evidence.get("latest_observed_date"),
   "actual_columns":evidence.get("columns",[]),"actual_types":evidence.get("column_types",{}),
   "historical_basis":"BROAD_REQUEST_MIN_OBSERVED_NOT_ALL_MARKET_CERTIFIED" if broad_pass else
      "STATIC_LIST_NO_DATE_BOUND" if static else "BOUNDED_DATE_PROBE_ONLY",
   "is_all_history_certified":False,
   "api_evidence_scope":"ANONYMOUS_FREE_ONLY"}
  results.append(result)
  print(json.dumps({"index":i,"count":len(candidates),"dataset":ds,"state":result["final_state"],
   "first":result.get("earliest_observed_date"),"last":result.get("latest_observed_date"),
   "query_count":len(trials)},ensure_ascii=False),flush=True)
  time.sleep(.35)
 summary={"schema":"JARVIS_V098_FINMIND_FREE_HISTORY_EVIDENCE_V1","date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "official_pricing_free_count":45,"official_registry_free_candidates":len(candidates),
   "official_registry_sha256":sha,"registry_source":DOC,"pricing_vs_registry_count_reconciled":len(candidates)==45,
   "actual_tested":len(results),"pass":sum(x["final_state"]=="PASS" for x in results),
   "empty":sum(x["final_state"]=="EMPTY" for x in results),
   "no_data_or_error":sum(x["final_state"] not in ("PASS","EMPTY") for x in results),
   "global_oldest_stock_history_certified":False,"date_to":STOP,"rows":results}
 (ROOT/"report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 with (ROOT/"free_dataset_history.csv").open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.writer(f);w.writerow(["source","dataset_id","registry_tier","tested_state","data_id_used",
      "earliest_observed_date","latest_observed_date","date_evidence_basis","columns","field_types","history_certified","all_trials"])
  for x in results:
   w.writerow(["FinMind_Free",x["dataset"],x["registry_tier"],x["final_state"],x["data_id_used"],
    x.get("earliest_observed_date"),x.get("latest_observed_date"),x["historical_basis"],
    "|".join(x.get("actual_columns",[])),json.dumps(x.get("actual_types",{}),ensure_ascii=False),False,
    json.dumps([{"query":t["query"],"state":t["result"]["state"],"http_status":t["result"].get("http_status")} for t in x["trials"]],ensure_ascii=False)])
 print("FREE_FINAL "+json.dumps({k:v for k,v in summary.items() if k!="rows"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
