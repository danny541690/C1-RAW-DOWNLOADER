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
import requests
from urllib.parse import urlparse
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_content_qa import (
  call,children,destinations,load_json,qa_bytes,save,service,folder
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
"TWSE":["twse.com.tw"],"TPEx":["tpex.org.tw"],
"MOPS":["mops.twse.com.tw"],"TAIFEX":["taifex.com.tw"],
"TDCC":["tdcc.com.tw"],"NDC":["ndc.gov.tw"],
"FinMind":["api.finmindtrade.com"],
}
SOURCE_ORDER=["TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"]
REGISTRY_NAME="v097_bronze_source_url_registry.json"
MAX_HTTP_BYTES=int(os.getenv("REPAIR_MAX_HTTP_BYTES",str(24*1024*1024)))

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


def trusted_url(url,provider):
    if not isinstance(url,str) or len(url)>2048:
        return False
    try:
        p=urlparse(url)
        if p.scheme!="https" or not p.hostname or p.username or p.password or p.fragment:
            return False
        return any(p.hostname==h or p.hostname.endswith("."+h)
                   for h in SOURCE_DOMAINS.get(provider,[]))
    except ValueError:
        return False

def load_registry(api):
    """Private Drive file-id to verified provider-specific source mapping.

    Every entry must contain exact dataset identity; absence is never guessed.
    """
    folder_ids,_,_,_=destinations(api)
    arr=[x for x in children(api,folder_ids) if x["name"]==REGISTRY_NAME]
    if len(arr)>1:raise RuntimeError("Ambiguous private download registry")
    if not arr:return {}
    d=load_json(api,arr[0]["id"])
    if d.get("schema")!="v097_source_registry_1":raise RuntimeError("Invalid source registry")
    return d.get("files",{})

def provenance(row,item,provider):
    """Explicit file, period and dataset equivalence, including cross-source."""
    if not isinstance(item,dict) or not item.get("dataset_key"):
        return False
    if item.get("source_file_id")!=row["file_id"]:
        return False
    if str(item.get("year"))!=str(row.get("year")):
        return False
    if item.get("source")!=provider:
        return False
    if row.get("month") and item.get("month")!=row["month"]:
        return False
    if provider!=row["source"] and item.get("verified_equivalent_to")!=item["dataset_key"]:
        return False
    if provider=="FinMind":
        return bool(item.get("finmind_dataset") and
                    item.get("verified_equivalent_to")==item["dataset_key"] and
                    item.get("stock_id") and item.get("start_date") and item.get("end_date"))
    return bool(item.get("url") and trusted_url(item["url"],provider))

def fetch_source(item,provider):
    if provider=="FinMind":
        url="https://api.finmindtrade.com/api/v4/data"
        if not trusted_url(url,provider):raise RuntimeError("FinMind host rejected")
        params={"dataset":item["finmind_dataset"],"data_id":item["stock_id"],
                "start_date":item["start_date"],"end_date":item["end_date"]}
        token=os.getenv("FINMIND_TOKEN","")
        if token:params["token"]=token
    else:
        url=item["url"];params=None
        if not trusted_url(url,provider):raise RuntimeError("Official host rejected")
    last=None
    for n in range(1,MAX_RETRIES+1):
        try:
            with requests.get(url,params=params,timeout=(8,35),
                              allow_redirects=False,stream=True,
                              headers={"User-Agent":"JARVIS-C1-v0.97-quality-recovery/1.0"}) as resp:
                if resp.status_code!=200:
                    raise RuntimeError("HTTP_STATUS_%s"%resp.status_code)
                body=bytearray()
                for chunk in resp.iter_content(chunk_size=131072):
                    body.extend(chunk)
                    if len(body)>MAX_HTTP_BYTES:raise RuntimeError("HTTP_RESPONSE_OVER_LIMIT")
                result=bytes(body)
                if not result:raise RuntimeError("EMPTY_PROVIDER_RESPONSE")
                if result[:100].lstrip().lower().startswith(b"<!doctype html") and item.get("format") not in ("html",):
                    raise RuntimeError("UNEXPECTED_HTML_PROVIDER_RESPONSE")
                if provider=="FinMind":
                    obj=json.loads(result.decode("utf-8"))
                    if not isinstance(obj,dict) or obj.get("status")!=200 or not isinstance(obj.get("data"),list) or not obj["data"]:
                        raise RuntimeError("FINMIND_EMPTY_OR_ERROR_RESPONSE")
                return result,n
        except (requests.RequestException,RuntimeError,ValueError,UnicodeError) as err:
            last=type(err).__name__+":"+str(err)[:100]
            if n<MAX_RETRIES:time.sleep(n*2)
    raise RuntimeError("PROVIDER_RETRY_EXHAUSTED:"+str(last))

