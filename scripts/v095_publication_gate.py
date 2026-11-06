"""JARVIS v0.95 availability gate: release schedules are not data receipts.
All classification is evidence-aware and can never grant PIT or formal QA.
"""
import datetime as dt
import json
from pathlib import Path
POLICY_PATH=Path("config/v095_publication_availability_policy.json")
TZ=dt.timezone(dt.timedelta(hours=8))
def policy():return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
def reference_month(m):
 year,month=map(int,m.split("-"));return year,month
def next_month_deadline(m,day):
 y,k=reference_month(m);return dt.datetime(y+1 if k==12 else y,1 if k==12 else k+1,day,tzinfo=TZ)
def classify(source,reference,now=None,actual_official_receipt=None,applicable=True):
 """No exact trading-day schedule inference; due only means an official lookup is needed."""
 if not applicable:return {"status":"SOURCE_NOT_APPLICABLE","count_as_missing":False}
 if now is None:now=dt.datetime.now(TZ)
 if now.tzinfo is None:raise ValueError("timezone aware now required")
 now=now.astimezone(TZ)
 p=policy()
 if actual_official_receipt:
  first=dt.datetime.fromisoformat(actual_official_receipt)
  if first.tzinfo is None:raise ValueError("official receipt timestamp must have timezone")
  if first<=now:return {"status":"AVAILABLE_OFFICIAL_VERIFIED","count_as_missing":False,"first_published_at":first.isoformat()}
 if source=="MOPS_MONTHLY_REVENUE":
  deadline=next_month_deadline(reference,10)
  insurer=next_month_deadline(reference,15)
  if now<dt.datetime(*reference_month(reference),1,tzinfo=TZ):raise ValueError("invalid")
  return {"status":"NOT_YET_DUE" if now<deadline else "DUE_CHECK_OFFICIAL",
   "count_as_missing":now>=deadline,
   "nominal_deadline":deadline.isoformat(),
   "insurance_special_deadline":insurer.isoformat(),
   "early_issuer_disclosure_must_be_collected":True,
   "PIT_requires_per_company_timestamp":True,
   "insurer_applicability_not_inferred":True}
 if source=="NDC_BUSINESS_CYCLE":
  release=p["source_rules"][source]["confirmed_calendar"].get(reference)
  if release:
   when=dt.datetime.fromisoformat(release)
   return {"status":"NOT_YET_DUE" if now<when else "DUE_CHECK_OFFICIAL",
    "count_as_missing":now>=when,"confirmed_calendar_release":when.isoformat()}
  y,m=reference_month(reference)
  if (now.year,now.month)<=(y,m):return {"status":"NOT_YET_DUE","count_as_missing":False}
  return {"status":"DUE_CHECK_OFFICIAL_CALENDAR","count_as_missing":None}
 if source in ("CUSTOMS_TRADE","MOEA_INDUSTRIAL_PRODUCTION"):
  rule=p["source_rules"][source]
  date=rule.get("confirmed_calendar",{}).get(reference)
  if date:
   when=dt.datetime.fromisoformat(date)
   return {"status":"NOT_YET_DUE" if now<when else "DUE_CHECK_OFFICIAL",
    "count_as_missing":now>=when,"confirmed_calendar_release":when.isoformat()}
  date=rule.get("confirmed_release",{}).get(reference)
  if date:
   when=dt.datetime.fromisoformat(date)
   return {"status":"DUE_CHECK_OFFICIAL" if now>=when else "NOT_YET_DUE","count_as_missing":now>=when}
  if reference>=now.strftime("%Y-%m"):return {"status":"NOT_YET_DUE","count_as_missing":False}
  return {"status":"DUE_CHECK_OFFICIAL_CALENDAR","count_as_missing":None}
 if source in ("TWSE_DAILY_MARKET","TPEX_DAILY_MARKET","TAIFEX_DAILY"):
  if reference>now.strftime("%Y-%m"):return {"status":"NOT_YET_DUE","count_as_missing":False}
  return {"status":"DUE_CHECK_PAST_TRADING_DAYS","count_as_missing":None,
   "needs_actual_exchange_sessions":True,"needs_dataset_publish_evidence":True}
 if source=="TDCC_WEEKLY_OWNERSHIP":
  if reference>now.strftime("%Y-%m"):return {"status":"NOT_YET_DUE","count_as_missing":False}
  return {"status":"DUE_CHECK_PUBLISHED_WEEKLY_SNAPSHOTS","count_as_missing":None,
   "needs_week_by_week_official_receipts":True}
 return {"status":"UNKNOWN_DATASET_CONTRACT","count_as_missing":None}
SOURCE_MAP={
 "TWSE":"TWSE_DAILY_MARKET","TPEx":"TPEX_DAILY_MARKET",
 "MOPS":"MOPS_MONTHLY_REVENUE","TDCC":"TDCC_WEEKLY_OWNERSHIP",
 "TAIFEX":"TAIFEX_DAILY","NDC":"NDC_BUSINESS_CYCLE"}
def selftest():
 t=dt.datetime(2026,11,6,19,32,tzinfo=TZ)
 assert classify("MOPS_MONTHLY_REVENUE","2026-11",t)["status"]=="NOT_YET_DUE"
 assert classify("MOPS_MONTHLY_REVENUE","2026-10",t)["status"]=="NOT_YET_DUE"
 assert classify("MOPS_MONTHLY_REVENUE","2026-09",t)["status"]=="DUE_CHECK_OFFICIAL"
 assert classify("NDC_BUSINESS_CYCLE","2026-10",t)["status"]=="NOT_YET_DUE"
 assert classify("NDC_BUSINESS_CYCLE","2026-09",t)["status"]=="DUE_CHECK_OFFICIAL"
 assert classify("CUSTOMS_TRADE","2026-10",t)["status"]=="NOT_YET_DUE"
 assert classify("TAIFEX_DAILY","2026-11",t)["status"]=="DUE_CHECK_PAST_TRADING_DAYS"
 assert classify("TDCC_WEEKLY_OWNERSHIP","2026-11",t)["status"]=="DUE_CHECK_PUBLISHED_WEEKLY_SNAPSHOTS"
 assert classify("MOPS_MONTHLY_REVENUE","2026-10",dt.datetime(2026,11,11,tzinfo=TZ))["status"]=="DUE_CHECK_OFFICIAL"
 assert classify("MOPS_MONTHLY_REVENUE","2026-10",t,actual_official_receipt="2026-11-04T16:00:00+08:00")["status"]=="AVAILABLE_OFFICIAL_VERIFIED"
 try:classify("MOPS_MONTHLY_REVENUE","2026-10",t,actual_official_receipt="2026-11-04T16:00:00")
 except ValueError:pass
 else:raise AssertionError("naive PIT timestamp mistakenly accepted")
 print("PUBLICATION_GATE_SELFTEST_PASS")
if __name__=="__main__":selftest()
