#!/usr/bin/env python3
"""R3 bounded real Drive Bronze canary, read-only.

Uses existing repo OAuth service and frozen 74,750 manifests.
Reads at most one bounded destination for each of seven sources.
NO upload, checkpoint update, source rewriting, certification or conversion.
"""
import collections
import hashlib
import json
import os
import sys

from scripts.v097_bronze_autopilot import source_api
from scripts.v097_schema_gate_v21 import read_baseline, inspect
from scripts.v097_v3_preflight import assert_cohort, SOURCE_COUNTS
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS, period
from scripts.v097_r3_gate_core import SOURCES, COHORT

MAX_BYTES = 2 * 1024 * 1024
MAX_CANDIDATES_PER_SOURCE = 90
PASS = {"BYTE_SHA_MATCH"}
def check():
    api, control, quality, match, load_json, _, _, call = source_api()
    total = 0
    reports = []
    for source in SOURCES:
        rows = read_baseline(api, quality, match, load_json, source)
        assert_cohort(rows, source)
        total += len(rows)
        result={"source":source,"cohort":len(rows),"candidates_examined":0,
                "file_bytes_verified":0,"format_candidates":0,
                "official_template_attested":0,"status":"NO_ELIGIBLE_SMALL_FILE"}
        # deterministic first eligible rows, bounded transfers and SHA from baseline
        for row in rows[:MAX_CANDIDATES_PER_SOURCE]:
            result["candidates_examined"]+=1
            sha=row.get("source_sha256")
            did=row.get("destination_id")
            if not did or not isinstance(sha,str) or len(sha)!=64: continue
            try:
                meta=call(lambda: api.files().get(fileId=did, fields="id,size,mimeType"))
                if int(meta.get("size") or (MAX_BYTES+1)) > MAX_BYTES: continue
                blob=call(lambda:api.files().get_media(fileId=did))
                if not isinstance(blob,bytes): blob=bytes(blob)
                if hashlib.sha256(blob).hexdigest()!=sha.lower():
                    result["status"]="DESTINATION_SHA_MISMATCH"
                    break
                result["file_bytes_verified"]+=1
                path=str(row.get("source_path") or "")
                if blob[:4]==b"PK\\x03\\x04":
                    result["signature_status"]="ZIP_CANDIDATE_NOT_DECOMPRESSED"
                else:
                    observed=inspect(blob,path,source)
                    result["signature_status"]=observed.get("status")
                result["format_candidates"]+=1
                ym=str(row.get("data_date") or row.get("date") or "")[:7]
                if len(ym)==7:
                    try: result["historical_period_id"]=period(source,ym)["id"]
                    except ValueError: result["historical_period_id"]="UNVERIFIED_DATE"
                result["status"]="BYTE_SHA_MATCH_FORMAT_CANDIDATE_ONLY"
                break
            except Exception as e:
                # Never log Drive file ids or API exception bodies.
                result["status"]="READ_EXCEPTION_"+type(e).__name__
                break
        reports.append(result)
        print("R3_REAL_CANARY_SOURCE="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    if total!=COHORT:
        raise RuntimeError("FROZEN_COHORT_DRIFT")
    out={"schema":"R3_REAL_READ_ONLY_CANARY_V1","cohort":total,"sources":reports,
         "byte_verified_sources":sum(x["file_bytes_verified"]>0 for x in reports),
         "formal_silver_ready":0,"side_effects":"NONE",
         "note":"Read-only sample checks of v0.97 destination; historical source provenance and G2-G5 certification are NOT asserted."}
    print("R3_REAL_CANARY_SUMMARY="+json.dumps(out,ensure_ascii=False,sort_keys=True),flush=True)
    if any(x["status"]=="DESTINATION_SHA_MISMATCH" for x in reports):
        raise RuntimeError("SHA_MISMATCH_HOLD")
    if not all(x["file_bytes_verified"] for x in reports):
        raise RuntimeError("UNVERIFIED_SOURCE_SAMPLE_REQUIRES_FOLLOWUP")
if __name__=="__main__":
    if sys.argv[1:] != ["read-only"]:raise SystemExit("usage: read-only")
    check()
