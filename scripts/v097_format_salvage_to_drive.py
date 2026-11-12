#!/usr/bin/env python3
"""v0.97 immutable salvage staging for verified HTML-in-RAW bytes.
Stage in the v0.97 quarantine data lake, NEVER Bronze until dataset/period/
publication and financial semantics are certified. Never modifies v0.93.
"""
import os,re,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import (
    service,common,match,load_json,put_once,upsert,call,makefolder
)
from scripts.v097_bf_residual_1131 import format_candidates,classify_payload

RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("STAGE_LANE","0"))
CAP=max(1,min(80,int(os.getenv("STAGE_BATCH","25"))))
NAMESPACE="v097_FORMAT_SALVAGE_HOLD_V2"
VALID={
 "TPEx":"TPEX_HTML_TABLE_ADAPTER_AND_DATASET_ORIGIN_PENDING",
 "MOPS":"MOPS_HTML_TABLE_ADAPTER_AND_FINANCIAL_UNITS_PENDING",
 "TDCC":"TDCC_HTML_TABLE_ADAPTER_AND_MARKET_SCOPE_PENDING",
}
MAX_SIZE=4*1024*1024
def sha(data):return hashlib.sha256(data).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def safe_path(row):
    source=str(row.get("source") or "")
    year=str(row.get("year") or "")
    month=str(row.get("month") or "")
    path=str(row.get("path") or "")
    if source not in VALID:return False
    if not re.fullmatch(r"(19|20)\d\d",year):return False
    if not re.fullmatch(year+r"-(0[1-9]|1[0-2])",month):return False
    if not path.startswith(year+"/"+source+"/"+month+"/"):return False
    return True
def root(api,create=False):
    _,_,_,bronze=common(api)
    # Parent of 01_BRONZE_ORIGINAL is 02_DATA_LAKE; quarantine is its sibling.
    info=call(lambda:api.files().get(fileId=bronze,fields="parents"))
    parents=info.get("parents") or []
    if len(parents)!=1:raise RuntimeError("BRONZE_PARENT_AMBIGUOUS")
    name="00_QUARANTINE_FORMAT_REPAIR_V2"
    f=makefolder(api,parents[0],name) if create else match(api,parents[0],name)
    if not f:raise RuntimeError("FORMAT_HOLD_NOT_BOOTSTRAPPED")
    return f["id"] if isinstance(f,dict) else f
def bootstrap(api):
    hold=root(api,create=True)
    for lane in range(6):
        makefolder(api,hold,"BF_LANE_%02d"%lane)
    print("SALVAGE_V2_BOOTSTRAP_READY",flush=True)
def candidate_inputs(api,m,c,lane):
    qa=match(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane)
    if not qa:raise RuntimeError("MISSING_FORMAT_QA_CK_%02d"%lane)
    ck=load_json(api,qa["id"])
    approved=ck.get("done",{})
    rows=[]
    for row,audit in format_candidates(api,m,c,lane):
        fid=row["file_id"]
        expected=VALID.get(row.get("source"))
        detail=approved.get(fid,{})
        if not expected or detail.get("state")!=expected:continue
        rows.append((row,detail,audit))
    return rows
