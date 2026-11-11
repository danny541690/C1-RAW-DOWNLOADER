#!/usr/bin/env python3
"""Stop ALL v0968- GitHub Actions workflows while keeping JARVIS v097 Bronze alive.

Explicit user authorization: disable old v0.968 schedules/workflows, preserving code and
past runs. Uses GitHub Actions REST, only if EXACT v0968- path prefix matches.
Never touches v097- workflows. Audit JSON emitted as uploadable artifact.
"""
import json,os,re,time,urllib.request,urllib.error
from datetime import datetime,timezone
REPO="danny541690/C1-RAW-DOWNLOADER"
PREFIX=.github/workflows/v0968-
API="https://api.github.com/repos/"+REPO
TOKEN=os.environ["GH_TOKEN"]
HEADERS={"Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json",
 "X-GitHub-Api-Version":"2022-11-28","User-Agent":"jarvis-bronze-v0968-safe-stop"}
def request(path,method="GET",data=None):
 url=API+path
 for attempt in range(6):
  req=urllib.request.Request(url,headers=HEADERS,method=method,data=data)
  try:
   with urllib.request.urlopen(req,timeout=50) as response:
    body=response.read()
    if method!="GET" and response.status!=204:
     raise RuntimeError("Unexpected API mutation status "+str(response.status))
    return json.loads(body) if body else {}
  except urllib.error.HTTPError as err:
   retry=err.code in (429,500,502,503,504) or (err.code==403 and ("secondary rate" in err.read().decode("utf-8","replace").lower()))
   if not retry or attempt==5:raise
   time.sleep(min(35,2**attempt+3))
  except (TimeoutError,urllib.error.URLError):
   if attempt==5:raise
   time.sleep(min(20,2**attempt))
def paged(path,key):
 output=[]
 for page in range(1,60):
  sep="&" if "?" in path else "?"
  obj=request(path+sep+"per_page=100&page="+str(page))
  chunk=obj.get(key,[])
  output.extend(chunk)
  if len(chunk)<100:return output
 raise RuntimeError("PAGINATION_LIMIT_EXCEEDED")
def is_v0968(w):
 path=w.get("path") or ""
 return path.startswith(PREFIX) and re.fullmatch(r"v0968-[^/]+\.(?:yaml|yml)",path.split("/")[-1]) is not None
def snapshot():
 workflows=paged("/actions/workflows","workflows")
 targets=[w for w in workflows if is_v0968(w)]
 modern=[w for w in workflows if (w.get("path") or "").startswith(".github/workflows/v097-")]
 return workflows,targets,modern
def active_runs():
 all_runs={}
 for status in ("in_progress","queued","waiting","pending","requested"):
  for r in paged("/actions/runs?status="+status,"workflow_runs"):
   all_runs[r["id"]]=r
 return list(all_runs.values())
