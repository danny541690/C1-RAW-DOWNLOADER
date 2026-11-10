#!/usr/bin/env python3
"""R2 automatic continuation after durable aggregate confirms pending work."""
import json,os,time,urllib.request,urllib.error
repo=os.environ["GITHUB_REPOSITORY"]
if repo!="danny541690/C1-RAW-DOWNLOADER":raise RuntimeError("Unexpected repository")
url="https://api.github.com/repos/%s/actions/workflows/v097-round2-content-verify.yml/dispatches"%repo
for i in range(1,4):
    req=urllib.request.Request(url,data=json.dumps({"ref":"main"}).encode(),method="POST",headers={
      "Accept":"application/vnd.github+json","Authorization":"Bearer "+os.environ["GH_TOKEN"],
      "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json",
      "User-Agent":"jarvis-v097-r2-continuation"})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.status!=204:raise RuntimeError("Dispatch status %s"%response.status)
        print("R2_NEXT_RUN_ACCEPTED source_run=%s"%os.environ.get("GITHUB_RUN_ID"),flush=True)
        break
    except urllib.error.HTTPError as e:
        print("R2_DISPATCH_RETRY status=%s attempt=%s"%(e.code,i),flush=True)
        if i==3 or e.code not in (429,500,502,503,504):raise
        time.sleep(i*4)
