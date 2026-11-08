#!/usr/bin/env python3
"""2025 autonomous source-lane wake-up. Source and transform workers own checkpoints.
Independent 2026 workflows unaffected. No formal release or 443 PIT certification.
"""
import datetime as dt,json,os,pathlib,urllib.error
from scripts.v095_2026_autonomous_controller import api,choose
REPO="danny541690/C1-RAW-DOWNLOADER"
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
ACTIVE={"queued","waiting","in_progress","pending","requested"}
OUT=pathlib.Path("v095_2025_controller")
def main():
 flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
 assert not flags["RELEASE_APPROVED"] and not flags["BULK_COPY_APPROVED"]
 assert os.getenv("GITHUB_REPOSITORY")==REPO
 token=os.environ["GH_TOKEN"];now=dt.datetime.now(dt.timezone.utc)
 # Fetch all three pages; source activity can be hidden by dozens of push-triggered downstream jobs.
 runs=[]
 for page in (1,2,3):
  page_runs=api(token,f"/actions/runs?per_page=100&page={page}").get("workflow_runs",[])
  runs+=page_runs
  if len(page_runs)<100:break
 out={"schema":"V095_2025_AUTONOMOUS_DISPATCH_R1","run_id":os.getenv("GITHUB_RUN_ID"),
  "at_utc":now.isoformat(),"year":2025,"source_actions":{},"source_writer_limit":6,
  "source_workflows_only":True,"formal_release":False,
  "2026_cursor_touched":False,"full_year_certified":False}
 for source in SOURCES:
  filename=f"v095-2025-source-{source.lower()}.yml"
  name=("JARVIS v0.95 2025 "+source+
    (" isolated Bronze official-first backfill" if source in ("TWSE","TPEx")
     else " isolated native Bronze candidate intake"))
  decision=choose(name,runs,now,25 if source in ("TWSE","TPEx") else 40)
  if decision=="DISPATCH":
   try:api(token,"/actions/workflows/"+filename+"/dispatches","POST",{"ref":"main"})
   except (urllib.error.HTTPError,urllib.error.URLError) as e:
    decision="ERROR_"+type(e).__name__
   else:decision="DISPATCH_ACCEPTED"
  out["source_actions"][source]=decision
 OUT.mkdir(exist_ok=True)
 (OUT/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(out,ensure_ascii=False))
 if any(v.startswith("ERROR_") for v in out["source_actions"].values()):raise SystemExit(2)
if __name__=="__main__":main()
