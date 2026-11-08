#!/usr/bin/env python3
"""Record failed JARVIS official source workflow actions to Drive with SHA readback.
This is a failure notice and correction gate, NOT an automatic code repair.
"""
import datetime as dt,json,os,pathlib,urllib.request
from scripts.v095_market_release_calendar_drive_archive import drive,archive
OUT=pathlib.Path("v095_source_run_errors")
SOURCE_NAMES={
"JARVIS v0.95 2026 TWSE independent Bronze and downstream gate":"TWSE",
"JARVIS v0.95 2026 TPEx independent Bronze and downstream gate":"TPEx",
"JARVIS v0.95 2026 MOPS independent Bronze and downstream gate":"MOPS",
"JARVIS v0.95 2026 TDCC independent Bronze and downstream gate":"TDCC",
"JARVIS v0.95 2026 TAIFEX independent Bronze and downstream gate":"TAIFEX",
"JARVIS v0.95 2026 NDC independent Bronze and downstream gate":"NDC",
"JARVIS v0.95 official format guided six-source native re-download and reconciliation":"SIX_SOURCE_REPAIR"
}
def get_json(url):
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+os.environ["GH_ACTIONS_READ_TOKEN"],
       "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
       "User-Agent":"jarvis-v095-error-audit"})
    with urllib.request.urlopen(req,timeout=35) as r:return json.load(r)
def main():
    event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    run=event.get("workflow_run",{})
    if run.get("conclusion")!="failure":
        print("NO_FAILED_SOURCE_RUN_TO_RECORD");return
    name=run.get("name")
    if name not in SOURCE_NAMES:raise ValueError("UNKNOWN_SOURCE_WORKFLOW_NAME")
    rid=run.get("id")
    if not isinstance(rid,int):raise ValueError("RUN_ID_INVALID")
    repo=os.environ.get("GITHUB_REPOSITORY")
    if repo!="danny541690/C1-RAW-DOWNLOADER":raise ValueError("REPOSITORY_MISMATCH")
    failures=[];page=1
    while True:
        job_page=get_json(f"https://api.github.com/repos/{repo}/actions/runs/{rid}/jobs?per_page=100&page={page}")
        for job in job_page.get("jobs",[]):
            if job.get("conclusion")!="failure":continue
            failures.append({"job":job.get("name"),"job_id":job.get("id"),
                "url":job.get("html_url"),"failed_steps":[s.get("name") for s in job.get("steps",[])
                    if s.get("conclusion")=="failure"]})
        if len(job_page.get("jobs",[]))<100:break
        page+=1
        if page>15:raise ValueError("TOO_MANY_GITHUB_JOB_PAGES")
    if not failures:raise ValueError("FAILED_WORKFLOW_NO_FAILED_JOB_METADATA")
    OUT.mkdir(parents=True,exist_ok=True)
    report={"schema":"JARVIS_V095_SOURCE_FAILURE_LEDGER_V1",
      "source":SOURCE_NAMES[name],"workflow_name":name,"source_run_id":rid,
      "source_workflow_url":run.get("html_url"),"source_branch":run.get("head_branch"),
      "head_sha":run.get("head_sha"),"source_run_created_at":run.get("created_at"),
      "source_run_updated_at":run.get("updated_at"),"recorded_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
      "workflow_conclusion":"failure","failed_jobs":failures,
      "error_class":"CI_JOB_FAILURE_NEEDS_LOG_AND_ORIGINAL_SOURCE_RECEIPT_REVIEW",
      "source_data_missing_not_inferred":True,"code_corrected":False,
      "rerun_required_after_correction":True,"bronze_complete":False,"PIT_approved":False,
      "next_action":"Inspect failed step, classify official source/format/internal error; fix, rerun, verify SHA/lineage and regenerate six-source dated report"}
    p=OUT/f"JARVIS_V095_SOURCE_ERROR_{SOURCE_NAMES[name]}_RUN_{rid}.json"
    p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    receipt=archive(drive(),p)
    print(json.dumps({"status":"FAILED_RUN_RECORDED_DRIVE_SHA_PASS","source_run_id":rid,
        "source":SOURCE_NAMES[name],"failed_jobs":len(failures),"drive_receipt":receipt},ensure_ascii=False))
if __name__=="__main__":main()
