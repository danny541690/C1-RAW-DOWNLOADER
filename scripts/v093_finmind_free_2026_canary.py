"""JARVIS v0.93 FinMind Free 2026 canary, scoped to explicit official Free datasets.
Never omits data_id for per-symbol requests; never claims all 45 complete.
Read-only FinMind calls, stores immutable proof/receipt in 2026/FinMind/_FREE_2026_CONTROL.
"""
import datetime,hashlib,json,os,time,urllib.parse,urllib.request,urllib.error
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
DATASETS=["TaiwanStockInfo","TaiwanStockPrice","TaiwanStockInstitutionalInvestorsBuySell","TaiwanStockMarginPurchaseShortSale","TaiwanStockMonthRevenue","TaiwanStockFinancialStatements","TaiwanStockBalanceSheet","TaiwanStockCashFlowsStatement","TaiwanStockPER","TaiwanStockShareholding"]
def fetch(ds,stock=None):
 args={"dataset":ds,"start_date":"2026-01-01","end_date":min(datetime.date.today(),datetime.date(2026,12,31)).isoformat()}
 if stock:args["data_id"]=stock
 if ds=="TaiwanStockInfo":args={"dataset":ds}
 url="https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode(args)
 headers={"User-Agent":"JARVIS-v0.93-FinMind-Free-2026/1.0","Accept":"application/json"}
 tok=os.environ.get("FINMIND_TOKEN","").strip() or os.environ.get("FINMIND_API_TOKEN","").strip()
 if tok:headers["Authorization"]="Bearer "+tok
 request=urllib.request.Request(url,headers=headers)
 with urllib.request.urlopen(request,timeout=45) as f:b=f.read(12000001)
 if len(b)>12000000:raise ValueError("RESPONSE_SIZE_CAP")
 j=json.loads(b.decode("utf-8-sig"))
 if j.get("status")!=200 or not isinstance(j.get("data"),list):raise ValueError("API_STATUS_OR_SHAPE:"+str(j.get("status"))+":"+str(j.get("msg",""))[:110])
 return b,j,args
def run():
 d=Drive(service());year=d.folder(ROOT,"2026");fm=d.folder(year,"FinMind");control=d.folder(fm,"_FREE_2026_CONTROL")
 results=[];stocks=[]
 for ds in DATASETS:
  ent={"dataset":ds,"stock":"2330" if ds!="TaiwanStockInfo" else None,"status":"PENDING"}
  try:
   raw,payload,args=fetch(ds,ent["stock"])
   rows=payload["data"]
   if ds=="TaiwanStockInfo":
    stocks=sorted({str(x["stock_id"]) for x in rows if isinstance(x,dict) and x.get("stock_id")})
   else:
    valid=[x for x in rows if isinstance(x,dict) and str(x.get("stock_id"))=="2330"]
    if len(valid)!=len(rows):raise ValueError("STOCK_SCOPE_MISMATCH")
    for v in valid:
     day=v.get("date")
     if day and isinstance(day,str) and day[:4]!="2026":raise ValueError("OUT_OF_YEAR_ROW")
   ent.update({"status":"FREE_API_SUCCESS","records":len(rows),"bytes":len(raw),"raw_sha256":hashlib.sha256(raw).hexdigest(),"param_scope":args,"observed_field_names":sorted({k for r in rows[:100] if isinstance(r,dict) for k in r})})
   d.put(control,"CANARY_"+ds+"_2330.json",raw,"application/json",overwrite=False)
  except Exception as e:ent.update({"status":"FAILED_OR_UNVERIFIED","error":type(e).__name__+":"+str(e)[:220]})
  results.append(ent)
  print(json.dumps({"dataset":ds,"status":ent["status"],"records":ent.get("records",0),"error":ent.get("error")},ensure_ascii=False),flush=True)
  if "402" in ent.get("error","") or "429" in ent.get("error",""):break
  time.sleep(1.3)
 manifest={"version":"FINMIND_2026_FREE_CANARY_R1","year":2026,"asof_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "token_supplied":bool(os.environ.get("FINMIND_TOKEN") or os.environ.get("FINMIND_API_TOKEN")),
  "sample_stock":"2330","datasets_tested":len(results),"official_free_dataset_target":45,
  "stock_universe_count":len(stocks),"stock_universe_provisional":True,"records":results,"market_coverage_verified":False,"numeric_verified":False,"pit_verified":False}
 d.put(control,"CANARY_2026_FREE_R1_REPORT.json",json.dumps(manifest,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
 if stocks:d.put(control,"TaiwanStockInfo_2026_stock_universe_provisional.json",json.dumps(stocks,ensure_ascii=False).encode(),"application/json",overwrite=True)
 print(json.dumps({"report":"2026/FinMind/_FREE_2026_CONTROL/CANARY_2026_FREE_R1_REPORT.json","datasets_ok":sum(x["status"]=="FREE_API_SUCCESS" for x in results),"tested":len(results),"stock_list":len(stocks),"complete":False},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
