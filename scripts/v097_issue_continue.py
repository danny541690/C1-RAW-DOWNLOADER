#!/usr/bin/env python3
"""R3 continuation after durable aggregate; all runs must have a committed state."""
import os,json,time,urllib.request,urllib.error
repo=os.environ["GITHUB_REPOSITORY"]
if repo!="danny541690/C1-RAW-DOWNLOADER":raise RuntimeError("Refusing other repository")
u="https://api.github.com/repos/"+repo+"/actions/workflows/v097-issue-repair-12-lanes.yml/dispatches"
for attempt in range(1,5):
 try:
  req=urllib.request.Request(u,method="POST",data=json.dumps({"ref":"main"}).encode(),headers={
   "Authorization":"Bearer "+os.environ["GH_TOKEN"],
   "Accept":"application/vnd.github+json","Content-Type":"application/json",
   "X-GitHub-Api-Version":"2022-11-28","User-Agent":"jarvis-r3-resumable-workflow"})
  with urllib.request.urlopen(req,timeout=30) as response:
   if response.status!=204:raise RuntimeError("Dispatch response "+str(response.status))
  print("R3_NEXT_RUN_ACCEPTED parent="+os.environ.get("GITHUB_RUN_ID","manual"),flush=True)
  break
 except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as e:
  if attempt==4:raise
  time.sleep(min(45,attempt*5))
