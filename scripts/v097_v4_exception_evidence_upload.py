#!/usr/bin/env python3
"""Preserve the frozen V4 6358 v0.93 copy exceptions in v0.97 quarantine.
Never use this to admit market Bronze. Immutable v0.93 preserved.
Receipt-first, checkpoint-second. Idempotent, fixed lane folders.
"""
import os,json,re,hashlib
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("V4_HOLD_LANE","0"))
BATCH=max(1,min(120,int(os.getenv("V4_HOLD_BATCH","80"))))
NAME="v097_V4_EXCEPTIONS_STAGED_V1"
FROZEN="43156776265"
MAX_FILE_BYTES=64*1024*1024
EXPECTED_TOTAL=6358
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def frozen_rows(api,q,lane):
    f=match(api,q,"v097_BF_REPAIR_V4_%s_L%02d.json"%(FROZEN,lane))
    if not f:raise RuntimeError("FROZEN_V4_LANE_NOT_FOUND_%d"%lane)
    d=load_json(api,f["id"])
    if d.get("schema")!="v097_bf_repair_v4_lane_1":raise RuntimeError("BAD_FROZEN_V4")
    return d["rows"]
def hold_parent(api,create=False):
    _,_,_,bronze=common(api)
    meta=call(lambda:api.files().get(fileId=bronze,fields="parents"))
    parents=meta.get("parents") or []
    if len(parents)!=1:raise RuntimeError("BRONZE_PARENT_NOT_UNIQUE")
    if create:
        return makefolder(api,parents[0],"00_QUARANTINE_V093_V4_EXCEPTIONS")
    f=match(api,parents[0],"00_QUARANTINE_V093_V4_EXCEPTIONS")
    if not f:raise RuntimeError("V4_HOLD_BOOTSTRAP_MISSING")
    return f["id"]
def bootstrap(api):
    root=hold_parent(api,create=True)
    for lane in range(6):
        makefolder(api,root,"EX_LANE_%02d"%lane)
    print("V4_HOLD_BOOTSTRAP_READY",flush=True)
def dest_folder(api,lane):
    f=match(api,hold_parent(api),"EX_LANE_%02d"%lane)
    if not f:raise RuntimeError("MISSING_LANE_ROOT")
    return f["id"]
