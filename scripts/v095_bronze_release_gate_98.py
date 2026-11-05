"""JARVIS v0.95 dataset-scoped Bronze 98% admission. Fail closed on critical errors.
Pure deterministic decision; no Drive mutations or production flag changes.
"""
import json, pathlib
POLICY=json.loads((pathlib.Path(__file__).resolve().parents[1]/"governance/v095/BRONZE_RELEASE_98_PERCENT_POLICY_V2_20261105.json").read_text(encoding="utf-8"))
NEEDED=("expected_due_units","valid_download_units","records_inspected","valid_records")
def admit(s):
    missing=[x for x in NEEDED if x not in s]
    if missing:return {"status":"UNKNOWN","reasons":["MISSING_COUNTS:"+",".join(missing)]}
    if not s.get("contract_approved",False) or not s.get("calendar_approved",False):
        return {"status":"UNKNOWN","reasons":["CONTRACT_OR_CALENDAR_NOT_APPROVED"]}
    numbers=[s[x] for x in NEEDED]
    if any(type(v)!=int or v<0 for v in numbers):return {"status":"QUARANTINE","reasons":["INVALID_COUNTS"]}
    exp,have,inspected,valid=numbers
    if exp==0:return {"status":"NOT_DUE" if s.get("source_not_due_proven",False) else "UNKNOWN","reasons":["NO_POSITIVE_EXPECTED_DENOMINATOR"]}
    if inspected==0 or have>exp or valid>inspected:
        return {"status":"UNKNOWN","reasons":["NO_VALID_CORRECTNESS_DENOMINATOR_OR_INCONSISTENT_COUNTS"]}
    # Correctness cannot be declared from arbitrary one-row spot checks.
    method=s.get("content_audit_method")
    if method not in ("EXHAUSTIVE","APPROVED_SAMPLE"):
        return {"status":"UNKNOWN","reasons":["CONTENT_AUDIT_METHOD_UNVERIFIED"]}
    if method=="APPROVED_SAMPLE" and not s.get("sampling_plan_approved",False):
        return {"status":"UNKNOWN","reasons":["SAMPLING_PLAN_UNAPPROVED"]}
    if method=="EXHAUSTIVE" and inspected!=s.get("inspectable_expected_records",inspected):
        return {"status":"UNKNOWN","reasons":["NOT_ACTUALLY_EXHAUSTIVE"]}
    # A single bad raw object is NEVER accepted into a 98% passing set.
    if s.get("unisolated_critical_errors",0)!=0:
        return {"status":"QUARANTINE","reasons":["CRITICAL_ERRORS_NOT_ISOLATED"]}
    if s.get("admitted_bad_sha_count",0)!=0 or s.get("admitted_bad_crc_count",0)!=0:
        return {"status":"QUARANTINE","reasons":["CORRUPT_ADMITTED_RAW_OBJECT"]}
    if s.get("pit_sensitive",False) and not s.get("pit_proven",False):
        return {"status":"PARTIAL","reasons":["PIT_UNPROVEN_SIGNAL_BLOCKED"]}
    if s.get("whole_required_market_day_missing",False):
        return {"status":"PARTIAL","reasons":["REQUIRED_MARKET_DAY_MISSING"]}
    # avoid rounding percentages when deciding, and avoid cross-source aggregating.
    pct=POLICY["default_thresholds"]["expected_unit_coverage_min"]
    assert pct==POLICY["default_thresholds"]["valid_content_rate_min"]==0.98
    cov=have/exp;acc=valid/inspected
    metrics={"coverage":cov,"correctness":acc}
    if cov>=pct and acc>=pct:
        return {"status":"PASS_98","reasons":[],"metrics":metrics}
    return {"status":"PARTIAL","reasons":["BELOW_98_COVERAGE_OR_CORRECTNESS"],"metrics":metrics}
