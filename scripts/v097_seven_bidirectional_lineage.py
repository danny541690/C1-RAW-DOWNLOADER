#!/usr/bin/env python3
"""JARVIS v0.97 bidirectional pre-Silver evidence-lineage reconciliation.

A frozen Bronze file -> formal intake -> A/native V2 -> deep -> D can be
traced in both directions by source_id and SHA. D does NOT assert Silver/Gold
materialization. This is an integrity audit, never a promotion process.
"""
import json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api
from scripts.v097_seven_parser_triage import latest_complete
STAGES={
 "A":"v097_AP_CHECKPOINT_{src}.json",
 "V2":"v097_SEVEN_FORMAT_V2_CK_{src}.json",
 "DEEP":"v097_SEVEN_INDEPENDENT_DEPTH_CK_{src}.json",
 "D":"v097_D_THREE_WAY_GATE_CK_{src}.json"}
SHA_KEYS=("original_sha256","bronze_sha256","source_sha256","sha")
def reconcile(src,rows,formal,stages):
 if src not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 bronze={r["source_id"]:r for r in rows}
 if len(bronze)!=len(rows):raise RuntimeError("BRONZE_DUPLICATE_IDS")
 intake={r["source_id"]:r for r in formal["records"]}
 if len(intake)!=len(formal["records"]) or set(bronze)!=set(intake):
  raise RuntimeError("BRONZE_FORMAL_BIDIRECTIONAL_IDS_MISMATCH")
 issues=Counter();examples={}
 coverage={}
 for sid,row in bronze.items():
  original=row["sha"]
  r=intake[sid]
  if r.get("source_sha256")!=original:
   issues["FORMAL_SOURCE_SHA_MISMATCH"]+=1
   if len(examples.setdefault("FORMAL_SOURCE_SHA_MISMATCH",[]))<6:examples["FORMAL_SOURCE_SHA_MISMATCH"].append(sid)
 for stage,done in stages.items():
  extras=set(done)-set(bronze)
  if extras:
   issues["ORPHAN_"+stage]+=len(extras)
   examples["ORPHAN_"+stage]=sorted(extras)[:6]
  checked=0;bad=0;states=Counter()
  for sid,record in done.items():
   if sid not in bronze:continue
   checked+=1
   states[str(record.get("status","UNKNOWN"))]+=1
   for key in SHA_KEYS:
    if key in record and record[key] is not None and record[key]!=bronze[sid]["sha"]:
     bad+=1
     if len(examples.setdefault(stage+"_SHA_MISMATCH",[]))<6:
      examples[stage+"_SHA_MISMATCH"].append({"source_id":sid,"sha_field":key})
   if "source" in record and record["source"]!=src:
    issues[stage+"_SOURCE_MISMATCH"]+=1
  if bad:issues[stage+"_SHA_MISMATCH"]+=bad
  coverage[stage]={"checked":checked,"not_reached":len(bronze)-checked,
    "status_counts":dict(states)}
  # Forward lineage: an advanced checkpoint should not exist without
  # intermediate V2 evidence (except pre-existing READY preserved in D).
  if stage in ("DEEP","D") and "V2" in stages:
   missing=set(done)-set(stages["V2"])
   if stage=="D":
    missing={sid for sid in missing if sid in bronze and intake[sid]["status"]!=READY}
   if missing:
    issues[stage+"_WITHOUT_V2"]+=len(missing)
    examples[stage+"_WITHOUT_V2"]=sorted(missing)[:6]
 reverse={"D_back_to_Bronze":len(set(stages.get("D",{})) & set(bronze)),
   "DEEP_back_to_Bronze":len(set(stages.get("DEEP",{})) & set(bronze)),
   "V2_back_to_Bronze":len(set(stages.get("V2",{})) & set(bronze))}
 return {"source":src,"frozen_bronze":len(bronze),
  "formal_ready_preserved":sum(x["status"]==READY for x in intake.values()),
  "formal_hold":sum(x["status"]!=READY for x in intake.values()),
  "stage_coverage":coverage,"issues":dict(issues),"issue_examples":examples,
  "reverse_lineage":reverse,"silver_gold_materialized_verified":False,
  "ready_promoted":0}
def run(source):
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 input_f=match(api,quality,"v097_AP_INPUT_"+source+".json")
 if not input_f:raise RuntimeError("MISSING_IMMUTABLE_INPUT")
 rows=load_json(api,input_f["id"])["rows"]
 rid,formal=latest_complete(api,quality,match,load_json)
 stages={}
 for name,filename in STAGES.items():
  f=match(api,control,filename.format(src=source))
  if f:stages[name]=load_json(api,f["id"])["done"]
 result=reconcile(source,rows,formal[source],stages)
 result.update({"run":os.getenv("GITHUB_RUN_ID","manual"),
  "formal_release_run":rid,"generated_utc":datetime.now(timezone.utc).isoformat()})
 name="v097_PRE_SILVER_BIDIRECTIONAL_LINEAGE_"+source+"_"+result["run"]+".json"
 if result["run"]!="manual":put_once(api,quality,name,result)
 print("SEVEN_LINEAGE_INTEGRITY="+json.dumps({"source":source,
  "bronze":result["frozen_bronze"],"stage_coverage":{
    k:v["checked"] for k,v in result["stage_coverage"].items()},
  "issues":result["issues"],"ready_promoted":0,"report":name},ensure_ascii=False),flush=True)
 if result["issues"]:raise RuntimeError("SOURCE_LINEAGE_INTEGRITY_FAILURE_"+source)
def selftest():
 row={"source_id":"s","sha":"a"*64}
 release={"records":[{"source_id":"s","source_sha256":"a"*64,"status":"HOLD"}]}
 record={"source_id":"s","source":"TWSE","bronze_sha256":"a"*64,"status":"GOOD"}
 r=reconcile("TWSE",[row],release,{"V2":{"s":record},"D":{"s":{"source_id":"s","status":"HOLD"}}})
 assert r["issues"]=={} and r["reverse_lineage"]["D_back_to_Bronze"]==1
 mismatch=reconcile("TWSE",[row],release,{"V2":{"s":{**record,"bronze_sha256":"b"*64}}})
 assert mismatch["issues"]["V2_SHA_MISMATCH"]==1
 assert r["ready_promoted"]==0 and r["silver_gold_materialized_verified"] is False
 print("SEVEN_BIDIRECTIONAL_PRE_SILVER_LINEAGE_TEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2 and sys.argv[1] in SOURCES:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
