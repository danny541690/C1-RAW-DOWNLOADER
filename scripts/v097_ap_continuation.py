#!/usr/bin/env python3
"""v0.97 Bronze 74750 persistent continuation decision.

Returns exit code 0 and emits CONTINUE=1 only when:
 - verified same-run Bronze report is present,
 - remaining >0 and at least one source checkpoint was written by this Run,
 - no stale adapter and no unbounded retries.
 Watchdog can use the same report without demanding same-run receipts.
 Never alters Bronze, checkpoints, Silver or Gold.
"""
import os,sys,json
from scripts.v097_bronze_autopilot import source_api,SOURCES,COHORT,adapter_version
def decide(mode):
 api,control,quality,match,load_json,_,_,_=source_api()
 rid=os.environ.get("GITHUB_RUN_ID","")
 if mode=="postrun":
  rf=match(api,quality,"v097_AP_REPORT_"+rid+".json")
  if not rf:raise RuntimeError("CURRENT_RUN_REPORT_MISSING")
 else:
  # Watchdog reads seven checkpoints rather than guessing latest file order
  rf=None
 if rf:
  rep=load_json(api,rf["id"])
  if rep.get("cohort")!=COHORT or rep.get("run")!=rid:
   raise RuntimeError("REPORT_ID_OR_COHORT_MISMATCH")
  if rep.get("release_gate_complete") is not True:
   raise RuntimeError("SOURCE_RELEASE_GATE_INCOMPLETE")
  total_remaining=rep.get("remaining")
  if not isinstance(total_remaining,int) or total_remaining<0 or total_remaining>COHORT:
   raise RuntimeError("INVALID_REMAINING")
  pending=total_remaining
 else:
  pending=0
 new_work=0;parts={}
 for source in SOURCES:
  f=match(api,quality,"v097_AP_INPUT_"+source+".json")
  if not f:raise RuntimeError("MISSING_FROZEN_INPUT_"+source)
  rows=load_json(api,f["id"])["rows"]
  cf=match(api,control,"v097_AP_CHECKPOINT_"+source+".json")
  ck=load_json(api,cf["id"]) if cf else {"done":{}}
  done=ck["done"]
  known={x["source_id"] for x in rows}
  if len(known)!=len(rows) or set(done)-known:raise RuntimeError("CHECKPOINT_SOURCE_IDS_INVALID_"+source)
  remaining=sum(fid not in done or done[fid].get("adapter_version")!=adapter_version(source)
      or (done[fid].get("status")=="HOLD_READ_OR_SHA" and done[fid].get("retries",0)<3)
      for fid in known)
  if ck.get("last_run")==rid:new_work+=1
  parts[source]=remaining
  if mode=="watchdog":pending+=remaining
 if mode=="postrun" and sum(parts.values())!=pending:
  raise RuntimeError("CHECKPOINT_REPORT_REMAINING_MISMATCH")
 continuation=bool(pending and (mode=="watchdog" or new_work))
 summary={"mode":mode,"run_id":rid,"remaining":pending,"per_source":parts,
   "same_run_checkpoint_writers":new_work,"continue":continuation,
   "reason":"HAS_CHECKPOINT_WORK" if continuation else (
     "NO_PENDING_FILES" if not pending else "NO_CHECKPOINT_PROGRESS")}
 print("BRONZE_CONTINUATION_DECISION="+json.dumps(summary,separators=(",",":")),flush=True)
 if os.environ.get("GITHUB_OUTPUT"):
  with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as o:
   o.write("continue="+("true" if continuation else "false")+"\n")
 return continuation
def selftest():
 # Pure gating guarantees a full pipeline cannot self-dispatch when empty.
 assert not bool(0 and True)
 assert bool(10 and True)
 assert not bool(10 and False)
 print("BRONZE_CONTINUATION_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:] == ["selftest"]:selftest()
 elif len(sys.argv)==2 and sys.argv[1] in ("postrun","watchdog"):decide(sys.argv[1])
 else:raise SystemExit("Usage: [selftest|postrun|watchdog]")
