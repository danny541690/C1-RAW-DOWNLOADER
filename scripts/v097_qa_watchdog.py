#!/usr/bin/env python3
"""JARVIS v0.97 A-group watchdog: repair missing triggers without duplicate runs.

Uses GitHub REST under GITHUB_TOKEN. Never clears Drive checkpoint. GitHub
schedule is best-effort; last-run timing and all decisions remain in job logs.
"""
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

REPOSITORY=os.environ.get("GITHUB_REPOSITORY","danny541690/C1-RAW-DOWNLOADER")
WORKFLOW="v097-bronze-qa-six-lanes.yml"
STALE_MINUTES=int(os.environ.get("QA_STALE_TRIGGER_MINUTES","12"))
STUCK_MINUTES=int(os.environ.get("QA_STUCK_RUN_MINUTES","90"))
TOKEN=os.environ.get("GH_TOKEN","")
BASE="https://api.github.com/repos/"+REPOSITORY
NOW=datetime.datetime.now(datetime.timezone.utc)

def github(method,path,payload=None):
    url=BASE+path
    body=None if payload is None else json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(url,method=method,data=body,headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+TOKEN,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"jarvis-v097-a-group-watchdog",
        **({"Content-Type":"application/json"} if body is not None else {})
    })
    with urllib.request.urlopen(req,timeout=22) as resp:
        return json.loads(resp.read()) if resp.status!=204 else {}

def stamp(st):
    return datetime.datetime.fromisoformat(st.replace("Z","+00:00"))

def main():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN missing; cannot assess/repair schedule")
    response=github("GET","/actions/workflows/"+WORKFLOW+"/runs?branch=main&per_page=35")
    runs=[r for r in response.get("workflow_runs",[])
          if r.get("event") in ("schedule","workflow_dispatch","push")]
    # Snapshot only: beware that newly-dispatched runs may take time to appear.
    runs.sort(key=lambda r:stamp(r["created_at"]),reverse=True)
    active=[r for r in runs if r.get("status") in ("queued","in_progress","waiting","requested","pending")]
    print("WATCHDOG time_utc="+NOW.isoformat())
    print("WORKFLOW_RUNS total=%d active=%d"%(len(runs),len(active)))
    if runs:
        r=runs[0];age=(NOW-stamp(r["created_at"])).total_seconds()/60
        print("LATEST id=%s status=%s conclusion=%s age_minutes=%.1f url=%s"%(
            r["id"],r.get("status"),r.get("conclusion"),age,r.get("html_url")))
    else:age=99999
    if active:
        oldest=max((NOW-stamp(r["created_at"])).total_seconds()/60 for r in active)
        print("ACTIVE_RUNS="+",".join(str(x["id"]) for x in active))
        if oldest>STUCK_MINUTES:
            # Never cancel by assumption: user data work needs review of run logs.
            print("ALERT_STUCK_RUN oldest_minutes=%.1f; not dispatching/cancelling to protect checkpoints"%oldest)
        else:
            print("HEALTHY_OR_PENDING: active QA run; no duplicate dispatch")
        return
    if age<STALE_MINUTES:
        print("HEALTHY: last QA run triggered recently, no dispatch")
        return
    print("STALE: no active QA and last trigger older than %d minutes"%STALE_MINUTES)
    github("POST","/actions/workflows/"+WORKFLOW+"/dispatches",{"ref":"main"})
    print("RECOVERY_DISPATCH_ACCEPTED: start QA on main; verify resulting run and Drive checkpoint")
if __name__=="__main__":main()
