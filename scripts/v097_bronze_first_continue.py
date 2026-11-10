#!/usr/bin/env python3
"""Queue next Bronze-first cycle only after a durable aggregate; never call Silver/Gold."""
import json,os,time,urllib.request,urllib.error
REPO="danny541690/C1-RAW-DOWNLOADER"
WF="v097-bronze-first-autopilot.yml"
def dispatch():
 if os.getenv("GITHUB_REPOSITORY")!=REPO:raise RuntimeError("wrong repo")
 url="https://api.github.com/repos/"+REPO+"/actions/workflows/"+WF+"/dispatches"
 body=json.dumps({"ref":"main","inputs":{"batch":"full"}}).encode()
 headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json",
          "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json",
          "User-Agent":"jarvis-v097-bronze-first"}
 for i in range(4):
  try:
   req=urllib.request.Request(url,method="POST",data=body,headers=headers)
   with urllib.request.urlopen(req,timeout=30) as res:
    if res.status!=204:raise RuntimeError("dispatch status "+str(res.status))
   print("BF_CONTINUATION_DISPATCHED",os.getenv("GITHUB_RUN_ID"),flush=True)
   return
  except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError):
   if i==3:raise
   time.sleep(4*(i+1))
if __name__=="__main__":dispatch()