def main():
 if os.getenv("GITHUB_REPOSITORY")!=REPO:raise RuntimeError("REPO_FENCE_FAILED")
 workflows,targets,modern=snapshot()
 modern_main=[w for w in modern if w["path"]==".github/workflows/v097-bronze-first-autopilot.yml"]
 modern_recovery=[w for w in modern if w["path"]==".github/workflows/v097-bronze-first-recovery.yml"]
 if len(modern_main)!=1 or len(modern_recovery)!=1:raise RuntimeError("V097_PROTECTED_WORKFLOWS_MISSING")
 if len(targets)!=5:
  raise RuntimeError("V0968_SCOPE_DRIFT_EXPECTED_5_ACTUAL_"+str(len(targets)))
 for w in modern_main+modern_recovery:
  if w["state"]!="active":raise RuntimeError("PROTECTED_V097_NOT_ACTIVE:"+w["path"])
 runs_before=active_runs()
 old_running=[r for r in runs_before if (r.get("path") or "").startswith(PREFIX)]
 v097_running=[{"id":r["id"],"path":r.get("path"),"status":r.get("status")}
   for r in runs_before if (r.get("path") or "").startswith(".github/workflows/v097-")]
 report={"schema":"v097_v0968_safe_stop_1","date_utc":datetime.now(timezone.utc).isoformat(),
  "repo":REPO,"target_prefix":PREFIX,"v0968_found":len(targets),
  "v097_active_runs_pre":v097_running,
  "v0968_active_runs_pre":[{"id":r["id"],"path":r.get("path"),"status":r.get("status")} for r in old_running],
  "disabled":[],"already_disabled":[],"failed":[],"cancel_requested":[],"remaining":[]}
 with open("v0968_disable_preflight.json","w") as f:json.dump(report,f,ensure_ascii=False,indent=2)
 print("PREFLIGHT",json.dumps({"v0968":len(targets),"v097_active_runs":len(v097_running),
   "v0968_active_runs":len(old_running)}),flush=True)
 # Halt scheduled/triggered future runs BEFORE touching any queued/in-flight v0.968 tasks.
 for index,w in enumerate(targets,1):
  ident=w["id"]
  try:
   if w.get("state")=="disabled_manually":
    report["already_disabled"].append(w["path"])
   else:
    request("/actions/workflows/"+str(ident)+"/disable","PUT",b"")
    report["disabled"].append(w["path"])
  except Exception as ex:
   report["failed"].append({"path":w["path"],"reason":type(ex).__name__+":"+str(ex)[:180]})
  if index%20==0:
   print("STOP_PROGRESS",index,"of",len(targets),"disabled",len(report["disabled"]),
     "already",len(report["already_disabled"]),"failed",len(report["failed"]),flush=True)
  time.sleep(0.13)
 # Cancel any previously queued or in-progress v0968 jobs, never v097.
 for run in old_running:
  try:
   request("/actions/runs/"+str(run["id"])+"/cancel","POST",b"")
   report["cancel_requested"].append(run["id"])
  except urllib.error.HTTPError as ex:
   if ex.code!=409:report["failed"].append({"run":run["id"],"reason":"CANCEL_HTTP_"+str(ex.code)})
  except Exception as ex:
   report["failed"].append({"run":run["id"],"reason":"CANCEL_"+str(ex)[:150]})
 # Verify immutable v097 was not disabled, and no target v0968 remains enabled.
 _,after,modern_after=snapshot()
 states={w["path"]:w["state"] for w in after}
 report["remaining"]=[w["path"] for w in after if w.get("state")=="active"]
 protected={w["path"]:w.get("state") for w in modern_after}
 report["v097_protected_final"]={
  ".github/workflows/v097-bronze-first-autopilot.yml":protected.get(".github/workflows/v097-bronze-first-autopilot.yml"),
  ".github/workflows/v097-bronze-first-recovery.yml":protected.get(".github/workflows/v097-bronze-first-recovery.yml")
 }
 report["final_time_utc"]=datetime.now(timezone.utc).isoformat()
 report["v0968_complete"]=len(report["remaining"])==0 and len(report["failed"])==0
 with open("v0968_disable_result.json","w") as f:json.dump(report,f,ensure_ascii=False,indent=2)
 summary=os.getenv("GITHUB_STEP_SUMMARY")
 if summary:
  with open(summary,"a") as f:
   f.write("## v0.968 stop result\n\n")
   f.write("Discovered: %s, disabled now: %s, already disabled: %s, still active: %s, errors: %s.\n\n"%(
    len(targets),len(report["disabled"]),len(report["already_disabled"]),len(report["remaining"]),len(report["failed"])))
   f.write("Protected v0.97 Bronze and recovery workflow states: %s.\n\n"%report["v097_protected_final"])
   f.write("Run-level evidence in uploaded JSON artifact.\n")
 print("FINAL_SAFE_STOP",json.dumps({"v0968":len(after),"newly_disabled":len(report["disabled"]),
  "already_disabled":len(report["already_disabled"]),"remaining_active":len(report["remaining"]),
  "failed":report["failed"][:10],"v097":report["v097_protected_final"]},ensure_ascii=False),flush=True)
 if any(v!="active" for v in report["v097_protected_final"].values()):
  raise RuntimeError("CRITICAL_V097_PROTECTION_CHECK_FAILED")
 if report["remaining"] or report["failed"]:
  raise RuntimeError("V0968_PARTIAL_STOP_NEEDS_ATTENTION")
if __name__=="__main__":main()
