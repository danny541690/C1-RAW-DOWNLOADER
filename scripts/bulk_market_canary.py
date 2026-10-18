"""One-day whole-market endpoint preflight. Never claims full-year completeness."""
import json,urllib.request,urllib.parse
DATE="20240102"
URLS={
"TWSE":"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20240102&type=ALLBUT0999&response=json",
"TPEx":"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?response=json&date=2024%2F01%2F02"}
def measure(source,raw):
    x=json.loads(raw.decode("utf-8-sig"))
    if source=="TWSE":
        tables=x.get("tables") or []
        matches=[t for t in tables if "證券代號" in t.get("fields",[]) and "收盤價" in t.get("fields",[])]
        if not matches:raise ValueError("TWSE whole-market securities table not found")
        rows=sum(len(t.get("data") or []) for t in matches)
    else:
        tables=x.get("tables") or []
        rows=sum(len(t.get("data") or []) for t in tables if any("代號" in str(f) for f in t.get("fields",[])))
        if rows==0:rows=len(x.get("aaData") or x.get("data") or [])
        if rows==0:raise ValueError("TPEx stock rows absent")
    if rows<300:raise ValueError("response too small to represent market snapshot")
    return {"source":source,"date":DATE,"rows":rows,"scope":"SINGLE_DAY_BULK_CANARY","numeric_verified":False,"pit_verified":False}
def run():
    for source,url in URLS.items():
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=35) as r:raw=r.read(10000000)
            print(json.dumps(measure(source,raw)))
        except Exception as e:
            print(json.dumps({"source":source,"error_type":type(e).__name__,"result":"FAIL"}))
            raise
if __name__=="__main__":run()
