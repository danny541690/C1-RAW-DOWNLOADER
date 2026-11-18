"""R3 LIVE G0 old-writer handover audit (read-only GitHub Actions API).

Never disables old workflows. A current active old run or dispatch/cron path
blocks production release. It prints only public run IDs and workflow names.
"""
from __future__ import annotations
import json, os, sys, urllib.request
from pathlib import Path
from scripts.v097_r3_workflow_collision_audit import audit
from scripts.v097_r3_formal_release_contracts import handover_decision

LEGACY_WRITERS={
 "v097_acceptance_r1.yml","v097_v3_acceptance.yml","v097_v3_watchdog.yml",
 "jarvis-v097-g2g3-resume.yml","v097_g2g3_contract_census.yml",
 "v097_g2g3_formal_contracts.yml","v097_g2g3_history_audit.yml",
 "v097_g2g3_native_headers.yml","v097_g2g3_typed_audit.yml"
}
ACTIVE={"queued","requested","waiting","pending","in_progress"}
def inspect():
    token=os.environ.get("GH_TOKEN","")
    repo=os.environ.get("GITHUB_REPOSITORY","")
    if not token or "/" not in repo:raise RuntimeError("GITHUB_READ_AUTH_MISSING")
    request=urllib.request.Request(
        "https://api.github.com/repos/"+repo+"/actions/runs?per_page=100",
        headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"})
    with urllib.request.urlopen(request,timeout=25) as resp:
        payload=json.load(resp)
    runs=payload.get("workflow_runs",[])
    if not isinstance(runs,list):raise RuntimeError("RUN_LIST_MALFORMED")
    active=[{"id":r["id"],"workflow":r.get("path"),"status":r.get("status")}
            for r in runs if r.get("status") in ACTIVE
            and str(r.get("path","")).split("/")[-1] in LEGACY_WRITERS]
    static=audit(Path(".github/workflows"))
    decision=handover_decision(old_runs_active=len(active),
        cron_disabled=not bool(static["scheduled_legacy"]),
        redispatch_disabled=not bool(static["potential_drive_writers"]),
        old_master_snapshot=False,old_checkpoint_snapshot=False,
        exclusive_writer_fence="")
    result={"schema":"R3_G0_LIVE_HANDOVER_AUDIT_V1",
            "active_legacy_run_sample":active,"inspected_recent_runs":len(runs),
            "legacy_scheduled":static["scheduled_legacy"],
            "legacy_potential_writers":static["potential_drive_writers"],
            "old_writers_active_at_snapshot":len(active),
            "handover":decision,
            "release":"BLOCKED",
            "note":"100 most recent runs sampled; a second read and post-quiescence fence needed for release."}
    print("R3_G0_LIVE_AUDIT="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    if decision["status"]=="PASS":
        raise RuntimeError("UNEXPECTED_RELEASE_BY_AUDIT_ONLY")
if __name__=="__main__":
    if sys.argv[1:]!=["audit"]:raise SystemExit("usage: audit")
    inspect()
