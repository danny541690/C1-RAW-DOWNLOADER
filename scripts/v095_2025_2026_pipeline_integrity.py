#!/usr/bin/env python3
"""Static two-year v0.95 source/QA/Silver/Gold/lineage orchestration gates.
This is a deploy check, never a proof of source/indicator data completeness.
"""
import collections,datetime as dt,json,os,pathlib,re,sys
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[1]
WF=ROOT/".github/workflows"
OUT=ROOT/"v095_2025_2026_pipeline_integrity"
SOURCES=("twse","tpex","mops","tdcc","taifex","ndc")
STAGES=("source","qa","downstream")
def inspect():
 out={"schema":"JARVIS_V095_2025_2026_PIPELINE_LINK_AUDIT_R1",
   "years":[2025,2026],"required_22_lanes_per_year":True,
   "source_names":list(SOURCES),"workflow_count":0,"checks":[],
   "errors":[],"warnings":[],"formal_443_certified":False,
   "historical_PIT_certified":False,"all_year_data_complete":False}
 errors=out["errors"]
 for year in (2025,2026):
  groups={};year_count=0
  for stage in STAGES:
   for source in SOURCES:
    path=WF/f"v095-{year}-{stage}-{source}.yml"
    if not path.is_file():errors.append("MISSING:"+str(path));continue
    txt=path.read_text()
    try:yml=yaml.safe_load(txt)
    except yaml.YAMLError as exc:errors.append("INVALID_YAML:"+str(path)+":"+str(exc)[:90]);continue
    jobs=yml.get("jobs") if isinstance(yml,dict) else None
    if not isinstance(jobs,dict) or len(jobs)!=1:errors.append("JOB_COUNT:"+str(path));continue
    for job in jobs.values():
     env=job.get("env") or {}
     if year==2025 and str(env.get("V095_DATA_YEAR"))!="2025":
      errors.append("YEAR_ENV_SCOPE:"+str(path))
     if stage=="source" and source in ("twse","tpex") and str(env.get("V095_BRONZE_ONLY"))!="1":
      errors.append("EQUITY_BRONZE_NOT_ISOLATED:"+str(path))
     if stage=="downstream" and source in ("twse","tpex"):
      steps=job.get("steps") or []
      if not any("v095_2026_equity_downstream" in str(x.get("run","")) for x in steps):
       errors.append("EQUITY_CONVERTER_NOT_LINKED:"+str(path))
     receipt_steps=[s for s in job.get("steps",[]) if "v095_2026_publish_run_receipt" in str(s.get("run",""))]
     if stage!="qa" and len(receipt_steps)!=1:errors.append("RECEIPT_STEP_COUNT:"+str(path))
    concurrency=yml.get("concurrency",{}).get("group")
    if not concurrency:errors.append("NO_WRITER_LOCK:"+str(path))
    elif concurrency in groups:errors.append("DUPLICATE_YEAR_LOCK:"+str(path)+" VS "+groups[concurrency])
    else:groups[concurrency]=str(path)
    if "schedule" not in (yml.get("on") or yml.get(True) or {}):
     errors.append("NO_CRON:"+str(path))
    year_count+=1
  for suffix in ("gold-market","gold-fundamental","lineage-audit","autonomous-controller"):
   path=WF/f"v095-{year}-{suffix}.yml"
   if not path.is_file():errors.append("MISSING_COORDINATOR:"+str(path));continue
   try:
    y=yaml.safe_load(path.read_text())
    if not isinstance(y.get("jobs"),dict):errors.append("NO_COORDINATOR_JOB:"+str(path))
   except Exception as exc:errors.append("COORDINATOR_INVALID:"+str(path)+":"+str(exc)[:80])
   year_count+=1
  if year_count!=22:errors.append("INCORRECT_22_LOGICAL_LANES:"+str(year)+":"+str(year_count))
  out["checks"].append({"year":year,"logical_jobs":year_count,"source_bronze":6,
    "source_qa":6,"source_downstream":6,"candidate_gold":2,"lineage":1,"source_controller":1,
    "source_2025_legacy_migration":year==2025,
    "PIT_certified":False})
  out["workflow_count"]+=year_count
 flags=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
 if flags["BULK_COPY_APPROVED"] or flags["RELEASE_APPROVED"]:errors.append("EARLY_BULK_OR_RELEASE_ENABLED")
 out["warnings"]+=["2025 and 2026 443 formula catalog has unapproved mathematical definitions",
 "2025-2026 QA workers classify recent receipts, not complete repair backfills",
 "MOPS TDCC TAIFEX NDC 2025 source workers handle legacy native only, not every official network fallback",
 "FinMind free exact-gap fallback is policy but not fully wired across six native source families",
 "Historical PIT publication evidence and full 2000-2026 rolling warmup not yet certified",
 "GitHub success verifies execution, not data or indicator completeness"]
 out["passed"]=not errors
 return out
def main():
 OUT.mkdir(exist_ok=True)
 r=inspect()
 (OUT/"result.json").write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"passed":r["passed"],"workflow_count":r["workflow_count"],"errors":r["errors"],
  "warnings":r["warnings"],"443_gold_PIT_approved":False},ensure_ascii=False))
 return 0 if r["passed"] else 2
if __name__=="__main__":sys.exit(main())
