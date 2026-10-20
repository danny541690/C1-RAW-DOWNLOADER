"""Pure governance primitives for C1 v0.93 02_STANDARD.
Never publishes a release from a staging file.  No Drive/network dependencies.
"""
import hashlib
import json
import math
from datetime import date, timedelta

class GateBlocked(ValueError):
    pass

def digest_bytes(raw):
    if not isinstance(raw, bytes):
        raise TypeError("raw must be bytes")
    return hashlib.sha256(raw).hexdigest()

def transformation_key(source, dataset, raw_sha256, adapter_version):
    """Content addressed transformation identity. Plan changes create a new key."""
    if not all(isinstance(s,str) and s.strip() for s in (source,dataset,raw_sha256,adapter_version)):
        raise ValueError("missing transformation identity")
    if len(raw_sha256)!=64 or any(c not in "0123456789abcdef" for c in raw_sha256):
        raise ValueError("invalid raw SHA256")
    payload=json.dumps([source,dataset,raw_sha256,adapter_version],ensure_ascii=False,separators=(",",":"))
    return hashlib.sha256(payload.encode()).hexdigest()

def classify_input(previous_receipt, current):
    """Exact same source/dataset + checksum + adapter => skip; no overwritten RAW."""
    required=("source","dataset","raw_sha256","adapter_version")
    if any(not current.get(k) for k in required):
        raise ValueError("incomplete receipt")
    if not previous_receipt:
        return "NEW_INPUT"
    if all(previous_receipt.get(k)==current.get(k) for k in required):
        return "SKIP_VERIFIED_INPUT"
    if (previous_receipt.get("source"),previous_receipt.get("dataset")) != (current.get("source"),current.get("dataset")):
        return "NEW_INPUT"
    if previous_receipt.get("raw_sha256")!=current.get("raw_sha256"):
        return "NEW_RAW_VERSION"
    return "ADAPTER_REBUILD"

def compare_candidates(records, *, approved_sources, tolerance=0):
    """No silent averaging. Reject unvalidated units/PIT, conflicts and unknown sources."""
    if not records:
        return {"status":"MISSING","chosen":None}
    if isinstance(tolerance,bool) or not isinstance(tolerance,(int,float)) or not math.isfinite(tolerance) or tolerance<0:
        raise ValueError("finite nonnegative tolerance required")
    accepted=[];rejected=[]
    for r in records:
        src=r.get("source")
        if src not in approved_sources:
            rejected.append({"source":src,"reason":"SOURCE_NOT_APPROVED"});continue
        if not all(r.get(k) is True for k in ("schema_ok","unit_ok","date_ok","pit_ok","numeric_ok","universe_ok")):
            rejected.append({"source":src,"reason":"GATE_INCOMPLETE"});continue
        v=r.get("value")
        if isinstance(v,bool) or not isinstance(v,(float,int)) or (isinstance(v,float) and not math.isfinite(v)):
            rejected.append({"source":src,"reason":"NUMERIC_INVALID"});continue
        if any(not isinstance(r.get(k),str) or not r[k].strip() for k in ("stock_id","period","field","unit","definition_version","as_of_mode")):
            rejected.append({"source":src,"reason":"IDENTITY_INCOMPLETE"});continue
        accepted.append(r)
    if not accepted:
        return {"status":"BLOCKED","chosen":None,"rejected":rejected}
    # Do not compare differing economic definitions even if numeric values happen to agree.
    identities={tuple(r.get(k) for k in ("stock_id","period","field","unit","definition_version","as_of_mode")) for r in accepted}
    if len(identities)!=1:
        return {"status":"CONFLICT_DEFINITION","chosen":None,"rejected":rejected}
    a=min(r["value"] for r in accepted);b=max(r["value"] for r in accepted)
    if b-a>tolerance:
        return {"status":"CONFLICT_VALUE","chosen":None,"range":[a,b],"rejected":rejected}
    chosen=next(r for s in approved_sources for r in accepted if r["source"]==s)
    # This only selects among externally preapproved candidates. It doesn't grant source approval.
    return {"status":"CANDIDATE_COMPATIBLE","chosen":chosen,"rejected":rejected}

def dirty_trade_days(changed_day, lookbacks, forward_deps=()):
    """Rolling windows (including the changed input day); no unsafely guessed date counts."""
    day=date.fromisoformat(changed_day)
    if not lookbacks or any(not isinstance(n,int) or n<1 for n in lookbacks):
        raise ValueError("explicit positive windows required")
    # Trading sessions require an official calendar. Return window requirements, not calendar-day ranges.
    return {"changed_day":day.isoformat(),"required_forward_trading_sessions":max(lookbacks)-1,
            "additional_dependencies":list(forward_deps),"status":"DIRTY_REQUIRES_TRADING_CALENDAR"}

REQUIRED_QA=("sha_readback","schema","unit","unique_key","numeric","universe","pit","source_contract","dependency")
def gate_release(manifest):
    failures=[key for key in REQUIRED_QA if manifest.get("qa",{}).get(key) is not True]
    if manifest.get("kind")!="APPROVED_STANDARD" or failures:
        raise GateBlocked("RELEASE_BLOCKED:"+",".join(failures or ["KIND_NOT_APPROVED"]))
    inputs=manifest.get("input_digests")
    def valid_sha(s):
        return isinstance(s,str) and len(s)==64 and all(c in '0123456789abcdef' for c in s)
    if not isinstance(inputs,list) or not inputs or not all(valid_sha(s) for s in inputs):
        raise GateBlocked("RELEASE_BLOCKED:NO_INPUT_DIGESTS")
    if not manifest.get("generation_id") or not valid_sha(manifest.get("parquet_sha256")):
        raise GateBlocked("RELEASE_BLOCKED:MISSING_GENERATION")
    return True

def plan_pointer_change(current_release, expected_release, candidate):
    """Pure CAS plan. Actual Drive pointer update must be single-writer and rechecked server-side."""
    if current_release!=expected_release:
        raise GateBlocked("RELEASE_CONFLICT")
    gate_release(candidate)
    return {"previous_release":current_release,"new_release":candidate["generation_id"],
            "action":"CAS_PLAN_ONLY_NOT_COMMITTED"}

