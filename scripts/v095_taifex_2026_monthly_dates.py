#!/usr/bin/env python3
"""TAIFEX 2026 futures official monthly native CSV session evidence.
Positive dates are verified from actual rows; missing/empty monthly source
does not imply closure. Reuse v0.93 native CSV validator and preserve bytes.
"""
import csv,datetime as dt,hashlib,io,json,os,pathlib,urllib.parse,urllib.request,zipfile,calendar
from scripts.v093_taifex_independent import csv_evidence,native_text,parse_date
from scripts.v095_market_release_calendar_drive_archive import drive,archive
OUT=pathlib.Path("v095_taifex_2026_dates")
URL="https://www.taifex.com.tw/cht/3/futDataDown"
def sha(b):return hashlib.sha256(b).hexdigest()
def request(start,end):
    form={"down_type":"1","queryStartDate":start.strftime("%Y/%m/%d"),
        "queryEndDate":end.strftime("%Y/%m/%d"),"commodity_id":"all","commodity_id2":""}
    req=urllib.request.Request(URL,data=urllib.parse.urlencode(form).encode(),
        headers={"User-Agent":"Mozilla/5.0 JARVIS-TAIFEX-G0/0.95",
          "Content-Type":"application/x-www-form-urlencoded","Referer":"https://www.taifex.com.tw/cht/3/futDailyMarketView"})
    with urllib.request.urlopen(req,timeout=45) as r:
        raw=r.read(7_000_001)
        if len(raw)>7_000_000:raise ValueError("OFFICIAL_MONTH_BYTES_LIMIT")
        return raw
def positive_days(raw,start,end):
    ev=csv_evidence(raw,start,end)
    text=native_text(raw).rstrip(chr(26)+" \t\r\n")
    reader=csv.reader(io.StringIO(text));fields=next(reader,[])
    date_indexes=[i for i,x in enumerate(fields) if "日期" in x or "Date" in x or "date" in x]
    if not date_indexes:raise ValueError("SOURCE_DATE_HEADER_UNVERIFIED")
    observed=set()
    for row in reader:
        if not row or not any(x.strip() for x in row):continue
        for i in date_indexes:
            if i>=len(row):continue
            d=parse_date(row[i])
            if d and start<=d<=end:
                observed.add(d.isoformat());break
    if len(observed)<2:raise ValueError("MARKET_DATES_TOO_FEW")
    if min(observed)!=ev["content_period"]["min"] or max(observed)!=ev["content_period"]["max"]:
        raise ValueError("SOURCE_DATE_BOUNDARY_MISMATCH")
    return sorted(observed),ev
def main():
    OUT.mkdir(exist_ok=True)
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    if now.year!=2026:raise RuntimeError("2026_CALENDAR_FIXED_BATCH_ONLY")
    months=[];seen={};sourcezip=OUT/"taifex_2026_monthly_native.zip"
    with zipfile.ZipFile(sourcezip,"w",zipfile.ZIP_DEFLATED) as z:
        for month in range(1,now.month+1):
            start=dt.date(2026,month,1);end=min(now,dt.date(2026,month,calendar.monthrange(2026,month)[1]))
            row={"month":f"2026-{month:02d}","status":"UNVERIFIED_NOT_ABSENCE"}
            try:
                raw=request(start,end)
                days,ev=positive_days(raw,start,end);digest=sha(raw)
                z.writestr(f"{month:02d}_{digest[:24]}.csv",raw)
                for d in days:
                    if d in seen:raise ValueError("DUPLICATE_MONTHLY_DATE")
                    seen[d]=digest
                row.update(status="OFFICIAL_MONTHLY_NATIVE_VALIDATED",session_days=len(days),
                           source_sha256=digest,rows=ev["rows"])
            except Exception as exc:
                row["error"]=type(exc).__name__+":"+str(exc)[:130]
            months.append(row)
            print(json.dumps(row,ensure_ascii=False),flush=True)
    p=OUT/"taifex_2026_confirmed.csv"
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["date","source","state","source_sha256","evidence_uri"])
        for day,h in sorted(seen.items()):w.writerow([day,"TAIFEX","CONFIRMED_TRADING",h,URL])
    result={"source":"TAIFEX","year":2026,"months_checked":len(months),
        "months_positive_verified":sum(x["status"]=="OFFICIAL_MONTHLY_NATIVE_VALIDATED" for x in months),
        "confirmed_session_days":len(seen),"monthly_receipts":months,
        "native_zip_sha256":sha(sourcezip.read_bytes()),"dates_csv_sha256":sha(p.read_bytes()),
        "full_year":False,"PIT":False}
    q=OUT/"taifex_2026_receipt.json";q.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"verified_months":result["months_positive_verified"],
        "confirmed_2026_session_days":len(seen),"unverified_months":len(months)-result["months_positive_verified"]}))
    d=drive()
    for item in (p,q,sourcezip):archive(d,item)
if __name__=="__main__":main()
