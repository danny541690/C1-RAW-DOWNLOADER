#!/usr/bin/env python3
"""Seven-source full known-error census across all production stage checkpoints.
This inventories EVERY observed error code in the currently frozen source cohort,
not only sampled examples; it never changes READY, Bronze, Silver or Gold.
"""
import json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,COHORT,READY,source_api
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_seven_source_specific_resolvers import triage
SOURCE_STAGES={
 "A":"v097_AP_CHECKPOINT_{src}.json",
 "B":"v097_B_FORMAT_FORENSICS_CK_{src}.json",
 "C":"v097_C_MANIFEST_NUMERIC_CK_{src}.json",
 "V2":"v097_SEVEN_FORMAT_V2_CK_{src}.json",
 "DEEP":"v097_SEVEN_INDEPENDENT_DEPTH_CK_{src}.json",
 "D":"v097_D_THREE_WAY_GATE_CK_{src}.json",
 "PRICE_WITNESS":"v097_BRIDGE_PRICE_WITNESS_CK_{src}.json"
}
def counter_from_done(done):
 if not isinstance(done,dict):raise RuntimeError("INVALID_STAGE_DONE")
 counts=Counter()
 examples={}
 for sid,v in done.items():
  status=str(v.get("status","NO_STATUS"))
  counts[status]+=1
  if len(examples.setdefault(status,[]))<2:
   examples[status].append({"source_id":sid,
     "historical_version":v.get("historical_version"),
     "source_path":v.get("source_path") or v.get("original_path")})
 return {"checked":len(done),"all_observed_statuses":dict(counts),
   "samples_by_status":examples}
def summarize(formal,stage_data):
 if set(formal)!=set(SOURCES):raise RuntimeError("SEVEN_SOURCES_MISSING")
 cohort=0;ready=0
 bysource={}
 for s in SOURCES:
  f=formal[s]
  r=f["records"]
  if f.get("source")!=s or len(r)!=f.get("cohort"):
   raise RuntimeError("INVALID_FORMAL_GATE_"+s)
  fids={x["source_id"] for x in r}
  if len(fids)!=len(r):raise RuntimeError("DUPLICATE_FORMAL_IDS_"+s)
  good={x["source_id"] for x in r if x["status"]==READY}
  cohort+=len(r);ready+=len(good)
  stages={}
  for stage,ck in stage_data.get(s,{}).items():
   done=ck.get("done",{})
   if set(done)-fids:raise RuntimeError("STAGE_UNKNOWN_ID_"+s+"_"+stage)
   stages[stage]=counter_from_done(done)
  errs=stages.get("A",{}).get("all_observed_statuses",{})
  bysource[s]={"formal_total":len(r),"formal_ready":len(good),"formal_hold":len(r)-len(good),
    "stages":stages,"native_error_resolution":[
     {"status":k,"count":v,"next_step":triage(s,k)["resolver"]}
     for k,v in sorted(errs.items(),key=lambda x:(-x[1],x[0]))],
    "official_historical_format_windows":OFFICIAL_VERSIONS[s]["periods"],
    "required_dataset_types":OFFICIAL_VERSIONS[s]["datasets"],
    "required_evidence_contract":OFFICIAL_VERSIONS[s]["strict"],
    "missing_stages":[k for k in SOURCE_STAGES if k not in stage_data.get(s,{})],
    "silver_gold_executed":False}
 if cohort!=COHORT:raise RuntimeError("WRONG_FROZEN_COHORT")
 return {"cohort":cohort,"formal_ready":ready,"formal_hold":cohort-ready,
  "ready_rate":round(ready/cohort,6),"by_source":bysource}
def run():
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 rid,formal=latest_complete(api,quality,match,load_json)
 stages={}
 for s in SOURCES:
  stages[s]={}
  for stage,template in SOURCE_STAGES.items():
   if stage in ("B","C") and s not in ("TWSE","TPEx"):continue
   if stage=="PRICE_WITNESS" and s not in ("TWSE","TPEx"):continue
   file=match(api,control,template.format(src=s))
   if not file:continue
   ck=load_json(api,file["id"])
   if ck.get("source")!=s:raise RuntimeError("WRONG_STAGE_SOURCE_"+s+"_"+stage)
   stages[s][stage]=ck
 out=summarize(formal,stages)
 run=os.getenv("GITHUB_RUN_ID","manual")
 out.update({"schema":"v097_seven_source_full_error_census_v1",
  "run":run,"frozen_formal_release_run":rid,
  "created_utc":datetime.now(timezone.utc).isoformat(),
  "evidence_is_proven_only_when_external_numeric_receipts_are_verified":True,
  "auto_silver_ready_promotion":False})
 name="v097_SEVEN_SOURCE_COMPLETE_ERROR_CENSUS_"+run+".json"
 if run!="manual":put_once(api,quality,name,out)
 print("SEVEN_SOURCE_COMPLETE_ERROR_CENSUS="+json.dumps({
  "report":name,"formal_ready":out["formal_ready"],"formal_hold":out["formal_hold"],
  "sources":{s:{"ready":x["formal_ready"],"hold":x["formal_hold"],
    "per_stage_covered":{k:v["checked"] for k,v in x["stages"].items()},
    "native_errors":len(x["native_error_resolution"])}
    for s,x in out["by_source"].items()}},ensure_ascii=False),flush=True)
def selftest():
 f={}
 for s in SOURCES:
  f[s]={"source":s,"cohort":0,"records":[]}
 try:summarize(f,{})
 except RuntimeError as e:assert "WRONG_FROZEN_COHORT" in str(e)
 else:raise AssertionError("EMPTY_COHORT_ACCEPTED")
 assert len(SOURCE_STAGES)>=7
 assert set(OFFICIAL_VERSIONS)==set(SOURCES)
 assert counter_from_done({"a":{"status":"HOLD_DATE"},"b":{"status":"HOLD_DATE"},
  "c":{"status":"HOLD_WIDTH"}})["all_observed_statuses"]=={"HOLD_DATE":2,"HOLD_WIDTH":1}
 print("SEVEN_SOURCE_FULL_ERROR_CENSUS_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif not sys.argv[1:]:run()
 else:raise SystemExit("usage: [selftest]")
