#!/usr/bin/env python3
"""Admit TAIFEX 2015-2017 date-only and 2026 month-native positive sessions.

Verify original source bytes, receipt CSV and G0 source-specific row provenance.
This only certifies existence of sessions, not malformed numeric rows or PIT.
"""
import csv,hashlib,io,json,pathlib,re,zipfile,datetime as dt
from scripts.v095_market_release_calendar_drive_archive import drive
from scripts.v095_market_release_taifex_history_merge import load as archived
from scripts.v095_taifex_2015_2017_dates_only import read_positive
from scripts.v095_taifex_2026_monthly_dates import positive_days
ROOT=pathlib.Path("v095_market_release_calendar")
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    d=drive();dates={};receipts=[]
    for year in (2015,2016,2017):
        prefix=f"taifex_{year}"
        raw,source_sha=archived(d,prefix+"_native_annual","zip")
        csvraw,csv_sha=archived(d,prefix+"_dates_only","csv")
        receipt_raw,_=archived(d,prefix+"_date_receipt","json")
        receipt=json.loads(receipt_raw)
        if source_sha!=receipt["sha256"] or not receipt["date_only_verified"]:
            raise ValueError("TAIFEX_YEAR_DATE_SOURCE_RECEIPT_SHA_MISMATCH")
        rebuilt,diagnostics=read_positive(raw,year)
        present=list(csv.DictReader(csvraw.decode("utf-8-sig").splitlines()))
        if set(rebuilt)!={x["date"] for x in present} or len(rebuilt)!=len(present):
            raise ValueError("TAIFEX_DATE_ONLY_NATIVE_VS_CSV")
        for row in present:
            if row["source"]!="TAIFEX" or row["sha256"]!=source_sha:
                raise ValueError("TAIFEX_DATE_ONLY_PROVENANCE_MISMATCH")
            dates[row["date"]]=source_sha
        receipts.append({"year":year,"positive_sessions":len(rebuilt),"original_numeric_schema_pass":False})
    rawzip,zipsha=archived(d,"taifex_2026_monthly_native","zip")
    csvraw,csvsha=archived(d,"taifex_2026_confirmed","csv")
    receipt_raw,_=archived(d,"taifex_2026_receipt","json")
    receipt=json.loads(receipt_raw)
    if zipsha!=receipt["native_zip_sha256"] or csvsha!=receipt["dates_csv_sha256"]:
        raise ValueError("TAIFEX_2026_SOURCE_SHA_MISMATCH")
    discovered={}
    with zipfile.ZipFile(io.BytesIO(rawzip)) as z:
        if z.testzip():raise ValueError("TAIFEX_2026_ZIP_CRC_FAIL")
        for info in z.infolist():
            m=re.fullmatch(r"(\d{2})_([a-f0-9]{24})\.csv",info.filename)
            if not m:raise ValueError("TAIFEX_MONTH_MEMBER_FORMAT")
            month=int(m[1])
            b=z.read(info);h=sha(b)
            if h[:24]!=m[2]:raise ValueError("TAIFEX_2026_MONTH_SOURCE_SHA")
            import calendar
            d1=dt.date(2026,month,1);d2=min(dt.date(2026,11,8),dt.date(2026,month,calendar.monthrange(2026,month)[1]))
            days,_=positive_days(b,d1,d2)
            for day in days:
                if day in discovered:raise ValueError("TAIFEX_2026_MONTH_OVERLAP")
                discovered[day]=h
    rows=list(csv.DictReader(csvraw.decode("utf-8-sig").splitlines()))
    if len(rows)!=len(discovered) or set(discovered)!={r["date"] for r in rows}:
        raise ValueError("TAIFEX_2026_DATED_CSV_MISMATCH")
    for row in rows:
        if row["source"]!="TAIFEX" or row["source_sha256"]!=discovered[row["date"]]:
            raise ValueError("TAIFEX_2026_MONTH_RAW_PROVENANCE")
        dates[row["date"]]=row["source_sha256"]
    p=ROOT/"market_dates_2000_2026.csv"
    with p.open(newline="",encoding="utf-8") as f:allrows=list(csv.DictReader(f))
    promoted=0
    for row in allrows:
        day=row["date"]
        if row["source"]!="TAIFEX" or day not in dates:continue
        if row["market_state"] not in ("WEEKDAY_UNVERIFIED","WEEKEND_ASSUMED_UNVERIFIED","CONFIRMED_TRADING"):
            raise ValueError("TAIFEX_MONTHLY_G0_STATE_CONFLICT")
        if row["market_state"]!="CONFIRMED_TRADING":
            row["market_state"]="CONFIRMED_TRADING"
            row["evidence_level"]="TAIFEX_DATE_ONLY_OR_2026_NATIVE_SHA_"+dates[day]
            row["potential_market_missing_eligible"]="0"
            promoted+=1
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=allrows[0].keys());w.writeheader();w.writerows(allrows)
    rp=ROOT/"report.json";report=json.loads(rp.read_text())
    report.update(taifex_date_only_recovered_2015_2017=receipts,
                  taifex_2026_official_monthly_positive_days=len(discovered),
                  taifex_last_g0_new_dates=promoted,
                  taifex_annual_numeric_schema_complete=False,
                  taifex_historical_announcement_timestamps_verified=False,
                  calendar_csv_sha256=sha(p.read_bytes()))
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"2015_2017_date_only_days":sum(x["positive_sessions"] for x in receipts),
        "2026_positive_days":len(discovered),"g0_newly_verified":promoted,
        "numeric_schema_certified":False,"PIT":False},ensure_ascii=False))
if __name__=="__main__":main()
