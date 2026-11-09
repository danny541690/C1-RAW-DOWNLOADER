#!/usr/bin/env python3
"""JARVIS v0.97: six independent diagnosis lanes for six existing QA year-shards.

Read-only on 0.93. Consume immutable, completed QA receipts, diagnose and retry
transient byte read failures up to three times; generate source-specific review
and next-action queues on private Google Drive. No false Bronze certification.
"""
import csv
import io
import json
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from googleapiclient.errors import HttpError
from scripts.v097_bronze_content_qa import (
    service, call, children, folder, destinations, load_json, save, qa_bytes
)

LANE_COUNT = 6
BATCH_RECEIPTS = int(os.getenv("DIAG_MAX_RECEIPTS_PER_LANE", "8"))
RUN = os.environ.get("GITHUB_RUN_ID","manual")
QA_RE = re.compile(r"^v097_bronze_qa_(\d+(?:_batch\d+)?)_lane([0-5])[.]json$")
CHECKPOINT_SCHEMA = "v097_bronze_diagnosis_checkpoint_v1"

def utc():
    return datetime.now(timezone.utc).isoformat()

def classification(r):
    status=r.get("status","UNKNOWN")
    src=r.get("source","")
    obs=r.get("observations") or []
    name=(r.get("name") or r.get("path") or "").lower()
    if status == "STRUCTURAL_PASS_DATASET_PENDING":
        if "ZIP_CONTAINS_CONTROL_METADATA" in obs:
            return "MIXED_ARCHIVE_REVIEW","INSPECT_MEMBER_MANIFEST_BEFORE_DATASET_CERTIFICATION","CONTENT_UNVERIFIED"
        if src == "TDCC" and r.get("kind") == "HTML":
            return "TDCC_TABLE_SCHEMA_PENDING","VERIFY_STOCK_DATE_GRADE_AND_NUMERIC_VALUES","CONTENT_UNVERIFIED"
        return "STRUCTURE_OK_SEMANTIC_PENDING","VALIDATE_DATASET_SCHEMA_TIMING_AND_UNITS","CONTENT_UNVERIFIED"
    if status == "CONTROL_OR_DERIVED_REVIEW":
        return "CONTROL_METADATA_SEPARATE","PRESERVE_AS_EVIDENCE_NOT_MARKET_RAW","CLASSIFIED_NON_MARKET_CANDIDATE"
    if status == "JSON_SEMANTICS_REVIEW":
        keys=" ".join(r.get("top_keys") or []).lower()
        if any(x in keys or x in name for x in ("receipt","checkpoint","manifest","coverage_certified","report")):
            return "CONTROL_METADATA_SEPARATE","PRESERVE_AS_EVIDENCE_NOT_MARKET_RAW","CLASSIFIED_NON_MARKET_CANDIDATE"
        return "JSON_DATASET_UNKNOWN","REVIEW_JSON_KEYS_AND_ORIGINAL_SOURCE","CONTENT_UNVERIFIED"
    if status in ("LARGE_FILE_DEFERRED","ZIP_UNCOMPRESSED_OVERSIZE_REVIEW"):
        return "OVERSIZE_QUARANTINE","STREAMED_BOUNDED_VALIDATION_REQUIRED","QUARANTINED_PENDING_REVIEW"
    if status in ("ZIP_CRC_FAILED","ZIP_PARSE_FAILED","BYTE_MISMATCH","EMPTY_ZIP","EMPTY_CONTENT","PDF_HEADER_FAILED","JSON_PARSE_FAILED"):
        return "INTEGRITY_FAILURE","RECHECK_SOURCE_BYTE_AND_RECORD_EXCEPTION","QUARANTINED_PENDING_REVIEW"
    if status in ("TEXT_SCHEMA_REVIEW","TEXT_DECODE_FAILED","HTML_NO_TABLE_REVIEW","FORMAT_PARSER_PENDING","JSON_SEMANTICS_REVIEW"):
        return "FORMAT_SCHEMA_GAP","ROUTE_TO_SOURCE_SPECIFIC_PARSER","QUARANTINED_PENDING_REVIEW"
    if status == "READ_FAILED":
        return "TRANSIENT_READ_FAILED","RETRY_THREE_TIMES_THEN_QUARANTINE","RETRY_REQUIRED"
    return "UNKNOWN_QA_STATUS","MANUAL_REVIEW","QUARANTINED_PENDING_REVIEW"

def recheck_failed(api,r):
    # Download the file ONLY if the previous QA could not access it, with a
    # bounded 3-attempt fallback and no modification to the existing file.
    if r.get("status")!="READ_FAILED":
        return None
    for attempt in range(1,4):
        try:
            blob=call(lambda:api.files().get_media(fileId=r["file_id"]))
            row={"file_name":r.get("name") or (r.get("path") or "").split("/")[-1],
                 "file_id":r["file_id"],"path":r.get("path",""),
                 "source":r.get("source",""),"year":r.get("year",""),
                 "month":r.get("month",""),"classification":r.get("original_class","")}
            out=qa_bytes(row,blob)
            return {"attempts":attempt,"status":"RECOVERED_READ","rechecked":out}
        except Exception as e:
            if attempt==3:
                return {"attempts":3,"status":"RETRY_EXHAUSTED","error_class":type(e).__name__}
            time.sleep(attempt*2)
    return None

