"""Combined R3 prelaunch go/no-go report.

Offline/read-only. Never promotes a synthetic PASS to production release.
Use --legacy-dir to inspect the repository's current workflow files.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from scripts.v097_r3_workflow_collision_audit import audit

REQUIRED = (
    "G0_NO_LEGACY_WRITERS",
    "G1_REAL_BRONZE_SHA_SAMPLE",
    "G2_OFFICIAL_ERA_CONTRACT_SAMPLE",
    "G3_REAL_PARSE_SAMPLE",
    "G4_REAL_SILVER_INPUT_SAMPLE",
    "G5_DRIVE_COMMIT_READBACK",
    "SEVEN_SOURCE_QUEUE_LEASES",
    "REAL_70_700_1000_INTEGRATION",
    "COHORT_74750_DRIVE_READBACK",
)
def report(workflow_dir: Path, real_attestations: dict | None = None) -> dict:
    checks = {k: False for k in REQUIRED}
    discovery = audit(workflow_dir)
    checks["G0_NO_LEGACY_WRITERS"] = bool(discovery["safe_to_release"])
    for name in REQUIRED:
        if name != "G0_NO_LEGACY_WRITERS" and real_attestations and real_attestations.get(name) is True:
            # Uploaded evidence must be validated by a separate signed approver;
            # this local report does NOT accept caller assertions for release.
            checks[name] = False
    blocked = [x for x,v in checks.items() if not v]
    return {
        "test_environment":"ISOLATED_R3_STAGING",
        "synthetic_ci_result":"SEE_GITHUB_JOB_STATUS",
        "production_release":"BLOCKED" if blocked else "READY_FOR_CONTROLLED_CUTOVER",
        "blockers":blocked,
        "legacy_nonfrozen":discovery["nonfrozen_legacy"],
        "legacy_scheduled":discovery["scheduled_legacy"],
        "potential_drive_writers":discovery["potential_drive_writers"],
        "safe_effects":"NO_DRIVE_WRITES_NO_BRONZE_MUTATION_NO_SILVER_GOLD"
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--legacy-dir",default=".github/workflows")
    parser.add_argument("--output",default="")
    args=parser.parse_args()
    result=report(Path(args.legacy_dir))
    blob=json.dumps(result,indent=2,ensure_ascii=False)
    print(blob)
    if args.output:
        Path(args.output).write_text(blob+"\n",encoding="utf-8")
if __name__=="__main__": main()
