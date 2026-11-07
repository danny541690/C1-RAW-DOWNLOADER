#!/usr/bin/env python3
"""Read-only R2 single-repo plan contract audit. Not a bulk downloader."""
import argparse,json,pathlib,sys,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
C=ROOT/"config/v095_single_repo_fast_backfill_r2.json"
R1=ROOT/"config/v095_ultimate_r1.json"
FLAGS=ROOT/"governance/v095/PHASE1_FLAGS.json"
def check(cfg,r1,flags):
 issues=[]
 def must(condition,reason):
  if not condition:issues.append(reason)
 assert_type=lambda x,t:isinstance(x,t)
 must(cfg.get("canonical_repository")=="danny541690/C1-RAW-DOWNLOADER","WRONG_SINGLE_REPO")
 must(cfg.get("mode")=="PLAN_AND_GATE_ONLY" and cfg.get("activation")=="MANUAL_AFTER_INDEPENDENT_PILOT_PASS","UNSAFE_ACTIVATION")
 d=cfg.get("date_window",{})
 start,end=d.get("start"),d.get("end")
 try:
  a,b=map(lambda x:datetime.datetime.strptime(x,"%Y-%m"),(start,end))
  count=(b.year-a.year)*12+b.month-a.month+1
 except (ValueError,TypeError):count=-1
 must(start=="2000-01" and end=="2026-11" and count==323 and d.get("month_count")==count,"HISTORY_MONTHS_INVALID")
 lanes=cfg.get("lanes",{});lengths=[len(lanes.get(x,[])) for x in ("bronze","silver","gold")]
 must(lengths==[6,4,4] and len(set(sum((lanes.get(x,[]) for x in ("bronze","silver","gold")),[])))==14,"LANE_ALLOCATION_INVALID")
 must(set(lanes.get("bronze",[]))=={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC"},"SOURCES_INVALID")
 ctl=cfg.get("control",{})
 must(ctl.get("controller_jobs")==1 and ctl.get("initial_active")==6 and ctl.get("max_active")==14
      and ctl.get("scale_steps")==[6,8,10,14] and ctl.get("dispatch_only_ready_tasks") is True,"SCHEDULER_INVALID")
 must(ctl.get("cron_utc")==r1["orchestrator"]["cron_utc"],"CRON_CONFLICT")
 must(cfg.get("retry",{}).get("transient_max")==3 and cfg.get("retry",{}).get("resume_from_checkpoint") is True,"RETRY_INVALID")
 checkpoint=cfg.get("checkpoint",{})
 must(checkpoint.get("durable_cross_run") and checkpoint.get("lease_fencing_required") and checkpoint.get("immutable_raw"),"CHECKPOINT_UNSAFE")
 qa=cfg.get("partition_gate",{})
 must(all(qa.get(x) for x in ("bronze","silver","pit","gold","lineage","release")),"MISSING_QA_GATE")
 feature=cfg.get("feature_policy",{})
 must(feature.get("catalog_target")==443 and feature.get("only_tse_otc_analysis") and feature.get("emerging_raw_only")
      and feature.get("missing_indicator")=="DISABLED_WITH_REASON" and feature.get("forbid_future_knowledge"),"PIT_FEATURE_POLICY_INVALID")
 must(flags.get("BULK_COPY_APPROVED") is False and flags.get("RELEASE_APPROVED") is False,"PRODUCTION_GATE_MUST_REMAIN_CLOSED")
 must(cfg.get("acceptance",{}).get("historical_bulk_start_allowed") is False,"BULK_START_UNSAFE")
 return {"schema":"JARVIS_V095_SINGLE_REPO_R2_PLAN_AUDIT","plan":"PASS" if not issues else "FAIL",
         "historical_data_ready":False,"production_bulk_start_allowed":False,
         "historical_month_count":count,"lanes":sum(lengths),"issues":issues}
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--out",default="r2_plan_audit/report.json")
 a=ap.parse_args()
 result=check(json.loads(C.read_text()),json.loads(R1.read_text()),json.loads(FLAGS.read_text()))
 p=pathlib.Path(a.out);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(result,ensure_ascii=False))
 return 0 if result["plan"]=="PASS" else 2
if __name__=="__main__":sys.exit(main())
