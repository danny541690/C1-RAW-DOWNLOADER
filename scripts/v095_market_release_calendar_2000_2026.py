#!/usr/bin/env python3
"""G0 six-source market/release calendar for 2000--2026.
Only primary-source documented dates may classify historical trading status.
Source publishing dates are NOT interchangeable with stock market holidays.
A filing deadline is NOT a point-in-time publication timestamp.
"""
import csv,datetime as dt,hashlib,json,pathlib,collections,argparse
from scripts.v095_2026_cash_market_calendar import load_calendar,status as cash_status
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/"governance/v095"
REG=BASE/"MARKET_RELEASE_CONTRACTS.json"
OVERRIDES=BASE/"MARKET_CALENDAR_EVIDENCE_2000_2025.csv"
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
VALID_OVERRIDE={"CONFIRMED_TRADING","CONFIRMED_CLOSED","CONFIRMED_SETTLEMENT_ONLY"}
TZ=dt.timezone(dt.timedelta(hours=8))
def digest(x):return hashlib.sha256(x).hexdigest()
def history_evidence():
    values={}
    with OVERRIDES.open(newline="",encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if not any(r.values()):continue
            d=dt.date.fromisoformat(r["date"]);s=r["source"]
            if not 2000<=d.year<=2025 or s not in ("TWSE","TPEx","TAIFEX") or r["state"] not in VALID_OVERRIDE:
                raise ValueError("INVALID_HISTORICAL_EVIDENCE_SCOPE")
            if not r["evidence_uri"].startswith("https://") or len(r["source_sha256"])!=64 or any(c not in "0123456789abcdef" for c in r["source_sha256"]):
                raise ValueError("HISTORICAL_EVIDENCE_SOURCE_SHA_REQUIRED")
            if (r["date"],s) in values:raise ValueError("DUPLICATE_HISTORICAL_EVIDENCE")
            values[(r["date"],s)]=r
    return values
def contracts():
    data=json.loads(REG.read_text(encoding="utf-8"))
    if data["schema"]!="JARVIS_V095_SOURCE_PUBLICATION_CONTRACT_V1" or {x["source"] for x in data["sources"]}!=set(SOURCES):
        raise ValueError("SIX_SOURCE_REGISTRY_INCOMPLETE")
    mapping={}
    for src in data["sources"]:
        for x in src["datasets"]:
            k=(src["source"],x["id"])
            if k in mapping or x["PIT_available_at_verified"] is not False:raise ValueError("INVALID_DATASET_CONTRACT")
            if x["frequency"] not in ("daily_cash","daily_exchange_specific","weekly","monthly","quarterly","irregular"):
                raise ValueError("BAD_DATASET_FREQUENCY")
            mapping[k]=x
    return mapping
def market_day(day,source,evidence=None):
    d=dt.date.fromisoformat(day)
    if not 2000<=d.year<=2026 or source not in SOURCES:raise ValueError("OUT_OF_SCOPE")
    if d.year==2026 and source in ("TWSE","TPEx"):
        code=cash_status(day,source)
        state={"TRADING":"CONFIRMED_TRADING","WEEKEND":"CONFIRMED_CLOSED",
               "HOLIDAY":"CONFIRMED_CLOSED","SETTLEMENT_ONLY":"CONFIRMED_SETTLEMENT_ONLY"}[code]
        return state,"2026_PRIMARY_CASH_CALENDAR"
    override=(evidence if evidence is not None else history_evidence()).get((day,source))
    if override:return override["state"],"HISTORICAL_PRIMARY_SOURCE_SHA_"+override["source_sha256"]
    return ("WEEKEND_ASSUMED_UNVERIFIED" if d.weekday()>4 else "WEEKDAY_UNVERIFIED"),"NO_PRIMARY_SOURCE_DATE_EVIDENCE"
def due(source,dataset,date,as_of=None,published_at=None,evidence=None):
    as_of=as_of or dt.datetime.now(TZ)
    if as_of.tzinfo is None:raise ValueError("NAIVE_AS_OF_FORBIDDEN")
    d=dt.date.fromisoformat(date);spec=contracts()[(source,dataset)]
    if d>as_of.astimezone(TZ).date():return "FUTURE_NOT_DUE"
    first=spec["earliest_official_date_verified"]
    if first and date<first:return "SOURCE_NOT_YET_AVAILABLE_CONFIRMED"
    if published_at is not None:
        p=dt.datetime.fromisoformat(published_at)
        if p.tzinfo is None:raise ValueError("NAIVE_PUBLISH_TIME_FORBIDDEN")
        return "PUBLISHED_EVIDENCED" if p<=as_of else "NOT_YET_PUBLISHED_AS_OF"
    if source in ("TWSE","TPEx") and spec["frequency"]=="daily_cash":
        state,_=market_day(date,source,evidence)
        if state in ("CONFIRMED_CLOSED","CONFIRMED_SETTLEMENT_ONLY"):return "OFFICIAL_NONTRADING_NOT_GAP"
        if state!="CONFIRMED_TRADING":return "HISTORICAL_TRADE_DATE_UNKNOWN_NOT_GAP"
        return "TRADING_CONFIRMED_PUBLICATION_UNPROVEN"
    if spec["frequency"]=="weekly":return "WEEKLY_PUBLICATION_DATE_UNVERIFIED_NOT_GAP"
    if spec["frequency"] in ("monthly","quarterly"):return "FILING_DEADLINE_NOT_ACTUAL_PUBLISH_TIMESTAMP"
    return "SOURCE_SPECIFIC_PUBLICATION_UNVERIFIED_NOT_GAP"
def build(output):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=True)
    ev=history_evidence();con=contracts();official,official_sha,cash_count=load_calendar()
    p=output/"market_dates_2000_2026.csv";counter=collections.Counter();n=0
    with p.open("w",encoding="utf-8",newline="") as f:
        writer=csv.writer(f);writer.writerow(["date","source","market_state","evidence_level","potential_market_missing_eligible"])
        d=dt.date(2000,1,1)
        while d<=dt.date(2026,12,31):
            for s in SOURCES:
                state,evidence=market_day(d.isoformat(),s,ev)
                eligible=state=="CONFIRMED_TRADING" and s in ("TWSE","TPEx")
                writer.writerow([d.isoformat(),s,state,evidence,int(eligible)])
                counter[(s,state)]+=1;n+=1
            d+=dt.timedelta(days=1)
    with (BASE/"DATASET_CONTRACTS.csv").open(newline="",encoding="utf-8-sig") as reader:
        candidate_contracts=list(csv.DictReader(reader))
    candidate_sources=collections.Counter(x["source_class_id"] for x in candidate_contracts)
    result={"schema":"JARVIS_V095_G0_MARKET_RELEASE_CALENDAR_V1",
      "date_start":"2000-01-01","date_end":"2026-12-31","calendar_rows":n,
      "sources":list(SOURCES),"dataset_contracts":len(con),
      "existing_scoped_dataset_contracts":len(candidate_contracts),
      "existing_scoped_contracts_by_source":dict(candidate_sources),
      "existing_scoped_contracts_ready":sum(x.get("status")=="READY" for x in candidate_contracts),
      "historical_primary_evidence_rows":len(ev),"market_status_counts":{
        s:{state:k for (src,state),k in counter.items() if src==s} for s in SOURCES},
      "official_cash_2026_counts":cash_count,"official_cash_2026_sha256":official_sha,
      "calendar_csv_sha256":digest(p.read_bytes()),"contract_registry_sha256":digest(REG.read_bytes()),
      "verified_historical_closures_complete":False,"publishing_vintage_complete":False,
      "g0_coverage_denominator_certified":False,"PIT_APPROVED":False,
      "interpretation":"UNVERIFIED_IS_NEVER_MISSING; DEADLINE_IS_NEVER_ACTUAL_PUBLICATION"}
    (output/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",default="v095_market_release_calendar");args=p.parse_args()
    r=build(args.output);print(json.dumps({k:r[k] for k in ("calendar_rows","dataset_contracts","historical_primary_evidence_rows","official_cash_2026_counts")},ensure_ascii=False))
