#!/usr/bin/env python3
"""JARVIS v0.97 B-lane targeted auto remediation.

Consumes already written QA receipts, does not reprocess successful dataset files,
saves immutable repair evidence before a durable per-lane checkpoint. All raw
v0.93 sources are strictly read-only. No unverifiable vendor download invented.
"""
import hashlib
import io
import json
import os
import re
import time
import zipfile
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_content_qa import (
  call,children,destinations,load_json,qa_bytes,save,service
)
from scripts.v097_bronze_diagnosis import drive_checkpoint,save_or_update

QA_RE=re.compile(r"^v097_bronze_qa_(\d+(?:_batch\d+)?)_lane([0-5])[.]json$")
REPAIRABLE={
    "READ_FAILED","BYTE_MISMATCH","ZIP_PARSE_FAILED","ZIP_CRC_FAILED",
    "EMPTY_CONTENT","EMPTY_ZIP","JSON_PARSE_FAILED","PDF_HEADER_FAILED",
    "LARGE_FILE_DEFERRED","ZIP_UNCOMPRESSED_OVERSIZE_REVIEW",
    "TEXT_DECODE_FAILED","HTML_NO_TABLE_REVIEW","TEXT_SCHEMA_REVIEW",
}
MAX_FILES=int(os.getenv("REPAIR_MAX_FILES_PER_LANE","12"))
MAX_INPUT_BYTES=int(os.getenv("REPAIR_MAX_INPUT_BYTES",str(32*1024*1024)))
MAX_MEMBER_UNCOMPRESSED=int(os.getenv("REPAIR_MAX_MEMBER_BYTES",str(256*1024*1024)))
MAX_RETRIES=3
SOURCE_DOMAINS={
"TWSE":["twse.com.tw"],
"TPEx":["tpex.org.tw","tpex.org.tw"],
"MOPS":["mops.twse.com.tw"],
"TAIFEX":["taifex.com.tw"],
"TDCC":["tdcc.com.tw","tdcc.com.tw"],
"NDC":["ndc.gov.tw"],
"FinMind":["finmindtrade.com"],
}
def now():return datetime.now(timezone.utc).isoformat()

def official_redownload_possible(record):
    """Do NOT use storage URL or file path as provider URL."""
    u=record.get("official_original_download_url") or record.get("source_url")
    if not isinstance(u,str):return False
    from urllib.parse import urlparse
    try:
        p=urlparse(u)
        hosts=SOURCE_DOMAINS.get(record.get("source"),[])
        return p.scheme=="https" and p.hostname in hosts and p.username is None and p.password is None
    except ValueError:return False

