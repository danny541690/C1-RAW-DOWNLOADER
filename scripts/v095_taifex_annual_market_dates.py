#!/usr/bin/env python3
"""Acquire official TAIFEX 2000-2025 annual futures ZIP market dates.

Original ZIP is validated with existing v0.93 native parser; a dated row is a
positive session only. 2026 current-year monthly files require separate intake.
No stock-market holiday copying or fake gaps from failed source responses.
"""
import argparse,csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,urllib.parse,urllib.request,zipfile
from scripts.v093_taifex_independent import validate,parse_date,native_text
OUT=pathlib.Path("v095_taifex_historical_sessions")
URL="https://www.taifex.com.tw/cht/3/futDataDown"
def sha(b):return hashlib.sha256(b).hexdigest()
def post_year(year):
    body=urllib.parse.urlencode({"down_type":"2","his_year":str(year)}).encode()
    req=urllib.request.Request(URL,data=body,headers={"User-Agent":"Mozilla/5.0 JARVIS-CALENDAR/0.95",
        "Content-Type":"application/x-www-form-urlencoded","Accept":"*/*",
        "Referer":"https://www.taifex.com.tw/cht/3/dlFutDailyMarketView"})
    with urllib.request.urlopen(req,timeout=45) as res:
        raw=res.read(85_000_001)
        if len(raw)>85_000_000:raise ValueError("TAIFEX_ANNUAL_ZIP_TOO_LARGE")
        return raw
def dates_from_zip(raw,year):
    job={"kind":"annual","start":f"{year}-01-01","end":f"{year}-12-31"}
    ev=validate(raw,job)
    sessions=set()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.testzip():raise ValueError("ANNUAL_ZIP_CRC")
        for info in z.infolist():
            if info.is_dir():continue
            text=native_text(z.read(info)).rstrip(chr(26)+" \t\r\n")
            reader=csv.reader(io.StringIO(text))
            columns=next(reader,[])
            indices=[i for i,x in enumerate(columns) if "日期" in x or "Date" in x or "date" in x]
            if not indices:raise ValueError("OFFICIAL_ANNUAL_DATE_HEADER_ABSENT")
            for row in reader:
                if not any(x.strip() for x in row):continue
                hits=[]
                for i in indices:
                    if i<len(row):
                        d=parse_date(row[i])
                        if d and d.year==year:hits.append(d.isoformat())
                if hits:sessions.add(hits[0])
    if len(sessions)<50:raise ValueError("ANNUAL_FUTURES_DATE_COVERAGE_SUSPICIOUS")
    return sorted(sessions),ev
def run(start,end):
    OUT.mkdir(exist_ok=True)
    records=[];dates=[];native=OUT/f"taifex_{start}_{end}_annual_natives.zip"
    with zipfile.ZipFile(native,"w",zipfile.ZIP_DEFLATED) as package:
        for year in range(start,end+1):
            if year>=2026:continue
            receipt={"year":year,"source":"TAIFEX","state":"UNVERIFIED_NOT_ABSENCE"}
            try:
                blob=post_year(year)
                session,ev=dates_from_zip(blob,year)
                digest=sha(blob)
                package.writestr(f"{year}_{digest[:24]}.zip",blob)
                for d in session:dates.append({"date":d,"source":"TAIFEX","state":"CONFIRMED_TRADING",
                     "evidence_uri":URL,"source_sha256":digest,
                     "verified_at":dt.datetime.now(dt.timezone.utc).isoformat(),
                     "explanation":"TAIFEX_FUTURES_OFFICIAL_ANNUAL_ZIP_POSITIVE_DATE"})
                receipt.update(state="CONFIRMED_ANNUAL_NATIVE_ZIP",days=len(session),
                    sha256=digest,rows=ev.get("rows"),max=ev.get("content_period",{}).get("max"))
            except Exception as e:
                receipt["error"]=type(e).__name__+":"+str(e)[:180]
            records.append(receipt)
            print(json.dumps({"year":year,"state":receipt["state"],"days":receipt.get("days",0),"error":receipt.get("error")},ensure_ascii=False),flush=True)
    if len({x["date"] for x in dates})!=len(dates):raise ValueError("ANNUAL_DATE_OVERLAP")
    p=OUT/f"taifex_{start}_{end}_confirmed.csv"
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["date","source","state","evidence_uri","source_sha256","verified_at","explanation"])
        w.writeheader();w.writerows(dates)
    result={"source":"TAIFEX","year_start":start,"year_end":end,
      "confirmed_years":sum(x["state"]=="CONFIRMED_ANNUAL_NATIVE_ZIP" for x in records),
      "years_checked":len(records),"confirmed_dates":len(dates),"year_receipts":records,
      "native_zip_sha256":sha(native.read_bytes()),"csv_sha256":sha(p.read_bytes()),
      "historical_calendar_complete":False,"2026_session_calendar_complete":False,"PIT":False}
    (OUT/f"taifex_{start}_{end}_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("year_start","year_end","years_checked","confirmed_years","confirmed_dates")},ensure_ascii=False))
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--start",type=int,required=True);parser.add_argument("--end",type=int,required=True)
    a=parser.parse_args();run(a.start,a.end)
