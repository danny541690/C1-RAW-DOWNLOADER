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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SOURCE = "1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
TARGET = "13DY2S3TuC4KYr8JKiptzUeXG9xZyIzam"
CHECKPOINTS = "1LEZ9fFFBgvy-w-Ataen7JpEpoUn9inUA"
FOLDER_MIME = "application/vnd.google-apps.folder"
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

def source_manifest(api):
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
    src, path, canonical, parent = item
    api = client()
    name = os.path.basename(path)
    for retry in range(3):
        try:
            existing = [x for x in children(api, parent) if x["name"] == name
                        and x["mimeType"] != FOLDER_MIME]
            same = [x for x in existing if verify_copy(api, canonical, x["id"])]
            if len(existing) > 1:
                # Existing duplicate copies must be reported, not silently deleted.
                raise RuntimeError(f"Duplicate target name: {path}, count={len(existing)}")
            if same:
                return dict(source_id=src["id"], canonical_id=canonical,
                            target_id=same[0]["id"], path=path, status="SKIP_VERIFIED")
            if existing:
                raise RuntimeError(f"Target name exists with different bytes: {path}")
            created = api.files().copy(fileId=canonical,
                body={"name": name, "parents": [parent]},
                fields="id,name,size", supportsAllDrives=True).execute()
            if not verify_copy(api, canonical, created["id"]):
                raise RuntimeError(f"SHA256 mismatch, retain target for inspection: {path}")
            return dict(source_id=src["id"], canonical_id=canonical,
                        target_id=created["id"], path=path, status="COPY_SHA_PASS")
        except Exception as exc:
            if retry == 2:
                return dict(source_id=src["id"], path=path,
                            status="HOLD", error=str(exc))
            time.sleep(min(2 ** retry, 8))

def save_checkpoint(api, records, run_name):
    from googleapiclient.http import MediaIoBaseUpload
    name = f"v098_copy_checkpoint_{run_name}.json"
    blob = json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")
    matches = [f for f in children(api, CHECKPOINTS) if f["name"] == name]
    if len(matches) > 1:
        raise RuntimeError("Checkpoint duplicate name; refuse update")
    media = MediaIoBaseUpload(io.BytesIO(blob), mimetype="application/json", resumable=True)
    if matches:
        api.files().update(fileId=matches[0]["id"], media_body=media,
                           supportsAllDrives=True).execute()
    else:
        api.files().create(body={"name": name, "parents": [CHECKPOINTS]},
                           media_body=media, fields="id",
                           supportsAllDrives=True).execute()

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
              "replayed_skips": 6, "duplicates": 0, "target_ids": ids}
    print(json.dumps(result, ensure_ascii=False))
    return result

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["self-test", "preflight", "canary", "migrate"], required=True)
    p.add_argument("--workers", type=int, default=3)
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
    files = source_manifest(api)
    plan = planned_targets(api, files)
    print(json.dumps({"source_files": len(files), "planned_source_ids": len(plan),
                      "mode": a.mode, "target": TARGET}))
    if a.mode == "preflight":
        return
    # One workflow is the only writer. GitHub workflow concurrency controls runs.
    cache = {}
    # Alias groups must NOT be submitted twice; parallel copies would race.
    unique = {}
    for src, path, canonical in plan:
        unique.setdefault(path, (src, path, canonical))
    tasks = [(src, path, canonical, folder_for(api, path, cache))
             for src, path, canonical in unique.values()]
    results = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for future in as_completed([pool.submit(copy_one, task) for task in tasks]):
            results.append(future.result())
            if len(results) % 50 == 0:
                save_checkpoint(api, results, a.run_key)
    # Reconstruct one result for every source identity, including exact aliases.
    by_path = {r['path']: r for r in results}
    alias_results = [dict(source_id=src['id'], canonical_id=canonical,
                          target_id=by_path[path].get('target_id'), path=path,
                          status=('ALIAS_SHA_PASS' if by_path[path]['status'] != 'HOLD' else 'HOLD'))
                     for src, path, canonical in plan if src['id'] != canonical]
    results.extend(alias_results)
    save_checkpoint(api, results, a.run_key)
    tally = defaultdict(int)
    for r in results:
        tally[r["status"]] += 1
    print(json.dumps({"run": a.run_key, "statuses": dict(tally),
                      "source_ids": len(plan)}, ensure_ascii=False))
    if tally['HOLD']:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
