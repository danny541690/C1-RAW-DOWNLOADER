#!/usr/bin/env python3
"""v0.98 copy-only Bronze transfer. No schema, PIT, numeric or source-content audit."""
import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
import datetime as dt
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SOURCE = "1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
TARGET = "13DY2S3TuC4KYr8JKiptzUeXG9xZyIzam"
CHECKPOINTS = "1LEZ9fFFBgvy-w-Ataen7JpEpoUn9inUA"
FOLDER_MIME = "application/vnd.google-apps.folder"
_THREAD_LOCAL = threading.local()
YEAR = re.compile(r"^(200[0-9]|201[0-9]|202[0-6])$")
EXCLUDED = re.compile(r"(^|/)(?:_?jarvis.*canary|.*checkpoint_canary.*|__pycache__)(?:/|$)", re.I)

def client():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google.auth.exceptions import RefreshError
    values = [os.getenv("GOOGLE_CLIENT_ID"), os.getenv("GOOGLE_CLIENT_SECRET"),
              os.getenv("GOOGLE_REFRESH_TOKEN")]
    if not all(values):
        raise RuntimeError("Google OAuth secrets missing in C1-RAW-DOWNLOADER; refuse Drive modification")
    c = Credentials(None, refresh_token=values[2], token_uri="https://oauth2.googleapis.com/token",
                    client_id=values[0], client_secret=values[1],
                    scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request())
    return build("drive", "v3", credentials=c, cache_discovery=False)

def worker_client():
    if not hasattr(_THREAD_LOCAL, "api"):
        _THREAD_LOCAL.api = client()
    return _THREAD_LOCAL.api

def children(api, parent):
    token = None
    while True:
        result = api.files().list(q=f"'{parent}' in parents and trashed = false",
            fields="nextPageToken,files(id,name,mimeType,size,md5Checksum)",
            pageSize=1000, pageToken=token, supportsAllDrives=True,
            includeItemsFromAllDrives=True).execute()
        yield from result.get("files", [])
        token = result.get("nextPageToken")
        if not token:
            break

def source_manifest(api, source=None):
    out = []
    stack = [(SOURCE, "")]
    while stack:
        fid, prefix = stack.pop()
        for item in children(api, fid):
            path = f"{prefix}/{item['name']}".lstrip("/")
            if not prefix and not YEAR.fullmatch(item["name"]):
                continue  # strict scope: year-based raw originals, not control/canary at root
            if EXCLUDED.search(path):
                continue
            if source and YEAR.fullmatch(prefix) and item["name"] != source:
                continue
            if item["mimeType"] == FOLDER_MIME:
                stack.append((item["id"], path))
            else:
                if item["mimeType"].startswith("application/vnd.google-apps."):
                    raise RuntimeError(f"Non-binary Google-native item in RAW path: {path}")
                out.append(dict(item, path=path))
    return sorted(out, key=lambda x: (x["path"], x["id"]))

