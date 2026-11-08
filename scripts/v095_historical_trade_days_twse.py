#!/usr/bin/env python3
"""Collect TWSE official *positive* historical trading-day evidence, 2000--2026.

Uses monthly official FMTQIK (daily market aggregate) without interpreting an
empty/error response as a non-trading day. Every positive date must occur in
the requested month and in a dated official native response. Records SHA,
retrieval UTC, URL, and validation. This is NOT a full historical holiday table.
"""
import argparse,calendar,csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error,zipfile
ROOT=pathlib.Path("v095_historical_days")
TZ=dt.timezone(dt.timedelta(hours=8))
URL="https://www.twse.com.tw/rwd/zh/exchangeReport/FMTQIK"
def sha(b):return hashlib.sha256(b).hexdigest()
def normalize_date(s):
    s=re.sub(r"<[^>]*>","",str(s)).strip()
    m=re.fullmatch(r"(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})",s)
    if not m:
        m=re.fullmatch(r"(\d{3})(\d{2})(\d{2})",s)
    if not m:return None
    year,mo,day=map(int,m.groups());year=year+1911 if year<1911 else year
    try:return dt.date(year,mo,day).isoformat()
    except ValueError:return None
def parse_native(raw,year,month):
    doc=json.loads(raw.decode("utf-8-sig"))
    if not isinstance(doc,dict):raise ValueError("NOT_OBJECT")
    if str(doc.get("stat","")).upper()!="OK":raise ValueError("OFFICIAL_STAT_NOT_OK:"+str(doc.get("stat"))[:90])
    fields=doc.get("fields")
    data=doc.get("data")
    if not isinstance(fields,list) or not any("日期" in str(x) for x in fields):
        raise ValueError("OFFICIAL_DATE_FIELD_MISSING")
    if not isinstance(data,list) or not data:raise ValueError("OFFICIAL_DATA_EMPTY")
    date_col=next(i for i,x in enumerate(fields) if "日期" in str(x))
    days=set()
    for row in data:
        if not isinstance(row,list) or len(row)!=len(fields):raise ValueError("NATIVE_FIELD_WIDTH")
        day=normalize_date(row[date_col])
        if not day or day[:7]!=f"{year:04d}-{month:02d}":
            raise ValueError("HISTORICAL_RESPONSE_MONTH_MISMATCH")
        if day in days:raise ValueError("NATIVE_DUPLICATE_DATE")
        if len([x for x in row if str(x).strip() not in ("","--","-")])<2:
            raise ValueError("NATIVE_ROW_NO_MARKET_VALUES")
        days.add(day)
    if len(days)>calendar.monthrange(year,month)[1]:
        raise ValueError("TOO_MANY_OFFICIAL_DATES")
    return sorted(days)
def request(url):
    last=None
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                "Referer":"https://www.twse.com.tw/","Accept-Encoding":"identity"})
            with urllib.request.urlopen(req,timeout=22) as r:
                if r.status!=200:raise ValueError("OFFICIAL_HTTP_NOT_200")
                blob=r.read(4_000_001)
                if len(blob)>4_000_000:raise ValueError("OFFICIAL_TOO_LARGE")
                return blob
        except (urllib.error.URLError,TimeoutError,OSError) as exc:
            last=exc
            if attempt<2:time.sleep(2*(attempt+1))
    raise RuntimeError("SOURCE_TRANSPORT_RETRIES_EXHAUSTED:"+str(last)[:100])
def run(year_start,year_end,months_limit=0):
    if not 2000<=year_start<=year_end<=2026:raise ValueError("BAD_YEAR_SHARD")
    ROOT.mkdir(exist_ok=True)
    all_days=[];receipts=[];month_count=0
    archive=zipfile.ZipFile(ROOT/f"twse_{year_start}_{year_end}_official_native.zip","w",zipfile.ZIP_DEFLATED)
    for year in range(year_start,year_end+1):
        for month in range(1,13):
            if (year,month)>(2026,11):continue
            if months_limit and month_count>=months_limit:break
            month_count+=1
            url=URL+"?"+urllib.parse.urlencode({"response":"json","date":f"{year:04d}{month:02d}01"})
            try:
                raw=request(url)
                dates=parse_native(raw,year,month)
                digest=sha(raw)
                archive.writestr(f"{year:04d}-{month:02d}_{digest[:18]}.json",raw)
                stamp=dt.datetime.now(dt.timezone.utc).isoformat()
                for day in dates:
                    all_days.append({"date":day,"source":"TWSE","state":"CONFIRMED_TRADING",
                     "evidence_uri":url,"source_sha256":digest,"verified_at":stamp,
                     "explanation":"TWSE_FMTQIK_MONTHLY_DAILY_MARKET_TABLE"})
                receipts.append({"month":f"{year:04d}-{month:02d}","status":"CONFIRMED_OFFICIAL_TRADING_DAYS",
                                 "records":len(dates),"sha256":digest,"url":url,"retrieved_at":stamp})
            except Exception as e:
                receipts.append({"month":f"{year:04d}-{month:02d}","status":"UNVERIFIED_NOT_ABSENCE",
                    "error":type(e).__name__+":"+str(e)[:170],"url":url})
            if len(receipts)%6==0:print(json.dumps({"processed_months":len(receipts),"positive_trading_days":len(all_days),
                "unverified_months":sum(x["status"]!="CONFIRMED_OFFICIAL_TRADING_DAYS" for x in receipts)},ensure_ascii=False),flush=True)
        if months_limit and month_count>=months_limit:break
    archive.close()
    p=ROOT/f"twse_{year_start}_{year_end}_confirmed.csv"
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=("date","source","state","evidence_uri","source_sha256","verified_at","explanation"));w.writeheader();w.writerows(all_days)
    report={"schema":"TWSE_HISTORICAL_DAILY_POSITIVE_EVIDENCE_V1","run_id":os.getenv("GITHUB_RUN_ID"),
        "year_start":year_start,"year_end":year_end,"months_checked":len(receipts),
        "months_with_positive_official_dates":sum(x["status"]=="CONFIRMED_OFFICIAL_TRADING_DAYS" for x in receipts),
        "months_unverified":sum(x["status"]!="CONFIRMED_OFFICIAL_TRADING_DAYS" for x in receipts),
        "confirmed_unique_dates":len(set(x["date"] for x in all_days)),
        "raw_response_sha_recorded":True,"raw_zip_sha256":sha((ROOT/f"twse_{year_start}_{year_end}_official_native.zip").read_bytes()),"no_inferred_holidays":True,"csv_sha256":sha(p.read_bytes()),
        "months":receipts,"complete_year_holiday_certification":False}
    (ROOT/f"twse_{year_start}_{year_end}_result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("year_start","year_end","months_checked","months_with_positive_official_dates","months_unverified","confirmed_unique_dates")},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("--start",type=int,required=True);a.add_argument("--end",type=int,required=True)
    a.add_argument("--max-months",type=int,default=0)
    x=a.parse_args();run(x.start,x.end,x.max_months)
