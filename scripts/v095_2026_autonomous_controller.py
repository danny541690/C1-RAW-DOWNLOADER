#!/usr/bin/env python3
"""2026-only dispatch supervision. Source writers keep their own immutable checkpoints.
Run is NOT a dataset certification. No historical (2000-2025) dispatch.
"""
import datetime as dt
import json, os, pathlib, urllib.request, urllib.error
REPO="danny541690/C1-RAW-DOWNLOADER"
SOURCES={
 "TWSE":("v095-2026-source-twse.yml","JARVIS v0.95 2026 TWSE independent Bronze and downstream gate"),
 "TPEx":("v095-2026-source-tpex.yml","JARVIS v0.95 2026 TPEx independent Bronze and downstream gate"),
 "MOPS":("v095-2026-source-mops.yml","JARVIS v0.95 2026 MOPS independent Bronze and downstream gate"),
 "TDCC":("v095-2026-source-tdcc.yml","JARVIS v0.95 2026 TDCC independent Bronze and downstream gate"),
 "TAIFEX":("v095-2026-source-taifex.yml","JARVIS v0.95 2026 TAIFEX independent Bronze and downstream gate"),
 "NDC":("v095-2026-source-ndc.yml","JARVIS v0.95 2026 NDC independent Bronze and downstream gate"),
}
QA=("v095-2026-independent-qa-hourly.yml","JARVIS v0.95 2026 independent hourly QA and gap ledger")
ACTIVE={"queued","in_progress","waiting","pending","requested"}
OUT=pathlib.Path("v095_2026_controller")
def api(token,path,method="GET",data=None):
    b=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+path,data=b,method=method,
      headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
               "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JARVIS-v095-2026-controller"})
    with urllib.request.urlopen(req,timeout=25) as r:
        raw=r.read()
    return json.loads(raw) if raw else {}
def choose(name,runs,now,minutes):
    rows=[r for r in runs if r.get("name")==name and r.get("head_branch")=="main"]
    if any(r.get("status") in ACTIVE for r in rows):return "SKIP_ACTIVE"
    if not rows:return "DISPATCH"
    latest=max(rows,key=lambda r:r.get("created_at",""))
    stamp=dt.datetime.fromisoformat((latest.get("updated_at") or latest["created_at"]).replace("Z","+00:00"))
    gap=(now-stamp).total_seconds()/60
    if gap<minutes:return "SKIP_RECENT"
    # Limit old failed jobs to a bounded cooldown; the regular source cron also retries.
    if latest.get("conclusion") not in ("success","skipped"):
        return "SKIP_FAILED_REQUIRE_TRIAGE" if gap<120 else "DISPATCH"
    return "DISPATCH"
def main():
    flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
    assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
    assert os.environ["GITHUB_REPOSITORY"]==REPO
    OUT.mkdir(exist_ok=True)
    now=dt.datetime.now(dt.timezone.utc)
    token=os.environ["GH_TOKEN"]
    runs=api(token,"/actions/runs?per_page=100").get("workflow_runs",[])
    result={"schema":"V095_CONTROLLER_R1","at_utc":now.isoformat(),
            "scope":"2026_only","full_year_verified":False,"history_2000_2025_dispatched":False,
            "production_release":False,"source_actions":{}}
    # The six native source cron workflows are primary; intervene only on stale/idle lanes.
    # Dispatch max 2 sources per control run, never the same active writer.
    dispatched=0
    for source,(workflow,name) in SOURCES.items():
        decision=choose(name,runs,now,65)
        if decision=="DISPATCH" and dispatched>=2:decision="DEFER_CAPACITY"
        if decision=="DISPATCH":
            try:
                api(token,"/actions/workflows/"+workflow+"/dispatches","POST",{"ref":"main"})
                decision="DISPATCH_ACCEPTED"
                dispatched+=1
            except (urllib.error.HTTPError,urllib.error.URLError) as err:
                decision="DISPATCH_ERROR_"+type(err).__name__
        result["source_actions"][source]=decision
    qa_decision=choose(QA[1],runs,now,90)
    if qa_decision=="DISPATCH":
        try:
            api(token,"/actions/workflows/"+QA[0]+"/dispatches","POST",{"ref":"main"})
            qa_decision="DISPATCH_ACCEPTED"
        except (urllib.error.HTTPError,urllib.error.URLError) as err:
            qa_decision="DISPATCH_ERROR_"+type(err).__name__
    result["qa_action"]=qa_decision
    (OUT/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
    if any(v.startswith("DISPATCH_ERROR") for v in result["source_actions"].values()) or qa_decision.startswith("DISPATCH_ERROR"):
        raise SystemExit(2)
if __name__=="__main__":main()
