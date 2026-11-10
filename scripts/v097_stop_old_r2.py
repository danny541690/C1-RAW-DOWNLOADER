#!/usr/bin/env python3
"""Cancel old R2 scan runs before freezing issue receipts. Only fixed repository/workflow."""
import json,os,time,urllib.request,urllib.error
REPO="danny541690/C1-RAW-DOWNLOADER"
assert os.environ["GITHUB_REPOSITORY"]==REPO
TOKEN=os.environ["GH_TOKEN"]
API="https://api.github.com/repos/"+REPO
H={"Authorization":"Bearer "+TOKEN,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
   "User-Agent":"jarvis-v097-r3-stop-legacy"}
def req(url,method="GET"):
 r=urllib.request.Request(url,method=method,headers=H,data=b"" if method=="POST" else None)
 try:
  with urllib.request.urlopen(r,timeout=30) as x:
   v=x.read()
   return x.status,json.loads(v) if v else {}
 except urllib.error.HTTPError as e:
  return e.code,{"error":e.read().decode()[:200]}
def active():
 results=[]
 for state in ("in_progress","queued","waiting"):
  url=API+"/actions/workflows/v097-round2-content-verify.yml/runs?status="+state+"&per_page=100"
  status,res=req(url)
  if status!=200:raise RuntimeError("Cannot inspect legacy workflow runs: "+str(status))
  for run in res.get("workflow_runs",[]):
   if run.get("status") in ("in_progress","queued","waiting"):
    results.append(run["id"])
 return sorted(set(results))
for iteration in range(5):
 ids=active()
 print("OLD_R2_ACTIVE",ids,flush=True)
 if not ids:
  print("OLD_R2_FULLY_STOPPED",flush=True);break
 for run_id in ids:
  status,_=req(API+"/actions/runs/"+str(run_id)+"/cancel","POST")
  if status not in (202,409):
   raise RuntimeError("Cannot cancel old R2 run "+str(run_id)+" HTTP "+str(status))
  print("OLD_R2_CANCEL_REQUESTED",run_id,status,flush=True)
 time.sleep(20)
else:
 raise RuntimeError("Old R2 jobs still active; do not freeze concurrent receipts")
