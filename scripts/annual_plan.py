#!/usr/bin/env python3
"""Safe, offline annual planning; does not download or certify market data."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

SOURCES = ("TWSE", "TPEx", "FinMind", "MOPS")

def build_plan(year):
    if not 1990 <= year <= datetime.now(timezone.utc).year:
        raise ValueError("Year out of allowed range")
    return {
        "spec_version": "C1_0.93",
        "year": year,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_mode": "PLAN_ONLY_NO_DOWNLOAD",
        "data_verified": False,
        "google_drive_uploaded": False,
        "sources": list(SOURCES),
        "expected_units": 48,
        "completed_units": 0,
        "verified_units": 0,
        "units": [
            {"year": year, "month": f"{month:02d}", "source": source,
             "status": "BLOCKED_UNIMPLEMENTED", "request_count": 0,
             "downloaded_rows": 0, "verified_rows": 0}
            for month in range(1, 13) for source in SOURCES
        ],
        "blockers": [
            "Four source API contracts and implementation must be verified",
            "Google Drive write authorization/checkpoint persistence not configured",
            "Historical market scope, listing history and PIT QA not implemented"
        ],
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", default="output/annual_manifest.json")
    parser.add_argument("--dry-run", choices=("true",), default="true")
    args = parser.parse_args()
    payload = build_plan(args.year)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    print(f"PLAN_ONLY year={args.year} units={len(payload['units'])} verified=0 downloaded=0")
    print("No network fetch, no Google Drive upload, no private strategy access")

if __name__ == "__main__":
    main()
