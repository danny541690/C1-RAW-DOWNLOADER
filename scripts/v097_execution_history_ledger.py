#!/usr/bin/env python3
"""JARVIS v0.97 GitHub execution ledger -> Google Drive.

One append/update master index (JSON + CSV) and one immutable, category-sorted
report for each COMPLETED GitHub Actions run attempt. Failed job/step details
are included; full raw logs remain linked to GitHub (bounded excerpts only).
This collector NEVER runs data pipelines, Silver, or Gold.
"""
import csv
import io
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import PurePosixPath

import requests
from googleapiclient.http import MediaInMemoryUpload

from scripts.v097_bronze_first_pipeline import (
    service, call, folder, makefolder, match, load_json, put_once
)

SCHEMA = "v097_execution_history_master_v1"
REPORT_SCHEMA = "v097_execution_history_report_v1"
MASTER = "v097_EXECUTION_MASTER_INDEX.json"
MASTER_CSV = "v097_EXECUTION_MASTER_INDEX.csv"
CHECKPOINT = "v097_EXECUTION_HISTORY_COLLECTOR_CK.json"
SOURCES = ("TWSE", "TPEx", "MOPS", "TDCC", "TAIFEX", "NDC", "FinMind")
LIMIT = max(1, min(45, int(os.getenv("HISTORY_BATCH", "25"))))
REPO = os.getenv("GH_REPO", "danny541690/C1-RAW-DOWNLOADER")
TOKEN = os.environ.get("GH_TOKEN")
BASE = "https://api.github.com/repos/" + REPO
CATALOG = ("BRONZE_RELEASE", "BRONZE_QA", "SOURCE_FORMAT", "SOURCE_REPAIR",
           "EXECUTION_AUDIT", "OTHER")
MAX_LOG_JOBS = 4
MAX_ERROR_LINES = 36
ERROR_REGEX = re.compile(
    r"(?i)(traceback|exception|fatal|error[: ]|##\[error\]|assertionerror|"
    r"process completed with exit code|failed|permission denied|timed out)"
)

def now():
    return datetime.now(timezone.utc).isoformat()

def classify(name):
    n = name.lower()
    if "bronze v2.1" in n or "ready release" in n:
        return "BRONZE_RELEASE"
    if "format" in n or "parser" in n or "native historical" in n or "translation" in n:
        return "SOURCE_FORMAT"
    if ("repair" in n or "recover" in n or "salvage" in n or "reconcile" in n
            or "a1-a5" in n or "exception" in n):
        return "SOURCE_REPAIR"
    if "bronze" in n or "silver ready" in n or "checksum" in n or "content qa" in n:
        return "BRONZE_QA"
    if "watchdog" in n or "audit" in n or "execution" in n or "monitor" in n:
        return "EXECUTION_AUDIT"
    return "OTHER"

def identify_sources(run, jobs):
    text = " ".join([run.get("name", "")] + [x.get("name", "") for x in jobs])
    return [src for src in SOURCES if re.search(r"\b" + re.escape(src) + r"\b", text, re.I)]

