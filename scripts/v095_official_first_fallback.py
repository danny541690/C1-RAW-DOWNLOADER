"""v0.95 Bronze source priority policy engine. No download occurs in this module."""
import json
from pathlib import Path

POLICY_FILE=Path(__file__).resolve().parents[1]/"governance/v095/OFFICIAL_FIRST_FINMIND_FREE_FALLBACK_V1.json"
POLICY=json.loads(POLICY_FILE.read_text(encoding="utf-8"))
RETRYABLE=set(POLICY["official"]["retryable"])
REQUIRED=set(POLICY["finmind_free"]["require"])
NO_DATA={"EXPECTED_NON_TRADING_DAY","NOT_YET_PUBLISHED","OFFICIAL_NOT_OFFERED"}
def next_action(item):
    """Return a fail-closed decision plus reason; attempt count includes original request."""
    if item.get("verified_existing_v095"):
        return {"action":"REUSE_V095_RAW","accepted":True}
    if item.get("verified_existing_v093"):
        return {"action":"COPY_V093_WITH_PROVENANCE","accepted":True}
    if item.get("calendar_status") in NO_DATA:
        return {"action":"KEEP_EXPECTED_EXCEPTION","accepted":False,"reason":item["calendar_status"]}
    n=item.get("official_attempts_total",0)
    if type(n) is not int or not 0 <= n <= 3:
        return {"action":"BLOCKED","accepted":False,"reason":"INVALID_OFFICIAL_ATTEMPT_COUNTER"}
    if item.get("rate_limited") or item.get("global_quota_exhausted"):
        return {"action":"DEFER_BY_RATE_LIMIT","accepted":False}
    if item.get("verified_official_response_valid"):
        return {"action":"PRESERVE_OFFICIAL_BRONZE","accepted":True}
    last=item.get("official_last_error")
    if n == 0 or (n < 3 and last in RETRYABLE):
        return {"action":"OFFICIAL_DOWNLOAD","accepted":False,"attempt_number":n+1,
                "backoff_seconds":(0 if n==0 else POLICY["official"]["retry_intervals_seconds"][n-1])}
    if n < 3 and last not in RETRYABLE:
        return {"action":"REVIEW_OFFICIAL_FAILURE","accepted":False,"reason":last or "NO_ERROR_CLASSIFICATION"}
    if n == 3 and not item.get("official_missing_confirmed"):
        return {"action":"HOLD_NOT_PROVEN_OFFICIAL_MISSING","accepted":False}
    evidence=set(item.get("finmind_free_approved_evidence",[]))
    gaps=sorted(REQUIRED-evidence)
    if gaps:
        return {"action":"HOLD_FINMIND_NOT_ELIGIBLE","accepted":False,"missing_evidence":gaps}
    return {"action":"FINMIND_FREE_GAP_DOWNLOAD","accepted":False,
            "must_store_separate_provenance":True,"requires_validation_before_bronze":True}