def copy_item(api,hold,row,verified,audit_lane,lane):
    fid=row["file_id"]
    item={"file_id":fid,"source":row["source"],"audit_lane":audit_lane,
          "source_path":row.get("path"),"period":row.get("month"),
          "legacy_format_status":"QUARANTINED_JSON_ERROR",
          "source_original_unchanged":True,"official_origin_certified":False,
          "market_bronze_promoted":False,"silver_promoted":False,
          "semantic_qa_pending":True}
    try:
        if not safe_path(row):raise ValueError("UNVERIFIED_SOURCE_YEAR_MONTH")
        meta=call(lambda:api.files().get(fileId=fid,
                fields="id,name,size,md5Checksum,parents,mimeType"))
        if meta.get("name")!=row.get("file_name"):raise ValueError("SOURCE_FILENAME_CHANGED")
        size=int(meta.get("size") or 0)
        if not 0<size<=MAX_SIZE:raise ValueError("SOURCE_SIZE_OUTSIDE_SALVAGE_CAP")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size:raise ValueError("SOURCE_SIZE_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("SOURCE_MD5_CONFLICT")
        digest=sha(raw)
        if verified.get("sha256")!=digest:raise ValueError("PRIOR_FORMAT_QA_SHA_CONFLICT")
        status,proof=classify_payload(raw,row["source"])
        if status!=VALID[row["source"]]:raise ValueError("SOURCE_DATA_TABLE_NOT_CONFIRMED:"+status)
        # Preserve the original suffix and original bytes. Never recode HTML as JSON.
        s=makefolder(api,hold,row["source"])
        y=makefolder(api,s,row["year"])
        month=makefolder(api,y,str(row["month"])[-2:])
        original=meta["name"].replace("/","_")
        filename=f"{fid}__{digest[:16]}__{original}"
        existing=match(api,month,filename)
        if not existing:
            media=MediaInMemoryUpload(raw,mimetype="application/octet-stream",resumable=False)
            existing=call(lambda:api.files().create(
                body={"name":filename,"parents":[month],
                  "description":"JARVIS v0.97 format-mismatch quarantine; not certified Bronze; original v0.93 id="+fid},
                media_body=media,fields="id,name,parents"))
        dest_id=existing["id"]
        destmeta=call(lambda:api.files().get(fileId=dest_id,fields="id,name,size,parents"))
        if destmeta.get("parents")!=[month] or destmeta.get("name")!=filename:
            raise RuntimeError("DESTINATION_WRONG_FOLDER_OR_NAME")
        copied=call(lambda:api.files().get_media(fileId=dest_id))
        if len(copied)!=size or sha(copied)!=digest:raise ValueError("SOURCE_DEST_SHA_MISMATCH")
        item.update(state="STAGED_SHA_VERIFIED_IN_097_FORMAT_QUARANTINE",
                    source_sha256=digest,dest_sha256=sha(copied),
                    bytes=size,destination_file_id=dest_id,
                    destination_parent_id=month,
                    destination_path=f"02_DATA_LAKE/00_QUARANTINE_FORMAT_REPAIR_V2/BF_LANE_{lane:02d}/{row['source']}/{row['year']}/{row['month'][-2:]}/{filename}",
                    format_proof=proof)
    except Exception as ex:
        item.update(state="STAGE_BLOCKED",error=type(ex).__name__+":"+str(ex)[:180])
    return item
def lane_run(api,lane):
    m,c,q,_=common(api)
    hold=root(api)
    target=match(api,hold,"BF_LANE_%02d"%lane)
    if not target:raise RuntimeError("LANE_HOLD_NOT_BOOTSTRAPPED")
    target=target["id"]
    rows=candidate_inputs(api,m,c,lane)
    name=f"{NAMESPACE}_CK_{lane:02d}.json"
    f=match(api,c,name)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_format_salvage_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_format_salvage_ck_1" or ck.get("lane")!=lane:
        raise RuntimeError("SALVAGE_CHECKPOINT_CONFLICT")
    eligible={row["file_id"] for row,_,_ in rows}
    if not set(ck["done"]).issubset(eligible):raise RuntimeError("SALVAGE_CK_ORPHANS")
    todo=[(r,v,a) for r,v,a in rows if r["file_id"] not in ck["done"]][:CAP]
    offset=len(ck["done"])
    receipt=f"{NAMESPACE}_{RUN}_L{lane:02d}_O{offset:05d}.json"
    old=match(api,q,receipt)
    if old:
        items=load_json(api,old["id"])["items"]
        if len(items)>CAP or not {i["file_id"] for i in items}.issubset(eligible):
            raise RuntimeError("SALVAGE_RECEIPT_CONFLICT")
    else:
        items=[copy_item(api,target,r,v,a,lane) for r,v,a in todo]
        put_once(api,q,receipt,{"schema":"v097_format_salvage_receipt_1",
                  "run":RUN,"lane":lane,"at":now(),"items":items,
                  "market_bronze_promotions":0,"source_originals_mutated":0})
    for item in items:
        ck["done"][item["file_id"]]={"state":item["state"],
         "source_sha256":item.get("source_sha256"),
         "destination_file_id":item.get("destination_file_id"),"run":RUN}
    upsert(api,c,name,dict(ck,last_receipt=receipt,updated_at=now()))
    print("SALVAGE_LANE="+json.dumps({"lane":lane,"new_items":len(items),
       "checked":len(ck["done"]),"eligible":len(rows),"remaining":len(rows)-len(ck["done"]),
       "states":dict(Counter(x["state"] for x in ck["done"].values()))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api)
    eligible_total=checked=0;states=Counter();seen=set()
    for lane in range(6):
        rows=candidate_inputs(api,m,c,lane)
        ids={r["file_id"] for r,_,_ in rows}
        if len(ids)!=len(rows) or seen&ids:raise RuntimeError("CROSS_LANE_SALVAGE_DUPLICATES")
        seen.update(ids);eligible_total+=len(ids)
        f=match(api,c,f"{NAMESPACE}_CK_{lane:02d}.json")
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("SALVAGE_SUMMARY_ORPHANS")
        checked+=len(ck["done"]);states.update(x["state"] for x in ck["done"].values())
    if eligible_total!=1104:raise RuntimeError("SALVAGE_EXPECTED_1104_GOT_%d"%eligible_total)
    out={"schema":"v097_salvage_report_1","run":RUN,"at":now(),
        "expected":eligible_total,"handled":checked,
        "remaining":eligible_total-checked,
        "staged_sha_verified":states["STAGED_SHA_VERIFIED_IN_097_FORMAT_QUARANTINE"],
        "stage_blocked":states["STAGE_BLOCKED"],
        "by_status":dict(states),
        "target":"JARVIS_C1_v097_LIFECYCLE/02_DATA_LAKE/00_QUARANTINE_FORMAT_REPAIR_V2",
        "bronze_market_admitted":0,"silver_admitted":0,
        "original_v093_modified":False,
        "note":"Raw source bytes staged in v0.97 quarantine only; financial/market semantics and publication time remain outstanding."}
    put_once(api,q,f"{NAMESPACE}_SUMMARY_{RUN}.json",out)
    print("SALVAGE_SUMMARY="+json.dumps(out,ensure_ascii=False),flush=True)
def selftest():
    assert safe_path({"source":"TPEx","year":"2026","month":"2026-10","path":"2026/TPEx/2026-10/file.raw"})
    assert not safe_path({"source":"TPEx","year":"2026","month":"2026-10","path":"2026/MOPS/2026-10/file.raw"})
    assert not safe_path({"source":"TDCC_ARCHIVE","year":"2026","month":"2026-10","path":"2026/TDCC_ARCHIVE/2026-10/file.zip"})
    assert classify_payload(b"<html><table><tr><td>1</td></tr></table></html>","MOPS")[0]==VALID["MOPS"]
    print("SALVAGE_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("SALVAGE_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="bootstrap":bootstrap(api)
        elif mode=="lane":lane_run(api,LANE)
        elif mode=="summary":summary(api)
        else:raise SystemExit("BAD_SALVAGE_MODE")
