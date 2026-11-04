"""Daily v0.95 TEST_ONLY operational pilot. One schedule, one runner, one report.

Weekdays: bounded seven-provider probe + MOPS/NDC/TDCC sample three-layer QA.
Friday or manual full: additionally complete TDCC, both company masters,
79 isolated regressions, PIT negative tests, final gate and lineage manifest.

Never publishes, never changes Drive/main/v0.93 data. Reports test scope honestly.
"""
import argparse, datetime, hashlib, json, os, pathlib, subprocess, sys, traceback

OUT=pathlib.Path("v095_pilot_operational")
OUT.mkdir(parents=True,exist_ok=True)
SOURCES=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
BRANCH="test/jarvis-v095-parquet-isolated-20261104"
STEPS_BASE=[
 ("R17_sources","tests/v095_r17_live_source_smoke.py"),
 ("R18_routes","tests/v095_r18_recover_source_routes.py"),
 ("R19_three_layers","tests/v095_r19_live_three_layer_candidates.py")
]
STEPS_FULL=[
 ("R20_tdcc_full","tests/v095_r20_tdcc_full_roundtrip.py"),
 ("R24_gold_qa","tests/v095_r24_tdcc_gold_qa.py"),
 ("R27_current_master","tests/v095_r27_current_official_security_master.py"),
 ("QA_01","tests/v095_isolated_parquet_integration.py"),
 ("QA_02","tests/v095_immutable_release_isolated.py"),
 ("QA_03","tests/v095_concurrent_release_isolated.py"),
 ("QA_04","tests/v095_full_combined_gate.py"),
 ("QA_05","tests/v095_release_gate_evidence.py"),
 ("QA_06","tests/v095_real_twse_sample_parquet.py"),
 ("QA_07","tests/v095_historical_error_regression.py"),
 ("QA_08","tests/v095_source_config_release_audit.py"),
 ("QA_09","tests/v095_r21_tdcc_semantic_rules.py"),
 ("R22_lineage","tests/v095_r22_single_run_release_gate.py"),
 ("R25_admission","tests/v095_r25_pit_security_publish_admission.py"),
 ("R26_evidence","tests/v095_r26_reconciled_gate.py"),
 ("R28_lookahead_rollback","tests/v095_r28_historical_pit_and_release_rollback.py"),
 ("FINAL_GATE","tests/v095_final_oneshot_prelaunch_adjudication.py"),
 ("PILOT_MANIFEST","tests/v095_pilot_readonly_manifest.py")
]
def load(path):
    p=pathlib.Path(path)
    if not p.is_file():return None
    return json.loads(p.read_text(encoding="utf-8"))
