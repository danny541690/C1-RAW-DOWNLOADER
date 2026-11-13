#!/usr/bin/env python3
"""Preserve only 27 remaining non-HTML residuals from 0.93 in v0.97 evidence quarantine.
No Silver/Gold, no Bronze. Large sources get bounded copy and SHA or explicit hold.
"""
import os,json,re,hashlib
from datetime import datetime,timezone
from collections import Counter
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,makefolder
from scripts.v097_bf_residual_1131 import relevant
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("NONHTML_LANE","0"))
NAME="v097_NONHTML_RESIDUAL_HOLD_V1"
MAX_BYTES=220*1024*1024
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def candidates(api,m,c,lane):
    return [(row,k,a) for row,k,a in relevant(api,m,c,lane)
            if row.get("prior_status")!="QUARANTINED_JSON_ERROR"]
def getroot(api,create=False):
    _,_,_,bronze=common(api)
    parent=call(lambda:api.files().get(fileId=bronze,fields="parents")).get("parents",[])
    if len(parent)!=1:raise RuntimeError("NO_UNIQUE_DATA_LAKE")
    name="00_QUARANTINE_V093_OTHER_27"
    if create:return makefolder(api,parent[0],name)
    f=match(api,parent[0],name)
    if not f:raise RuntimeError("MISSING_RESIDUAL_HOLD_ROOT")
    return f["id"]
def bootstrap(api):
    parent=getroot(api,create=True)
    for lane in range(6):makefolder(api,parent,"HOLD_LANE_%02d"%lane)
    print("OTHER27_BOOTSTRAP_PASS",flush=True)
def verify_copy(api,row,kind,folder):
    fid=row["file_id"]
    rec={"file_id":fid,"source":row.get("source"),"category":kind,
         "old_status":row.get("prior_status"),"path":row.get("path"),
         "market_bronze_promoted":False,"v093_unchanged":True}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,mimeType,parents"))
        size=int(meta.get("size") or 0)
        rec.update(file_name=meta.get("name"),size=size)
        if meta.get("name")!=row.get("file_name"):
            raise ValueError("ORIGINAL_NAME_CHANGED")
        if size<=0 or size>MAX_BYTES:
            rec.update(status="SOURCE_EXCEEDS_220MB_OR_EMPTY",error="COPY_LIMIT")
            return rec
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size:raise ValueError("ORIGINAL_SIZE_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("ORIGINAL_MD5_CHANGED")
        digest=sha(raw)
        fname=f"{fid}__{digest[:16]}__{meta['name'].replace('/','_')}"
        target=match(api,folder,fname)
        if not target:
            media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
            target=call(lambda:api.files().create(
                body={"name":fname,"parents":[folder],
                    "description":"v0.93 residual evidence pending scope and source certification; source="+fid},
                media_body=media,fields="id,name"))
        destmeta=call(lambda:api.files().get(fileId=target["id"],fields="id,name,parents"))
        if destmeta.get("name")!=fname or destmeta.get("parents")!=[folder]:
            raise RuntimeError("DEST_METADATA_WRONG")
        dest=call(lambda:api.files().get_media(fileId=target["id"]))
        if len(dest)!=size or sha(dest)!=digest:
            raise RuntimeError("SOURCE_DEST_SHA_MISMATCH")
        rec.update(status="STAGED_OTHER27_SHA_PASS",source_sha256=digest,
                   destination_sha256=sha(dest),dest_id=target["id"],
                   destination_folder_id=folder)
    except Exception as exc:
        rec.update(status="OTHER27_REVIEW_REQUIRED",error=type(exc).__name__+":"+str(exc)[:175])
    return rec
def lane_run(api,lane):
    m,c,q,_=common(api)
    src=candidates(api,m,c,lane)
    f=match(api,c,NAME+"_CK_%02d.json"%lane)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_other27_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_other27_ck_1" or ck.get("lane")!=lane:
        raise RuntimeError("OTHER27_CHECKPOINT_CONFLICT")
    eligible={r["file_id"] for r,k,a in src}
    if not set(ck["done"]).issubset(eligible):raise RuntimeError("OTHER27_ORPHAN")
    todo=[(r,k,a) for r,k,a in src if r["file_id"] not in ck["done"]]
    f=match(api,getroot(api),"HOLD_LANE_%02d"%lane)
    if not f:raise RuntimeError("MISSING_LANE_FOLDER")
    dest=f["id"]
    offset=len(ck["done"])
    receipt="%s_%s_L%02d_O%05d.json"%(NAME,RUN,lane,offset)
    old=match(api,q,receipt)
    if old:
        items=load_json(api,old["id"])["rows"]
    else:
        items=[verify_copy(api,r,k,dest) for r,k,a in todo]
        put_once(api,q,receipt,{"schema":"v097_other27_receipt_1","run":RUN,"at":now(),"lane":lane,
            "rows":items,"originals_modified":0,"bronze_promotions":0})
    for a in items:
        ck["done"][a["file_id"]]={"status":a["status"],"source_sha256":a.get("source_sha256"),
                                  "dest_id":a.get("dest_id")}
    upsert(api,c,NAME+"_CK_%02d.json"%lane,dict(ck,updated_at=now(),last_receipt=receipt))
    print("OTHER27_LANE="+json.dumps({"lane":lane,"total":len(src),"processed":len(ck["done"]),
         "by_status":dict(Counter(z["status"] for z in ck["done"].values()))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api)
    count=handled=0;seen=set();states=Counter()
    for lane in range(6):
        src=candidates(api,m,c,lane)
        ids={r["file_id"] for r,k,a in src}
        if len(ids)!=len(src) or seen&ids:raise RuntimeError("OTHER27_DUPLICATES")
        seen.update(ids);count+=len(ids)
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("OTHER27_ORPHAN")
        handled+=len(ck["done"]);states.update(v["status"] for v in ck["done"].values())
    if count!=27:raise RuntimeError("EXPECTED_27_FOUND_%d"%count)
    report={"schema":"v097_other27_hold_summary_1","run":RUN,"at":now(),
        "total":count,"handled":handled,"remaining":count-handled,"states":dict(states),
        "sha_verified_copied":states["STAGED_OTHER27_SHA_PASS"],
        "pending_review":states["OTHER27_REVIEW_REQUIRED"]+states["SOURCE_EXCEEDS_220MB_OR_EMPTY"],
        "originals_unchanged":True,"bronze_promoted":0,
        "target":"02_DATA_LAKE/00_QUARANTINE_V093_OTHER_27"}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,report)
    print("OTHER27_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
    assert MAX_BYTES==220*1024*1024
    print("OTHER27_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("OTHER27_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="bootstrap":bootstrap(api)
        elif mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise SystemExit("OTHER27_BAD_MODE")