def temp_folder(api):
    user=folder(api,"root","ChatGPT資料存取")
    base=folder(api,user,"JARVIS_C1_v097_LIFECYCLE")
    lake=folder(api,base,"02_DATA_LAKE")
    return folder(api,lake,"07_TEMP_CACHE")

def provider_reacquire(api,row,evidence,registry,run,lane):
    """Exact original source first, FinMind last. Store only isolated candidates."""
    mapping=registry.get(row["file_id"],{})
    evidence["source_priority"]=["v0.93"]+SOURCE_ORDER
    origin=row.get("source")
    # Only the exact named original official source is safe without a separately
    # approved cross-source equivalence mapping.
    providers=([origin] if origin in SOURCE_ORDER[:-1] else []) + [x for x in SOURCE_ORDER[:-1] if x!=origin] + ["FinMind"]
    attempts=[]
    for provider in providers:
        item=(mapping.get("providers") or {}).get(provider)
        if not provenance(row,item,provider):
            attempts.append({"provider":provider,"state":"NO_VERIFIED_EXACT_MAPPING"})
            continue
        try:
            blob,n=fetch_source(item,provider)
            filename=item.get("filename") or row["file_name"]
            checkrow=dict(row,file_name=filename)
            qa=qa_bytes(checkrow,blob)
            if qa["status"]!="STRUCTURAL_PASS_DATASET_PENDING":
                attempts.append({"provider":provider,"state":"DOWNLOADED_REJECTED_BY_QA",
                     "attempts":n,"status":qa["status"],"sha256":qa["sha256"]})
                continue
            expected=item.get("expected_sha256")
            if expected and expected.lower()!=qa["sha256"]:
                attempts.append({"provider":provider,"state":"DOWNLOAD_HASH_MISMATCH",
                                 "attempts":n,"sha256":qa["sha256"]})
                continue
            # Direct to private isolation, NOT canonical certified Bronze.
            hashprefix=qa["sha256"][:16]
            safe_name="recovery_%s_lane%d_%s_%s.bin"%(run,lane,provider,hashprefix)
            uploaded=save(api,temp_folder(api),safe_name,blob,
                          mime="application/octet-stream")
            evidence.update(state="RECOVERED_TO_QUARANTINE",
                provider=provider,new_sha256=qa["sha256"],new_file_id=uploaded["id"],
                new_file_name=safe_name,new_status=qa["status"],
                new_bytes=len(blob),attempts_source=n,
                original_source_file_id=row["file_id"],
                next_action="VERIFY_DATASET_IDENTITY_NUMERIC_VALUES_DATE_PIT_BEFORE_BRONZE")
            attempts.append({"provider":provider,"state":"RECOVERED_QUARANTINED",
                            "file_id":uploaded["id"]})
            evidence["provider_attempts"]=attempts
            evidence["official_redownload_performed"]=provider!="FinMind"
            evidence["finmind_fallback_used"]=provider=="FinMind"
            return evidence
        except Exception as exc:
            attempts.append({"provider":provider,"state":"DOWNLOAD_ERROR",
                             "error_type":type(exc).__name__,"detail":str(exc)[:130]})
    evidence.update(state="SOURCE_MAPPING_OR_PROVIDER_FAILURE",
        provider_attempts=attempts,
        next_action="VERIFY_SOURCE_URL_DATASET_KEY_PERIOD_OR_FINMIND_EQUIVALENCE")
    return evidence

