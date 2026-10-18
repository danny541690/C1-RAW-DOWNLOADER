"""Bounded 2024 public canaries: TPEx OTC OHLC and MOPS monthly revenue."""
import json
import urllib.request
from datetime import date

def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-v093-canary"})
    with urllib.request.urlopen(req,timeout=25) as resp:
        data=resp.read(2000001)
    if len(data)>2000000: raise ValueError("size cap")
    return data

def inspect_tpex(body):
    payload=json.loads(body)
    rows=payload.get("aaData")
    if not isinstance(rows,list) or not rows: raise ValueError("no TPEx historical rows")
    dates=[]
    for row in rows:
        parts=str(row[0]).split("/")
        if len(parts)!=3: raise ValueError("TPEx unknown date format")
        y,m,d=map(int,parts)
        y+=1911 if y<1911 else 0
        value=date(y,m,d)
        if (value.year,value.month)!=(2024,1): raise ValueError("TPEx wrong month")
        dates.append(value)
    return {"source":"TPEx","dataset":"OTC_STOCK_DAY","records":len(rows),
            "first_date":min(dates).isoformat(),"last_date":max(dates).isoformat(),
            "result":"STRUCTURE_DATE_PASS","drive_uploaded":False}

def inspect_mops(body):
    # Raw archived official monthly revenue page, not financial statement PIT validation.
    if len(body)<1000: raise ValueError("MOPS response too short")
    text=body.decode("big5",errors="replace")
    if "營業收入" not in text and "營收" not in text: raise ValueError("no revenue header")
    if "<table" not in text.lower(): raise ValueError("no revenue table")
    return {"source":"MOPS","dataset":"MONTHLY_REVENUE_ARCHIVE","bytes":len(body),
            "result":"HTML_REVENUE_TABLE_PRESENT","content_month_confirmed":False,
            "numeric_verified":False,"pit_verified":False,"drive_uploaded":False}

def main():
    results=[]
    probes=[
      ("TPEx","https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?d=113/01&stkno=6488",inspect_tpex),
      ("MOPS","https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_113_1_0.html",inspect_mops)]
    for name,url,fn in probes:
        try:
            result=fn(get(url))
            print(json.dumps(result,ensure_ascii=False));results.append(result)
        except Exception as exc:
            print(json.dumps({"source":name,"result":"CANARY_FAIL","error_type":type(exc).__name__}))
            results.append(None)
    if any(x is None for x in results): raise SystemExit(1)

if __name__=="__main__": main()
