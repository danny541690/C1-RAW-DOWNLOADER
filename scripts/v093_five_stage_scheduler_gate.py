"""Prelaunch five-stage L1 scheduler policy; pure, no Drive writes or GitHub schedules.
This is a testable candidate, NOT an active distributed lock implementation.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from scripts.v093_five_stage_policy import load_policy,bounded_month

STAGES = ("RAW", "QA1", "PRICE", "FINANCIAL", "CHIP")
OWNERS = {"PRICE": frozenset(("ohlc", "volume", "corporate_action")),
          "FINANCIAL": frozenset(("revenue", "balance", "income", "cashflow", "pit")),
          "CHIP": frozenset(("institutional", "margin", "broker", "ownership"))}
MAX_TOTAL_ATTEMPTS = load_policy()['retry']['max_total_attempts']
MAX_RETRIES = MAX_TOTAL_ATTEMPTS  # compatibility alias; counts total attempts

@dataclass(frozen=True)
class Work:
    month: str
    stage: str
    dataset: str
    raw_committed: bool = False
    raw_sha256: str = ""
    qa_complete: bool = False
    qa_sha256: str = ""
    attempts: int = 0
    done: bool = False
    certified: bool = False

def eligible(w: Work) -> bool:
    if w.stage not in STAGES: raise ValueError("UNKNOWN_STAGE")
    try:bounded_month(w.month)
    except (TypeError,ValueError):return False
    if w.done or w.attempts >= MAX_RETRIES: return False
    if w.stage == "RAW": return True
    if not w.raw_committed or len(w.raw_sha256) != 64: return False
    if w.stage == "QA1": return True
    if not w.qa_complete or len(w.qa_sha256) != 64: return False
    if w.stage in OWNERS and w.dataset not in OWNERS[w.stage]: return False
    return True

def claim(w: Work, lease: Optional[dict], *, worker: str, now: int, ttl: int = 300) -> dict:
    if not eligible(w): raise ValueError("INELIGIBLE")
    if not worker or ttl <= 0: raise ValueError("INVALID_LEASE")
    key=f"{w.month}:{w.dataset}:{w.stage}"
    if lease is not None and lease.get("key")==key and lease.get("expires_at",0)>now:
        raise ValueError("ALREADY_LEASED")
    # A production implementation MUST perform an atomic CAS on shared durable storage.
    return {"key":key,"owner":worker,"expires_at":now+ttl,"attempt":w.attempts+1}

def can_publish(w: Work) -> bool:
    # 'done' means processed, not numerically/PIT verified.
    return bool(w.done and w.certified and w.raw_committed and w.qa_complete
                and len(w.raw_sha256)==64 and len(w.qa_sha256)==64)

def validate_partition(months):
    if len(months)!=len(set(months)):raise ValueError("DUPLICATE_MONTH")
    if months!=sorted(months,reverse=True):raise ValueError("NOT_NEWEST_FIRST")
    return True
