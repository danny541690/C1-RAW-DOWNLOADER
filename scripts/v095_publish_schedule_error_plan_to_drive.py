#!/usr/bin/env python3
"""Immutable, SHA-readback publication of v0.95 schedule/error/roadmap to Drive Operations.

Content is a dated audit snapshot; do not overwrite previous versions. Fail
closed on missing artifacts, missing credential, duplicate SHA name, or readback.
"""
import datetime as dt,hashlib,json,os,pathlib
from scripts.v095_market_release_calendar_drive_archive import drive,archive,OPS
SOURCE=pathlib.Path("governance/v095/JARVIS_V095_SCHEDULE_ERROR_PLAN_20261108.md")
OUT=pathlib.Path("v095_schedule_governance")
CRONS={
    "TWSE":"4,19,34,49 * * * *",
    "TPEx":"6,21,36,51 * * * *",
    "MOPS":"8,38 * * * *",
    "TDCC":"10,40 * * * *",
    "TAIFEX":"12,42 * * * *",
    "NDC":"14,44 * * * *",
}
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    if not SOURCE.is_file():raise FileNotFoundError(str(SOURCE))
    content=SOURCE.read_bytes()
    if len(content)<8000:raise ValueError("REPORT_UNEXPECTEDLY_SHORT")
    OUT.mkdir(exist_ok=True)
    # Validate schedules against the *current* GitHub workflow files, not memory.
    for source,expected in CRONS.items():
        wf=pathlib.Path(".github/workflows/v095-2026-source-"+source.lower()+".yml")
        if not wf.exists():raise FileNotFoundError(str(wf))
        if ("cron: '"+expected+"'") not in wf.read_text():
            raise ValueError("SOURCE_SCHEDULE_CHANGED_"+source)
    machine={
      "schema":"JARVIS_V095_SCHEDULE_ERROR_PLAN_R1",
      "as_of":"2026-11-08",
      "source_repo":"danny541690/C1-RAW-DOWNLOADER",
      "source_run_id":"42458778942",
      "publish_run_id":os.getenv("GITHUB_RUN_ID"),
      "schedule_timezone":"UTC",
      "source_cron":CRONS,
      "latest_source_success":{"TWSE":{"candidate_bsg_days":10,"lineage_checks_passed":10,
          "next_offset":186,"year_complete":False,"pit":False},
         "TPEx":{"candidate_bsg_days":10,"lineage_checks_passed":10,
          "next_offset":186,"year_complete":False,"pit":False},
         "MOPS":{"bronze_candidate_new":6,"archive_blocked":0,
          "silver_typed_certified":False,"pit":False},
         "TDCC":{"bronze_candidate_new":0,"unchanged_good_archives":3,
          "cached_quarantine_skipped":1,"silver_typed_certified":False},
         "TAIFEX":{"bronze_candidate_new":0,"source_or_format_exceptions":214,
          "immutable_exception_count":213,"silver_typed_certified":False},
         "NDC":{"official_observation_months_reused":321,
          "historical_release_timestamp_certified":False}},
      "root_cause_fixed":"Legacy quarantine JSON literal backslash-n suffix; SHA-safe reader added",
      "latest_source_error_counts":{"TAIFEX":{"TAIFEX_SPREAD_DATE_OUTSIDE_REQUEST_MONTH":31,
         "UNSAFE_ARCHIVE":116,"TAIFEX_NATIVE_ZIP_NOT_SINGLE_CSV":61,
         "RESPONSE_DATE_OUTSIDE_REQUEST":1,"ZIP_EXPANSION_LIMIT":4,
         "V093_MONTH_FOLDER_NOT_UNIQUE_OR_MISSING":1}},
      "quarantined_not_retried_unless_validator_changes":True,
      "official_market_and_release_calendar_complete":False,
      "year_data_complete":False,"PIT_APPROVED":False,"RELEASE_APPROVED":False,
      "report_file":SOURCE.name,"report_sha256":sha(content),
      "target_drive_operations_folder":OPS,
      "workflow_run_url":"https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/42458778942",
    }
    machine_path=OUT/"JARVIS_V095_SCHEDULE_ERROR_PLAN_20261108.json"
    machine_path.write_text(json.dumps(machine,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    d=drive()
    evidence=[archive(d,SOURCE),archive(d,machine_path)]
    receipt={"result":"DRIVE_SHA_READBACK_PASS","run_id":os.getenv("GITHUB_RUN_ID"),
       "target_folder_id":OPS,"files":evidence,
       "all_source_data_complete":False,"PIT_certified":False}
    p=OUT/"drive_publication_receipt.json"
    p.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=="__main__":main()
