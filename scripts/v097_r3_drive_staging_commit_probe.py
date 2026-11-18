"""R3 isolated staging-only Drive commit/readback probe.

Creates at most one immutable receipt per GitHub Run under its own staging
folder in 03_DATA_QUALITY. Never touches Bronze, R1/V3 checkpoints, or Master.
"""
from __future__ import annotations
import hashlib, json, os, sys
from datetime import datetime, timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_autopilot import source_api

FOLDER = "R3_STAGING_PREFLIGHT_ISOLATED"
def canon(v): return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode("utf-8")
def probe():
    run=os.environ.get("GITHUB_RUN_ID")
    if not run or not run.isdigit(): raise RuntimeError("GITHUB_RUN_ID_REQUIRED")
    api,control,quality,match,load_json,_,_,call=source_api()
    folder=match(api,quality,FOLDER)
    if folder is None:
        created=call(lambda:api.files().create(body={
            "name":FOLDER,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"
        },fields="id"))
        folder_id=created["id"]
    elif folder["mimeType"]!="application/vnd.google-apps.folder":
        raise RuntimeError("R3_STAGING_PATH_TYPE_CONFLICT")
    else: folder_id=folder["id"]
    name="r3_prelaunch_write_readback_run_"+run+".json"
    body={"schema":"r3-staging-commit-readback-1","run":run,
          "created_at":datetime.now(timezone.utc).isoformat(),
          "release":"BLOCKED","bronze_mutation":False,
          "silver_materialized":False,"gold_materialized":False,
          "key":"R3_STAGING_ONLY"}
    payload=canon(body)
    prev=match(api,folder_id,name)
    if prev:
        actual=canon(load_json(api,prev["id"]))
        if actual!=payload: raise RuntimeError("AMBIGUOUS_EXISTING_RECEIPT")
    else:
        media=MediaInMemoryUpload(payload,mimetype="application/json",resumable=False)
        obj=call(lambda:api.files().create(body={
            "name":name,"parents":[folder_id],"mimeType":"application/json"
        },media_body=media,fields="id"))
        actual=canon(load_json(api,obj["id"]))
        if actual!=payload: raise RuntimeError("DRIVE_COMMIT_READBACK_MISMATCH")
    # exactly-one listing check: no duplicate file under same run.
    found=match(api,folder_id,name)
    if not found:raise RuntimeError("POST_COMMIT_RECEIPT_MISSING")
    print("R3_STAGING_DRIVE_PROBE="+json.dumps({
        "run":run,"result":"PASS","folder_name":FOLDER,
        "receipt_name":name,"payload_sha256":hashlib.sha256(payload).hexdigest(),
        "certificates_released":0,"production_writes":0
    },sort_keys=True),flush=True)
if __name__=="__main__":
    if sys.argv[1:]!=["staging-readback"]:raise SystemExit("usage: staging-readback")
    probe()