def digest_media(api, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    h = hashlib.sha256()
    import tempfile
    sink = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    request = api.files().get_media(fileId=file_id, supportsAllDrives=True)
    dl = MediaIoBaseDownload(sink, request, chunksize=4 * 1024 * 1024)
    done = False
    while not done:
        _, done = dl.next_chunk(num_retries=3)
    sink.seek(0)
    while True:
        block = sink.read(4 * 1024 * 1024)
        if not block:
            break
        h.update(block)
    return h.hexdigest()

def planned_targets(api, files):
    """Only *same directory+same name* is a collision. Preserve separate paths."""
    groups = defaultdict(list)
    for f in files:
        groups[f["path"]].append(f)
    plan = []
    for path, group in sorted(groups.items()):
        first = group[0]
        plan.append((first, path, first["id"]))
        for other in group[1:]:
            # SHA verifies actual equality; MD5/size metadata is only a prefilter.
            equal = (first.get("md5Checksum") and
                     first.get("md5Checksum") == other.get("md5Checksum") and
                     first.get("size") == other.get("size") and
                     digest_media(api, first["id"]) == digest_media(api, other["id"]))
            if equal:
                plan.append((other, path, first["id"]))  # alias to canonical file
            else:
                base, ext = os.path.splitext(path)
                plan.append((other, f"{base}__src_{other['id']}{ext}", other["id"]))
    targets = {}
    for src, path, canonical in plan:
        # No two different source contents may silently claim one destination name.
        if path in targets and targets[path] != canonical:
            raise RuntimeError(f"Target collision: {path}")
        targets[path] = canonical
    return plan

def folder_for(api, path, cache):
    parent = TARGET
    for component in Path(path).parts[:-1]:
        key = (parent, component)
        if key not in cache:
            matches = [x for x in children(api, parent)
                       if x["name"] == component and x["mimeType"] == FOLDER_MIME]
            if len(matches) > 1:
                raise RuntimeError(f"Duplicate destination folder: {component}")
            if matches:
                value = matches[0]["id"]
            else:
                value = api.files().create(body={"name": component,
                    "mimeType": FOLDER_MIME, "parents": [parent]},
                    fields="id", supportsAllDrives=True).execute()["id"]
            cache[key] = value
        parent = cache[key]
    return parent

def verify_copy(api, src_id, dst_id):
    return digest_media(api, src_id) == digest_media(api, dst_id)

def copy_one(item):
    """Copy a single unique destination path, recording actual source/dest SHA."""
    src, path, canonical, parent = item[:4]
    api = worker_client()
    supplied_existing = item[4] if len(item) > 4 else None
    name = os.path.basename(path)
    source_sha = None
    attempts = []
    for retry in range(3):
        try:
            if not source_sha:
                source_sha = digest_media(api, canonical)
            # Retry MUST re-list Drive: copy may have succeeded before an API timeout.
            if retry > 0:
                supplied_existing = None
            existing = supplied_existing if supplied_existing is not None else [
                x for x in children(api, parent) if x["name"] == name
                and x["mimeType"] != FOLDER_MIME]
            if len(existing) > 1:
                raise RuntimeError("Duplicate target file name")
            if existing:
                target_sha = digest_media(api, existing[0]["id"])
                if source_sha != target_sha:
                    raise RuntimeError("Existing target byte mismatch; no overwrite")
                return dict(source_id=src["id"], canonical_id=canonical,
                    target_id=existing[0]["id"], path=path,
                    source_sha256=source_sha, target_sha256=target_sha,
                    source_bytes=int(src.get("size") or 0),
                    status="SKIP_VERIFIED",attempt=retry+1,
                    verified_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    run_id=os.getenv("GITHUB_RUN_ID"),attempt_errors=attempts)
            created = api.files().copy(fileId=canonical,
                body={"name":name,"parents":[parent]},
                fields="id,name,size", supportsAllDrives=True).execute()
            existing.append({"id":created["id"],"name":name,
                             "mimeType":"application/octet-stream"})
            target_sha = digest_media(api, created["id"])
            if source_sha != target_sha:
                raise RuntimeError("Copied file SHA mismatch; original target retained")
            return dict(source_id=src["id"], canonical_id=canonical,
                target_id=created["id"], path=path,
                source_sha256=source_sha, target_sha256=target_sha,
                source_bytes=int(src.get("size") or 0),
                status="COPY_SHA_PASS",attempt=retry+1,
                verified_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                run_id=os.getenv("GITHUB_RUN_ID"),attempt_errors=attempts)
        except Exception as exc:
            attempts.append({"attempt":retry+1,"error_type":type(exc).__name__})
            # A pooled Drive connection can be invalid after OAuth refresh or broken pipe.
            # A new client on retry avoids reusing the poisoned httplib2 transport.
            if retry < 2 and not isinstance(exc, RuntimeError):
                try:
                    _THREAD_LOCAL.api = client()
                    api = _THREAD_LOCAL.api
                except Exception:
                    pass
            if retry == 2:
                return dict(source_id=src["id"], canonical_id=canonical,
                    path=path,source_sha256=source_sha,
                    status="HOLD",attempt=3,error_type=type(exc).__name__,
                    run_id=os.getenv("GITHUB_RUN_ID"),attempt_errors=attempts)
            time.sleep(min(2 ** retry, 8))


def read_checkpoint(api, run_name):
    name = f"v098_copy_checkpoint_{run_name}.json"
    matches = [f for f in children(api, CHECKPOINTS) if f["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Checkpoint duplicate name; refuse to choose")
    if not matches:
        return []
    data = api.files().get_media(fileId=matches[0]["id"]).execute()
    records = json.loads(data)
    if not isinstance(records, list) or any("source_id" not in x for x in records):
        raise RuntimeError("Checkpoint invalid")
    return records

def save_checkpoint(api, records, run_name):
    """Retry transient Drive I/O with a NEW connection, keeping one canonical ledger ID.

    A failed upload can already have reached Drive. Repeating update by the same
    file ID is idempotent; never create a second same-name checkpoint.
    """
    from googleapiclient.http import MediaIoBaseUpload
    name = f"v098_copy_checkpoint_{run_name}.json"
    blob = json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")
    last_error = None
    for attempt in range(8):
        try:
            # Stale OAuth + httplib2 connections caused BrokenPipeError after ~2h.
            fresh_api = client() if attempt else api
            matches = [f for f in children(fresh_api, CHECKPOINTS) if f["name"] == name]
            if len(matches) > 1:
                raise RuntimeError("Duplicate checkpoint name; refuse update")
            media = MediaIoBaseUpload(io.BytesIO(blob), mimetype="application/json",
                                      resumable=True)
            if matches:
                fid = matches[0]["id"]
                fresh_api.files().update(fileId=fid, media_body=media,
                                         supportsAllDrives=True).execute(num_retries=3)
            else:
                fresh_api.files().create(body={"name": name,"parents":[CHECKPOINTS]},
                    media_body=media,fields="id",supportsAllDrives=True).execute(num_retries=3)
            return
        except RuntimeError:
            raise
        except Exception as exc:
            last_error = exc
            print(json.dumps({"checkpoint_retry":attempt+1,
                "source":run_name,"error_type":type(exc).__name__}), flush=True)
            time.sleep(min(2**attempt,30))
    raise RuntimeError(f"Checkpoint could not be committed after 8 attempts: {type(last_error).__name__}") from last_error

def self_test():
    import tempfile
    payload = b"JARVIS-v098-binary-payload" * (1024 * 1024)  # 25+MB
    expected = hashlib.sha256(payload).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "original.bin"
        p.write_bytes(payload)
        assert hashlib.sha256(p.read_bytes()).hexdigest() == expected
        seen = set()
        def worker(_):
            # Simulates contention; test is NOT real remote Drive/CAS validation.
            import threading
            with lock:
                if expected in seen:
                    return "SKIP"
                seen.add(expected)
                return "COPY"
        import threading
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(worker, range(8)))
        assert results.count("COPY") == 1
        assert results.count("SKIP") == 7
        assert all(worker(i) == "SKIP" for i in range(8))  # simulated replay
    print(json.dumps({"self_test": "PASS", "size_bytes": len(payload),
                      "sha256": expected, "parallel_workers": 8,
                      "copy": 1, "skips": 15, "real_drive_test": False}))



OFFICIAL_SOURCES = ("TWSE", "TPEx", "MOPS", "NDC", "TDCC", "TAIFEX")

def quick_canary_manifest(api):
    """One file per official source from 2026. Does NOT inventory 78k files."""
    roots = [x for x in children(api, SOURCE) if x["name"] == "2026"
             and x["mimeType"] == FOLDER_MIME]
    if len(roots) != 1:
        raise RuntimeError("Expected exactly one source year 2026")
    year = roots[0]["id"]
    source_dirs = list(children(api, year))
    selected = []
    for source in OFFICIAL_SOURCES:
        parents = [x for x in source_dirs if x["name"] == source and
                   x["mimeType"] == FOLDER_MIME]
        if len(parents) != 1:
            raise RuntimeError(f"Source folder missing or duplicate: {source}")
        months = [x for x in children(api, parents[0]["id"])
                  if x["mimeType"] == FOLDER_MIME]
        months.sort(key=lambda x: x["name"], reverse=True)
        candidate = None
        for month in months:
            # Choose a source-specific *real* original; no numeric/format interpretation.
            candidates = (x for x in children(api, month["id"])
                          if x["mimeType"] != FOLDER_MIME and
                          not x["mimeType"].startswith("application/vnd.google-apps.") and
                          0 < int(x.get("size") or 0) <= 40_000_000)
            if source == "TWSE":
                eligible = [x for x in candidates if int(x.get("size") or 0) >= 1_000_000]
                if not eligible:
                    continue
                candidate = sorted(eligible, key=lambda x: x["id"])[0]
            else:
                candidate = next(candidates, None)
            if candidate:
                candidate = dict(candidate, source=source,
                                 path=f"2026/{source}/{month['name']}/{candidate['name']}")
                break
        if not candidate:
            raise RuntimeError(f"No eligible binary 2026 canary source: {source}")
        selected.append(candidate)
    if len(selected) != 6 or max(int(x["size"]) for x in selected) < 1_000_000:
        raise RuntimeError("Canary coverage invalid")
    return selected

def live_canary(api, files, workers):
    """Real Drive copy+SHA, parallel distinct files, interrupted batch then replay."""
    # Exactly one real file from each of the six official source lanes.
    picks = files
    if len(picks) != 6 or len({f["source"] for f in picks}) != 6:
        raise RuntimeError("Expected six distinct sources")
    dirname = "__V098_MIGRATION_CANARY_COPY_ONLY__"
    matching = [f for f in children(api, TARGET) if f["name"] == dirname]
    if len(matching) > 1:
        raise RuntimeError("Duplicate canary directories")
    if matching and matching[0]["mimeType"] != FOLDER_MIME:
        raise RuntimeError("Canary directory name occupied by file")
    if matching:
        parent = matching[0]["id"]
    else:
        parent = api.files().create(body={"name": dirname, "mimeType": FOLDER_MIME,
            "parents": [TARGET]}, fields="id", supportsAllDrives=True).execute()["id"]
    tasks = [(f, f["id"] + "__" + f["name"], f["id"], parent) for f in picks]
    # First half acts as interrupted earlier run. Complete the rest, then replay.
    first = [copy_one(t) for t in tasks[:3]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        resumed = list(pool.map(copy_one, tasks))
        repeated = list(pool.map(copy_one, tasks))
    assert all(x["status"] in {"COPY_SHA_PASS", "SKIP_VERIFIED"} for x in first + resumed + repeated)
    assert all(x["status"] == "SKIP_VERIFIED" for x in repeated)
    ids = [x["target_id"] for x in repeated]
    assert len(set(ids)) == 6
    # Confirm each target name remains unique after interruption and replay.
    present = list(children(api, parent))
    for _, path, _, _ in tasks:
        assert sum(x["name"] == os.path.basename(path) for x in present) == 1
    result = {"live_canary": "PASS", "source_files": 6, "min_bytes": min(int(f["size"]) for f in picks),
              "interrupted_first_batch": 3, "parallel_workers": workers,
              "replayed_skips": 6, "duplicates": 0}
    print(json.dumps(result, ensure_ascii=False))
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["self-test", "preflight", "canary", "migrate"], required=True)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--source", choices=OFFICIAL_SOURCES)
    p.add_argument("--deadline-seconds", type=int, default=0)
    p.add_argument("--report-file", default="")
    p.add_argument("--limit", type=int, default=0,
                   help="Bounded live pilot: maximum original identities per source; 0 = all")
    p.add_argument("--run-key", default=os.getenv("GITHUB_RUN_ID", "local"))
    a = p.parse_args()
    if a.mode == "self-test":
        self_test()
        return
    if not 1 <= a.workers <= 6:
        raise ValueError("workers must be 1..6")
    api = client()
    if a.mode == "canary":
        live_canary(api, quick_canary_manifest(api), a.workers)
        return
    files = source_manifest(api, a.source)
    plan = planned_targets(api, files)
    if a.limit < 0:
        raise ValueError("limit must be nonnegative")
    if a.mode == "preflight":
        print(json.dumps({"source_files":len(files),"planned_source_ids":len(plan),
                          "mode":a.mode,"source":a.source}))
        return
    cache = {}
    ledger_key = a.source or a.run_key
    prior_all = read_checkpoint(api, ledger_key)
    # Upgrade older test receipts lacking written hashes by byte-verifying again.
    prior = [r for r in prior_all if r.get("status") != "HOLD" and
               r.get("source_sha256") and r.get("source_sha256") == r.get("target_sha256")]
    prior_by_id = {r["source_id"]: r for r in prior}
    if len(prior_by_id) != len(prior):
        raise RuntimeError("Ledger has duplicate source file ID")
    all_by_path = defaultdict(list)
    for record in plan:
        all_by_path[record[1]].append(record)
    pending = [p for p in plan if p[0]["id"] not in prior_by_id]
    if a.limit:
        pending = pending[:a.limit]
    requested_paths = set(p[1] for p in pending)
    copy_candidates = []
    for path in sorted(requested_paths):
        group = all_by_path[path]
        canonical = group[0]
        if canonical[0]["id"] not in prior_by_id:
            copy_candidates.append(canonical)
    folders = [(src, path, canonical_id, folder_for(api, path, cache))
               for src, path, canonical_id in copy_candidates]
    # One target folder listing per folder (not one listing for every file).
    target_index = {}
    for parent in {p for _, _, _, p in folders}:
        mapping = defaultdict(list)
        for item in children(api, parent):
            if item["mimeType"] != FOLDER_MIME:
                mapping[item["name"]].append(item)
        target_index[parent] = mapping
    tasks = [(src,path,canonical_id,parent,
              list(target_index[parent].get(os.path.basename(path), [])))
             for src,path,canonical_id,parent in folders]
    results = list(prior)
    started = time.monotonic()
    print(json.dumps({"source":a.source,"originals":len(plan),"verified_prior":len(prior),
        "pending":len(pending),"batch_size":100}),flush=True)
    for start in range(0, len(tasks), 100):
        if a.deadline_seconds and time.monotonic() - started >= a.deadline_seconds:
            break
        batch = tasks[start:start+100]
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            for row in pool.map(copy_one, batch):
                results.append(row)
        save_checkpoint(api, results, ledger_key)
    by_path = {r["path"]:r for r in results}
    completed_ids = {r["source_id"] for r in results}
    for path in sorted(requested_paths):
        status = by_path.get(path)
        if not status:
            continue  # time-budgeted run: this path has not been copied yet
        for src, _, canonical in all_by_path[path]:
            if src["id"] not in completed_ids:
                results.append({"source_id":src["id"],"canonical_id":canonical,
                    "target_id":status.get("target_id"),"path":path,
                    "source_sha256":status.get("source_sha256"),
                    "target_sha256":status.get("target_sha256"),
                    "source_bytes":int(src.get("size") or 0),
                    "status":"ALIAS_SHA_PASS" if status["status"] != "HOLD" else "HOLD"})
                completed_ids.add(src["id"])
    if len(completed_ids) != len(results):
        raise RuntimeError("Duplicate ledger source IDs")
    save_checkpoint(api, results, ledger_key)
    tally = defaultdict(int)
    for row in results:
        tally[row["status"]] += 1
    summary = {"run":a.run_key,"source":a.source,"source_ids":len(plan),
               "recorded_source_ids":len(results), "remaining":len(plan)-len(results),
               "statuses":dict(tally)}
    if a.report_file:
        path = Path(a.report_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False))
    if tally["HOLD"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
