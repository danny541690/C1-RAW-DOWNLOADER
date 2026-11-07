"""R6 merged v0.95 prelaunch evidence assessor. Strictly no production release side effect.

Never promotes a source sample, staging Parquet, 443-ID mapping, or historic fixture
into a live 2000–2026 bulk download authorization.
"""
import argparse,json,pathlib,datetime,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(p):
 try:return json.loads((ROOT/p).read_text())
 except (OSError,ValueError,TypeError):return None
def assess(root=ROOT):
 def read(p):
  try:return json.loads((root/p).read_text())
  except (OSError,ValueError,TypeError):return None
 flags=read("governance/v095/PHASE1_FLAGS.json") or {}
 inventory=read("r5_history_discovery/summary.json")
 tpex=read("v095_sep_tpex_triage/report.json")
 october=read("ultimate_r1/october_bronze_silver_gold_receipt.json")
 octen=read("ultimate_r1/october_enlarged_bsg.json")
 november=read("ultimate_r1/november_latest_bsg.json")
 lineage=read("ultimate_r1_lineage/registry_receipt.json")
 stages=[]
 def add(id,level,state,evidence,reason):
  stages.append(dict(id=id,level=level,state=state,evidence=evidence,reason=reason))
 inv=bool(inventory and inventory.get("calendar_months")==323 and inventory.get("candidate_dataset_months")==2261 and inventory.get("download_tasks_released")==0)
 add("HISTORY_DISCOVERY","scope","PASS_DISCOVERY_NOT_DOWNLOADED" if inv else "NO_CURRENT_RUN_PROOF",inventory and {k:inventory.get(k) for k in ("calendar_months","candidate_dataset_months","download_tasks_released")},"Dataset-month discovery is not proof of source availability or historical data.")
 tp=bool(tpex and tpex.get("total")==412 and tpex.get("all_rows_have_original_lineage") is True and sum(tpex.get("by_kind",{}).values())==412)
 add("TPEX_202609_NATIVE","bronze","PASS_NATIVE_CLASSIFICATION" if tp else "NO_CURRENT_RUN_PROOF",tpex and {"rows":tpex.get("rows_all"),"nonnumeric":tpex.get("total"),"categories":tpex.get("by_kind")},"Official security-class / trading-status reason not yet certified; numeric PIT stays blocked.")
 ok_oct=bool(october and len(october.get("results",{}))==3 and not october.get("errors"))
 add("OCT_202610_THREE_PARTITIONS","silver_gold","PASS_DESCRIPTIVE_CANDIDATE" if ok_oct else "NO_CURRENT_RUN_PROOF",october and {"completed":len(october.get("results",{})),"errors":october.get("errors")},"Only three specified October partitions, not all source datasets and no certified PIT.")
 ok_octen=bool(octen and set(octen.get("sources",{}))=={"TWSE","TPEX"} and not octen.get("failures"))
 add("OCT_ENLARGED","silver_gold","PASS_DESCRIPTIVE_CANDIDATE" if ok_octen else "NO_CURRENT_RUN_PROOF",octen and {"sources":{k:v.get("silver_rows") for k,v in octen.get("sources",{}).items()},"failures":octen.get("failures")},"Bounded native archive sample; typed input is descriptive and not all market dates.")
 completed=november.get("completed",{}) if isinstance(november,dict) else {}
 rejected=november.get("rejected",{}) if isinstance(november,dict) else {}
 nvc=bool(len(completed)==6 and not rejected and all(all(x.get(k) for k in ("bronze_id","silver_id","gold_id","sha256")) for x in completed.values()))
 add("NOV_202611_SIX_DATES","bronze_silver_gold","PASS_SNAPSHOT_CANDIDATE_NOT_PIT" if nvc else "NO_CURRENT_RUN_PROOF",{"completed":len(completed),"rejected":rejected},"Snapshot readback is not fresh official HTTP or historical publication PIT.")
 summary=lineage.get("summary",{}) if isinstance(lineage,dict) else {}
 l443=summary.get("catalog_count")==443 and summary.get("monthly_audit_rows")==1329
 add("LINEAGE_443","lineage","PASS_CANDIDATE_MAPPING_ONLY" if l443 else "NO_CURRENT_RUN_PROOF",{"catalog_count":summary.get("catalog_count"),"monthly_audit_rows":summary.get("monthly_audit_rows")},"Formula DAG, per-row bidirectional Bronze/Silver/Gold SHA and published-at PIT are NOT certified.")
 add("GITHUB_CAS_FENCING","durable_checkpoint","NOT_INTEGRATED_IN_V095",None,"Legacy CAS fixture tests passed in Run 42353313608, but not wired to production v0.95 queue/Drive writer.")
 add("R22_TWSE_LIVE_SOURCE","source","BLOCKED",None,"R22 still has live official TWSE source BLOCKED in Run 42343175946; snapshot reuse is not a live source pass.")
 add("TDCC_SEMANTICS","quality","BLOCKED",{"discrepancies":58,"ratio_warnings":451},"Source unit/weekly date/ratio denominator requires row-level adjudication.")
 add("SOURCE_AVAILABILITY_DENOMINATORS","source","BLOCKED",None,"Expected applicable source/dataset/date/security denominator remains unverified.")
 add("FORMULA_PIT_RELEASE","gold","BLOCKED",None,"443 catalog IDs and hints are not 443 certified formula, warmup, historical PIT or row-lineage.")
 add("LIVE_HISTORY_ADAPTERS","bronze","BLOCKED",None,"2000–2026 production adapters have not been integrated into admitted, durable checkpoint tasks.")
 safe=(flags.get("BULK_COPY_APPROVED") is False and flags.get("RELEASE_APPROVED") is False)
 add("PHASE1_RELEASE_LOCK","governance","PASS_BLOCKED_SAFELY" if safe else "FAIL_UNSAFE",{"bulk":flags.get("BULK_COPY_APPROVED"),"release":flags.get("RELEASE_APPROVED")},"Fail closed: never turn incomplete pilot into formal data release.")
 report={"schema":"JARVIS_V095_R6_MERGED_ACCEPTANCE_V1","generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "operational_status":"RUN_FINISHED_WITH_BLOCKERS","production_bulk_ready":False,"release_approved":False,
 "checks":len(stages),"observed_candidate_pass":sum(x["state"].startswith("PASS_") for x in stages),
 "blockers":[x["id"] for x in stages if x["state"] in ("BLOCKED","NOT_INTEGRATED_IN_V095","FAIL_UNSAFE")],
 "not_observed_this_run":[x["id"] for x in stages if x["state"]=="NO_CURRENT_RUN_PROOF"],
 "stages":stages}
 if not safe:report["operational_status"]="UNSAFE_RELEASE_CONFIGURATION"
 return report
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--out",default="r6_merged_acceptance/summary.json")
 p=parser.parse_args()
 report=assess()
 o=ROOT/p.out;o.parent.mkdir(parents=True,exist_ok=True)
 o.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 md=["# JARVIS v0.95 R6 merged prelaunch acceptance",f"Run: {__import__('os').getenv('GITHUB_RUN_ID','LOCAL')}",
 f"Production bulk ready: **{report['production_bulk_ready']}**",f"Checks: {report['checks']}; candidate scope PASS: {report['observed_candidate_pass']}","",
 "| Gate | State | Reason |","|---|---|---|"]
 for stage in report["stages"]:md.append("| "+stage["id"]+" | "+stage["state"]+" | "+stage["reason"].replace("|","/")+" |")
 (o.parent/"summary.md").write_text("\n".join(md)+"\n")
 print(json.dumps({k:report[k] for k in ("operational_status","production_bulk_ready","checks","observed_candidate_pass","blockers","not_observed_this_run")},ensure_ascii=False))
 return 2 if report["operational_status"]=="UNSAFE_RELEASE_CONFIGURATION" else 0
if __name__=="__main__":raise SystemExit(main())