def validate_large_zip(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        infos=zf.infolist()
        if not infos:return {"state":"ZIP_EMPTY","members":0}
        total=sum(x.file_size for x in infos)
        if total>MAX_MEMBER_UNCOMPRESSED:
            return {"state":"ZIP_TOO_LARGE_FOR_BOUNDED_TEST","members":len(infos),"uncompressed_bytes":total}
        unsafe=any(x.filename.startswith("/") or ".." in x.filename.split("/") for x in infos)
        if unsafe:return {"state":"ZIP_UNSAFE_MEMBER_PATH","members":len(infos)}
        members_checked=0
        for info in infos:
            with zf.open(info) as stream:
                while stream.read(256*1024):pass
            members_checked+=1
        return {"state":"ZIP_CRC_ALL_MEMBERS_PASS","members":len(infos),
                "members_checked":members_checked,"uncompressed_bytes":total}

def attempt_repair(api,r):
    prev=r.get("status")
    fid=r["file_id"]
    row={"file_id":fid,"path":r.get("path",""),
         "file_name":r.get("name") or r.get("path","").split("/")[-1],
         "source":r.get("source",""),"year":r.get("year",""),
         "month":r.get("month",""),
         "classification":r.get("original_class","")}
    evidence={"file_id":fid,"path":row["path"],"source":row["source"],
      "prior_status":prev,"checked_at":now(),"attempts":0,"raw_modified":False,
      "official_redownload_performed":False,"source_url_available":official_redownload_possible(r)}
    if prev not in REPAIRABLE:
        evidence.update(state="NOT_ELIGIBLE",reason="Not a targeted repairable status")
        return evidence
    # v0.93 inventory is immutable. Unknown official source URLs MUST NOT be
    # fabricated. This tests re-reading ORIGINAL bytes only.
    for attempt in range(1,MAX_RETRIES+1):
        evidence["attempts"]=attempt
        try:
            metadata=call(lambda:api.files().get(fileId=fid,fields="id,size,md5Checksum,mimeType"))
            size=int(metadata.get("size") or 0)
            evidence["expected_bytes"]=size
            if size>MAX_INPUT_BYTES:
                evidence.update(state="UNRESOLVED_LARGE_INPUT",
                    next_action="STREAM_WITH_DEDICATED_BUDGET_OR_TRUSTED_SOURCE_REDOWNLOAD")
                return evidence
            blob=call(lambda:api.files().get_media(fileId=fid))
            evidence["bytes"]=len(blob)
            evidence["sha256"]=hashlib.sha256(blob).hexdigest()
            original_md5=metadata.get("md5Checksum")
            if original_md5 and hashlib.md5(blob).hexdigest()!=original_md5:
                raise ValueError("Drive content differs from metadata MD5")
            if prev=="ZIP_UNCOMPRESSED_OVERSIZE_REVIEW":
                try:
                    result=validate_large_zip(blob)
                    evidence.update(zip_validation=result)
                    if result["state"]=="ZIP_CRC_ALL_MEMBERS_PASS":
                        evidence.update(state="REVALIDATED_ORIGINAL",
                          new_status="STRUCTURAL_PASS_DATASET_PENDING",
                          next_action="SEMANTIC_AND_LINEAGE_VALIDATION")
                    else:
                        evidence.update(state="NEEDS_SOURCE_REDOWNLOAD_OR_MANUAL",
                            next_action="FILE_SPECIFIC_REPAIR_REQUIRED")
                    return evidence
                except (zipfile.BadZipFile,RuntimeError,EOFError,ValueError) as err:
                    evidence.update(state="NEEDS_SOURCE_REDOWNLOAD_OR_MANUAL",
                        error_type=type(err).__name__,next_action="SOURCE_URL_MISSING_OR_INVALID")
                    return evidence
            result=qa_bytes(row,blob)
            evidence["recheck_status"]=result["status"]
            evidence["recheck_sha256"]=result["sha256"]
            if result["status"]=="STRUCTURAL_PASS_DATASET_PENDING":
                evidence.update(state="REVALIDATED_ORIGINAL",
                    new_status=result["status"],
                    next_action="SEMANTIC_AND_LINEAGE_VALIDATION")
            elif result["status"]=="CONTROL_OR_DERIVED_REVIEW":
                evidence.update(state="NON_MARKET_CONTROL_CLASSIFIED",
                    next_action="SEPARATE_FROM_MARKET_BRONZE")
            else:
                evidence.update(state="NEEDS_SOURCE_REDOWNLOAD_OR_MANUAL",
                    next_action="VERIFIED_OFFICIAL_URL_NOT_PRESENT_DO_NOT_INVENT_DOWNLOAD",
                    error_classification=result["status"])
            return evidence
        except Exception as err:
            evidence["error_type"]=type(err).__name__
            evidence["error_message"]=str(err)[:100]
            if attempt<MAX_RETRIES:time.sleep(attempt*2)
    evidence.update(state="RETRY_EXHAUSTED",
        next_action="OFFICIAL_SOURCE_URL_AND_SOURCE_SCHEMA_REQUIRED")
    return evidence

def main():
    api=service()
    lane=int(os.environ["REPAIR_LANE"]);run=os.environ.get("GITHUB_RUN_ID","manual")
    _,qa_folder,repair_folder,report_folder=destinations(api)
    ck_folder=drive_checkpoint(api)
    ledger_name="v097_REPAIR_LANE%d_CHECKPOINT.json"%lane
    matches=[x for x in children(api,ck_folder) if x["name"]==ledger_name]
    if len(matches)>1:raise RuntimeError("Ambiguous repair checkpoint")
    ckid=matches[0]["id"] if matches else None
    ck=load_json(api,ckid) if ckid else {
      "schema":"v097_repair_checkpoint_v1","lane":lane,
      "completed_file_ids":[],"results_by_state":{}}
    if ck["schema"]!="v097_repair_checkpoint_v1" or ck["lane"]!=lane:
        raise RuntimeError("Repair checkpoint mismatch")
    done=set(ck["completed_file_ids"])
    records=[]
    for ref in children(api,qa_folder):
        mat=QA_RE.fullmatch(ref["name"])
        if mat and int(mat.group(2))==lane:
            records.append(ref)
    records.sort(key=lambda x:(x["name"],x["id"]))
    selected=[];seen=set()
    for ref in records:
        receipt=load_json(api,ref["id"])
        for r in receipt["results"]:
            fid=r.get("file_id")
            if not fid or fid in done or fid in seen or r.get("status") not in REPAIRABLE:
                continue
            seen.add(fid);selected.append(r)
            if len(selected)>=MAX_FILES:break
        if len(selected)>=MAX_FILES:break
    save(api,ck_folder,"v097_REPAIR_WORKORDER_%s_lane%d.json"%(run,lane),{
        "schema":"v097_repair_claim_v1","run":run,"lane":lane,
        "claimed_ids":[r["file_id"] for r in selected],
        "created":now(),"state":"CLAIMED"})
    results=[attempt_repair(api,r) for r in selected]
    # Immutable per-file evidence first; checkpoint only after successful write.
    payload={"schema":"v097_repair_evidence_v1","run":run,"lane":lane,
        "created":now(),"results":results}
    save(api,qa_folder,"v097_bronze_repair_%s_lane%d.json"%(run,lane),payload)
    for row in results:done.add(row["file_id"])
    counts=Counter(ck["results_by_state"])
    counts.update(x["state"] for x in results)
    ck.update(completed_file_ids=sorted(done),
        results_by_state=dict(counts),last_run=run,updated_at=now())
    save_or_update(api,ck_folder,ledger_name,ck,ckid)
    save(api,repair_folder,"BRONZE_REPAIR_%s_lane%d.json"%(run,lane),{
        "lane":lane,"run":run,"results":results,
        "requires_source_reacquisition":[x for x in results
           if x["state"] in ("NEEDS_SOURCE_REDOWNLOAD_OR_MANUAL","RETRY_EXHAUSTED","UNRESOLVED_LARGE_INPUT")],
        "revalidated":[x["file_id"] for x in results if x["state"]=="REVALIDATED_ORIGINAL"],
        "note":"File reread/revalidated only. No external official URL in QA receipt; source redownload not performed."})
    print("REPAIR lane=%d candidates=%d cumulative=%d state=%s"%(
        lane,len(selected),len(done),json.dumps(dict(Counter(x["state"] for x in results)))))

if __name__=="__main__":main()
