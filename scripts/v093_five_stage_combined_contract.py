"""Read-only integrated five-stage contract check for v0.93 cutover.

This is a release audit, not an activation. Never writes Google Drive or cron.
"""
import datetime,json,pathlib,yaml
from scripts.v093_five_stage_scheduler_gate import STAGES,OWNERS,Work,eligible,validate_partition
from scripts.v093_five_stage_durable_gate import decide_adapter

WORKFLOWS={s:pathlib.Path(f".github/workflows/v093-v2-{i:02d}-{suffix}.yml") for i,(s,suffix) in enumerate(zip(STAGES,("raw","qa","price","financial","chip")),1)}
def run():
 months=[f"{y}-{m:02d}" for y in range(2026,1999,-1) for m in range(12,0,-1) if (y,m)<=(2026,10)]
 validate_partition(months)
 assert len(months)==322 and months[0]=="2026-10" and months[-1]=="2000-01"
 owner_fields=[f for fields in OWNERS.values() for f in fields]
 assert len(owner_fields)==len(set(owner_fields))
 stages={}
 for stage,path in WORKFLOWS.items():
  raw=path.read_text()
  wf=yaml.safe_load(raw)
  triggers=wf.get("on",wf.get(True))
  if isinstance(triggers,str):triggers={triggers:None}
  if isinstance(triggers,list):triggers=dict.fromkeys(triggers)
  assert isinstance(triggers,dict)
  jobs=wf.get("jobs",{})
  script_text="\n".join(str(step.get("run","")) for job in jobs.values() for step in job.get("steps",[]))
  has_cron="schedule" in triggers
  is_stub="FIVE_STAGE_PRELAUNCH_CHECK_PASS" in script_text and "writes':0" in script_text
  stage_status="BLOCKED_STUB_ONLY" if is_stub else "REQUIRES_REAL_WRITE_PATH_AUDIT"
  stages[stage]={"path":str(path),"dispatch_only":set(triggers)=={"workflow_dispatch"},"cron_active":has_cron,"stage_status":stage_status,"concurrency_group":wf.get("concurrency",{}).get("group")}
  assert not has_cron,stage
  assert stages[stage]["dispatch_only"],stage
  assert is_stub,stage
 assert not eligible(Work("2026-10","PRICE","ohlc"))
 assert not eligible(Work("2026-10","FINANCIAL","revenue"))
 assert not eligible(Work("2026-10","CHIP","institutional"))
 assert decide_adapter("PRICE",None,None,None)=="BLOCKED_MISSING_INPUT_OR_ADAPTER"
 assert decide_adapter("FINANCIAL",None,None,None)=="BLOCKED_MISSING_INPUT_OR_ADAPTER"
 assert decide_adapter("CHIP",None,None,None)=="BLOCKED_MISSING_INPUT_OR_ADAPTER"
 # The real RAW resume writer must not trust a passing canary from an old commit.
 raw_resume=pathlib.Path(".github/workflows/v093-raw-resume.yml").read_text()
 assert "MERGED_GATE_NOT_PASSED_FOR_THIS_EXACT_COMMIT" in raw_resume
 assert "run.get('head_sha')==current_sha" in raw_resume
 # The quick canary explicitly disclaims production approval; do not conflate it
 # with a fully validated multi-stage release.
 quick_gate=pathlib.Path(".github/workflows/v093-merged-quick-gate.yml").read_text()
 assert "'production_ready':False" in quick_gate
 assert "'pit_verified':False" in quick_gate
 assert "'numeric_verified':False" in quick_gate
 legacy_writers={}
 for filename in ("v093-2024-four-source-annual-capture.yml","v093-layer02-standard-r2.yml"):
  path=pathlib.Path(".github/workflows")/filename
  doc=yaml.safe_load(path.read_text())
  triggers=doc.get("on",doc.get(True))
  legacy_writers[filename]={"push_trigger":isinstance(triggers,dict) and "push" in triggers,"concurrency_group":doc.get("concurrency",{}).get("group")}
 shared_groups={v["concurrency_group"] for v in stages.values()}
 assert len(shared_groups)==1
 return {"period":"2000-01..2026-10","months":len(months),"stages":stages,"source_of_truth":"GITHUB_WORKFLOW_FILES","legacy_writers":legacy_writers,"shared_stage_concurrency_group":next(iter(shared_groups)),"raw_resume_requires_same_commit_canary":True,"production_writes":0,"production_release":"BLOCKED","reason":"FIVE_STAGES_STILL_PRELAUNCH_STUBS"}
if __name__=="__main__":
 print("FIVE_STAGE_COMBINED_CONTRACT "+json.dumps(run(),ensure_ascii=False,sort_keys=True),flush=True)
