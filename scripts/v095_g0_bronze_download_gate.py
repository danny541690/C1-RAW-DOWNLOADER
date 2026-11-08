#!/usr/bin/env python3
"""G0 download eligibility policy for six sources, independent of G0 PIT release.

A positive market session permits a Bronze request. A historical weekday with
unknown status permits a verification probe, not a confirmed missing-data claim.
A confirmed no-trade date forbids cash-market OHLCV download. Source publication
datasets (MOPS, TDCC, NDC) have non-daily frequencies; never translate a weekday
into an expected publication. A dataset's historically unavailable period
never counts as missing. This is not a point-in-time certification.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib
from scripts.v095_market_release_calendar_2000_2026 import contracts
from scripts.v095_2026_cash_market_calendar import load_calendar
BASE=pathlib.Path("v095_market_release_calendar")
MARKETS=("TWSE","TPEx","TAIFEX")
SOURCES=MARKETS+("MOPS","TDCC","NDC")
NO_TRADE={"CONFIRMED_CLOSED","CONFIRMED_SETTLEMENT_ONLY"}
UNKNOWN={"WEEKDAY_UNVERIFIED","WEEKEND_ASSUMED_UNVERIFIED"}
def classification(source,date,market_state,has_native_date=False):
    if source in ("MOPS","TDCC","NDC"):
        return "PUBLICATION_FREQUENCY_CHECK_ONLY_NOT_DAILY_TRADING_EXPECTATION"
    if market_state in NO_TRADE:
        if has_native_date:raise ValueError("OFFICIAL_CLOSED_VS_NATIVE_DATE_CONFLICT")
        return "SKIP_VERIFIED_NO_TRADE"
    if market_state=="CONFIRMED_TRADING":
        if dt.date.fromisoformat(date)>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date():
            return "FUTURE_NOT_DUE"
        return "BRONZE_ELIGIBLE_WITH_SOURCE_VALIDATION"
    if market_state in UNKNOWN:
        if has_native_date:raise ValueError("POSITIVE_SOURCE_DATE_STILL_UNKNOWN")
        return "PROBE_SOURCE_ONLY_NOT_A_CONFIRMED_GAP"
    raise ValueError("UNKNOWN_MARKET_DATE_CLASSIFICATION")
def run():
    lookups=contracts()
    calendar,_,_=load_calendar()
    record_path=BASE/"market_dates_2000_2026.csv"
    report_path=BASE/"report.json"
    metadata=json.loads(report_path.read_text())
    digest=hashlib.sha256(record_path.read_bytes()).hexdigest()
    if digest!=metadata["calendar_csv_sha256"]:raise ValueError("G0_CALENDAR_REPORT_SHA_MISMATCH")
    summary=collections.defaultdict(collections.Counter)
    conflicts=[]
    rows=0
    with record_path.open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            source=row["source"];date=row["date"]
            if source not in SOURCES:raise ValueError("UNREGISTERED_MARKET_SOURCE")
            state=row["market_state"];rows+=1
            # 2026 cash market calendar must never drift from official primary CSV.
            if source in ("TWSE","TPEx") and date.startswith("2026-"):
                expected=calendar[date]["TWSE_CASH" if source=="TWSE" else "TPEx_CASH"]
                expected_state={"TRADING":"CONFIRMED_TRADING","WEEKEND":"CONFIRMED_CLOSED",
                  "HOLIDAY":"CONFIRMED_CLOSED","SETTLEMENT_ONLY":"CONFIRMED_SETTLEMENT_ONLY"}[expected]
                if state!=expected_state:raise ValueError("TWSE_TPEX_OFFICIAL_CASH_CALENDAR_CONFLICT_"+date)
            try:decision=classification(source,date,state)
            except ValueError as ex:
                conflicts.append({"source":source,"date":date,"error":str(ex)[:100]})
                continue
            summary[source][decision]+=1
    if rows!=9862*6 or conflicts:raise ValueError("G0_ELIGIBILITY_SOURCE_DATE_CONFLICT")
    tdcc=lookups[("TDCC","ownership_distribution")]
    if tdcc.get("earliest_official_date_verified")!="2008-07-01":
        raise ValueError("TDCC_EARLIEST_SOURCE_DATE_NOT_VERIFIED")
    for key,spec in lookups.items():
        if spec["PIT_available_at_verified"] is not False:
            raise ValueError("UNSUPPORTED_PIT_RELEASE_CLAIM_"+str(key))
    result={"schema":"V095_G0_BRONZE_DOWNLOAD_ELIGIBILITY_V1",
      "calendar_sha256":digest,"source_date_rows":rows,"status_by_source":{s:dict(summary[s]) for s in SOURCES},
      "confirmed_no_trade_excluded_from_bronze":sum(summary[s]["SKIP_VERIFIED_NO_TRADE"] for s in ("TWSE","TPEx")),
      "unknown_not_classified_as_missing":sum(summary[s]["PROBE_SOURCE_ONLY_NOT_A_CONFIRMED_GAP"] for s in MARKETS),
      "data_source_available_before_2008_tdcc_distribution":False,
      "cash_market_2026_calendar_crosscheck":"PASS","no_invalid_source_day_state":not conflicts,
      "bronze_collection_allowed":True,"final_coverage_certified":False,
      "PIT_release_certified":False,
      "rules":{"BRONZE_ELIGIBLE_WITH_SOURCE_VALIDATION":"Source may be requested; validate original bytes and market date",
      "PROBE_SOURCE_ONLY_NOT_A_CONFIRMED_GAP":"Request only to discover source, do not count absence as gap",
      "SKIP_VERIFIED_NO_TRADE":"Exclude this market day from daily cash downloads",
      "PUBLICATION_FREQUENCY_CHECK_ONLY_NOT_DAILY_TRADING_EXPECTATION":"Check per dataset frequency and source availability, not daily market sessions"}}
    output=BASE/"bronze_download_eligibility.json"
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"g0_bronze_download_gate":"PASS",
      "confirmed_no_trade_excluded":result["confirmed_no_trade_excluded_from_bronze"],
      "unknown_marked_as_confirmed_missing":0,
      "bronze_collection_allowed":True,"PIT_release_certified":False},ensure_ascii=False))
    return result
if __name__=="__main__":run()
