#!/usr/bin/env python3
"""Independently read back TAIFEX official annual ZIPs and promote positive futures sessions to G0.

The annual ZIP contains source-native ZIPs each validated with the official
schema parser. Period 2026 is not inferred from 2025. Absences are UNKNOWN.
"""
import csv,datetime as dt,hashlib,io,json,pathlib,re,zipfile
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
from scripts.v095_taifex_annual_market_dates import dates_from_zip
BASE=pathlib.Path("v095_market_release_calendar")
PREFIX="JARVIS_V095_G0_2000_2026_"
SHARDS=((2000,2004),(2005,2009),(2010,2014),(2015,2019),(2020,2025))
def sha(b):return hashlib.sha256(b).hexdigest()
def load(d,stem,ext):
    files=[];token=None
    match=PREFIX+stem+"_"
    q="'"+OPS+"' in parents and name contains '"+match+"' and trashed=false"
    while True:
        result=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=1000,pageToken=token).execute()
        if result.get("incompleteSearch"):raise ValueError("G0_TAIFEX_DRIVE_LIST_INCOMPLETE")
        files+=result.get("files",[]);token=result.get("nextPageToken")
        if not token:break
    selected=[]
    for f in files:
        m=re.fullmatch(re.escape(match)+r"([a-f0-9]{24})\."+re.escape(ext),f["name"])
        if m:
            b=d.files().get_media(fileId=f["id"]).execute()
            if sha(b)[:24]!=m[1]:raise ValueError("G0_TAIFEX_REMOTE_SHA_MISMATCH")
            selected.append((b,sha(b)))
    if len(selected)!=1:raise ValueError("MISSING_OR_DUPLICATE_TAIFEX_ARCHIVE")
    return selected[0]
def main():
    d=drive();all_dates={};statuses=[]
    for start,end in SHARDS:
        stem=f"taifex_{start}_{end}"
        try:
            report_raw,_=load(d,stem+"_result","json")
            r=json.loads(report_raw)
            dates_csv,hash_csv=load(d,stem+"_confirmed","csv")
            zip_raw,hash_zip=load(d,stem+"_annual_natives","zip")
        except ValueError as exc:
            statuses.append({"years":f"{start}-{end}","state":"NOT_YET_ARCHIVED","reason":str(exc)[:90]})
            continue
        if r["csv_sha256"]!=hash_csv or r["native_zip_sha256"]!=hash_zip:
            raise ValueError("TAIFEX_NATIVE_MANIFEST_SHA_MISMATCH")
        listed=list(csv.DictReader(dates_csv.decode("utf-8-sig").splitlines()))
        rebuilt={}
        with zipfile.ZipFile(io.BytesIO(zip_raw)) as z:
            if z.testzip():raise ValueError("TAIFEX_OUTER_NATIVE_ZIP_CRC")
            for member in z.infolist():
                m=re.fullmatch(r"(20\d{2})_([a-f0-9]{24})\.zip",member.filename)
                if not m:raise ValueError("TAIFEX_WRONG_NATIVE_MEMBER_NAME")
                year=int(m[1]);raw=z.read(member)
                if not start<=year<=end or sha(raw)[:24]!=m[2]:
                    raise ValueError("TAIFEX_NATIVE_YEAR_SHA_CONFLICT")
                days,_=dates_from_zip(raw,year)
                for day in days:
                    if day in rebuilt:raise ValueError("TAIFEX_YEAR_OVERLAP")
                    rebuilt[day]=sha(raw)
        if len(rebuilt)!=len(listed) or set(rebuilt)!={x["date"] for x in listed}:
            raise ValueError("TAIFEX_NATIVE_POSITIVE_DATES_VS_CSV")
        for x in listed:
            if x["source"]!="TAIFEX" or x["state"]!="CONFIRMED_TRADING" or x["source_sha256"]!=rebuilt[x["date"]]:
                raise ValueError("TAIFEX_NATIVE_DATE_LINEAGE_MISMATCH")
            if x["date"] in all_dates:raise ValueError("TAIFEX_SHARD_DUPLICATE")
            all_dates[x["date"]]=x
        statuses.append({"years":f"{start}-{end}","state":"OFFICIAL_ANNUAL_NATIVE_REVERIFIED",
                         "positive_dates":len(listed)})
    base=BASE/"market_dates_2000_2026.csv"
    with base.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    promoted=0
    for row in rows:
        if row["source"]!="TAIFEX" or row["date"] not in all_dates:continue
        if row["market_state"] not in ("WEEKDAY_UNVERIFIED","WEEKEND_ASSUMED_UNVERIFIED","CONFIRMED_TRADING"):
            raise ValueError("TAIFEX_G0_CONFLICT")
        if row["market_state"]!="CONFIRMED_TRADING":
            row.update(market_state="CONFIRMED_TRADING",
                       evidence_level="TAIFEX_ANNUAL_NATIVE_SHA_"+all_dates[row["date"]]["source_sha256"],
                       potential_market_missing_eligible="0")
            promoted+=1
    with base.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    p=BASE/"report.json";report=json.loads(p.read_text())
    report.update(taifex_historical_annual_archive_shards=statuses,
        taifex_official_positive_session_count=len(all_dates),taifex_new_G0_source_days=promoted,
        taifex_full_calendar_certified=False,taifex_2026_calendar_certified=False,
        calendar_csv_sha256=sha(base.read_bytes()))
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":"TAIFEX","positive_sessions":len(all_dates),"g0_dates_promoted":promoted,
       "shard_states":statuses,"full_market_calendar_certified":False},ensure_ascii=False))
if __name__=="__main__":main()
