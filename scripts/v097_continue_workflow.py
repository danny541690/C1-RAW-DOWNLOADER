#!/usr/bin/env python3
"""Safe A/B next-run dispatch after durable checkpoint/report.

GitHub workflow_dispatch using GITHUB_TOKEN is explicitly supported.
This helper is called only if validated aggregate says work remains.
"""
import json
import os
import urllib.error
import urllib.request
import time

ALLOWED={
    "A":"v097-bronze-qa-six-lanes.yml",
    "B":"v097-bronze-diagnosis-six-lanes.yml",
}
def main():
    group=os.environ["CONTINUE_GROUP"]
    workflow=ALLOWED[group]
    repo=os.environ["GITHUB_REPOSITORY"]
    token=os.environ["GH_TOKEN"]
    if not token:raise RuntimeError("Missing GitHub token for continuation")
    if repo!="danny541690/C1-RAW-DOWNLOADER":
        raise RuntimeError("Wrong repository; refusing dispatch")
    url="https://api.github.com/repos/"+repo+"/actions/workflows/"+workflow+"/dispatches"
    req=urllib.request.Request(url,data=json.dumps({"ref":"main"}).encode(),
        method="POST",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json",
        "User-Agent":"jarvis-v097-next-run-continuation"})
    for n in range(1,4):
        try:
            with urllib.request.urlopen(req,timeout=30) as response:
                if response.status!=204:
                    raise RuntimeError("Unexpected dispatch status %d"%response.status)
                print("NEXT_RUN_ACCEPTED group=%s source_run=%s attempt=%d"%(group,os.getenv("GITHUB_RUN_ID"),n))
                return
        except urllib.error.HTTPError as exc:
            print("DISPATCH_ERROR group=%s status=%s attempt=%d"%(group,exc.code,n))
            if exc.code not in (429,500,502,503,504) or n==3:raise
        except (urllib.error.URLError,TimeoutError) as exc:
            print("DISPATCH_NETWORK_ERROR group=%s type=%s attempt=%d"%(group,type(exc).__name__,n))
            if n==3:raise
        time.sleep(n*3)
if __name__=="__main__":main()
