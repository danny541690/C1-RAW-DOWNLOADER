"""Single TWSE historical public API connectivity canary; never publishes raw payloads."""
import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone

def inspect_twse_stock_day(payload, year, month):
    if not isinstance(payload, dict):
        raise ValueError("invalid JSON root")
    stat = payload.get("stat")
    data = payload.get("data")
    if stat != "OK" or not isinstance(data, list) or not data:
        raise ValueError("TWSE response not valid nonempty stock-day data")
    dates = []
    for record in data:
        if not isinstance(record, list) or not record:
            raise ValueError("invalid source row")
        parts = str(record[0]).split("/")
        if len(parts) != 3:
            raise ValueError("unexpected ROC date")
        yyyy = int(parts[0])+1911
        mm = int(parts[1])
        if yyyy != year or mm != month:
            raise ValueError("unexpected historical period")
        dates.append(f"{yyyy:04d}-{mm:02d}-{int(parts[2]):02d}")
    return {"source":"TWSE","dataset":"STOCK_DAY","year":year,"month":month,
            "records":len(data),"first_date":min(dates),"last_date":max(dates),
            "result":"STRUCTURE_DATE_PASS","numeric_verified":False,"pit_verified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--year",type=int,default=2024)
    p.add_argument("--month",type=int,default=1)
    p.add_argument("--stock",default="2330")
    a=p.parse_args()
    if (a.year,a.month,a.stock)!=(2024,1,"2330"):
        raise SystemExit("Safety canary only supports 2330 in January 2024")
    url=f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={a.year}{a.month:02d}02&stockNo={a.stock}&response=json"
    request=urllib.request.Request(url,headers={"User-Agent":"C1-RAW-DOWNLOADER-public-canary/0.93","Accept":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=25) as resp:
            if resp.status != 200:
                raise ValueError(f"HTTP {resp.status}")
            if int(resp.headers.get("Content-Length","0")) > 2000000:
                raise ValueError("response too large")
            raw=resp.read(2000001)
            if len(raw)>2000000:
                raise ValueError("response exceeded cap")
        result=inspect_twse_stock_day(json.loads(raw.decode("utf-8-sig")),a.year,a.month)
        print(json.dumps(result,ensure_ascii=False))
    except (urllib.error.URLError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({"result":"CANARY_FAIL","exception_type":type(exc).__name__,
                          "numeric_verified":False,"pit_verified":False}))
        raise SystemExit(1) from None

if __name__=="__main__":
    main()
