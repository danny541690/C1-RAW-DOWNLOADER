#!/usr/bin/env python3
"""FinMind Free vs Backer same-parameter empirical comparison (JARVIS v0.98).
No secrets in report; no Google Drive writes. Categories reflect official
FinMind Pricing table; status from API, not assumed from documentation.
"""
import csv,datetime as dt,hashlib,json,os,time,urllib.request,urllib.error,urllib.parse
from pathlib import Path
MODE=os.environ.get("FINMIND_PLAN","FREE").upper()
TOKEN=(os.environ.get("FINMIND_BACKER_TOKEN","") if MODE=="BACKER" else "")
BASE="https://api.finmindtrade.com/api/v4/data"
def entry(ds,category,tier,data_id="2330",start="2024-01-02",end="2024-01-05"):
    q={"dataset":ds,"start_date":start,"end_date":end}
    if data_id is not None: q["data_id"]=data_id
    return {"dataset":ds,"category":category,"official_min_tier":tier,"params":q}
TESTS=[
    entry("TaiwanStockPrice","daily_price","FREE"),
    entry("TaiwanStockInstitutionalInvestorsBuySell","institutional","FREE"),
    entry("TaiwanStockMarginPurchaseShortSale","margin_short","FREE"),
    entry("TaiwanStockMonthRevenue","revenue","FREE",start="2024-01-01",end="2024-12-31"),
    entry("TaiwanStockFinancialStatements","financial_income","FREE",start="2024-01-01",end="2024-12-31"),
    entry("TaiwanStockBalanceSheet","balance_sheet","FREE",start="2024-01-01",end="2024-12-31"),
    entry("TaiwanStockCashFlowsStatement","cash_flow","FREE",start="2024-01-01",end="2024-12-31"),
    entry("TaiwanStockPER","valuation","FREE"),
    entry("TaiwanStockShareholding","foreign_shareholding","FREE"),
    entry("TaiwanStockPriceAdj","adjusted_price","BACKER",start="2024-01-01",end="2024-01-31"),
    entry("TaiwanStockHoldingSharesPer","shareholding_tiers","BACKER",start="2024-01-01",end="2024-01-31"),
    entry("TaiwanStockMarketValue","market_value","BACKER",start="2024-01-01",end="2024-01-31"),
    entry("TaiwanBusinessIndicator","macro_indicator","BACKER",data_id=None,start="2024-01-01",end="2024-03-31"),
    entry("TaiwanStockPrice","all_stocks_one_day","BACKER_ALL_STOCKS",data_id=None,start="2024-01-02",end="2024-01-02"),
]
def test(spec):
    req=urllib.request.Request(BASE+"?"+urllib.parse.urlencode(spec["params"]),
      headers={"User-Agent":"JARVIS-C1-v098-plan-comparison/1.0",
               "Accept":"application/json",**({"Authorization":"Bearer "+TOKEN} if MODE=="BACKER" else {})})
    try:
        with urllib.request.urlopen(req,timeout=50) as res:
            http=res.status; body=res.read(8000001)
            if len(body)>8000000:return {"state":"SIZE_LIMIT", "http_status":http}
    except urllib.error.HTTPError as e:
        return {"state":"HTTP_ERROR","http_status":e.code}
    except Exception as e:
        return {"state":"TRANSPORT_ERROR","error_type":type(e).__name__}
    try:
        p=json.loads(body.decode("utf-8-sig"));rows=p.get("data")
        if p.get("status")!=200:return {"state":"API_REJECTED","http_status":http,"api_status":p.get("status")}
        if not isinstance(rows,list):return {"state":"SHAPE_ERROR","http_status":http}
        if not rows:return {"state":"EMPTY","http_status":http,"rows":0}
        if not all(isinstance(x,dict) for x in rows):return {"state":"ROW_ERROR","http_status":http}
        fields=sorted(set().union(*(x.keys() for x in rows)))
        canonical=json.dumps(sorted(rows,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False)),
                             sort_keys=True,ensure_ascii=False,separators=(",",":"))
        return {"state":"PASS","http_status":http,"rows":len(rows),
                "columns":fields,"normalized_rows_sha256":hashlib.sha256(canonical.encode()).hexdigest(),
                "sample_row":rows[0]}
    except Exception as e:
        return {"state":"JSON_ERROR","error_type":type(e).__name__}
def main():
    if MODE=="BACKER" and not TOKEN:raise SystemExit("MISSING_BACKER_TOKEN")
    out=Path("finmind_plan_comparison");out.mkdir(exist_ok=True)
    report={"plan":MODE,"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "authentication":"BACKER_BEARER" if MODE=="BACKER" else "ANONYMOUS_FREE",
       "no_drive_writes":True,"complete_dataset_catalog":False,"tests":[]}
    for idx,spec in enumerate(TESTS,1):
        result=test(spec);rec={**spec,**result};report["tests"].append(rec)
        print(json.dumps({"index":idx,"dataset":spec["dataset"],"category":spec["category"],
            "official_min_tier":spec["official_min_tier"],"state":result["state"],
            "rows":result.get("rows",0),"api_status":result.get("api_status"),
            "http_status":result.get("http_status"),"columns":len(result.get("columns",[]))},ensure_ascii=False),flush=True)
        if result.get("http_status")==429:break
        time.sleep(.5)
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    with (out/"overview.csv").open("w",newline="",encoding="utf-8-sig") as fh:
        w=csv.writer(fh);w.writerow(["plan","category","dataset","official_min_tier","state","rows","http_status","api_status","normalized_rows_sha256","columns"])
        for r in report["tests"]:
            w.writerow([MODE,r["category"],r["dataset"],r["official_min_tier"],r["state"],r.get("rows"),r.get("http_status"),r.get("api_status"),r.get("normalized_rows_sha256"),"|".join(r.get("columns",[]))])
    print("COMPLETE",MODE,"PASS",sum(x["state"]=="PASS" for x in report["tests"]),"OF",len(report["tests"]))
if __name__=="__main__":main()
