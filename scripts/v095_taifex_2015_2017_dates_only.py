#!/usr/bin/env python3
"""TAIFEX 2015-17 date-only reconciliation of malformed-width annual CSV records.

A row with fewer numeric columns can still carry a legitimate trading date,
but must NOT pass numeric / full Bronze validation. Require source-native ZIP
CRC, dated header, well-formed dates, plausible sessions, and SHA readback.
"""
import argparse,csv,datetime as dt,hashlib,io,json,pathlib,re,zipfile
from scripts.v095_taifex_annual_market_dates import post_year
from scripts.v093_taifex_independent import parse_date,native_text
from scripts.v095_market_release_calendar_drive_archive import archive,drive
OUT=pathlib.Path("v095_taifex_2015_2017_date_only")
def sha(b):return hashlib.sha256(b).hexdigest()
def read_positive(raw,year):
    sessions=set();problems=[];row_count=0;short=0;members=0
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.testzip():raise ValueError("ANNUAL_ZIP_CRC_FAILED")
        for m in z.infolist():
            if m.is_dir():continue
            if not m.filename.lower().endswith(".csv"):raise ValueError("UNEXPECTED_ZIP_MEMBER")
            members+=1
            if m.file_size>100_000_000:raise ValueError("CSV_MEMBER_SIZE_LIMIT")
            text=native_text(z.read(m)).rstrip(chr(26)+" \t\r\n")
            reader=csv.reader(io.StringIO(text));header=next(reader,[])
            datecols=[i for i,x in enumerate(header) if x.strip() in ("日期","交易日期","Date","date")]
            if not datecols:raise ValueError("SOURCE_DATE_HEADER_NOT_VERIFIED")
            col=datecols[0]
            for row in reader:
                if not any(x.strip() for x in row):continue
                row_count+=1
                if len(row)<len(header)-int(bool(header) and not header[-1].strip()):
                    short+=1
                if len(row)<=col:
                    problems.append("TRUNCATED_DATE_COLUMN");continue
                day=parse_date(row[col])
                if day is None or day.year!=year:
                    problems.append("BAD_SOURCE_TRADING_DATE");continue
                sessions.add(day.isoformat())
    if problems or len(sessions)<200 or len(sessions)>260 or not members:
        raise ValueError("DATE_ONLY_PROOF_UNSAFE:"+str({"sessions":len(sessions),"bad_dates":len(problems)})[:100])
    return sorted(sessions),{"parsed_rows":row_count,"short_numeric_rows":short,
      "source_member_count":members,"numeric_schema_certified":False,
      "date_only_certified":True}
def main(year):
    if year not in (2015,2016,2017):raise ValueError("YEAR_OUT_OF_TARGET")
    OUT.mkdir(exist_ok=True)
    raw=post_year(year);h=sha(raw)
    positives,stats=read_positive(raw,year)
    source=OUT/f"taifex_{year}_native_annual.zip";source.write_bytes(raw)
    p=OUT/f"taifex_{year}_dates_only.csv"
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.writer(f);w.writerow(["date","source","state","sha256","date_evidence"])
        for date in positives:w.writerow([date,"TAIFEX","CONFIRMED_TRADING",h,"OFFICIAL_NATIVE_ANNUAL_CSV_DATE_ONLY"])
    receipt={"year":year,"positive_sessions":len(positives),"sha256":h,
      "date_only_verified":True,"original_numeric_bronze_schema_pass":False,
      "PIT_verified":False,**stats}
    report=OUT/f"taifex_{year}_date_receipt.json"
    report.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    service=drive()
    for item in (source,p,report):archive(service,item)
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True);a=p.parse_args();main(a.year)
