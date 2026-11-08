#!/usr/bin/env python3
"""Inventory NDC official monthly observation dates 2000-2026 from native ZIP.
Monthly observation date is NOT the initial release/publication date; vintages
remain unverified and any absent series start is not a false missing value.
"""
import csv,datetime as dt,hashlib,json,os,pathlib,urllib.request
from scripts.v093_ndc_independent import ZIP_URL,parse_bundle,availability
OUT=pathlib.Path("v095_ndc_historical_publication")
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    OUT.mkdir(exist_ok=True)
    req=urllib.request.Request(ZIP_URL,headers={"User-Agent":"Mozilla/5.0 JARVIS-G0-NDC/0.95"})
    with urllib.request.urlopen(req,timeout=32) as r:raw=r.read(40_000_001)
    if len(raw)>40_000_000:raise ValueError("NDC_NATIVE_ARCHIVE_OVER_40MB")
    tables=parse_bundle(raw)
    summary=availability(tables)
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    upper=f"{today.year:04d}-{today.month:02d}"
    dates=sorted({day for t in tables for day in t["rows"] if "2000-01"<=day<=upper})
    if not dates:raise ValueError("NDC_NO_OFFICIAL_MONTHS_IN_SCOPE")
    native=OUT/"ndc_current_revised_source.zip";native.write_bytes(raw)
    p=OUT/"ndc_observation_months.csv"
    with p.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f);w.writerow(["month","source","state","source_sha256","source_url","pit_verified"])
        for date in dates:w.writerow([date,"NDC","REVISED_OBSERVATION_MONTH_CONFIRMED_NOT_PUBLISHED_AT",sha(raw),ZIP_URL,False])
    manifest={"source":"NDC","source_sha256":sha(raw),"source_url":ZIP_URL,
      "monthly_observation_first":dates[0],"monthly_observation_last":dates[-1],
      "month_rows":len(dates),"native_indicator_series":len(summary["series"]),
      "observations_current_revised_vintage":True,"initial_release_day_verified":False,
      "market_holiday_calendar_not_applicable":True,"PIT_approved":False,
      "native_zip_sha256":sha(native.read_bytes()),"csv_sha256":sha(p.read_bytes())}
    (OUT/"ndc_monthly_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:manifest[k] for k in ("monthly_observation_first","monthly_observation_last",
      "month_rows","native_indicator_series","initial_release_day_verified")},ensure_ascii=False))
if __name__=="__main__":main()