def gh(path, *, raw=False):
    if not TOKEN:
        raise RuntimeError("GH_TOKEN_REQUIRED")
    response = requests.get(
        "https://api.github.com" + path,
        headers={"Authorization": "Bearer " + TOKEN,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        timeout=45
    )
    response.raise_for_status()
    return response.content if raw else response.json()

def runs_page(page):
    if page < 1 or page > 10000:
        raise ValueError("INVALID_PAGE")
    data = gh("/repos/" + REPO + "/actions/runs?per_page=100&page=" + str(page))
    return data.get("workflow_runs", [])

def job_list(run):
    results = []
    page = 1
    while True:
        obj = gh("/repos/" + REPO + "/actions/runs/" + str(run["id"]) +
                 "/jobs?per_page=100&page=" + str(page))
        results.extend(obj.get("jobs", []))
        if len(results) >= obj.get("total_count", 0) or not obj.get("jobs"):
            break
        page += 1
        if page > 30:
            raise RuntimeError("JOB_PAGE_BOUND_REACHED:" + str(run["id"]))
    return results

def job_error_lines(job):
    """Full run logs stay at GitHub. Only bounded relevant diagnostics in Drive."""
    if job.get("conclusion") not in ("failure", "timed_out", "action_required"):
        return []
    try:
        body = gh("/repos/" + REPO + "/actions/jobs/" + str(job["id"]) + "/logs",
                  raw=True)
        text = body.decode("utf-8", "replace")
        selected = [line[:750] for line in text.splitlines()
                    if ERROR_REGEX.search(line)]
        return selected[-MAX_ERROR_LINES:]
    except Exception as exc:
        return ["LOG_RETRIEVAL_UNAVAILABLE:" + type(exc).__name__ +
                "; see GitHub job URL"]

def report_for(run):
    jobs = job_list(run)
    compact = []
    errors = []
    log_jobs = 0
    for job in jobs:
        steps = [{
            "number": step.get("number"),
            "name": step.get("name"),
            "status": step.get("status"),
            "conclusion": step.get("conclusion"),
            "started_at": step.get("started_at"),
            "completed_at": step.get("completed_at")
        } for step in job.get("steps", [])]
        bad_steps = [s for s in steps if s.get("conclusion") in
                     ("failure", "timed_out", "action_required")]
        excerpts = []
        if (job.get("conclusion") in ("failure", "timed_out", "action_required")
                and log_jobs < MAX_LOG_JOBS):
            excerpts = job_error_lines(job)
            log_jobs += 1
        item = {
            "job_id": job.get("id"),
            "job_name": job.get("name"),
            "conclusion": job.get("conclusion"),
            "status": job.get("status"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
            "steps": steps,
            "error_log_excerpt": excerpts,
            "github_job_url": job.get("html_url")
        }
        compact.append(item)
        if job.get("conclusion") in ("failure", "timed_out", "action_required"):
            errors.append({
                "job_id": job.get("id"),
                "job_name": job.get("name"),
                "failed_steps": [s["name"] for s in bad_steps],
                "error_log_excerpt": excerpts,
                "github_job_url": job.get("html_url")
            })
    category = classify(run.get("name", ""))
    source = identify_sources(run, jobs)
    report = {
        "schema": REPORT_SCHEMA,
        "run_id": run["id"],
        "run_attempt": run.get("run_attempt", 1),
        "workflow": run.get("name", ""),
        "category": category,
        "sources": source,
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "event": run.get("event"),
        "branch": run.get("head_branch"),
        "head_sha": run.get("head_sha"),
        "created_at": run.get("created_at"),
        "run_started_at": run.get("run_started_at"),
        "updated_at": run.get("updated_at"),
        "github_url": run.get("html_url"),
        "jobs": compact,
        "job_counts": dict(Counter(x.get("conclusion") or x.get("status")
                                   for x in jobs)),
        "errors": errors,
        "errors_captured": len(errors),
        "raw_logs_storage": "GITHUB_ACTIONS_JOB_LOGS_LINKED",
        "raw_logs_archived_in_drive": False,
        "data_transformations_executed_by_collector": False,
        "silver_gold_executed_by_collector": False
    }
    return report

def master_row(report, drive_path, drive_id):
    return {
        "run_id": report["run_id"],
        "attempt": report["run_attempt"],
        "workflow": report["workflow"],
        "category": report["category"],
        "sources": ",".join(report["sources"]),
        "status": report["status"],
        "conclusion": report["conclusion"],
        "created_at": report["created_at"],
        "updated_at": report["updated_at"],
        "error_jobs": report["errors_captured"],
        "error_summary": "; ".join(
            (e["job_name"] + ": " + ", ".join(e["failed_steps"][:2]))[:110]
            for e in report["errors"][:4]
        ),
        "report_path": drive_path,
        "report_file_id": drive_id,
        "github_url": report["github_url"]
    }

COLUMNS = (
    "run_id", "attempt", "workflow", "category", "sources", "status", "conclusion",
    "created_at", "updated_at", "error_jobs", "error_summary",
    "report_path", "report_file_id", "github_url"
)

def to_csv(records):
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=COLUMNS)
    w.writeheader()
    for r in sorted(records.values(), key=lambda x: (x["run_id"], x["attempt"]),
                    reverse=True):
        safe = {}
        for key in COLUMNS:
            value = str(r.get(key, "") if r.get(key) is not None else "")
            # Prevent CSV formula injection when opened in a spreadsheet.
            if value and value[0] in ("=", "+", "-", "@"):
                value = "'" + value
            safe[key] = value
        w.writerow(safe)
    return out.getvalue().encode("utf-8-sig")

def upload_master(api, parent, name, body, mime):
    existing = match(api, parent, name)
    upload = MediaInMemoryUpload(body, mimetype=mime, chunksize=1024*1024,
                                 resumable=True)
    if existing:
        req = api.files().update(fileId=existing["id"], media_body=upload,
                                 fields="id")
    else:
        req = api.files().create(body={"name": name, "parents": [parent],
                                       "mimeType": mime},
                                 media_body=upload, fields="id")
    result = None
    while result is None:
        _, result = req.next_chunk(num_retries=3)
    return result["id"]

def selftest():
    assert classify("JARVIS v097 Bronze v2.1 Direct READY Release Only") == "BRONZE_RELEASE"
    assert classify("JARVIS v097 TAIFEX Source-Native CSV Format Translation") == "SOURCE_FORMAT"
    assert classify("JARVIS v097 A1-A5 automatic TDCC recovery") == "SOURCE_REPAIR"
    assert identify_sources({"name": "Seven Sources"},
                            [{"name": "source-parser (TWSE)"}, {"name": "QA TDCC"}]) == ["TWSE", "TDCC"]
    rows = {"1:1": {k: "" for k in COLUMNS}}
    rows["1:1"]["workflow"] = "=HYPERLINK(0)"
    assert "'=HYPERLINK" in to_csv(rows).decode("utf-8-sig")
    fake = {"run_id": 123, "run_attempt": 1, "name": "Test",
            "status": "completed", "conclusion": "failure",
            "html_url": "https://github.com/example"}
    report = {**fake, "schema": REPORT_SCHEMA, "workflow": "Test",
              "category": "OTHER", "sources": [], "errors_captured": 0, "errors": [],
              "created_at": "2026-11-17T00:00:00Z",
              "updated_at": "2026-11-17T00:00:01Z",
              "github_url": "https://github.com/example"}
    assert master_row(report, "/test", "a")["report_file_id"] == "a"
    print("EXECUTION_HISTORY_SELFTEST_PASS")

def run():
    if "/" not in REPO or REPO.count("/") != 1:
        raise RuntimeError("INVALID_GH_REPO")
    api = service()
    root = folder(api, "root", "ChatGPT資料存取")
    root = folder(api, root, "JARVIS_C1_v097_LIFECYCLE")
    quality = folder(api, root, "03_DATA_QUALITY")
    history = makefolder(api, quality, "08_EXECUTION_HISTORY")
    index_folder = makefolder(api, history, "01_MASTER_INDEX")
    reports_folder = makefolder(api, history, "02_REPORTS")
    ctl = folder(api, root, "00_SYSTEM_CONTROL")
    ck_folder = folder(api, ctl, "04_CHECKPOINTS")

    mf = match(api, index_folder, MASTER)
    m = load_json(api, mf["id"]) if mf else {
        "schema": SCHEMA, "repo": REPO, "records": {}, "created_at": now()
    }
    if m.get("schema") != SCHEMA or m.get("repo") != REPO:
        raise RuntimeError("EXECUTION_MASTER_SCHEMA_OR_REPO_MISMATCH")
    index = m["records"]
    cf = match(api, ck_folder, CHECKPOINT)
    ck = load_json(api, cf["id"]) if cf else {
        "schema": SCHEMA, "backfill_page": 2, "processed_runs": 0
    }
    if ck.get("schema") != SCHEMA:
        raise RuntimeError("EXECUTION_CHECKPOINT_SCHEMA_MISMATCH")
    page = int(ck.get("backfill_page", 2))
    newest = runs_page(1)
    older = runs_page(page)
    candidates = []
    for r in newest + older:
        key = str(r["id"]) + ":" + str(r.get("run_attempt", 1))
        if r.get("status") == "completed" and key not in index and (
            r.get("conclusion") is not None
        ) and r.get("id"):
            if r["id"] not in {x["id"] for x in candidates}:
                candidates.append(r)
    # Keep most recent first, then advance historical pages when exhausted.
    selected = candidates[:LIMIT]
    folder_cache = {}
    created = 0
    for item in selected:
        report = report_for(item)
        month = (report["created_at"] or "unknown")[:7]
        if not re.fullmatch(r"\d{4}-\d{2}", month):
            month = "UNKNOWN_MONTH"
        category = report["category"]
        folder_key = (month, category)
        if folder_key not in folder_cache:
            month_folder = makefolder(api, reports_folder, month)
            folder_cache[folder_key] = makefolder(api, month_folder, category)
        parent = folder_cache[folder_key]
        filename = "RUN_%s_ATTEMPT_%s.json" % (
            report["run_id"], report["run_attempt"])
        rid = put_once(api, parent, filename, report)
        path = ("ChatGPT資料存取/JARVIS_C1_v097_LIFECYCLE/"
                "03_DATA_QUALITY/08_EXECUTION_HISTORY/02_REPORTS/"
                + month + "/" + category + "/" + filename)
        key = str(report["run_id"]) + ":" + str(report["run_attempt"])
        index[key] = master_row(report, path, rid)
        created += 1

    # Advance older-page scanner only when its remaining completed attempts
    # are already indexed; this prevents skipped history after partial runs.
    if older and all(
        (r.get("status") != "completed" or r.get("conclusion") is None
         or (str(r["id"]) + ":" + str(r.get("run_attempt", 1))) in index)
        for r in older
    ):
        ck["backfill_page"] = page + 1
    elif not older:
        ck["backfill_completed_at"] = now()

    m["updated_at"] = now()
    m["report_count"] = len(index)
    m["status_counts"] = dict(Counter(r["conclusion"] for r in index.values()))
    m["category_counts"] = dict(Counter(r["category"] for r in index.values()))
    m["backfill_page"] = ck.get("backfill_page", page)
    # Publish per-run immutable reports FIRST, then index, so the master
    # never points at an upload that does not exist.
    raw = json.dumps(m, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    mid = upload_master(api, index_folder, MASTER, raw, "application/json")
    csv_id = upload_master(api, index_folder, MASTER_CSV, to_csv(index), "text/csv")
    ck["processed_runs"] = len(index)
    ck["last_run"] = os.getenv("GITHUB_RUN_ID", "manual")
    ck["updated_at"] = now()
    upload_master(api, ck_folder, CHECKPOINT,
                  json.dumps(ck, ensure_ascii=False).encode("utf-8"),
                  "application/json")
    # Verify both files exist; do not claim success from create request alone.
    assert match(api, index_folder, MASTER)["id"] == mid
    assert match(api, index_folder, MASTER_CSV)["id"] == csv_id
    print("EXECUTION_HISTORY_REPORT=" + json.dumps({
        "current_run": ck["last_run"], "new_reports": created,
        "total_reports": len(index),
        "historical_page": ck.get("backfill_page", page),
        "status_counts": m["status_counts"],
        "category_counts": m["category_counts"],
        "master_json_file_id": mid, "master_csv_file_id": csv_id,
        "master_drive_path": (
            "ChatGPT資料存取/JARVIS_C1_v097_LIFECYCLE/"
            "03_DATA_QUALITY/08_EXECUTION_HISTORY/01_MASTER_INDEX"),
        "report_drive_path": (
            "ChatGPT資料存取/JARVIS_C1_v097_LIFECYCLE/"
            "03_DATA_QUALITY/08_EXECUTION_HISTORY/02_REPORTS"),
        "silver_gold_executed": False
    }, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    if sys.argv[1:] == ["selftest"]:
        selftest()
    elif not sys.argv[1:]:
        run()
    else:
        raise SystemExit("usage: selftest | (no args)")
