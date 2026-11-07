#!/usr/bin/env python3
"""Fail closed when the November official Bronze/Silver/Gold canary is incomplete.

The upstream canary intentionally records per-date rejection rather than raising;
this standalone gate ensures a CI success never masks that partial outcome.
It does not change market data or re-download source bytes.
"""
import argparse
import json
from pathlib import Path

EXPECTED = {f"{source}_{day}" for source in ("TWSE", "TPEx")
            for day in ("2026-11-02", "2026-11-03", "2026-11-06")}

def evaluate(manifest):
    completed = manifest.get("completed")
    rejected = manifest.get("rejected")
    if not isinstance(completed, dict) or not isinstance(rejected, dict):
        return {"outcome": "BLOCKED", "errors": ["INVALID_CANARY_RECEIPT"], "passed": 0, "expected": 6}
    errors = []
    for key in sorted(EXPECTED):
        if key in rejected:
            errors.append(f"REJECTED:{key}:{str(rejected[key])[:140]}")
        if key not in completed and key not in rejected:
            errors.append(f"MISSING:{key}")
        if key in completed:
            row = completed[key]
            if not isinstance(row, dict) or not all(row.get(x) for x in
                ("bronze_id", "silver_id", "gold_id", "sha256")):
                errors.append(f"MISSING_THREE_TIER_EVIDENCE:{key}")
    if manifest.get("pit_verified") is True:
        errors.append("UNSUPPORTED_FULL_PIT_ASSERTION")
    return {"outcome": "PASS_CANDIDATE_NOT_PIT" if not errors else "PARTIAL_BLOCKED",
            "passed": len(EXPECTED & set(completed)) - sum(e.startswith("MISSING_THREE_TIER_EVIDENCE") for e in errors),
            "expected": len(EXPECTED), "errors": errors,
            "historical_pit_approved": False, "bulk_download_approved": False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default="ultimate_r1/november_latest_bsg.json")
    p.add_argument("--out", default="ultimate_r1/november_canary_gate.json")
    args = p.parse_args()
    source = Path(args.manifest)
    try:
        receipt = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        receipt = {}
    result = evaluate(receipt)
    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["outcome"] == "PASS_CANDIDATE_NOT_PIT" else 2

if __name__ == "__main__":
    raise SystemExit(main())
