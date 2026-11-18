"""JARVIS R3 stratified 70 real Bronze SHA and minimal-structure canary.

Ten byte-verified 0.97 destination samples per source across full frozen
source cohort, not only the first records. No formal G2/G3/G4 certification,
no mutations and no confidential paths in logs.
"""
from __future__ import annotations
import collections, hashlib, json, sys
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_schema_gate_v21 import read_baseline, inspect
from scripts.v097_v3_preflight import assert_cohort
from scripts.v097_r3_gate_core import SOURCES, COHORT

TARGET=10
MAX_BYTES=2*1024*1024
SCAN_RADIUS=45

def canary():
    api,control,quality,match,load_json,_,_,call=source_api()
    source_reports=[]
    total=0
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src); total+=len(rows)
        seen=set()
        passed=0; mismatched=0; read_errors=0; skipped=0; status_counts=collections.Counter()
        for slot in range(TARGET):
            ix=int((slot+0.5)*len(rows)/TARGET)
            for offset in range(SCAN_RADIUS):
                idx=min(len(rows)-1,ix+offset)
                if idx in seen:continue
                seen.add(idx)
                row=rows[idx]
                did=row.get("destination_id")
                expected=row.get("source_sha256")
                if not did or not isinstance(expected,str) or len(expected)!=64:
                    skipped+=1;continue
                try:
                    meta=call(lambda:api.files().get(fileId=did,fields="id,size,mimeType"))
                    if int(meta.get("size") or MAX_BYTES+1)>MAX_BYTES:
                        skipped+=1;continue
                    blob=call(lambda:api.files().get_media(fileId=did))
                    if hashlib.sha256(blob).hexdigest()!=expected.lower():
                        mismatched+=1;status_counts["DEST_SHA_MISMATCH"]+=1
                        break
                    passed+=1
                    if blob[:4]==b"PK\\x03\\x04":
                        status="ZIP_BYTES_MATCH_MEMBER_SCHEMA_NOT_TESTED"
                    else:
                        try:status=inspect(blob,str(row.get("source_path") or ""),src).get("status","UNCLASSIFIED")
                        except Exception:status="FORMAT_PARSE_EXCEPTION"
                    status_counts[status]+=1
                    break
                except Exception as e:
                    read_errors+=1;status_counts["DRIVE_"+type(e).__name__]+=1
                    break
        summary={"source":src,"cohort":len(rows),"verified":passed,
                 "mismatch":mismatched,"read_errors":read_errors,
                 "skipped_candidates":skipped,"format_statuses":dict(status_counts)}
        print("R3_REAL_70_SOURCE="+json.dumps(summary,ensure_ascii=False,sort_keys=True),flush=True)
        source_reports.append(summary)
    if total!=COHORT:raise RuntimeError("COHORT_MISMATCH")
    result={"cohort":total,"expected_samples":70,
            "verified_samples":sum(s["verified"] for s in source_reports),
            "mismatches":sum(s["mismatch"] for s in source_reports),
            "read_errors":sum(s["read_errors"] for s in source_reports),
            "formal_ready":0,"source_reports":source_reports}
    print("R3_REAL_70_SUMMARY="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
    if result["verified_samples"]!=70 or result["mismatches"] or result["read_errors"]:
        raise RuntimeError("REAL_70_NOT_FULLY_VERIFIED")
if __name__=="__main__":
    if sys.argv[1:]!=["read-only"]:raise SystemExit("usage: read-only")
    canary()
