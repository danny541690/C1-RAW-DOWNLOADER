#!/usr/bin/env python3
"""JARVIS v0.97 fail-closed release gate / three management ledgers.

This is an *audit*, not a data downloader or semantic validator.
It reads existing Drive evidence and publishes non-certifying control ledgers.
No original files, Checkpoints, repair records or layer objects are modified.
"""
import json
import os
import re
from datetime import datetime, timezone

from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_content_qa import service, call, folder, children, load_json, save

ROOT_NAME="JARVIS_C1_v097_LIFECYCLE"
SOURCES=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC")
KNOWN_QA_DENOMINATOR=82273
REQUIRED_YEARS=(2000,2026)

def latest(files, prefix):
    rx=re.compile(r"^"+re.escape(prefix)+r"_(\d+)_summary\.json$")
    matches=[]
    for f in files:
        m=rx.fullmatch(f["name"])
        if m:matches.append((int(m.group(1)),f))
    return max(matches,key=lambda item:item[0])[1] if matches else None

def upsert(api, parent, name, payload):
    entries=[x for x in children(api,parent) if x["name"]==name]
    if len(entries)>1:raise RuntimeError("Ambiguous management ledger: "+name)
    if not entries:return save(api,parent,name,payload)
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":")).encode()
    media=MediaInMemoryUpload(raw,mimetype="application/json",resumable=False)
    return call(lambda:api.files().update(fileId=entries[0]["id"],media_body=media,fields="id,name"))

def leaf_count(api, parent):
    return sum(x["mimeType"]!="application/vnd.google-apps.folder" for x in children(api,parent))