def attempt_repair(api,r,registry,run,lane):
    prev=r.get("status")
    fid=r["file_id"]
    row={"file_id":fid,"path":r.get("path",""),
         "file_name":r.get("name") or r.get("path","").split("/")[-1],
         "source":r.get("source",""),"year":r.get("year",""),
         "month":r.get("month",""),
         "classification":r.get("original_class","")}
    evidence={"file_id":fid,"path":row["path"],"source":row["source"],
      "prior_status":prev,"checked_at":now(),"attempts":0,"raw_modified":False,
      "official_redownload_performed":False,"finmind_fallback_used":False,
      "source_order":["v0.93","TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"]}
    if prev not in REPAIRABLE:
        evidence.update(state="NOT_ELIGIBLE",reason="Not a targeted repairable status")
        return evidence
    # 1. Existing v0.93 file: retry safely without modifying source.
    for attempt in range(1,MAX_RETRIES+1):
        evidence["attempts"]=attempt
        try:
            metadata=call(lambda:api.files().get(fileId=fid,fields="id,size,md5Checksum,mimeType"))
            size=int(metadata.get("size") or 0)
            evidence["expected_bytes"]=size
            if size>MAX_INPUT_BYTES:
                evidence["v093_result"]="LARGE_INPUT_LIMIT"
                break
            blob=call(lambda:api.files().get_media(fileId=fid))
            evidence["bytes"]=len(blob)
            evidence["sha256"]=hashlib.sha256(blob).hexdigest()
            original_md5=metadata.get("md5Checksum")
            if original_md5 and hashlib.md5(blob).hexdigest()!=original_md5:
                raise ValueError("Drive content differs from metadata MD5")
            if prev=="ZIP_UNCOMPRESSED_OVERSIZE_REVIEW":
                z=validate_large_zip(blob)
                evidence["zip_validation"]=z
                if z["state"]=="ZIP_CRC_ALL_MEMBERS_PASS":
                    evidence.update(state="REVALIDATED_V093",new_status="STRUCTURAL_PASS_DATASET_PENDING",
                        next_action="SEMANTIC_LINEAGE_PIT_VALIDATION")
                    return evidence
                evidence["v093_result"]=z["state"]
                break
            checked=qa_bytes(row,blob)
            evidence["recheck_status"]=checked["status"]
            if checked["status"]=="STRUCTURAL_PASS_DATASET_PENDING":
                evidence.update(state="REVALIDATED_V093",new_status=checked["status"],
                                next_action="SEMANTIC_LINEAGE_PIT_VALIDATION")
                return evidence
            if checked["status"]=="CONTROL_OR_DERIVED_REVIEW":
                evidence.update(state="NON_MARKET_CONTROL_CLASSIFIED",
                                next_action="RETAIN_AUDIT_ONLY")
                return evidence
            evidence["v093_result"]=checked["status"]
            break
        except Exception as err:
            evidence["v093_error_class"]=type(err).__name__
            evidence["v093_error_detail"]=str(err)[:90]
            if attempt<MAX_RETRIES:time.sleep(attempt*2)
    # 2. Six official providers with verified exact source mapping.
    # 3. FinMind only when dataset equivalence is explicit.
    return provider_reacquire(api,row,evidence,registry,run,lane)

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
    registry=load_registry(api)
    results=[attempt_repair(api,r,registry,run,lane) for r in selected]
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
           if x["state"] in ("SOURCE_MAPPING_OR_PROVIDER_FAILURE","RETRY_EXHAUSTED","UNRESOLVED_LARGE_INPUT")],
        "revalidated":[x["file_id"] for x in results if x["state"] in ("REVALIDATED_V093","RECOVERED_TO_QUARANTINE")],
        "note":"Strict priority: v0.93 then verified exact official source then explicitly equivalent FinMind; successful downloads are quarantined, not certified Bronze."})
    print("REPAIR lane=%d candidates=%d cumulative=%d state=%s"%(
        lane,len(selected),len(done),json.dumps(dict(Counter(x["state"] for x in results)))))

if __name__=="__main__":main()