def preserve_one(api,folder,item,lane):
    fid=item["file_id"]
    rec={"file_id":fid,"lane":lane,"v4_category":item.get("category"),
         "prior_error":item.get("prior_error"),
         "original_source_path":item.get("source_path"),
         "v093_original_unchanged":True,
         "bronze_market_admitted":False,"dataset_semantics_certified":False}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,mimeType,parents"))
        size=int(meta.get("size") or 0)
        rec.update(original_name=meta.get("name"),byte_size=size)
        if not 0<size<=MAX_FILE_BYTES:
            rec.update(status="HOLD_LARGE_OR_EMPTY_SOURCE",reason="CAP_64MB")
            return rec
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size:raise ValueError("SOURCE_SIZE_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("ORIGINAL_MD5_CHANGED")
        digest=sha(raw)
        expected=str(item.get("source_sha") or "")
        if re.fullmatch(r"[0-9a-f]{64}",expected) and expected!=digest:
            rec.update(status="HOLD_SOURCE_SHA_CHANGED",observed_sha256=digest,expected_sha256=expected)
            return rec
        # Category and lane fixed for safe parallelism, no concurrent writes to same folder.
        group=str(item.get("category") or "UNCLASSIFIED")
        if not re.fullmatch(r"[A-Za-z0-9_]{2,64}",group):group="UNCLASSIFIED"
        target=makefolder(api,folder,group)
        name=f"{fid}__{digest[:16]}__{meta['name'].replace('/','_')}"
        existing=match(api,target,name)
        if not existing:
            media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
            existing=call(lambda:api.files().create(
                body={"name":name,"parents":[target],
                  "description":"v0.93 V4 exception evidence; not certified Bronze; source id="+fid},
                media_body=media,fields="id,name,parents"))
        dm=call(lambda:api.files().get(fileId=existing["id"],fields="id,name,size,parents"))
        if dm.get("name")!=name or dm.get("parents")!=[target]:
            raise RuntimeError("DEST_METADATA_PATH_MISMATCH")
        dest=call(lambda:api.files().get_media(fileId=existing["id"]))
        if len(dest)!=size or sha(dest)!=digest:
            raise RuntimeError("DEST_INDEPENDENT_SHA_MISMATCH")
        rec.update(status="V097_V4_QUARANTINE_SHA_PASS",
                   source_sha256=digest,destination_sha256=sha(dest),
                   dest_id=existing["id"],dest_folder_id=target,
                   dest_path="02_DATA_LAKE/00_QUARANTINE_V093_V4_EXCEPTIONS/EX_LANE_%02d/%s/%s"%(lane,group,name))
    except Exception as exc:
        rec.update(status="V4_HOLD_REQUIRES_REVIEW",error=type(exc).__name__+":"+str(exc)[:180])
    return rec
def lane_run(api,lane):
    _,c,q,_=common(api)
    frozen=frozen_rows(api,q,lane)
    ckname=NAME+"_CK_%02d.json"%lane
    f=match(api,c,ckname)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_v4_hold_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_v4_hold_ck_1" or ck.get("lane")!=lane:
        raise RuntimeError("V4_HOLD_CHECKPOINT_CONFLICT")
    ids={r["file_id"] for r in frozen}
    if len(ids)!=len(frozen) or not set(ck["done"]).issubset(ids):
        raise RuntimeError("V4_HOLD_DUPLICATE_OR_ORPHAN")
    todo=[r for r in frozen if r["file_id"] not in ck["done"]][:BATCH]
    offset=len(ck["done"])
    receipt="%s_%s_L%02d_O%05d.json"%(NAME,RUN,lane,offset)
    prior=match(api,q,receipt)
    if prior:
        results=load_json(api,prior["id"])["rows"]
        if not {r["file_id"] for r in results}.issubset(ids):
            raise RuntimeError("V4_HOLD_REPLAY_ORPHAN")
    else:
        folder=dest_folder(api,lane)
        results=[preserve_one(api,folder,row,lane) for row in todo]
        put_once(api,q,receipt,{"schema":"v097_v4_hold_receipt_1","run":RUN,
                 "lane":lane,"at":now(),"rows":results,
                 "v093_mutations":0,"market_bronze_admissions":0})
    for r in results:
        ck["done"][r["file_id"]]={"status":r["status"],"run":RUN,
             "dest_id":r.get("dest_id"),"source_sha256":r.get("source_sha256")}
    upsert(api,c,ckname,dict(ck,last_receipt=receipt,updated_at=now()))
    states=Counter(r["status"] for r in ck["done"].values())
    print("V4_HOLD_LANE="+json.dumps({"lane":lane,"processed":len(ck["done"]),
      "total":len(frozen),"remaining":len(frozen)-len(ck["done"]),
      "states":dict(states)},ensure_ascii=False),flush=True)
def summary(api):
    _,c,q,_=common(api)
    n=handled=0;seen=set();counts=Counter()
    for lane in range(6):
        rows=frozen_rows(api,q,lane)
        ids={r["file_id"] for r in rows}
        if len(ids)!=len(rows) or ids&seen:raise RuntimeError("V4_HOLD_DUPLICATES")
        seen.update(ids);n+=len(rows)
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("V4_HOLD_ORPHANS")
        handled+=len(ck["done"]);counts.update(r["status"] for r in ck["done"].values())
    if n!=EXPECTED_TOTAL:raise RuntimeError("V4_HOLD_EXPECTED_%d_ACTUAL_%d"%(EXPECTED_TOTAL,n))
    report={"schema":"v097_v4_exception_hold_report_1","run":RUN,"at":now(),
       "total":n,"processed":handled,"remaining":n-handled,
       "sha_verified_copied":counts["V097_V4_QUARANTINE_SHA_PASS"],
       "large_or_empty":counts["HOLD_LARGE_OR_EMPTY_SOURCE"],
       "source_sha_changed":counts["HOLD_SOURCE_SHA_CHANGED"],
       "needs_review":counts["V4_HOLD_REQUIRES_REVIEW"],
       "by_status":dict(counts),"target":"02_DATA_LAKE/00_QUARANTINE_V093_V4_EXCEPTIONS",
       "source_v093_unchanged":True,"market_bronze_admitted":0}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,report)
    print("V4_HOLD_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    assert EXPECTED_TOTAL==6358
    assert sha(b"abc")=="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    print("V4_HOLD_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("V4_HOLD_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="bootstrap":bootstrap(api)
        elif mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise SystemExit("UNKNOWN_V4_HOLD_MODE")
