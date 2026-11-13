#!/usr/bin/env python3
"""JARVIS v0.97: retry seven frozen V4 raw copy exceptions to existing Bronze raw.
Independent source/destination SHA, original source month/path and raw structure
must all pass. This is ORIGINAL BRONZE BYTE/PATH QA, NOT publication/PIT certification.
No Silver/Gold and no change to v0.93 or any historical checkpoint.
"""
import os,io,re,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call,partition,raw_integrity
from scripts.v097_v4_exception_evidence_upload import frozen_rows
from scripts.v097_bronze_first_batch_v3 import qa_one
RUN=os.getenv("GITHUB_RUN_ID","manual")
SRC="TRANSIENT_RETRY"
def now():return datetime.now(timezone.utc).isoformat()
def digest(x):return hashlib.sha256(x).hexdigest()
def records(api,c,q):
    out=[]
    for lane in range(6):
        stage=match(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%lane)
        if not stage:raise RuntimeError("V4_STAGE_LANE_MISSING")
        done=load_json(api,stage["id"])["done"]
        for item in frozen_rows(api,q,lane):
            if item.get("category")!=SRC:continue
            fid=item["file_id"]
            v=done.get(fid,{})
            if v.get("status")!="V097_V4_QUARANTINE_SHA_PASS" or not v.get("dest_id") or not re.fullmatch(r"[a-f0-9]{64}",v.get("source_sha256") or ""):
                raise RuntimeError("TRANSIENT_SOURCE_QUARANTINE_NOT_HASH_CERTIFIED:"+fid)
            out.append((lane,item,v))
    if len(out)!=7 or len({r["file_id"] for l,r,v in out})!=7:
        raise RuntimeError("NOT_SEVEN_FROZEN_TRANSIENT_SOURCE_IDS")
    return out
def repair_one(api,bronze,lane,item,stage):
    fid=item["file_id"]
    result={"file_id":fid,"original_path":item.get("source_path"),"source_sha256":stage["source_sha256"],
        "prior_category":SRC,"market_full_release_certified":False,"v093_untouched":True}
    try:
        p=str(item.get("source_path") or "").split("/")
        if len(p)<4:raise ValueError("MISSING_PATH_PARTS")
        year,source,month=p[:3]
        if source not in ("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind"):
            raise ValueError("UNSUPPORTED_DATA_SOURCE")
        if not re.fullmatch(r"(19|20)\d{2}",year) or not re.fullmatch(r"(19|20)\d{2}-(0[1-9]|1[0-2])",month) or not month.startswith(year+"-"):
            raise ValueError("PERIOD_PATH_INVALID")
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,parents"))
        name=meta["name"]
        if name.endswith((".receipt.json",".manifest.json",".checkpoint.json")):raise ValueError("CONTROL_FILE_DISALLOWED")
        if name!=p[-1]:raise ValueError("SOURCE_FILE_BASENAME_CONFLICT")
        size=int(meta.get("size") or 0)
        if size<=0 or size>40*1024*1024:raise ValueError("COPY_SIZE_LIMIT")
        original=call(lambda:api.files().get_media(fileId=fid))
        quarantined=call(lambda:api.files().get_media(fileId=stage["dest_id"]))
        if len(original)!=size or digest(original)!=stage["source_sha256"] or digest(quarantined)!=stage["source_sha256"]:
            raise ValueError("SOURCE_QUARANTINE_SHA_CONFLICT")
        if meta.get("md5Checksum") and hashlib.md5(original).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_CHANGED")
        if raw_integrity(original,name)!="RAW_STRUCTURE_PASS":raise ValueError("RAW_STRUCTURE_FAILED")
        row={"source":source,"year":year,"month":month,"path":item["source_path"],
             "file_name":name,"prior_status":"","expected_sha256":stage["source_sha256"]}
        targetfolder=partition(api,bronze,row,lane)
        targetname=fid+"__"+stage["source_sha256"][:16]+"__"+name.replace("/","_")
        existing=match(api,targetfolder,targetname)
        if not existing:
            media=MediaInMemoryUpload(original,mimetype="application/octet-stream",resumable=False)
            existing=call(lambda:api.files().create(body={"name":targetname,"parents":[targetfolder],
                    "description":"JARVIS original v093 "+fid+"; raw bytes QA only; not PIT/release-certified"},
                    media_body=media,fields="id,name"))
        detail={"state":"COPY_MATCHED_PENDING_INDEPENDENT_QA",
           "sha":stage["source_sha256"],"dest_id":existing["id"],
           "dest_path":"/".join([source,"BF_LANE_%02d"%lane,year,month[-2:],targetname]),
           "dest_folder_id":targetfolder}
        qa=qa_one(api,fid,detail,lane)
        if qa.get("state")!="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":
            raise ValueError("INDEPENDENT_BRONZE_QA:"+str(qa.get("error")))
        result.update(state="RAW_BRONZE_BYTE_AND_PATH_QA_PASS_PIT_PENDING",
            bronze_dest_id=existing["id"],bronze_dest_sha256=stage["source_sha256"],
            source=source,year=year,month=month)
    except Exception as exc:
        result.update(state="HOLD_NOT_ADMITTED",error=type(exc).__name__+":"+str(exc)[:170])
    return result
def run(api):
    m,c,q,bronze=common(api)
    rows=records(api,c,q)
    results=[]
    for lane,item,stage in rows:
        receipt="v097_V4_SEVEN_BRONZE_QA_"+item["file_id"]+".json"
        f=match(api,q,receipt)
        if f:
            v=load_json(api,f["id"])
        else:
            v=repair_one(api,bronze,lane,item,stage)
            put_once(api,q,receipt,v)
        results.append(v)
        print("V4_SEVEN_FILE="+json.dumps(v,ensure_ascii=False),flush=True)
    states=Counter(v["state"] for v in results)
    report={"schema":"v097_v4_7_bronze_incremental_report_1","run":RUN,"at":now(),
       "total":7,"by_state":dict(states),"raw_bronze_qa_pass":states["RAW_BRONZE_BYTE_AND_PATH_QA_PASS_PIT_PENDING"],
       "held":states["HOLD_NOT_ADMITTED"],
       "full_dataset_release_certified":0,"silver_certified":0,
       "note":"01_BRONZE_ORIGINAL contains immutable raw bytes only; PIT and full release gate remain blocked.",
       "rows":results}
    put_once(api,q,"v097_V4_SEVEN_BRONZE_SUMMARY_"+RUN+".json",report)
    print("V4_SEVEN_BRONZE_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    assert SRC=="TRANSIENT_RETRY"
    assert digest(b"abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    print("V4_SEVEN_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("V4_SEVEN_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="run":run(service())
    else:raise SystemExit("UNKNOWN_MODE")
