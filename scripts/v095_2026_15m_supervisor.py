#!/usr/bin/env python3
"""JARVIS v0.95 2026 fifteen-minute watchdog: GitHub Actions recovery only.

Runs every 15 min, dispatches the existing bounded YEAR-2026 audit only when
there is no active audit, previous audit is stale, and bounded retry backoff
permits. It NEVER turns on historical bulk, market-data writes, or release.
"""
import datetime as dt
import json
import os
import pathlib
import urllib.error
import urllib.request

REPO="danny541690/C1-RAW-DOWNLOADER"
WORKFLOW="v095-2026-auto-recovery.yml"
OUT=pathlib.Path("v095_watchdog_2026")
UTC=dt.timezone.utc
ACTIVE={"queued","in_progress","waiting","pending","requested"}
BACKOFF_MIN=(15,30,60,120,240,360)

def parse_time(s):
    return dt.datetime.fromisoformat(s.replace("Z","+00:00"))

def decide(runs,now):
    """No claim of resumed data processing; only auditable workflow dispatch."""
    relevant=sorted((r for r in runs if r.get("name")=="JARVIS v0.95 2026 AUTO incremental inventory and 3-tier evidence"
                     and r.get("head_branch")=="main"),key=lambda r:r.get("created_at",""),reverse=True)
    if any(r.get("status") in ACTIVE for r in relevant):
        return {"decision":"SKIP_ACTIVE","reason":"another annual workflow run is active","retry_minutes":15}
    if not relevant:
        return {"decision":"DISPATCH","reason":"no previous annual run"}
    last=relevant[0]
    age=(now-parse_time(last.get("updated_at") or last["created_at"])).total_seconds()/60
    if last.get("conclusion")=="success":
        return {"decision":"DISPATCH" if age>=60 else "SKIP_COOLDOWN",
                "reason":"hourly bounded 2026 evidence refresh (15-minute watchdog)",
                "age_minutes":round(age,2),"min_interval":60}
    # Backoff by *consecutive recent* failures; no endless tight retry loop.
    streak=0
    for r in relevant:
        if r.get("conclusion") in ("failure","timed_out","cancelled","startup_failure"):
            streak+=1
        else:
            break
    wait=BACKOFF_MIN[min(max(streak-1,0),len(BACKOFF_MIN)-1)]
    return {"decision":"DISPATCH" if age>=wait else "SKIP_BACKOFF",
            "reason":"bounded failed-run recovery","consecutive_failures":streak,
            "age_minutes":round(age,2),"retry_minutes":wait}

def request_json(path, token, method="GET", payload=None):
    url="https://api.github.com/repos/"+REPO+path
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method,headers={
        "Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JARVIS-v095-2026-watchdog"})
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read()
        return json.loads(raw) if raw else {}

def main():
    OUT.mkdir(exist_ok=True)
    now=dt.datetime.now(UTC)
    flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
    assert flags["BULK_COPY_APPROVED"] is False
    assert flags["RELEASE_APPROVED"] is False
    assert os.environ.get("GITHUB_REPOSITORY")==REPO
    token=os.environ["GH_TOKEN"]
    result={"at_utc":now.isoformat(),"run_id":os.environ.get("GITHUB_RUN_ID"),
            "scope":"2026 pilot only","market_data_writes":False,
            "history_2000_2025_dispatch":False,"release_approved":False}
    try:
        allruns=request_json("/actions/runs?per_page=100",token).get("workflow_runs",[])
        result.update(decide(allruns,now))
        if result["decision"]=="DISPATCH":
            request_json("/actions/workflows/"+WORKFLOW+"/dispatches",token,
                         "POST",{"ref":"main"})
            result["decision"]="DISPATCH_ACCEPTED"
    except (urllib.error.HTTPError,urllib.error.URLError,ValueError,KeyError) as exc:
        result.update(decision="WATCHDOG_ERROR",error_type=type(exc).__name__,error=str(exc)[:200])
    (OUT/"status.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    if result["decision"]=="WATCHDOG_ERROR":raise SystemExit(2)

if __name__=="__main__":
    main()
