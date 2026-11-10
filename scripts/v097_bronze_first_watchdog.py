#!/usr/bin/env python3
"""Bronze-first retry watchdog: bounded recovery for failed runs, no duplicate active runs."""
import os,json,time,urllib.request,urllib.error
REPO="danny541690/C1-RAW-DOWNLOADER";WF="v097-bronze-first-autopilot.yml"
if os.environ.get("GITHUB_REPOSITORY")!=REPO:raise RuntimeError("Wrong repository")
HEADERS={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json",
         "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json",
         "User-Agent":"jarvis-bronze-first-recovery"}
def req(url,method="GET",data=None):
 r=urllib.request.Request(url,method=method,data=data,headers=HEADERS)
 with urllib.request.urlopen(r,timeout=30) as res:
  if method=="POST" and res.status!=204:raise RuntimeError("Dispatch status "+str(res.status))
  return json.load(res) if method=="GET" else True
pending=int(os.environ.get("BF_PENDING","-1"))
if pending<0:raise RuntimeError("NO_DURABLE_PENDING_COUNT_NO_RESUME")
if pending==0:
 print("BF_WATCH_FINISHED_NO_PENDING_COPIES_RESCUE_OR_QA");exit(0)
root="https://api.github.com/repos/"+REPO+"/actions/workflows/"+WF
runs=req(root+"/runs?branch=main&per_page=60").get("workflow_runs",[])
active=[r for r in runs if r.get("status") in ("queued","in_progress","waiting","pending","requested")]
if active:
 print("BF_WATCH_ACTIVE_RUN",[(x["id"],x["status"]) for x in active[:5]]);exit(0)
if not runs:
 print("BF_WATCH_BOOTSTRAP_MISSING_RUN");eligible=True
else:
 last=runs[0]
 print("BF_WATCH_LAST",last.get("id"),last.get("status"),last.get("conclusion"))
 eligible=last.get("conclusion") in ("failure","timed_out","cancelled","success")
 if not eligible:raise RuntimeError("UNRECOGNIZED_LAST_WORKFLOW_CONCLUSION")
 failures=0
 for r in runs:
  if r.get("conclusion") in ("failure","timed_out","cancelled"):failures+=1
  else:break
 if failures>=3:
  print("BF_WATCH_BLOCKED_THREE_CONSECUTIVE_FAILURES","last",last.get("id"));exit(0)
# A failed preflight, audit, copy, or QA should not silently halt the all-run flow.
for i in range(3):
 try:
  req(root+"/dispatches",method="POST",data=json.dumps({"ref":"main","inputs":{"batch":"full"}}).encode())
  print("BF_WATCH_DISPATCHED_CONTINUATION","pending",pending)
  break
 except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
  if i==2:raise
  time.sleep(5*(i+1))
