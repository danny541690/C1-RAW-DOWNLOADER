#!/usr/bin/env python3
"""JARVIS v0.97 A/B periodic recovery watchdog.

Checks real GitHub workflow runs and dispatches idle/stale A and B workflows.
Never changes data files or resets Checkpoints. Cron itself is best effort.
"""
import datetime
import json
import os
import urllib.error
import urllib.request

REPOSITORY=os.environ.get("GITHUB_REPOSITORY","danny541690/C1-RAW-DOWNLOADER")
WORKFLOWS={"A":"v097-bronze-qa-six-lanes.yml",
           "B":"v097-bronze-diagnosis-six-lanes.yml"}
STALE_MINUTES=int(os.getenv("AB_STALE_MINUTES","15"))
STUCK_MINUTES=int(os.getenv("AB_STUCK_MINUTES","120"))
TOKEN=os.getenv("GH_TOKEN","")
BASE="https://api.github.com/repos/"+REPOSITORY
NOW=datetime.datetime.now(datetime.timezone.utc)

def github(method,path,payload=None):
    body=None if payload is None else json.dumps(payload).encode("utf-8")
    req=urllib.request.Request(BASE+path,data=body,method=method,headers={
      "Accept":"application/vnd.github+json",
      "Authorization":"Bearer "+TOKEN,
      "X-GitHub-Api-Version":"2022-11-28",
      "User-Agent":"jarvis-v097-ab-watchdog",
      **({"Content-Type":"application/json"} if body is not None else {})
    })
    try:
        with urllib.request.urlopen(req,timeout=25) as resp:
            return json.loads(resp.read()) if resp.status!=204 else {}
    except urllib.error.HTTPError as err:
        raise RuntimeError("GitHub API HTTP %d on %s"%(err.code,path)) from err

def stamp(value):
    return datetime.datetime.fromisoformat(value.replace("Z","+00:00"))

def check(group,workflow):
    # Query workflow, not just last successful report: active work must not duplicate.
    data=github("GET","/actions/workflows/"+workflow+"/runs?branch=main&per_page=60")
    runs=sorted(data.get("workflow_runs",[]),
                key=lambda r:stamp(r["created_at"]),reverse=True)
    active=[r for r in runs if r.get("status") in
            ("queued","in_progress","waiting","requested","pending")]
    age=(NOW-stamp(runs[0]["created_at"])).total_seconds()/60 if runs else 999999
    print("GROUP_%s last_id=%s last_event=%s last_status=%s age_min=%.1f active=%d"%(
        group,runs[0]["id"] if runs else "none",
        runs[0].get("event") if runs else "none",
        runs[0].get("status") if runs else "none",age,len(active)))
    if active:
        oldest=max((NOW-stamp(r["created_at"])).total_seconds()/60 for r in active)
        if oldest>STUCK_MINUTES:
            print("GROUP_%s STUCK_ALERT: active run older than %.0f min; no blind cancellation"%(group,oldest))
            return "STUCK_ALERT"
        print("GROUP_%s ACTIVE: skip duplicate dispatch"%group)
        return "ACTIVE"
    if age<STALE_MINUTES:
        print("GROUP_%s RECENT: skip duplicate dispatch"%group)
        return "RECENT"
    github("POST","/actions/workflows/"+workflow+"/dispatches",{"ref":"main"})
    print("GROUP_%s RECOVERY_DISPATCH_ACCEPTED after %.1f minutes"%(group,age))
    return "DISPATCHED"

def main():
    if not TOKEN:raise RuntimeError("Missing GITHUB_TOKEN")
    print("WATCHDOG_UTC="+NOW.isoformat())
    result={}
    errors=[]
    for group,workflow in WORKFLOWS.items():
        try:
            result[group]=check(group,workflow)
        except Exception as exc:
            errors.append(group+":"+str(exc))
            print("GROUP_%s ERROR: %s"%(group,str(exc)))
    print("WATCHDOG_RESULT "+json.dumps(result,sort_keys=True))
    if errors:raise RuntimeError(";".join(errors))
if __name__=="__main__":main()
