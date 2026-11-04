"""JARVIS v0.95 isolated pilot v1: first real, non-destructive read-only run.
All live source collection is performed by preceding R17-R28 steps.
This script creates an audited pilot manifest. NEVER mutates main, Drive
production, current release pointer, or historical data.
"""
import datetime,hashlib,json,os,pathlib,sys
from collections import Counter
OUT=pathlib.Path("v095_pilot_readonly")
OUT.mkdir(exist_ok=True)
FILES={
 "source_probe":"r17_live_source_connectivity.json",
 "recovery":"r18_live_recovery_report.json",
 "candidate":"r19_live_candidates/report.json",
 "tdcc_full":"r20_tdcc_full/report.json",
 "tdcc_gold_qa":"r24_tdcc_numeric_gold_candidate/report.json",
 "signed_admission":"r25_integrated_admission/R25_SIGNED_ADMISSION_GATE.json",
 "master_join":"r27_official_security_master/R27_current_master_join_report.json",
 "historical_rollback_qa":"r28_prelaunch/R28_GATE.json",
 "final_gate":"final_prelaunch_gate/FINAL_PRELAUNCH_GATE.json"
}
def sha_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()
def main():
    manifest={"schema":"JARVIS_C1_V095_ISOLATED_PILOT_V1",
        "stage":"FIRST_READONLY_PILOT",
        "branch":os.environ.get("JARVIS_PILOT_SOURCE_BRANCH") or os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME","UNKNOWN"),
        "github_event_name":os.environ.get("GITHUB_EVENT_NAME","UNKNOWN"),
        "git_commit":__import__("subprocess").run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip(),
        "github_run_id":os.environ.get("GITHUB_RUN_ID","UNKNOWN"),
        "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "production_release_approved":False,
        "production_writes":False,
        "drive_writes_by_runner":False,
        "historical_pit_approved":False,
        "investment_gold_enabled":False,
        "scheduling_activated":os.environ.get("JARVIS_PILOT_SCHEDULE_INSTALLED")=="1",
        "source_evidence":{}}
    if manifest["branch"]!="test/jarvis-v095-parquet-isolated-20261104":
        raise RuntimeError("PILOT_REF_NOT_ISOLATED_BRANCH")
    documents={}
    for name,fp in FILES.items():
        p=pathlib.Path(fp)
        if not p.exists():raise RuntimeError("MISSING_REQUIRED_PILOT_EVIDENCE:"+fp)
        documents[name]=json.loads(p.read_text(encoding="utf-8"))
        manifest["source_evidence"][name]={"path":fp,"sha256":sha_file(p),"size_bytes":p.stat().st_size}
    probe=documents["source_probe"]
    manifest["seven_source_probe"]={x["source"]:{"status":x["status"],"data_verified":x.get("data_verified",False)}
                                    for x in probe["results"]}
    recovery=documents["recovery"]
    manifest["official_route_recovery"]={x["source"]:{"status":x["status"],"valid_data":x.get("valid_data",False)}
                                        for x in recovery["source_results"]}
    tdcc=documents["tdcc_full"]
    manifest["tdcc_rows"]=tdcc.get("source_rows")
    manifest["tdcc_full_structural_pass"]=tdcc.get("full_bronze_verified") is True
    qa=documents["tdcc_gold_qa"]
    manifest["tdcc_qa_groups"]=qa.get("security_date_groups")
    manifest["tdcc_qa_warnings"]=qa.get("warning_counts")
    manifest["current_master_join_pass"]=documents["master_join"].get("current_market_snapshot_join_pass",False)
    manifest["previous_final_gate_blocked"]=documents["final_gate"].get("production_gate_blocked")
    manifest["pilot_status"]="PASS_READONLY_CANDIDATES" if (
        manifest["tdcc_full_structural_pass"] and manifest["current_master_join_pass"] and
        manifest["previous_final_gate_blocked"]==11 and len(manifest["seven_source_probe"])==7
    ) else "BLOCKED"
    (OUT/"PILOT_MANIFEST.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PILOT_STATUS="+manifest["pilot_status"])
    print("PILOT_TDCC_ROWS="+str(manifest["tdcc_rows"]))
    print("PILOT_SEVEN_SOURCES="+str(len(manifest["seven_source_probe"])))
    print("PILOT_PRODUCTION_RELEASE_APPROVED=false")
    print("PILOT_SCHEDULE_ACTIVATED=false")
    if manifest["pilot_status"]!="PASS_READONLY_CANDIDATES":raise SystemExit(1)
if __name__=="__main__":main()
