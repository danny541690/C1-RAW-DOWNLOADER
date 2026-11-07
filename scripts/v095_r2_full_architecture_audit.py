#!/usr/bin/env python3
"""Independent no-download architecture review of R1 and R2 against explicit release rules.

PASS means that the inspected source contains an auditable control, not that
the real-world datasets passed. OPEN items are blockers or technical debt.
Only the earlier live execution Run and independent SHA/PIT evidence can
establish production data readiness.
"""
import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[1]
def read(name):
    return (ROOT / name).read_text(encoding="utf-8")
def assess():
    wf=read(".github/workflows/v095-ultimate-r1.yml")
    r1=json.loads(read("config/v095_ultimate_r1.json"))
    r2=json.loads(read("config/v095_single_repo_fast_backfill_r2.json"))
    flags=json.loads(read("governance/v095/PHASE1_FLAGS.json"))
    controller=read("scripts/v095_ultimate_r1_controller.py")
    worker=read("scripts/v095_ultimate_r1_14lane_worker.py")
    lineage=read("scripts/v095_443_bidirectional_lineage.py")
    november=read("scripts/v095_ultimate_r1_november_official.py")
    canary=read("scripts/v095_r2_canary_gate.py")
    rows=[]
    def gate(id,category,passed,priority,rationale,action):
        rows.append({"id":id,"area":category,"state":"PASS_STATIC" if passed else "OPEN",
                     "priority":priority,"finding":rationale,"remedy":action})
    gate("C01","governance",flags.get("RELEASE_APPROVED") is False and flags.get("BULK_COPY_APPROVED") is False,
         "P0","Production history and data release currently fail closed","Keep flags false until signed external acceptance")
    gate("C02","architecture",len(r1["worker_slots"]["BRONZE"])+len(r1["worker_slots"]["SILVER"])+len(r1["worker_slots"]["GOLD"])==14,
         "P2","Six Bronze, four Silver, four Gold responsibility slots are enumerated","Dispatch only READY work through one controller")
    gate("C03","schedule",'cron: \'*/15 * * * *\'' in wf and "max-parallel: 14" in wf,
         "P1","R1 launches fourteen inspection jobs on every scheduled wake, even without READY data units","R2 should dispatch only eligible work; start six live workers, measure then scale")
    gate("C04","download","writable_data_mutation\":False" not in worker and "writable_data_mutation\":False" not in worker.replace(" ",""),
         "P0","Existing 14 workers are candidate-evidence readers, not a full history downloader","Connect actual bounded official source adapters under R2 queue")
    gate("C05","credentials",all(x in wf for x in ("secrets.GOOGLE_CLIENT_ID","secrets.GOOGLE_CLIENT_SECRET","secrets.GOOGLE_REFRESH_TOKEN")),
         "P1","R1 uses repository-scoped Google OAuth Secrets","Protect public logs/artifacts, rotate if exposed and prefer minimal Drive scopes")
    gate("C06","storage","overwrite_if_changed=True" not in controller,
         "P0","R1 checkpoint is updated by file-name replacement without independently proven compare-and-swap","Implement durable CAS with lease/fence and recovery tests before concurrent writes")
    gate("C07","storage","except (OSError,ConnectionError,TimeoutError):" not in controller,
         "P1","Controller transport retry does not classify 408/429/5xx and can retry non-idempotent writes ambiguously","Separate read-only retry from write reconciliation; jitter and circuit breaker")
    gate("C08","canary","v095_r2_canary_gate.py" in wf and "if: always() && github.event_name != 'schedule'" in wf and "REJECTED:" in canary,
         "P0","November source-date partial failures previously stayed inside a successful pilot job","Now fail closed and keep explicit rejected/missing receipt")
    gate("C09","lineage","formula_catalog_pending" not in lineage,
         "P0","Catalog mapping is only candidate family lineage, not certified row-level bidirectional edges","Implement row/partition DAG+hash reverse traversal and orphan/loop check")
    gate("C10","pit","PIT_certified" not in lineage,
         "P0","Historical publication dates/knowledge as-of are not fully certified","Validate each observation's first publication, availability and revision before backtest")
    gate("C11","source","len(rows)<300" not in november,
         "P1","Single constant 300-row heuristic is not source/date-specific market expected universe","Use provider release calendar + security-master-asof expected counts")
    gate("C12","availability","dataset_release_matrix" in read("scripts/v095_ultimate_r1_3month_aggregate.py"),
         "P1","Source-specific published-date maturity matrix exists","Add true per dataset+security applicable denominator, not source-month folder count")
    gate("C13","gold","catalog_target" in r2.get("feature_policy",{}) and r2["feature_policy"]["catalog_target"]==443,
         "P1","443 target defined; raw ID count must not certify formula implementation","Track formula digest, warmup, QA, PIT or explicit disabled-with-reason")
    gate("C14","public_repo",r2.get("git_visibility_policy")=="PRIVATE_ONLY",
         "P0","The only execution repository is public, but private investment strategies belong in a private environment","Make repo private before merging strategies or carrying non-public metadata; never log credentials")
    gate("C15","resource",r2.get("control",{}).get("initial_active")==6 and r2.get("control",{}).get("scale_steps")==[6,8,10,14],
         "P2","R2 bounded gradual 6 to 14 worker expansion is documented, not yet activated","Use measured cost, Drive QPS, memory, source throttle and collision statistics")
    gate("C16","recovery",r2.get("checkpoint",{}).get("lease_fencing_required") and r2.get("retry",{}).get("transient_max")==3,
         "P1","R2 specifies bounded retry and fencing, not proof of real durable CAS","Cross-run crash and duplicate dispatch test with immutable receipt")
    critical=[r["id"] for r in rows if r["state"]=="OPEN" and r["priority"]=="P0"]
    return {"schema":"JARVIS_V095_FULL_ARCHITECTURE_AUDIT_R3",
            "generated_utc":datetime.now(timezone.utc).isoformat(),
            "review_scope":"R1 configuration, workflows, source code and R2 proposed safety contracts",
            "status":"PRODUCTION_BLOCKED" if critical else "STATIC_REVIEW_NO_PRODUCTION_CERTIFICATION",
            "checks":len(rows),"static_pass":sum(r["state"]=="PASS_STATIC" for r in rows),
            "open":sum(r["state"]=="OPEN" for r in rows),"critical_open":critical,
            "production_data_verification":"NOT_PERFORMED_BY_THIS_STATIC_AUDIT",
            "findings":rows}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",default="r2_architecture_audit/report.json")
    a=p.parse_args()
    report=assess()
    output=Path(a.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","checks","static_pass","open","critical_open")},
                     ensure_ascii=False))
    return 0
if __name__=="__main__":raise SystemExit(main())
