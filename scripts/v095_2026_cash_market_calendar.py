"""2026 TSE/OTC cash-market reference calendar with fail-closed source evidence.

Used by Bronze inventory *before* a request. Weekends, confirmed no-trade days,
and special settlement-only dates are not missing source data. Other sources
(TAIFEX, TDCC, MOPS, NDC) must use their own publication/market calendars.
Historical 2000-2025 years are intentionally not inferred from weekends.
"""
import csv, datetime as dt, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
PATH=ROOT/"governance/v095/CASH_MARKET_CALENDAR_2026.csv"
SOURCE_TWSE="https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=html"
SOURCE_TPEX="https://www.tpex.org.tw/storage/eb_data/11411/114007545811-1.pdf"
CASH_SOURCES=("TWSE","TPEx")
NO_TRADE={"WEEKEND","HOLIDAY","SETTLEMENT_ONLY"}
VALID=NO_TRADE|{"TRADING"}

def load_calendar():
    data=PATH.read_bytes()
    rows=list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
    if len(rows)!=365:raise ValueError("CASH_CALENDAR_EXPECTED_365_DAYS")
    dates=[(dt.date(2026,1,1)+dt.timedelta(days=n)).isoformat() for n in range(365)]
    if [x["date"] for x in rows]!=dates:raise ValueError("CASH_CALENDAR_GAP_OR_DUPLICATE")
    for row in rows:
        date=dt.date.fromisoformat(row["date"])
        for field in ("TWSE_CASH","TPEx_CASH"):
            state=row[field]
            if state not in VALID:raise ValueError("UNRECOGNIZED_CASH_DAY_STATE")
            if date.weekday()>=5 and state!="WEEKEND":raise ValueError("WEEKEND_CALENDAR_CONFLICT")
            if date.weekday()<5 and state=="WEEKEND":raise ValueError("WEEKDAY_CALENDAR_CONFLICT")
        if row["TWSE_CASH"]!=row["TPEx_CASH"]:raise ValueError("TSE_OTC_CASH_CALENDAR_DIFFERENCE_REQUIRES_REVIEW")
    # Independent evidence sanity checks; do not simply trust accidental CSV edits.
    controls={"2026-01-01":"HOLIDAY","2026-01-02":"TRADING",
              "2026-02-11":"TRADING","2026-02-12":"SETTLEMENT_ONLY",
              "2026-02-13":"SETTLEMENT_ONLY","2026-02-20":"HOLIDAY",
              "2026-02-23":"TRADING","2026-10-26":"HOLIDAY",
              "2026-12-25":"HOLIDAY"}
    lookup={row["date"]:row for row in rows}
    for day,state in controls.items():
        if lookup[day]["TWSE_CASH"]!=state:raise ValueError("OFFICIAL_CALENDAR_CONTROL_FAILED_"+day)
    count={s:sum(x["TWSE_CASH"]==s for x in rows) for s in VALID}
    if count!={"TRADING":243,"HOLIDAY":16,"SETTLEMENT_ONLY":2,"WEEKEND":104}:
        raise ValueError("CASH_CALENDAR_STATE_COUNTS_CHANGED_REVIEW_REQUIRED")
    return lookup,hashlib.sha256(data).hexdigest(),count

_CACHE=None
def status(day,source):
    global _CACHE
    if source not in CASH_SOURCES:raise ValueError("SOURCE_HAS_DISTINCT_PUBLICATION_CALENDAR")
    if not day.startswith("2026-"):raise ValueError("CASH_CALENDAR_YEAR_NOT_CERTIFIED")
    if _CACHE is None:_CACHE=load_calendar()
    row=_CACHE[0].get(day)
    if row is None:raise ValueError("DATE_NOT_IN_OFFICIAL_CALENDAR")
    return row["TWSE_CASH" if source=="TWSE" else "TPEx_CASH"]

def is_verified_closed(day,source):
    return status(day,source) in NO_TRADE

def require_trade_date(day,source):
    value=status(day,source)
    if value!="TRADING":raise ValueError("OFFICIAL_NON_TRADING_DAY_"+value)
    return True

def audit_file(output):
    lookup,digest,counts=load_calendar()
    doc={"schema":"V095_2026_CASH_MARKET_CALENDAR_V1","year":2026,
         "market_scope":["TSE_CASH","OTC_CASH"],"days":len(lookup),
         "calendar_sha256":digest,"counts":counts,
         "source_urls":[SOURCE_TWSE,SOURCE_TPEX],
         "excluded_other_sources":["TAIFEX","TDCC","MOPS","NDC"],
         "status":"CALENDAR_TABLE_VERIFIED_NOT_DATASET_COMPLETION",
         "note":"Cash equity closed day is not an official-data gap; do not assume other source publication calendars"}
    output=pathlib.Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+"\n")
    return doc
if __name__=="__main__":
    import sys
    print(json.dumps(audit_file(sys.argv[1] if len(sys.argv)>1 else "v095_market_calendar_2026/calendar_audit.json"),ensure_ascii=False))