def main():
    api=service()
    user=folder(api,"root","ChatGPT資料存取")
    root=folder(api,user,ROOT_NAME)
    control=folder(api,root,"00_SYSTEM_CONTROL")
    gates=folder(api,control,"07_RELEASE_GATES")
    quality=folder(api,root,"03_DATA_QUALITY")
    coverage=folder(api,folder(api,root,"10_REPORTS_DASHBOARDS"),"01_DATA_COVERAGE")
    lake=folder(api,root,"02_DATA_LAKE")
    bronze=folder(api,lake,"01_BRONZE_ORIGINAL")
    silver=folder(api,lake,"03_SILVER_PIT")
    gold=folder(api,lake,"04_GOLD_FEATURES")
    verification=folder(api,quality,"07_VERIFICATION_REPORTS")
    queue=folder(api,quality,"06_REPAIR_QUEUE")
    audit_time=datetime.now(timezone.utc).isoformat()
    run=os.environ.get("GITHUB_RUN_ID","manual")
    coverage_files=children(api,coverage)
    qf=latest(coverage_files,"BRONZE_QA")
    df=latest(coverage_files,"BRONZE_DIAG")
    rf=latest(coverage_files,"BRONZE_REPAIR")
    qa=load_json(api,qf["id"]) if qf else {}
    diag=load_json(api,df["id"]) if df else {}
    repair=load_json(api,rf["id"]) if rf else {}
    # Historical source inventory is a single fixed snapshot, not an expected
    # source/year/month/market calendar coverage contract.
    qa_done=int(qa.get("total_processed",0))
    qa_eligible=int(qa.get("total_eligible",0))
    qa_remaining=qa.get("remaining")
    qa_status=qa.get("status_count",{})
    diag_total=int(diag.get("diagnosed_cumulative",0))
    diag_pending=diag.get("qa_receipts_waiting")
    repair_pending=repair.get("pending_unattempted_repair_candidates")
    blocked_repair=repair.get("blocked_mapping_items_in_run")
    source_folders={x["name"]:x["id"] for x in children(api,bronze)
                    if x["mimeType"]=="application/vnd.google-apps.folder"}
    source_counts={name:leaf_count(api,source_folders[name]) if name in source_folders else None
                   for name in SOURCES}
    # Root-level objects alone cannot prove nested completeness. Reject any
    # apparent completion without dataset manifests and verified lineage.
    bronze_n=sum(count for count in source_counts.values() if isinstance(count,int))
    silver_root_files=leaf_count(api,silver)
    gold_root_files=leaf_count(api,gold)
    quality_ledger={
      "schema":"jarvis_v097_quality_ledger_v1","audit_time_utc":audit_time,
      "qa_run_id":qa.get("run_id"),"qa_level":qa.get("qa_level"),
      "fixed_inventory_run":"42591232910",
      "inventory_count":qa.get("inventory_count"),
      "inventory_eligible":qa_eligible,"inventory_scanned":qa_done,
      "remaining_initial_scan":qa_remaining,
      "initial_scan_fraction":round(qa_done/qa_eligible,6) if qa_eligible else None,
      "qa_status_current_batch":qa_status,
      "note":"STRUCTURAL_PASS_DATASET_PENDING is not semantic, temporal or PIT certification",
      "qa_snapshot_time":qa.get("time_utc"),
      "expected_source_year_month_calendar_verified":False,
      "market_universe_listed_otc_verified":False,
      "point_in_time_verified":False,
      "financial_units_100m_verified":False
    }
    repair_ledger={
      "schema":"jarvis_v097_repair_ledger_v1","audit_time_utc":audit_time,
      "diagnosis_run":diag.get("run_id"),"diagnosed_cumulative_receipt_rows":diag_total,
      "pending_qa_receipts_at_diagnosis_snapshot":diag_pending,
      "diagnosis_classes":diag.get("diagnosis_classes_cumulative",{}),
      "repair_run":repair.get("run_id"),
      "repair_pending_unattempted_at_snapshot":repair_pending,
      "blocked_mapping_in_latest_repair_batch":blocked_repair,
      "source_mapping_failures_latest_batch":repair.get("source_mapping_or_provider_failures"),
      "official_downloads_latest_batch":repair.get("official_downloads"),
      "finmind_downloads_latest_batch":repair.get("finmind_downloads"),
      "note":"Run-level repair counters are not global distinct unresolved issue counts; blockers require permanent case registry and post-repair QA",
      "global_distinct_unresolved_issues_verified":False,
      "post_repair_semantic_revalidation_verified":False
    }
    blockers=[]
    def require(ok,reason):
        if not ok:blockers.append(reason)
    require(qa_eligible>0 and qa_remaining==0,"A_INITIAL_SCAN_INCOMPLETE")
    require(qa_eligible==KNOWN_QA_DENOMINATOR,"FIXED_INVENTORY_CONTRACT_NOT_VERIFIED")
    require(False,"EXPECTED_2000_2026_SOURCE_YEAR_MONTH_COVERAGE_NOT_AUDITED")
    require(False,"DATASET_SCHEMA_AND_NUMERIC_VALIDATION_NOT_AUDITED")
    require(False,"PIT_NO_LOOKAHEAD_NOT_AUDITED")
    require(False,"MONETARY_UNITS_AND_STOCK_CODE_MASTER_NOT_AUDITED")
    require(False,"DISTINCT_REPAIR_EXCEPTION_REGISTRY_AND_POSTFIX_QA_NOT_CERTIFIED")
    require(False,"BRONZE_IMMUTABLE_RAW_AND_SOURCE_HASH_LINEAGE_NOT_CERTIFIED")
    require(False,"SILVER_DATASET_AND_TEMPORAL_TRANSFORM_NOT_CERTIFIED")
    require(False,"GOLD_400PLUS_FEATURES_AND_FORMULA_VALIDATION_NOT_CERTIFIED")
    require(False,"BIDIRECTIONAL_BRONZE_SILVER_GOLD_LINEAGE_NOT_CERTIFIED")
    require(False,"SOURCE_PUBLICATION_DATE_AND_REVISION_REFRESH_NOT_CERTIFIED")
    gate={
      "schema":"jarvis_v097_final_acceptance_v1","audit_time_utc":audit_time,"audit_run_id":run,
      "range":{"start":"2000-01-01","end":"2026-11-10","scope":"TWSE_OTC_EOD_PLUS_FINANCIAL_CHIP_MACRO"},
      "state":"BLOCKED_NOT_CERTIFIED","can_use_for_research_backtest":False,
      "can_claim_all_data_correct_complete":False,
      "scope_limit":"Snapshot auditing of existing evidence; no row-by-row market verification",
      "bronze_source_root_file_counts":source_counts,
      "bronze_root_files_observed":bronze_n,
      "silver_root_files_observed":silver_root_files,"gold_root_files_observed":gold_root_files,
      "qa_run":qa.get("run_id"),"qa_scanned":qa_done,"qa_eligible":qa_eligible,
      "b_run":diag.get("run_id"),"b_diagnosed_receipt_rows":diag_total,
      "repair_run":repair.get("run_id"),"repair_pending_at_snapshot":repair_pending,
      "blocker_count":len(blockers),"blockers":blockers,
      "acceptance_rule":"Only dataset-level expected inventory, documented exceptions, semantically verified Bronze, PIT-safe Silver, formula-checked Gold and bidirectional lineage can pass",
      "decision":"DO_NOT_RELEASE"
    }
    for name,payload in (
       ("v097_QUALITY_LEDGER_LATEST.json",quality_ledger),
       ("v097_REPAIR_LEDGER_LATEST.json",repair_ledger),
       ("v097_FINAL_ACCEPTANCE_LATEST.json",gate),
    ):
       upsert(api,gates,name,payload)
    # Immutable run audit: retained even when the LATEST pointer advances.
    save(api,gates,"v097_RELEASE_GATE_%s.json"%run,gate)
    print("V097_RELEASE_GATE="+json.dumps({
        "state":gate["state"],"qa_scanned":qa_done,
        "qa_eligible":qa_eligible,"b_rows":diag_total,
        "repair_pending":repair_pending,"blockers":blockers,
        "gate_folder_id":gates
    },ensure_ascii=False))
    if os.environ.get("GITHUB_OUTPUT"):
       with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as handle:
           handle.write("release_allowed=false\n")
if __name__=="__main__":
    main()
