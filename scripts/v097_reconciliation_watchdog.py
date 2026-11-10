#!/usr/bin/env python3
"""Recover v0.97 existing 12-lane receipt reconciliation; never touch market data.

This only dispatches the already-defined, read-only reconciliation workflow.
A successful run is terminal. Persistent failures are BLOCKED, not looped forever.
"""
import json, os, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

REPO = "danny541690/C1-RAW-DOWNLOADER"
WF = "v097-reconcile-existing-12-lanes.yml"
BASE = "https://api.github.com/repos/" + REPO
TOKEN = os.environ.get("GH_TOKEN","")
MAX_RUNS_PER_REVISION = 4  # 1 initial run + at most 3 recovery attempts
COOLDOWN_SECONDS = 600

def request(url, data=None):
    headers = {
        "Authorization": "Bearer " + TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "jarvis-v097-reconciliation-watchdog",
    }
    if data is not None: headers["Content-Type"]="application/json"
    req=urllib.request.Request(url,data=data,method="POST" if data is not None else "GET",headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as res:
                return json.loads(res.read()) if data is None else res.status
        except urllib.error.HTTPError as e:
            if e.code not in (429,500,502,503,504) or attempt==3: raise
        except (urllib.error.URLError, TimeoutError):
            if attempt==3:raise
        time.sleep(3*(attempt+1))

def main():
    if os.environ.get("GITHUB_REPOSITORY") != REPO or not TOKEN:
        raise RuntimeError("Unexpected repository or missing GitHub token")
    sha=request(BASE+"/commits/main")["sha"]
    response=request(BASE+"/actions/workflows/"+WF+"/runs?branch=main&per_page=100")
    runs=[r for r in response.get("workflow_runs",[]) if r.get("head_sha")==sha]
    runs.sort(key=lambda r:r.get("created_at",""),reverse=True)
    if any(r.get("status") in ("queued","in_progress","waiting","requested","pending") for r in runs):
        print("RECON_ACTIVE no duplicate dispatch");return
    if runs and runs[0].get("conclusion")=="success":
        print("RECON_COMPLETED run_id="+str(runs[0]["id"])+" no further dispatch");return
    if len(runs)>=MAX_RUNS_PER_REVISION:
        print("RECON_BLOCKED repeated unsuccessful runs="+str(len(runs))+"; manual/code correction needed")
        return
    if runs:
        last=runs[0]
        last_time=last.get("updated_at") or last.get("created_at")
        if last_time:
            seconds=(datetime.now(timezone.utc)-datetime.fromisoformat(last_time.replace("Z","+00:00"))).total_seconds()
            if seconds<COOLDOWN_SECONDS:
                print("RECON_COOLDOWN last_run="+str(last["id"])+" elapsed="+str(round(seconds)))
                return
    result=request(BASE+"/actions/workflows/"+WF+"/dispatches",json.dumps({"ref":"main"}).encode())
    if result != 204: raise RuntimeError("GitHub dispatch not accepted, HTTP "+str(result))
    print("RECON_DISPATCH_ACCEPTED previous_runs_for_revision="+str(len(runs))+" commit="+sha)

if __name__=="__main__":main()
