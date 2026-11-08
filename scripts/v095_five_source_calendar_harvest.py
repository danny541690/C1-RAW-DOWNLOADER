#!/usr/bin/env python3
"""Five-source 2000-2026 official historical date and publication evidence.
Distinct evidence rules per source: no source may borrow TWSE holidays;
no source-date publication inferred from a present-day revised data series.
Writes native bytes, SHA and explicit rejected/unknown entries to a ZIP.
"""
import argparse,csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error,zipfile
from html.parser import HTMLParser
OUT=pathlib.Path("v095_five_source_calendar")
SOURCES=("TPEx","TAIFEX","MOPS","TDCC","NDC")
TZ=dt.timezone(dt.timedelta(hours=8))
YEARS=range(2000,2027)
def sha(x):return hashlib.sha256(x).hexdigest()
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json,text/html,*/*",
                                              "Referer":"https://www.tpex.org.tw/"})
    with urllib.request.urlopen(req,timeout=18) as r:
        raw=r.read(3_000_001)
        if len(raw)>3_000_000:raise ValueError("OFFICIAL_REPLY_SIZE_LIMIT")
        return raw,r.headers.get("Content-Type","")
def roc_date(value):
    m=re.fullmatch(r"(\d{2,4})[/.-](\d{1,2})[/.-](\d{1,2})",str(value).strip())
    if not m:return None
    y,mo,d=map(int,m.groups());y=y+1911 if y<1911 else y
    try:return dt.date(y,mo,d).isoformat()
    except ValueError:return None
def otc_stock(raw,year,month,stock):
    obj=json.loads(raw.decode("utf-8-sig"))
    if not isinstance(obj,dict) or str(obj.get("stat","")).lower()!="ok":raise ValueError("TPEX_SOURCE_STATUS_UNVERIFIED")
    request_date=f"{year:04d}{month:02d}01"
    if str(obj.get("date"))!=request_date:raise ValueError("TPEX_RESPONSE_MONTH_MISMATCH")
    tables=obj.get("tables",[])
    if not isinstance(tables,list) or len(tables)!=1:raise ValueError("TPEX_STOCK_TABLE_AMBIGUOUS")
    rows=tables[0].get("data",[])
    if not isinstance(rows,list):raise ValueError("TPEX_ROWS_INVALID")
    dates=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<5:raise ValueError("TPEX_ROW_STRUCTURE")
        day=roc_date(row[0])
        if not day or day[:7]!=f"{year:04d}-{month:02d}":raise ValueError("TPEX_HISTORICAL_DATE_WRONG_MONTH")
        dates.append(day)
    if len(dates)!=len(set(dates)):raise ValueError("TPEX_DUPLICATE_DATE")
    return sorted(dates)
class HtmlText(HTMLParser):
    def __init__(self):super().__init__();self.text=[]
    def handle_data(self,v):self.text.append(v)
def public_html_content(raw):
    html=raw.decode("utf-8","replace")
    parser=HtmlText();parser.feed(html)
    text=" ".join(parser.text)
    if len(text)<60:raise ValueError("NO_DOCUMENT_BODY")
    return text
def dated_evidence(source,raw,year,month,code):
    if source=="TPEx":return otc_stock(raw,year,month,code),"OFFICIAL_STOCK_QUOTE_DAILY_POSITIVE"
    if source=="MOPS":
        # Revenue public archives may be restated, or contain undated HTML.
        # Record bytes for manual schema/PIT verification, not a publication day.
        txt=public_html_content(raw)
        if "查無" in txt[:500] or "not found" in txt[:500].lower():raise ValueError("OFFICIAL_EMPTY_OR_ERROR_PAGE")
        return [],"ARCHIVED_MONTHLY_REPORT_BYTES_ONLY_PIT_UNVERIFIED"
    if source=="TDCC":
        # OpenAPI documentation gives route/capture metadata, not weekly vintages.
        if len(raw)<200:raise ValueError("SOURCE_METADATA_TOO_SMALL")
        return [],"OFFICIAL_OPENAPI_DOC_ONLY"
    if source=="TAIFEX":
        obj=json.loads(raw.decode("utf-8-sig"))
        if not isinstance(obj,dict) or not any(k in obj for k in ("paths","openapi","swagger")):
            raise ValueError("TAIFEX_API_SCHEMA_UNVERIFIED")
        return [],"OFFICIAL_API_SCHEMA_ONLY_NOT_HISTORY"
    if source=="NDC":
        if not zipfile.is_zipfile(io.BytesIO(raw)):raise ValueError("NDC_REVISED_ARCHIVE_NOT_ZIP")
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.testzip():raise ValueError("NDC_ZIP_CRC")
            if not z.namelist():raise ValueError("NDC_EMPTY_ARCHIVE")
        return [],"NDC_REVISED_SERIES_ARCHIVE_ONLY_NOT_ORIGINAL_RELEASE"
    raise ValueError("BAD_SOURCE")
def jobs(source):
    if source=="TPEx":
        for year in YEARS:
            for month in range(1,13):
                if (year,month)>(2026,11):continue
                for stock in ("5483","3105"):
                    q=urllib.parse.urlencode({"code":stock,"date":f"{year:04d}/{month:02d}/01","response":"json"})
                    yield (year,month,stock,"https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?"+q)
    elif source=="MOPS":
        for year in YEARS:
            for month in range(1,13):
                if (year,month)>(2026,11):continue
                for board in ("sii","otc"):
                    url=f"https://mopsov.twse.com.tw/nas/t21/{board}/t21sc03_{year-1911}_{month}_0.html"
                    yield year,month,board,url
    else:
        if source=="TAIFEX":url="https://openapi.taifex.com.tw/swagger.json"
        elif source=="TDCC":url="https://openapi.tdcc.com.tw/tdcc-opendata-api-docs"
        else:
            from scripts.v093_ndc_independent import ZIP_URL
            url=ZIP_URL
        yield (2026,11,"catalog",url)
def main(source,batch):
    if source not in SOURCES:raise ValueError("SOURCE_NOT_ALLOWED")
    OUT.mkdir(exist_ok=True)
    files=[];attempts=[];good=[];seen_days=set();seen_raw={}
    # A source's official market/publishing calendar is bounded to dated,
    # original evidence. FinMind and other sources cannot certify it.
    slots=list(jobs(source))
    for idx,(year,month,category,url) in enumerate(slots[:batch]):
        entry={"source":source,"year":year,"month":month,"category":category,
               "url":url,"state":"UNVERIFIED_NOT_MISSING","confirmed_days":0}
        try:
            raw,ctype=fetch(url);digest=sha(raw)
            if source in ("TAIFEX","TDCC","NDC") and url in seen_raw:
                pass
            else:
                days,label=dated_evidence(source,raw,year,month,category)
                entry.update(state=label,sha256=digest,bytes=len(raw),content_type=ctype,
                             confirmed_days=len(days))
                if label=="OFFICIAL_STOCK_QUOTE_DAILY_POSITIVE":
                    for day in days:
                        if day not in seen_days:
                            seen_days.add(day)
                            good.append({"date":day,"source":source,"state":"CONFIRMED_TRADING",
                                "evidence_uri":url,"source_sha256":digest,
                                "verified_at":dt.datetime.now(dt.timezone.utc).isoformat(),
                                "explanation":"TPEX_STOCK_SPECIFIC_POSITIVE_SESSION_NOT_MARKET_WIDE_COMPLETENESS"})
                if digest not in seen_raw:
                    seen_raw[digest]=True
                    files.append((f"{idx:04d}_{year}_{month:02d}_{category}_{digest[:16]}.native",raw))
        except Exception as e:
            entry["error"]=type(e).__name__+":"+str(e)[:140]
        attempts.append(entry)
        if len(attempts)%20==0:print(json.dumps({"source":source,"source_requests":len(attempts),
          "confirmed_positive_unique_days":len(good),"rejected_or_unknown":sum(x["state"]=="UNVERIFIED_NOT_MISSING" for x in attempts)},ensure_ascii=False),flush=True)
    stem=f"{source.lower()}_historical_evidence"
    zpath=OUT/(stem+".zip")
    with zipfile.ZipFile(zpath,"w",zipfile.ZIP_DEFLATED) as z:
        for name,b in files:z.writestr(name,b)
    p=OUT/(stem+".csv")
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["date","source","state","evidence_uri","source_sha256","verified_at","explanation"])
        w.writeheader();w.writerows(sorted(good,key=lambda x:x["date"]))
    report={"source":source,"run_id":os.environ.get("GITHUB_RUN_ID"),
        "sample_requests":len(attempts),"available_jobs":len(slots),
        "positive_dates_unique":len(good),
        "official_native_responses_preserved":len(files),
        "source_rows":attempts,"native_zip_sha256":sha(zpath.read_bytes()),
        "csv_sha256":sha(p.read_bytes()),"market_calendar_complete":False,
        "publication_history_complete":False,"PIT_certified":False,
        "unverified_not_absence":True}
    (OUT/(stem+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("source","sample_requests","available_jobs",
        "positive_dates_unique","official_native_responses_preserved","market_calendar_complete")},ensure_ascii=False),flush=True)
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--source",required=True,choices=SOURCES)
    ap.add_argument("--batch",type=int,default=54);a=ap.parse_args();main(a.source,a.batch)
