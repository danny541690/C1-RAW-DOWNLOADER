"""R3 G0 static workflow-collision audit. Pure repository file inspection.

A finding is a potential writer, not proof of currently running jobs.
No API calls. No cancellation, mutations, or credentials.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

def describe(text: str, name: str) -> dict:
    noop = "JARVIS GLOBAL FREEZE" in text and "no-op" in text
    def trigger(key):
        return re.search(r"^\s{2}"+re.escape(key)+r":",text,re.M) is not None
    write_candidate=("GOOGLE_REFRESH_TOKEN" in text or "GOOGLE_CLIENT_ID" in text) and bool(
        re.search(r"\b(final|aggregate|build|publish|checkpoint|upload|reconcile)\b",text,re.I))
    return {"file":name,"frozen_noop":noop,"schedule":trigger("schedule"),
            "dispatch":trigger("workflow_dispatch"),"push":trigger("push"),
            "drive_write_candidate":write_candidate,
            "concurrency_group":(re.search(r"^\s*group:\s*([^\n]+)",text,re.M) or [None,None])[1]}

def audit(root: Path) -> dict:
    entries=[describe(p.read_text(encoding="utf-8"),p.name) for p in sorted(root.glob("*.yml"))]
    legacy=[e for e in entries if not e["frozen_noop"] and not e["file"].startswith("v097_r3_")]
    cron=[e["file"] for e in legacy if e["schedule"]]
    potential=[e["file"] for e in legacy if e["drive_write_candidate"]]
    return {"workflow_files":len(entries),"nonfrozen_legacy":len(legacy),
            "scheduled_legacy":cron,"potential_drive_writers":potential,
            "safe_to_release":not cron and not potential,
            "note":"Static detection only; inspect live Runs and Drive leases before production."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--directory",default=".github/workflows")
    p.add_argument("--assert-blocked",action="store_true")
    args=p.parse_args()
    result=audit(Path(args.directory))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.assert_blocked and result["safe_to_release"]:
        raise SystemExit("Unexpectedly unblocked: require live-run check")
if __name__=="__main__":main()
