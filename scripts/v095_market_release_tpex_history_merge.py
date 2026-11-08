#!/usr/bin/env python3
"""G0 TPEx historical positive-date admission from native official single-stock files.

Uses archived raw ZIP and dated CSV with SHA-verified readback; stock-specific
positive evidence is NOT a proof that other sessions/holidays are absent.
No publication vintage, universal OTC coverage or release gate is granted.
"""
import collections,csv,datetime as dt,hashlib,io,json,pathlib,re,zipfile
from scripts.v095_market_release_calendar_drive_archive import drive,archive,OPS
from scripts.v095_five_source_calendar_harvest import otc_stock
ROOT=pathlib.Path("v095_market_release_calendar")
PREFIX="JARVIS_V095_G0_2000_2026_"
SHARDS=((2000,2004),(2005,2009),(2010,2014),(2015,2019),(2020,2023),(2024,2026))
def sha(b):return hashlib.sha256(b).hexdigest()
def find(d,name):
    q="'"+OPS+"' in parents and name contains '"+PREFIX+name+"_' and trashed=false"
    all=[];token=None
    while True:
        r=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=1000,pageToken=token).execute()
        if r.get("incompleteSearch"):raise ValueError("DRIVE_INCOMPLETE_SEARCH")
        all+=r.get("files",[]);token=r.get("nextPageToken")
        if not token:break
    chosen=[]
    for f in all:
        m=re.fullmatch(re.escape(PREFIX+name+"_")+r"([0-9a-f]{24})\.(zip|csv|json)",f["name"])
        if not m:continue
        raw=d.files().get_media(fileId=f["id"]).execute()
        if sha(raw)[:24]!=m[1]:raise ValueError("REMOTE_SHA_NOT_FILENAME")
        chosen.append((raw,sha(raw),f["id"]))
    if len(chosen)!=1:raise ValueError("SOURCE_ARCHIVE_UNIQUE_EXPECTED_"+name)
    return chosen[0]
def merge():
    s=drive();positive={};shards=[]
    for a,b in SHARDS:
        stem=f"tpex_{a}_{b}_historical_evidence"
        try:
            report,_,_=find(s,stem+".json")
            report=json.loads(report)
            rawzip,ziphash,_=find(s,stem+".zip")
            rawcsv,csvhash,_=find(s,stem+".csv")
        except ValueError as exc:
            shards.append({"years":f"{a}-{b}","state":"SOURCE_EVIDENCE_PENDING","error":str(exc)[:120]})
            continue
        if report["native_zip_sha256"]!=ziphash or report["csv_sha256"]!=csvhash:
            raise ValueError("SOURCE_REPORT_ZIP_CSV_SHA_CONFLICT")
        dated=list(csv.DictReader(rawcsv.decode("utf-8-sig").splitlines()))
        rebuilt=collections.defaultdict(list)
        with zipfile.ZipFile(io.BytesIO(rawzip)) as z:
            if z.testzip():raise ValueError("NATIVE_ZIP_CRC_FAIL")
            for entry in z.infolist():
                m=re.fullmatch(r"(\d{4})_(\d{4})_(\d{2})_(\d{4})_([a-f0-9]{16})\.native",entry.filename)
                if not m:raise ValueError("UNRECOGNIZED_SOURCE_MEMBER")
                year,month,code=int(m[2]),int(m[3]),m[4]
                bts=z.read(entry)
                if sha(bts)[:16]!=m[5]:raise ValueError("NATIVE_MEMBER_SHA_FAIL")
                url=next((x["url"] for x in report["source_rows"] if x["year"]==year and x["month"]==month
                    and x["category"]==code and x.get("sha256")==sha(bts)),None)
                if url is None:raise ValueError("SOURCE_PROVENANCE_URL_MISSING")
                for day in otc_stock(bts,year,month,code):
                    rebuilt[day].append((sha(bts),url))
        if {r["date"] for r in dated}!=set(rebuilt) or len(dated)!=len(rebuilt):
            raise ValueError("SOURCE_DATED_CSV_RAW_MISMATCH")
        for r in dated:
            day=r["date"]
            if (r["source"],r["state"])!=("TPEx","CONFIRMED_TRADING"):raise ValueError("SOURCE_MARKET_STATE_INVALID")
            if (r["source_sha256"],r["evidence_uri"]) not in rebuilt[day]:
                raise ValueError("SOURCE_DATE_PROVENANCE_NOT_REPRODUCIBLE")
            if day in positive:raise ValueError("OVERLAPPING_OTC_SHARD")
            positive[day]=r
        shards.append({"years":f"{a}-{b}","state":"RAW_CSV_AND_SHA_VERIFIED",
                       "months_sampled":len({(x["year"],x["month"]) for x in report["source_rows"]}),
                       "positive_days":len(dated)})
    p=ROOT/"market_dates_2000_2026.csv"
    with p.open(newline="",encoding="utf-8") as f:rows=list(csv.DictReader(f))
    changed=0
    for r in rows:
        if r["source"]!="TPEx" or r["date"] not in positive:continue
        if r["market_state"] not in ("CONFIRMED_TRADING","WEEKDAY_UNVERIFIED","WEEKEND_ASSUMED_UNVERIFIED"):
            raise ValueError("OTC_NATIVE_VS_G0_CASH_DATE_CONFLICT_"+r["date"])
        if r["market_state"]!="CONFIRMED_TRADING":
            r["market_state"]="CONFIRMED_TRADING"
            r["evidence_level"]="TPEX_OFFICIAL_STOCK_DAY_NATIVE_SHA_"+positive[r["date"]]["source_sha256"]
            r["potential_market_missing_eligible"]="1"
            changed+=1
    with p.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    reportfile=ROOT/"report.json";report=json.loads(reportfile.read_text())
    report.update(tpex_source_shard_admissions=shards,tpex_official_stock_positive_days=len(positive),
                  tpex_historical_market_dates_promoted=changed,
                  tpex_full_market_calendar_certified=False,
                  tpex_source_native_calendar_sha256=sha(p.read_bytes()))
    reportfile.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"tpex_positive_days":len(positive),"g0_new_tpex_dates":changed,
         "source_shards":shards,"complete_market_calendar":False},ensure_ascii=False))
if __name__=="__main__":merge()
