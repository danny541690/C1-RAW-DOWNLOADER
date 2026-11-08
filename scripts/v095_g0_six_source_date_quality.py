#!/usr/bin/env python3
"""Six official source G0 date audit using persisted, SHA-verified evidence.

This is a factual date inventory, not a PIT/release certificate. Treat MOPS
report months, NDC observation months, and TDCC weekly official series as
distinct concepts (never synthesize publication timestamps).
"""
import collections,csv,datetime as dt,hashlib,json,pathlib
from scripts.v095_market_release_calendar_drive_archive import drive
from scripts.v095_market_release_taifex_history_merge import load as read_sha_archived
from scripts.v095_mops_historical_missing_month_repair import get_report
from scripts.v095_market_release_calendar_2000_2026 import contracts
ROOT=pathlib.Path("v095_market_release_calendar")
SHARDS=((2000,2004),(2005,2009),(2010,2014),(2015,2019),(2020,2023),(2024,2026))
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
    d=drive()
    g0=json.loads((ROOT/"report.json").read_text())
    datefile=ROOT/"market_dates_2000_2026.csv"
    if sha(datefile.read_bytes())!=g0["calendar_csv_sha256"]:raise ValueError("G0_DATE_SHA_RECEIPT_MISMATCH")
    counts=collections.Counter()
    with datefile.open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[(row["source"],row["market_state"])]+=1
    mops=[];missing=[];verified_total=0;expected_total=0
    for a,b in SHARDS:
        base=get_report(d,a,b)
        name=f"mops_{a}_{b}_repair_receipt"
        raw,h=read_sha_archived(d,name,"json")
        repair=json.loads(raw)
        attempted=len(base["source_rows"]);passed=repair["prior_verified"]+repair["new_verified"]
        unresolved=repair["still_unverified"]
        if passed+unresolved!=attempted:raise ValueError("MOPS_REPAIR_LEDGER_INCONSISTENT")
        verified_total+=passed;expected_total+=attempted
        mops.append({"years":f"{a}-{b}","candidate_month_board_cells":attempted,
            "source_month_reports_proven":passed,
            "official_source_unverified":unresolved,
            "initial_report_sha":base["csv_sha256"],
            "source_date_not_publication_timestamp":True})
        missing.extend({"year":x["year"],"month":x["month"],"board":x["board"],
            "state":"UNKNOWN_SOURCE_AVAILABILITY_NOT_MISSING"} for x in repair["unverified"])
    ndc_manifest_raw,ndc_hash=read_sha_archived(d,"ndc_monthly_manifest","json")
    ndc=json.loads(ndc_manifest_raw)
    ndc_csv,ndc_csv_sha=read_sha_archived(d,"ndc_observation_months","csv")
    if ndc["csv_sha256"]!=ndc_csv_sha:raise ValueError("NDC_SOURCE_DATES_SHA_MISMATCH")
    rows=list(csv.DictReader(ndc_csv.decode("utf-8-sig").splitlines()))
    if ndc["month_rows"]!=len(rows) or len({x["month"] for x in rows})!=len(rows):
        raise ValueError("NDC_HISTORICAL_OBSERVATION_MONTHS_INCONSISTENT")
    allcontracts=contracts()
    tdcc=allcontracts[("TDCC","ownership_distribution")]
    report={"schema":"JARVIS_V095_G0_SIX_SOURCE_DATE_QUALITY_V1",
      "as_of_run_date":"2026-11-08",
      "source_trade_session_counts":{s:counts[(s,"CONFIRMED_TRADING")] for s in ("TWSE","TPEx","TAIFEX")},
      "source_trade_calendar_full_certified":False,
      "MOPS":{"monthly_board_cells_proven":verified_total,"candidate_cells_queried":expected_total,
              "source_month_cells_unverified":expected_total-verified_total,
              "original_disclosure_timestamps_verified":False,
              "shards":mops,"unverified_cells":missing},
      "TDCC":{"earliest_official_archive_month":tdcc["earliest_official_date_verified"][:7],
              "official_current_history_retention":tdcc["historical_query_retention"],
              "complete_weekly_date_evidence":False,
              "pre_source_start_should_be_marked_missing":False},
      "NDC":{"observation_months_verified":len(rows),
             "first_month":rows[0]["month"],"last_month":rows[-1]["month"],
             "revised_indicator_series":ndc["native_indicator_series"],
             "original_publication_date_verified":False},
      "all_six_sources_pit_and_market_release_complete":False,
      "full_source_coverage_denominator_certified":False,
      "sha256_of_underlying_g0_table":sha(datefile.read_bytes()),
      "rule":"A SOURCE'S ABSENCE, HOLIDAY, OBSERVATION, FILING DEADLINE AND REAL DISCLOSURE TIME ARE DISTINCT"}
    out=ROOT/"six_source_date_quality.json"
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"market_positive_days":report["source_trade_session_counts"],
      "MOPS_source_month_boards_verified":verified_total,
      "MOPS_unverified_cells":expected_total-verified_total,
      "NDC_observation_months_verified":len(rows),
      "TDCC_historical_publication_day_complete":False,
      "six_source_complete":False},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