def diagnose_one(api,raw):
    category,action,phase=classification(raw)
    retry=recheck_failed(api,raw)
    if retry and retry["status"]=="RECOVERED_READ":
        category,action,phase=classification(retry["rechecked"])
    elif retry:
        category,action,phase="READ_FAILURE_THREE_TRIES","RETAIN_QUARANTINED_FOR_LATER_REPAIR","QUARANTINED_PENDING_REVIEW"
    return {
        "file_id":raw.get("file_id",""),"path":raw.get("path",""),
        "source":raw.get("source",""),"qa_status":raw.get("status",""),
        "diagnosis":category,"recommended_action":action,"stage":phase,
        "sha256":raw.get("sha256",""),"retry":retry,
        "observations":raw.get("observations",[]),
    }

def drive_checkpoint(api):
    user=folder(api,"root","ChatGPT資料存取")
    dest=folder(api,user,"JARVIS_C1_v097_LIFECYCLE")
    system=folder(api,dest,"00_SYSTEM_CONTROL")
    return folder(api,system,"04_CHECKPOINTS")

def save_or_update(api,parent,name,body,existing_id=None):
    encoded=json.dumps(body,ensure_ascii=False,separators=(",",":")).encode("utf-8")
    if existing_id:
        from googleapiclient.http import MediaInMemoryUpload
        media=MediaInMemoryUpload(encoded,mimetype="application/json",resumable=False)
        call(lambda:api.files().update(fileId=existing_id,media_body=media,fields="id"))
    else:
        save(api,parent,name,encoded)

def lane(api,idx):
    _,qa_folder,_,_=destinations(api)
    ck_folder=drive_checkpoint(api)
    ckname="v097_bronze_diagnosis_lane%d_checkpoint.json"%idx
    ckfiles=[f for f in children(api,ck_folder) if f["name"]==ckname]
    if len(ckfiles)>1:raise RuntimeError("Multiple lane diagnosis checkpoints")
    ckid=ckfiles[0]["id"] if ckfiles else None
    ck=load_json(api,ckid) if ckid else {
        "schema":CHECKPOINT_SCHEMA,"lane":idx,"processed_receipt_ids":[],
        "diagnosed_files_total":0,"counter_by_category":{}}
    if ck.get("schema")!=CHECKPOINT_SCHEMA or ck.get("lane")!=idx:
        raise RuntimeError("Diagnosis checkpoint schema/lane mismatch")
    already=set(ck["processed_receipt_ids"])
    allqa=[]
    for f in children(api,qa_folder):
        match=QA_RE.fullmatch(f["name"])
        if match and int(match.group(2))==idx:
            allqa.append(f)
    allqa.sort(key=lambda f:(f["name"],f["id"]))
    todo=[f for f in allqa if f["id"] not in already][:BATCH_RECEIPTS]
    # Persist exactly which immutable QA receipts were claimed before analysis.
    # A missing completion checkpoint means these receipts are automatically replayed.
    workorder={"schema":"v097_file_claim_1","pipeline":"DIAG",
        "run_id":RUN,"lane":idx,"claimed_at":utc(),"state":"CLAIMED",
        "receipt_ids":[x["id"] for x in todo],
        "prior_receipts_done":len(already),"qa_receipts_available":len(allqa),
        "pending_before":len(allqa)-len(already)}
    save(api,ck_folder,"v097_DIAG_WORKORDER_%s_lane%d.json"%(RUN,idx),workorder)
    results=[]; per_receipt=[]
    for receipt in todo:
        record=load_json(api,receipt["id"])
        if record.get("lane")!=idx: raise RuntimeError("QA receipt lane mismatch")
        one=[diagnose_one(api,r) for r in record.get("results",[])]
        results.extend(one)
        per_receipt.append({"receipt_file_id":receipt["id"],
            "qa_run_id":record.get("run_id"),"rows":len(one)})
    payload={"schema":"v097_bronze_diagnosis_results_v1","run_id":RUN,"lane":idx,
        "created":utc(),"qa_receipts":per_receipt,"results":results}
    # Immutable evidence FIRST; only after successful upload advance checkpoint.
    save(api,qa_folder,"v097_bronze_diagnosis_%s_lane%d.json"%(RUN,idx),payload)
    already.update(f["id"] for f in todo)
    c=Counter(ck["counter_by_category"])
    c.update(x["diagnosis"] for x in results)
    ck.update(processed_receipt_ids=sorted(already),
        diagnosed_files_total=ck["diagnosed_files_total"]+len(results),
        counter_by_category=dict(c),last_run=RUN,updated_at=utc(),
        pending_receipts=max(0,len(allqa)-len(already)),
        status="CURRENTLY_CAUGHT_UP" if len(allqa)==len(already) else "BACKLOG")
    save_or_update(api,ck_folder,ckname,ck,ckid)
    ledger_name="v097_DIAG_LANE%d_LEDGER.json"%idx
    ledger={"schema":"v097_DIAG_lane_ledger_1","lane":idx,"updated_at":utc(),
       "last_run":RUN,"qa_receipts_available":len(allqa),
       "completed_receipts":len(already),"pending_receipts":ck["pending_receipts"],
       "diagnosed_files_total":ck["diagnosed_files_total"],
       "category_counts":dict(c),
       "pending_receipt_ids":[x["id"] for x in allqa if x["id"] not in already][:30],
       "state":"CAUGHT_UP_WAITING_FOR_QA" if ck["pending_receipts"]==0 else "BACKLOG_REMAINS",
       "market_data_repaired":0,
       "important":"Classification and bounded read retry only. Source-specific correction and market numeric certification are NOT performed."}
    current=[x for x in children(api,ck_folder) if x["name"]==ledger_name]
    if len(current)>1:raise RuntimeError("Duplicate diagnosis ledger")
    save_or_update(api,ck_folder,ledger_name,ledger,current[0]["id"] if current else None)
    print("Diagnosis lane=%d receipts=%d diagnosed=%d cumulative=%d backlog=%d classes=%s"%(
        idx,len(todo),len(results),ck["diagnosed_files_total"],ck["pending_receipts"],
        json.dumps(dict(Counter(x["diagnosis"] for x in results)),ensure_ascii=False)))

