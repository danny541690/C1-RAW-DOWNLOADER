#!/usr/bin/env python3
"""R13 final *small* pre-migration tests, read-only and public-safe reports.
This is not production readiness: no Drive mutation, no Bronze transfer, no
global complete dataset catalogue, no transactional cross-run lock.
"""
import argparse, hashlib, io, json, os, pathlib, tempfile, urllib.request, zipfile
from v098_r11_six_source_metadata_pilot import SOURCES,service,children,unique_folder,unique_global_folder

REPO="danny541690/C1-RAW-DOWNLOADER"
PRIOR_RUN=44674769210
SNAPSHOT_NAME="r12-synthetic-ledger-snapshot"
def github_request(url):
    req=urllib.request.Request(url,headers={
        "Authorization":"Bearer "+os.environ["GITHUB_TOKEN"],
        "Accept":"application/vnd.github+json",
        "User-Agent":"JARVIS-R13-read-only-contract"})
    with urllib.request.urlopen(req,timeout=30) as res:return res.read()
def cross_run_checkpoint():
    # Independent GitHub Actions RUN uses a completed predecessor's real artifact;
    # this is recovery verification, NOT a linearizable master/lease primitive.
    index=json.loads(github_request("https://api.github.com/repos/"+REPO+
                             f"/actions/runs/{PRIOR_RUN}/artifacts?per_page=100"))
    matches=[a for a in index.get("artifacts",[]) if a["name"]==SNAPSHOT_NAME and not a.get("expired")]
    if len(matches)!=1:raise RuntimeError("PRIOR_ARTIFACT_UNAVAILABLE")
    data=github_request("https://api.github.com/repos/"+REPO+
                        f"/actions/artifacts/{matches[0]['id']}/zip")
    import sqlite3
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        members=[n for n in z.namelist() if n.endswith("state.sqlite") and not n.startswith("/")]
        if len(members)!=1:raise RuntimeError("INVALID_SNAPSHOT_CONTENTS")
        dbbytes=z.read(members[0])
    with tempfile.TemporaryDirectory() as folder:
        filename=pathlib.Path(folder)/"state.sqlite";filename.write_bytes(dbbytes)
        conn=sqlite3.connect(f"file:{filename}?mode=ro",uri=True)
        try:
            tasks=conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            closed=conn.execute("SELECT COUNT(*) FROM tasks WHERE status='COMMITTED'").fetchone()[0]
            attempts=conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            assert (tasks,closed,attempts)==(6,6,6)
        finally:conn.close()
    return {"status":"PASS","tasks":tasks,"committed":closed,"attempts":attempts,
            "scope":"CROSS_GITHUB_RUN_ARTIFACT_RESTORE_ONLY",
            "not_a_transactional_lease":True}
def drive_small_samples(source,max_size=4*1024*1024):
    # Exact source-root name resolution. No identifiers or file names are logged.
    counts={"api_pages":0};api=service()
    root=unique_global_folder(api,"C1_0.93",counts)
    raw=unique_folder(api,root,"01_RAW",counts)
    year=unique_folder(api,raw,"2026",counts) if raw else None
    src=unique_folder(api,year,source,counts) if year else None
    month=unique_folder(api,src,"2026-10",counts) if src else None
    result={"source":source,"month":"2026-10","api_pages":counts["api_pages"],
            "sample_count":0,"md5_match_count":0,"zip_crc_pass_count":0,
            "mismatch_count":0,"status":"COVERAGE_UNKNOWN"}
    if not month:return result
    files=[];stack=[month];visited=set()
    while stack and len(files)<1:
        current=stack.pop()
        if current in visited:raise RuntimeError("DIRECTORY_CYCLE")
        visited.add(current)
        for f in children(api,current,counts):
            if f["mimeType"]=="application/vnd.google-apps.folder":stack.append(f["id"])
            elif 0<int(f.get("size") or 0)<=max_size and f.get("md5Checksum"):
                files.append(f)
                break
    result["api_pages"]=counts["api_pages"]
    if not files:
        result["status"]="NO_SMALL_BINARY_SAMPLES";return result
    f=files[0]
    # Full read, strictly bounded by verified metadata size.
    payload=api.files().get_media(fileId=f["id"]).execute()
    if len(payload)>max_size:raise RuntimeError("DOWNLOAD_EXCEEDED_LIMIT")
    result["sample_count"]=1
    result["md5_match_count"]=int(hashlib.md5(payload).hexdigest()==f["md5Checksum"])
    result["mismatch_count"]=1-result["md5_match_count"]
    if payload[:4]==b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            if z.testzip() is None:result["zip_crc_pass_count"]=1
            else:result["mismatch_count"]+=1
    result["status"]="SAMPLE_BYTES_HASH_MATCH" if result["mismatch_count"]==0 else "SAMPLE_INTEGRITY_HOLD"
    result["note"]="No original file IDs, filenames, hashes, paths or source content exported"
    return result
def output(path,record):
    p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode",choices=("cross-run","sample","selftest"),required=True)
    p.add_argument("--source",choices=SOURCES)
    p.add_argument("--out",required=True)
    args=p.parse_args()
    if args.mode=="cross-run":res=cross_run_checkpoint()
    elif args.mode=="sample":
        if not args.source:p.error("--source required")
        try:res=drive_small_samples(args.source)
        except Exception as exc:
            res={"source":args.source,"status":"SCAN_ERROR","error_class":type(exc).__name__}
    else:
        assert set(SOURCES)=={"TWSE","TPEx","MOPS","NDC","TDCC","TAIFEX"}
        res={"status":"PASS","mode":"SELFTEST","public_safe":True}
    output(args.out,res)
    print(json.dumps(res))
    if res["status"] in ("SCAN_ERROR","SAMPLE_INTEGRITY_HOLD"):raise SystemExit(2)
if __name__=="__main__":main()
