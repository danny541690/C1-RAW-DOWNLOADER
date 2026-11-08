#!/usr/bin/env python3
"""Verify official TWSE 2000-2026 positive trading days from native Drive archives.

The 6 source-shards are discovered in Drive Operations, not trusted by filename.
Every positive date is recomputed from the original JSON response and matched
against the receipt CSV. For unverified months/dates, leave G0 UNKNOWN.
Never promote to OTC/TAIFEX market calendar and never infer closures from absence.
"""
import collections,csv,datetime as dt,hashlib,io,json,os,pathlib,re,zipfile
from scripts.v095_market_release_calendar_drive_archive import drive,OPS,archive
from scripts.v095_historical_trade_days_twse import parse_native
from scripts.v095_market_release_calendar_2000_2026 import ROOT,BASE,build
OUT=pathlib.Path("v095_market_release_calendar")
PREFIX="JARVIS_V095_G0_2000_2026_"
SHARDS=[(2000,2004),(2005,2009),(2010,2014),(2015,2019),(2020,2023),(2024,2026)]
def sha(b):return hashlib.sha256(b).hexdigest()
def all_files(s):
    token=None;rows=[]
    while True:
        x=s.files().list(q="'"+OPS+"' in parents and name contains '"+PREFIX+"twse_' and trashed=false",
          fields="nextPageToken,incompleteSearch,files(id,name,size)",pageSize=1000,pageToken=token).execute()
        if x.get("incompleteSearch"):raise RuntimeError("DRIVE_G0_SOURCE_LIST_INCOMPLETE")
        rows.extend(x.get("files",[]));token=x.get("nextPageToken")
        if not token:return rows
def load_verified(s,files,name,expected_digest=None):
    arr=[x for x in files if x["name"].startswith(PREFIX+name+"_")]
    if expected_digest:
        arr=[x for x in arr if x["name"].endswith("_"+expected_digest[:24]+pathlib.Path(name).suffix)]
    if len(arr)!=1:raise RuntimeError("UNIQUE_OFFICIAL_ARCHIVE_NOT_FOUND_"+name)
    raw=s.files().get_media(fileId=arr[0]["id"]).execute()
    stem,suffix=name.rsplit(".",1)
    if arr[0]["name"]!=PREFIX+stem+"_"+sha(raw)[:24]+"."+suffix:
        raise ValueError("ARCHIVED_SOURCE_FILENAME_SHA_MISMATCH")
    if expected_digest and sha(raw)!=expected_digest:raise ValueError("EXPECTED_NATIVE_SHA_MISMATCH")
    return raw
def best_version(s,files,start,end):
    prefix=f"twse_{start}_{end}"
    reports=[x for x in files if re.fullmatch(re.escape(PREFIX+prefix+"_result_")+r"[0-9a-f]{24}\\.json",x["name"])]
    valid=[]
    for f in reports:
        b=s.files().get_media(fileId=f["id"]).execute()
        if f["name"]!=PREFIX+prefix+"_result_"+sha(b)[:24]+".json":continue
        try:rec=json.loads(b)
        except ValueError:continue
        if rec.get("year_start")!=start or rec.get("year_end")!=end:continue
        valid.append(rec)
    if not valid:return None
    valid.sort(key=lambda x:(x.get("months_with_positive_official_dates",0),
                             x.get("confirmed_unique_dates",0)),reverse=True)
    if len(valid)>1 and (valid[0]["months_with_positive_official_dates"],valid[0]["confirmed_unique_dates"])==(
        valid[1]["months_with_positive_official_dates"],valid[1]["confirmed_unique_dates"]) and valid[0].get("csv_sha256")!=valid[1].get("csv_sha256"):
        raise ValueError("CONFLICTING_HISTORICAL_SOURCE_VERSION")
    return valid[0]