def sha(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("auto","daily","full"),default="auto")
    args=parser.parse_args()
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    mode=("full" if now.weekday()==4 else "daily") if args.mode=="auto" else args.mode
    event=os.getenv("GITHUB_EVENT_NAME","local")
    source_branch=os.getenv("JARVIS_PILOT_SOURCE_BRANCH","")
    if source_branch!=BRANCH:raise RuntimeError("PILOT_SOURCE_REF_UNTRUSTED")
    if event not in ("schedule","workflow_dispatch","push","pull_request"):
        raise RuntimeError("PILOT_EVENT_UNEXPECTED:"+event)
    source_sha=subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,check=True).stdout.strip()
    report={"schema":"JARVIS_V095_OPERATIONAL_PILOT_2026",
      "created_at_taipei":now.isoformat(),"mode":mode,"source_ref":source_branch,
      "source_commit":source_sha,"event":event,"github_run_id":os.getenv("GITHUB_RUN_ID"),
      "production_release_approved":False,"gold_investment_enabled":False,
      "production_drive_writes":False,"v093_changed":False,
      "schedule_installed_on_default_branch":event in ("schedule","workflow_dispatch"),
      "has_independent_market_day_evidence":False,
      "steps":[],"evidence":{}}
    script_err=None
    try:
        for ident,script in STEPS_BASE+(STEPS_FULL if mode=="full" else []):
            print("PILOT_STEP_START",ident,flush=True)
            r=subprocess.run([sys.executable,script],capture_output=True,text=True,timeout=210)
            combined=(r.stdout+"\n"+r.stderr)
            (OUT/(ident+".log")).write_text(combined[-30000:],encoding="utf-8")
            failed=(r.returncode!=0 or "\nFAILED (" in combined or "Traceback (most recent call last)" in combined)
            report["steps"].append({"name":ident,"exit_code":r.returncode,"status":"FAIL" if failed else "PASS"})
            print("PILOT_STEP_RESULT",ident,report["steps"][-1]["status"],flush=True)
            if failed:raise RuntimeError(ident+"_FAILED")
        for name,path in {
            "R17":"r17_live_source_connectivity.json",
            "R18":"r18_live_recovery_report.json",
            "R19":"r19_live_candidates/report.json",
            "R20":"r20_tdcc_full/report.json",
            "R24":"r24_tdcc_numeric_gold_candidate/report.json",
            "R27":"r27_official_security_master/R27_current_master_join_report.json",
            "FINAL":"final_prelaunch_gate/FINAL_PRELAUNCH_GATE.json",
            "PILOT_FIRST":"v095_pilot_readonly/PILOT_MANIFEST.json",
        }.items():
            if pathlib.Path(path).is_file():
                report["evidence"][name]={"sha256":sha(path),"path":path}
        r17=load("r17_live_source_connectivity.json") or {}
        report["source_probe"]={x["source"]:{
             "status":x["status"],"data_verified":x.get("data_verified",False),
             "reason":x.get("reason")}
              for x in r17.get("results",[])}
        report["source_count"]=len(report["source_probe"])
        r18=load("r18_live_recovery_report.json") or {}
        report["recovery"]={x["source"]:{
             "status":x["status"],"valid_data":x.get("valid_data",False),
             "error":x.get("error")}
             for x in r18.get("source_results",[])}
        r19=load("r19_live_candidates/report.json") or {}
        report["candidate_qa"]=[{"source":x.get("source"),"status":x.get("status")}
                                for x in r19.get("results",[])]
        if mode=="full":
            r20=load("r20_tdcc_full/report.json") or {}
            r27=load("r27_official_security_master/R27_current_master_join_report.json") or {}
            final=load("final_prelaunch_gate/FINAL_PRELAUNCH_GATE.json") or {}
            report["tdcc_full_count"]=r20.get("source_rows")
            report["tdcc_full_status"]=r20.get("status")
            report["current_master_join_pass"]=r27.get("current_market_snapshot_join_pass",False)
            report["formal_gates_blocked"]=final.get("production_gate_blocked")
            # The legacy smoke is bounded and not permission to publish anything.
            if not r20.get("full_bronze_verified") or not r27.get("current_market_snapshot_join_pass"):
                raise RuntimeError("FULL_CANDIDATE_QUALITY_GATE_MISSING")
            if final.get("release_approved") is not False:
                raise RuntimeError("UNSAFE_RELEASE_GATE_TRUE")
        if set(report["source_probe"])!=set(SOURCES):raise RuntimeError("SEVEN_SOURCE_PROBES_MISSING")
        report["trial_status"]="PASS_WITH_REPORTED_SOURCE_WARNINGS"
    except Exception as exc:
        report["trial_status"]="BLOCKED"
        report["exception"]=type(exc).__name__+":"+str(exc)
        script_err=exc
    finally:
        path=OUT/"PILOT_RUN_REPORT.json"
        path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
        print("PILOT_MODE="+mode)
        print("PILOT_TRIAL_STATUS="+report["trial_status"])
        print("PILOT_SOURCE_COUNT="+str(report.get("source_count",0)))
        print("PILOT_RELEASE_APPROVED=false")
        print("PILOT_REPORT_PATH="+str(path))
    if script_err:raise SystemExit(1)
if __name__=="__main__":main()
