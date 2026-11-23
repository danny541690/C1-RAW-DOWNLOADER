#!/usr/bin/env python3
"""JARVIS v0.98 five-session FinMind Free vs Backer collection audit.
Identical query parameters for both jobs; never writes Google Drive.
Backer-only queries rejected by Free are NOT evidence of missing history.
Dataset candidates are from previously working JARVIS API calls, not a claim
to have enumerated FinMind's entire 45/81 catalog.
"""
import csv,hashlib,datetime,json,os,time,urllib.parse,urllib.request,urllib.error
from pathlib import Path
PLAN=os.environ.get("JARVIS_FINMIND_PLAN","FREE").upper()
TOKEN=os.environ.get("FINMIND_BACKER_TOKEN","").strip() if PLAN=="BACKER" else ""
DAYS=("2024-01-02","2024-01-03","2024-01-04","2024-01-05","2024-01-08")
API="https://api.finmindtrade.com/api/v4/data"
# candidate id / domain / cadence / access
DATASETS=[
 ("TaiwanStockPrice","technical","daily","FREE"),
 ("TaiwanStockInstitutionalInvestorsBuySell","chip","daily","FREE"),
 ("TaiwanStockMarginPurchaseShortSale","chip","daily","FREE"),
 ("TaiwanStockPER","valuation","daily","FREE"),
 ("TaiwanStockShareholding","chip","daily","FREE"),
 ("TaiwanStockPriceAdj","technical","daily","BACKER"),
 ("TaiwanStockHoldingSharesPer","chip","daily","BACKER"),
 ("TaiwanStockMarketValue","fundamental","daily","BACKER"),
 ("TaiwanStockPrice","market_wide","all_market","BACKER"),
 ("TaiwanStockInfo","security_master","once","FREE"),
 ("TaiwanStockMonthRevenue","revenue","period","FREE"),
 ("TaiwanStockFinancialStatements","financial","period","FREE"),
 ("TaiwanStockBalanceSheet","financial","period","FREE"),
 ("TaiwanStockCashFlowsStatement","financial","period","FREE"),
 ("TaiwanBusinessIndicator","macro","period","BACKER"),
]
def get(ds,params):
 req=urllib.request.Request(API+"?"+urllib.parse.urlencode(params),
    headers={"Accept":"application/json","User-Agent":"JARVIS-v0.98-five-day-coverage/1.0",
      **({"Authorization":"Bearer "+TOKEN} if PLAN=="BACKER" else {})})
 try:
  with urllib.request.urlopen(req,timeout=65) as resp:
   http=resp.status; raw=resp.read(10_000_001)
   if len(raw)>10_000_000:return dict(state="SIZE_LIMIT",http_status=http)
 except urllib.error.HTTPError as e:
  return dict(state="HTTP_ERROR",http_status=e.code)
 except Exception as e:return dict(state="TRANSPORT_ERROR",error_type=type(e).__name__)
 try:
  body=json.loads(raw.decode("utf-8-sig"))
  if body.get("status")!=200:return dict(state="API_REJECTED",api_status=body.get("status"),http_status=http)
  data=body.get("data")
  if not isinstance(data,list):return dict(state="INVALID_DATA",http_status=http)
  if not data:return dict(state="EMPTY",http_status=http,rows=0,columns=[])
  if not all(isinstance(r,dict) for r in data):return dict(state="NON_OBJECT_ROWS",http_status=http)
  cols=sorted(set().union(*(set(r) for r in data)))
  dates=sorted({str(r.get("date")) for r in data if r.get("date") is not None})
  # Stable digest of response records across Free / Backer.
  canonical=json.dumps(sorted(data,key=lambda r:json.dumps(r,sort_keys=True,ensure_ascii=False)),
     ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
  return dict(state="PASS",http_status=http,rows=len(data),columns=cols,
     observed_dates=dates[:10],distinct_date_count=len(dates),
     distinct_stock_id_count=len({str(r.get("stock_id")) for r in data if "stock_id" in r}),
     content_sha256=hashlib.sha256(canonical).hexdigest(),
     sample=data[0] if len(raw)<500000 else None)
 except Exception as e:return dict(state="PARSE_ERROR",error_type=type(e).__name__)
def main():
 if PLAN not in ("FREE","BACKER"):raise SystemExit("UNKNOWN_PLAN")
 if PLAN=="BACKER" and not TOKEN:raise SystemExit("MISSING_BACKER_TOKEN")
 entries=[]
 for ds,domain,cadence,required_tier in DATASETS:
  if cadence in ("daily","all_market"):
   samples=DAYS
  else:samples=("period",)
  for day in samples:
   params={"dataset":ds}
   if cadence=="all_market":params.update(start_date=day,end_date=day)
   elif cadence=="daily":params.update(data_id="2330",start_date=day,end_date=day)
   elif cadence=="once":pass
   else:
    if ds!="TaiwanBusinessIndicator":params["data_id"]="2330"
    params.update(start_date="2024-01-01",end_date="2024-12-31" if ds!="TaiwanBusinessIndicator" else "2024-03-31")
   got=get(ds,params)
   ent={"plan":PLAN,"dataset":ds,"domain":domain,"cadence":cadence,"required_tier_candidate":required_tier,
       "scope_day":day,"request_params":params,**got}
   entries.append(ent)
   print(json.dumps({k:ent.get(k) for k in ("dataset","scope_day","state","http_status","rows","distinct_date_count")},ensure_ascii=False),flush=True)
   if got.get("http_status") in (402,429):break
   time.sleep(0.25)
 summary={"plan":PLAN,"asof_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "days":list(DAYS),"stock":"2330","auth":"BACKER_TOKEN" if PLAN=="BACKER" else "ANONYMOUS_FREE",
 "scope":"15 named query families; NOT complete 45 / 81 inventory",
 "no_google_drive_writes":True,"gold_443_individual_dependency_contract_verified":False,
 "requests":len(entries),"success":sum(x["state"]=="PASS" for x in entries),
 "entries":entries}
 out=Path("finmind_5day_audit");out.mkdir(exist_ok=True)
 (out/"report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
 with (out/"manifest.csv").open("w",newline="",encoding="utf-8-sig") as file:
  w=csv.writer(file);w.writerow(["plan","dataset","domain","cadence","tier","scope_day","state","http_status","rows","unique_dates","unique_stock_ids","fields","content_sha256"])
  for e in entries:w.writerow([PLAN,e["dataset"],e["domain"],e["cadence"],e["required_tier_candidate"],
     e["scope_day"],e["state"],e.get("http_status"),e.get("rows"),e.get("distinct_date_count"),
     e.get("distinct_stock_id_count"),"|".join(e.get("columns",[])),e.get("content_sha256")])
 print(f"FINAL plan={PLAN} passed={summary['success']}/{len(entries)}")
if __name__=="__main__":main()