def verify_shard(s,files,start,end):
    r=best_version(s,files,start,end)
    if not r or r.get("confirmed_unique_dates",0)==0:return [],{"years":f"{start}-{end}","status":"NO_POSITIVE_SOURCE_EVIDENCE"}
    prefix=f"twse_{start}_{end}"
    csv_bytes=load_verified(s,files,prefix+"_confirmed.csv",r["csv_sha256"])
    zip_bytes=load_verified(s,files,prefix+"_official_native.zip",r["raw_zip_sha256"])
    reader=list(csv.DictReader(csv_bytes.decode("utf-8-sig").splitlines()))
    by_month=collections.defaultdict(list)
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        if z.testzip():raise ValueError("OFFICIAL_NATIVE_ZIP_CRC")
        for info in z.infolist():
            m=re.fullmatch(r"(\\d{4})-(\\d{2})_([0-9a-f]{18})\\.json",info.filename)
            if not m:raise ValueError("UNEXPECTED_OFFICIAL_SOURCE_MEMBER")
            year,month=int(m[1]),int(m[2]);raw=z.read(info)
            if sha(raw)[:18]!=m[3]:raise ValueError("SOURCE_MEMBER_SHA_IN_NAME_MISMATCH")
            by_month[f"{year:04d}-{month:02d}"] += [
                {"date":day,"source":"TWSE","state":"CONFIRMED_TRADING",
                 "source_sha256":sha(raw),"evidence_uri":
                   "https://www.twse.com.tw/exchangeReport/FMTQIK?response=json&date="+f"{year:04d}{month:02d}01"}
                for day in parse_native(raw,year,month)]
    expected={(x["date"],x["source"],x["state"],x["source_sha256"]) for arr in by_month.values() for x in arr}
    actual={(x["date"],x["source"],x["state"],x["source_sha256"]) for x in reader}
    if expected!=actual or len(expected)!=len(reader):
        raise ValueError("OFFICIAL_RAW_VS_DATED_CSV_MISMATCH")
    if r["confirmed_unique_dates"]!=len(reader):raise ValueError("RUN_RECEIPT_COUNT_MISMATCH")
    for x in reader:
        if not start<=int(x["date"][:4])<=end:raise ValueError("CROSS_SHARD_DATE")
    return reader,{"years":f"{start}-{end}","status":"VERIFIED_RAW_AND_CSV",
                   "months":len(by_month),"confirmed_trading_days":len(reader)}
def main():
    s=drive();files=all_files(s);all_rows=[];statuses=[]
    for start,end in SHARDS:
        rows,status=verify_shard(s,files,start,end)
        all_rows+=rows;statuses.append(status)
    if len({x["date"] for x in all_rows})!=len(all_rows):raise ValueError("OVERLAPPING_OFFICIAL_SHARD_DATES")
    base_path=OUT/"market_dates_2000_2026.csv"
    all_dates={}
    with base_path.open(newline="",encoding="utf-8") as f:
        rowlist=list(csv.DictReader(f))
    for item in all_rows:all_dates[item["date"]]=item
    adjusted=0
    for r in rowlist:
        if r["source"]!="TWSE":continue
        if r["date"] not in all_dates:continue
        # 2026 baseline remains independently verified; disagreement is fatal.
        if r["date"].startswith("2026-") and r["market_state"]!="CONFIRMED_TRADING":
            raise ValueError("OFFICIAL_2026_MARKET_CALENDAR_CONFLICT_"+r["date"])
        if r["market_state"] not in ("CONFIRMED_TRADING","WEEKDAY_UNVERIFIED","WEEKEND_ASSUMED_UNVERIFIED"):
            raise ValueError("HISTORICAL_G0_EVIDENCE_CONFLICT")
        if r["market_state"]!="CONFIRMED_TRADING":
            r["market_state"]="CONFIRMED_TRADING"
            r["evidence_level"]="OFFICIAL_FMTQIK_NATIVE_SHA_"+all_dates[r["date"]]["source_sha256"]
            r["potential_market_missing_eligible"]="1"
            adjusted+=1
    with base_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rowlist[0].keys());w.writeheader();w.writerows(rowlist)
    report_path=OUT/"report.json";report=json.loads(report_path.read_text())
    report["official_historical_trade_shards"]=statuses
    report["official_historical_raw_confirmed_days"]=len(all_rows)
    report["historical_cash_market_dates_promoted"]=adjusted
    report["calendar_csv_sha256"]=sha(base_path.read_bytes())
    report["market_calendar_source_positive_only"]=True
    report["historical_closures_fully_certified"]=False
    report["g0_coverage_denominator_certified"]=False
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\\n")
    result={"source":"TWSE","shards":statuses,
       "positive_days":len(all_rows),"historical_days_promoted":adjusted,
       "official_negative_days_inferred":0,"tpEx_dates_promoted":0}
    print(json.dumps(result,ensure_ascii=False),flush=True)
    return result
if __name__=="__main__":main()
