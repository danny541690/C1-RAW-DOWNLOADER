"""FinMind historical 2330 canary: bounded network, no raw publication."""
import json
import urllib.parse
import urllib.request
from datetime import date

def validate(payload):
    if not isinstance(payload,dict) or payload.get("status")!=200:
        raise ValueError("FinMind API status not success")
    rows=payload.get("data")
    if not isinstance(rows,list) or not rows:
        raise ValueError("FinMind returned empty or invalid rows")
    for row in rows:
        if row.get("stock_id")!="2330":
            raise ValueError("stock identifier mismatch")
        d=date.fromisoformat(row["date"])
        if d.year!=2024 or d.month!=1:
            raise ValueError("wrong historical month")
    return {"source":"FinMind","dataset":"TaiwanStockPrice","year":2024,"month":1,
            "rows":len(rows),"result":"STRUCTURE_DATE_PASS",
            "numeric_verified":False,"pit_verified":False,"drive_uploaded":False}

def main():
    query=urllib.parse.urlencode({"dataset":"TaiwanStockPrice","data_id":"2330",
          "start_date":"2024-01-01","end_date":"2024-01-31"})
    request=urllib.request.Request("https://api.finmindtrade.com/api/v4/data?"+query,
          headers={"User-Agent":"C1-RAW-DOWNLOADER-canary/0.93"})
    try:
        with urllib.request.urlopen(request,timeout=25) as response:
            raw=response.read(2000001)
            if len(raw)>2000000: raise ValueError("payload too large")
        report=validate(json.loads(raw))
        print(json.dumps(report))
    except Exception as exc:
        print(json.dumps({"result":"CANARY_FAIL","error_type":type(exc).__name__}))
        raise SystemExit(1) from None

if __name__=="__main__":
    main()
