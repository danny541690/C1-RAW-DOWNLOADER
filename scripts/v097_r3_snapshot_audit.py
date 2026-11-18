"""R3 G0 cross-generation snapshot audit; accepts downloaded JSON files, read-only.

R1 and V3 progress are different metrics and MUST NEVER be added or auto-promoted.
No Google credentials, API calls, Drive writes, Bronze writes, or Silver/Gold operations.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from scripts.v097_r3_gate_core import COHORT, SOURCES

def audit_snapshots(r1: dict, v3: dict) -> dict:
    problems=[]
    for name, obj in (("R1",r1),("V3",v3)):
        if obj.get("cohort") != COHORT:
            problems.append(f"{name}_COHORT_MISMATCH")
        names=[s.get("source") for s in obj.get("sources",[])]
        if sorted(names)!=sorted(SOURCES):
            problems.append(f"{name}_SOURCE_SET_MISMATCH")
        if sum(int(s.get("cohort",0)) for s in obj.get("sources",[])) != COHORT:
            problems.append(f"{name}_SOURCE_CENSUS_MISMATCH")
        for s in obj.get("sources",[]):
            if int(s.get("cohort",0)) < 0:
                problems.append(f"{name}_NEGATIVE_SOURCE_COHORT")
    if {s["source"]:s["cohort"] for s in r1.get("sources",[])} != {s["source"]:s["cohort"] for s in v3.get("sources",[])}:
        problems.append("CROSS_VERSION_COHORT_DIVERGENCE")
    r1_pending=int(r1.get("status",{}).get("PENDING",-1))
    r1_remaining=int(r1.get("status",{}).get("NOT_EVALUATED",-1))
    if min(r1_pending,r1_remaining)<0 or r1_pending+r1_remaining!=COHORT:
        problems.append("R1_STATUS_RECONCILIATION_FAILED")
    if int(r1.get("evaluated",-1)) != r1_pending:
        problems.append("R1_EVALUATED_MISMATCH")
    v3_checked=int(v3.get("checked",-1))
    v3_remaining=int(v3.get("not_checked",-1))
    if min(v3_checked,v3_remaining)<0 or v3_checked+v3_remaining!=COHORT:
        problems.append("V3_STATUS_RECONCILIATION_FAILED")
    if int(v3.get("statuses",{}).get("EVIDENCE_PENDING",-1)) != v3_checked:
        problems.append("V3_PENDING_MISMATCH")
    for name,obj in (("R1",r1),("V3",v3)):
        ssum=sum(int(s.get("status",{}).get("PENDING",0)) for s in obj["sources"]) if name=="R1" else sum(int(s.get("checked",0)) for s in obj["sources"])
        target=r1_pending if name=="R1" else v3_checked
        if ssum!=target: problems.append(f"{name}_SOURCE_PROGRESS_MISMATCH")
    if r1.get("ready",0)!=0 or v3.get("schema_ready_certified",0)!=0:
        # Existing formal release must be reconciled using a certificate ledger, never inferred.
        problems.append("FORMAL_RELEASE_REQUIRES_CERTIFICATE_RECONCILIATION")
    for name,obj in (("R1",r1),("V3",v3)):
        if int(obj.get("silver_materialized",0)) or int(obj.get("gold_materialized",0)):
            problems.append(f"{name}_UNAUTHORIZED_MATERIALIZATION")
    return {"pass":not problems,"problems":problems,"cohort":COHORT,
            "r1":{"run":r1.get("run"),"evaluated":r1_pending,"remaining":r1_remaining},
            "v3":{"run":v3.get("run"),"checked":v3_checked,"remaining":v3_remaining},
            "note":"Read-only snapshot arithmetic; no per-file certification or R3 release."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--r1",required=True)
    p.add_argument("--v3",required=True)
    args=p.parse_args()
    output=audit_snapshots(json.loads(Path(args.r1).read_text(encoding="utf-8")),
                           json.loads(Path(args.v3).read_text(encoding="utf-8")))
    print(json.dumps(output,indent=2,ensure_ascii=False))
    if not output["pass"]:
        raise SystemExit(1)
if __name__=="__main__": main()
