#!/usr/bin/env python3
"""Attempt official TWSE historical annual open/close calendars for 2000-2026.
No inference from HTTP missing/error/current-year fallback. Preserve raw bytes,
query year, provenance and rejection reasons. Only explicit single-day closures
can become confirmed no-trade evidence after title/year and date verification.
"""
import argparse,csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,urllib.parse,urllib.request,urllib.error,zipfile
ROOT=pathlib.Path("v095_official_holidays")
API="https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule"
def sha(x):return hashlib.sha256(x).hexdigest()
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json","Referer":"https://www.twse.com.tw/"})
    with urllib.request.urlopen(req,timeout=20) as f:
        b=f.read(3_000_001)
        if len(b)>3_000_000:raise ValueError("RESPONSE_TOO_LARGE")
        return b
def native_year(raw,year):
    obj=json.loads(raw.decode("utf-8-sig"))
    if not isinstance(obj,dict) or str(obj.get("stat","")).upper()!="OK":
        raise ValueError("SOURCE_RESPONSE_NOT_OK")
    title=str(obj.get("title",""))
    roc=year-1911
    # Never accept an undated or wrong-year web response as a historical calendar.
    if not re.search(r"(?<!\d)(?:"+str(roc)+"|"+str(year)+r")\s*年",title):
        raise ValueError("ANNUAL_TITLE_YEAR_UNVERIFIED:"+title[:60])
    rows=obj.get("data")
    if not isinstance(rows,list) or len(rows)<5:raise ValueError("NO_ANNUAL_HOLIDAY_ROWS")
    evidence=[]
    for row in rows:
        if not isinstance(row,list) or len(row)<2:continue
        text=str(row[0]).strip()
        match=re.fullmatch(r"(?:(?:\d{2,4})[/-])?(\d{1,2})月(\d{1,2})日.*",text)
        if not match:
            match=re.match(r"^(\d{1,2})[/-](\d{1,2})(?:\s|$)",text)
        if not match:continue
        mm,dd=map(int,match.groups())
        try:day=dt.date(year,mm,dd).isoformat()
        except ValueError:continue
        desc=" ".join(str(v) for v in row[1:])
        if "無交易" in desc and ("交割" in desc or "結算" in desc):state="CONFIRMED_SETTLEMENT_ONLY"
        elif any(word in desc for word in ("放假","休市","紀念日","春節","假日","補假")) and not any(x in desc for x in ("開始交易","最後交易")):
            state="CONFIRMED_CLOSED"
        elif any(word in desc for word in ("開始交易","最後交易")):state="CONFIRMED_TRADING"
        else:continue
        evidence.append({"date":day,"source":"TWSE","state":state,"detail":desc[:100]})
    if not evidence:raise ValueError("NO_EXPLICIT_CLASSIFIED_YEAR_DATES")
    return evidence
def run(start,end):
    ROOT.mkdir(exist_ok=True)
    zip_path=ROOT/f"twse_{start}_{end}_annual_holiday_raw.zip"
    summaries=[];collected=[]
    with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
        for year in range(start,end+1):
            attempts=[]
            for form in (year-1911,year):
                url=API+"?"+urllib.parse.urlencode({"response":"json","queryYear":str(form)})
                try:
                    raw=get(url)
                    digest=sha(raw)
                    z.writestr(f"{year}_query_{form}_{digest[:18]}.json",raw)
                    events=native_year(raw,year)
                    collected += [{**r,"evidence_uri":url,"source_sha256":digest,
                      "verified_at":dt.datetime.now(dt.timezone.utc).isoformat(),"explanation":"TWSE_OFFICIAL_HOLIDAY_ANNUAL_DATE"} for r in events]
                    attempts.append({"year_form":form,"result":"VERIFIED_SINGLE_DATE_EVENTS","events":len(events),"sha256":digest})
                    break
                except Exception as e:
                    attempts.append({"year_form":form,"result":"UNVERIFIED_NOT_ABSENCE",
                      "error":type(e).__name__+":"+str(e)[:120]})
            summaries.append({"year":year,"attempts":attempts,
              "status":"PARTIAL_OFFICIAL_EVENTS" if any(x["result"]=="VERIFIED_SINGLE_DATE_EVENTS" for x in attempts) else "ANNUAL_OFFICIAL_CALENDAR_UNVERIFIED"})
            print(json.dumps({"year":year,"state":summaries[-1]["status"],"events":len(collected)},ensure_ascii=False),flush=True)
            time.sleep(0.2)
    csv_path=ROOT/f"twse_{start}_{end}_annual_events.csv"
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=("date","source","state","detail","evidence_uri","source_sha256","verified_at","explanation"))
        w.writeheader();w.writerows(collected)
    result={"year_start":start,"year_end":end,"years_checked":len(summaries),
      "years_with_verified_event_rows":sum(x["status"]=="PARTIAL_OFFICIAL_EVENTS" for x in summaries),
      "total_verified_single_date_events":len(collected),"annual_closure_complete":False,
      "archive_sha256":sha(zip_path.read_bytes()),"events_csv_sha256":sha(csv_path.read_bytes()),
      "years":summaries}
    (ROOT/f"twse_{start}_{end}_annual_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--start",required=True,type=int);p.add_argument("--end",required=True,type=int)
    a=p.parse_args();print(json.dumps(run(a.start,a.end),ensure_ascii=False))
