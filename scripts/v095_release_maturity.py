"""JARVIS v0.95: split execution from data acceptance and release maturity.

Four acceptance states:
PASS    complete, approved dataset contract + quality + PIT/lineage
PARTIAL observed valid subset; incomplete scope
BLOCK   waiting on publication, missing upstream, or unapproved evidence
ERROR   technical/structural failure; eligible for finite repair

RMI is a coverage/availability indicator, NOT a certificate. Unknown evidence
never becomes a zero or a PASS. One item is (source,dataset,period,security?).
"""
import datetime as dt
from v095_publication_gate import classify, SOURCE_MAP, TZ

ACCEPTANCE=("PASS","PARTIAL","BLOCK","ERROR")
def maturity(availability,observed_count,expected_count=None,verified_count=0,has_error=False,contract_ok=False,pit_ok=False,lineage_ok=False):
    """Returns both release state and meaningful measurable maturity, without assumptions."""
    if has_error:
        return dict(status="ERROR",reason="TECHNICAL_OR_INTEGRITY_FAILURE",rmi=None,overdue=None)
    observed=int(observed_count or 0)
    verified=int(verified_count or 0)
    if observed<0 or verified<0 or verified>observed:raise ValueError("INVALID_COUNTS")
    expected=int(expected_count) if expected_count is not None else None
    if expected is not None and (expected<0 or observed>expected):
        return dict(status="ERROR",reason="UNEXPECTED_COUNT_OR_DUPLICATION",rmi=None,overdue=None)
    stage=availability.get("status","UNKNOWN_DATASET_CONTRACT")
    not_due=stage in ("NOT_YET_DUE","SOURCE_NOT_APPLICABLE","NO_TRADING_SESSION")
    # Release-ready coverage is only numerical if the expected denominator is
    # established by an actual dataset-level contract and not a month folder.
    coverage=verified/expected if expected and contract_ok else None
    rmi=round(100*coverage,2) if coverage is not None else None
    certified=(expected is not None and verified==expected and contract_ok and pit_ok and lineage_ok)
    if certified:
        return dict(status="PASS",reason="ALL_APPLICABLE_ROWS_AND_PIT_CERTIFIED",rmi=rmi,overdue=False)
    if observed>0:
        return dict(status="PARTIAL",reason="DATA_OBSERVED_NOT_ALL_CONTRACT_PIT_LINEAGE_CERTIFIED",rmi=rmi,
                    overdue=(availability.get("count_as_missing") is True),availability=stage)
    reason=("WAITING_PUBLICATION" if not_due else
            "CHECK_OFFICIAL_OR_MISSING_UPSTREAM" if stage.startswith(("DUE_","PARTIALLY")) else
            "AWAITING_CONTRACT_OR_RECEIPT")
    return dict(status="BLOCK",reason=reason,rmi=rmi,
                overdue=False if not_due else availability.get("count_as_missing"),availability=stage)

def source_period_maturity(source,month,observed_count,now=None,**kwargs):
    if source not in SOURCE_MAP:raise ValueError("SOURCE_UNMAPPED_"+source)
    if now is None:now=dt.datetime.now(TZ)
    release=classify(SOURCE_MAP[source],month,now)
    return dict(source=source,reference_month=month,release=release,
                acceptance=maturity(release,observed_count,**kwargs))

def combined_state(states,technical_error=False):
    if technical_error or "ERROR" in states:return "ERROR"
    if states and all(x=="PASS" for x in states):return "PASS"
    if "PASS" in states or "PARTIAL" in states:return "PARTIAL"
    return "BLOCK"

def selftest():
    now=dt.datetime(2026,11,6,22,11,tzinfo=TZ)
    x=source_period_maturity("MOPS","2026-11",0,now=now)
    assert x["acceptance"]["status"]=="BLOCK" and x["acceptance"]["reason"]=="WAITING_PUBLICATION"
    assert x["acceptance"]["overdue"] is False
    x=source_period_maturity("MOPS","2026-09",0,now=now)
    assert x["acceptance"]["status"]=="BLOCK" and x["acceptance"]["overdue"] is True
    x=source_period_maturity("MOPS","2026-10",7,now=now)
    assert x["acceptance"]["status"]=="PARTIAL" and x["acceptance"]["rmi"] is None
    x=source_period_maturity("NDC","2026-10",0,now=now)
    assert x["acceptance"]["status"]=="BLOCK" and x["acceptance"]["overdue"] is False
    assert maturity({"status":"AVAILABLE_OFFICIAL_VERIFIED"},10,expected_count=10,verified_count=10,
                    contract_ok=True,pit_ok=True,lineage_ok=True)["status"]=="PASS"
    assert maturity({"status":"AVAILABLE_OFFICIAL_VERIFIED"},10,expected_count=10,verified_count=10,
                    contract_ok=True,pit_ok=False,lineage_ok=True)["status"]=="PARTIAL"
    assert maturity({"status":"DUE_CHECK_OFFICIAL"},0,has_error=True)["status"]=="ERROR"
    assert combined_state(["BLOCK","PARTIAL"])=="PARTIAL"
    assert combined_state(["PASS","PASS"])=="PASS"
    print("JARVIS_V095_RMI_FOUR_STATE_SELFTEST_PASS")

if __name__=="__main__":selftest()