def csv_bytes(rows,columns):
    buf=io.StringIO()
    w=csv.DictWriter(buf,fieldnames=columns,extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k:json.dumps(r.get(k),ensure_ascii=False) if isinstance(r.get(k),(list,dict)) else r.get(k,"") for k in columns})
    return buf.getvalue().encode("utf-8-sig")

def aggregate(api):
    _,qa_folder,repair_folder,report_folder=destinations(api)
    ck_folder=drive_checkpoint(api)
    qfiles=children(api,qa_folder)
    ckfiles=children(api,ck_folder)
    lanes=[];rows=[]
    for idx in range(6):
        matches=[f for f in qfiles if f["name"]=="v097_bronze_diagnosis_%s_lane%d.json"%(RUN,idx)]
        if len(matches)!=1: raise RuntimeError("Missing diagnosis lane output %d"%idx)
        lanes.append(load_json(api,matches[0]["id"]))
    for lane_data in lanes:
        rows.extend(lane_data["results"])
    category=Counter(x["diagnosis"] for x in rows)
    checkpoints=[]
    for idx in range(6):
        matches=[f for f in ckfiles if f["name"]=="v097_bronze_diagnosis_lane%d_checkpoint.json"%idx]
        if len(matches)!=1:raise RuntimeError("Missing diagnosis checkpoint %d"%idx)
        checkpoints.append(load_json(api,matches[0]["id"]))
    prior=sum(x["diagnosed_files_total"] for x in checkpoints)
    pending=sum(x["pending_receipts"] for x in checkpoints)
    counts=Counter()
    for c in checkpoints:counts.update(c["counter_by_category"])
    summary={
        "run_id":RUN,"created":utc(),"diagnosis_lanes_completed":6,
        "source_inventory_total":83249,"diagnosed_this_run":len(rows),
        "diagnosed_cumulative":prior,"qa_receipts_waiting":pending,
        "diagnosis_classes_this_run":dict(category),
        "diagnosis_classes_cumulative":dict(counts),
        "status":"CURRENTLY_CAUGHT_UP" if pending==0 else "BACKLOG_REMAINS",
        "bronze_certified":0,"market_data_repaired":0,
        "explanation":"Structural diagnosis, deduped immutable QA receipts, bounded read retry; no source mutation, no semantic data certification."}
    save(api,report_folder,"BRONZE_DIAG_%s_summary.json"%RUN,summary)
    keys=["file_id","path","source","qa_status","diagnosis","recommended_action","stage","sha256","retry","observations"]
    save(api,report_folder,"BRONZE_DIAG_%s_results.csv"%RUN,csv_bytes(rows,keys),"text/csv")
    issues=[x for x in rows if x["stage"]!="CONTENT_UNVERIFIED" or x["diagnosis"]!="STRUCTURE_OK_SEMANTIC_PENDING"]
    save(api,repair_folder,"BRONZE_DIAG_%s_repair_queue.csv"%RUN,csv_bytes(issues,keys),"text/csv")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as out:
            out.write("pending_receipts=%d\n"%pending)
    print("Diagnosis aggregate: "+json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    api=service()
    if os.environ.get("DIAG_MODE")=="aggregate":aggregate(api)
    else:lane(api,int(os.environ.get("DIAG_LANE","0")))
