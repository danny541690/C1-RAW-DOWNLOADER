#!/usr/bin/env python3
"""JARVIS v0.97 bounded, six-lane, read-only Bronze content QA.

Reads prior v0.93 inventory and samples actual bytes. Results go ONLY to private
v0.97 Google Drive. Never modifies source data or publishes sensitive file lists.
All checks are *structural*, not Bronze certification or PIT validation.
"""
import csv
import hashlib
import io
import json
import os
import re
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload

SRC_INVENTORY_RUN = "42591232910"
SCHEMA = "v097_bronze_byte_qa_1"
BATCH_PER_LANE = int(os.environ.get("QA_BATCH_PER_LANE","60"))
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_ZIP_UNCOMPRESSED = 60 * 1024 * 1024
LANES = 6
FOLDER_MIME = "application/vnd.google-apps.folder"

def call(request_fn):
    for attempt in range(5):
        try:
            return request_fn().execute()
        except HttpError as exc:
            code = exc.resp.status
            if code not in (403,429,500,502,503,504) or attempt==4:
                raise
            time.sleep(min(2**attempt,20))
    raise RuntimeError("retry exhausted")

def service():
    env=["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN"]
    if any(not os.getenv(x) for x in env):
        raise RuntimeError("Google Drive OAuth secrets missing")
    cred=Credentials(None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive"])
    cred.refresh(Request())
    return build("drive","v3",credentials=cred,cache_discovery=False)

def children(api, parent):
    out=[]; token=None
    while True:
        args=dict(q="'%s' in parents and trashed = false"%parent,
            fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size)",
            pageSize=1000,supportsAllDrives=True,includeItemsFromAllDrives=True)
        if token: args["pageToken"]=token
        result=call(lambda:api.files().list(**args))
        if result.get("incompleteSearch"):
            raise RuntimeError("Drive search incomplete")
        out.extend(result.get("files",[]))
        token=result.get("nextPageToken")
        if not token: return out

def folder(api,parent,name):
    a=[x for x in children(api,parent) if x["name"]==name and x["mimeType"]==FOLDER_MIME]
    if len(a)!=1: raise RuntimeError("Folder %s count %s"%(name,len(a)))
    return a[0]["id"]

def destinations(api):
    user=folder(api,"root","ChatGPT資料存取")
    v097=folder(api,user,"JARVIS_C1_v097_LIFECYCLE")
    ctl=folder(api,v097,"00_SYSTEM_CONTROL")
    source_manifests=folder(api,ctl,"03_RUN_MANIFESTS")
    quality=folder(api,v097,"03_DATA_QUALITY")
    reports=folder(api,quality,"07_VERIFICATION_REPORTS")
    queue=folder(api,quality,"06_REPAIR_QUEUE")
    dashboard=folder(api,v097,"10_REPORTS_DASHBOARDS")
    coverage=folder(api,dashboard,"01_DATA_COVERAGE")
    return source_manifests,reports,queue,coverage

def load_json(api,file_id):
    return json.loads(call(lambda:api.files().get_media(fileId=file_id)).decode("utf-8"))

def save(api,parent,name,data,mime="application/json"):
    if isinstance(data,(dict,list)):
        data=json.dumps(data,ensure_ascii=False,separators=(",",":"))
    if isinstance(data,str):data=data.encode("utf-8")
    media=MediaInMemoryUpload(data,mimetype=mime,resumable=False)
    return call(lambda:api.files().create(body={"name":name,"parents":[parent],"mimeType":mime},
         media_body=media,fields="id,name,size"))

def qa_bytes(row, blob):
    name=row["file_name"]
    ext=name.rsplit(".",1)[-1].lower() if "." in name else ""
    rec=dict(file_id=row["file_id"],path=row["path"],source=row["source"],year=row["year"],
        month=row.get("month",""),name=name,original_class=row.get("classification",""),
        checked_at=datetime.now(timezone.utc).isoformat(),
        bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),
        mime=row.get("mime",""),md5_consistent=None,kind="",status="",observations=[])
    if row.get("md5"):
        rec["md5_consistent"]=hashlib.md5(blob).hexdigest()==row["md5"]
        if not rec["md5_consistent"]:
            rec["status"]="BYTE_MISMATCH"
            rec["observations"].append("METADATA_MD5_DISAGREES")
            return rec
    if not blob:
        rec["status"]="EMPTY_CONTENT";return rec
    if ext=="zip" or blob[:4]==b"PK\x03\x04":
        rec["kind"]="ZIP"
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as zf:
                members=zf.infolist()
                rec["zip_members"]=len(members)
                rec["zip_uncompressed_bytes"]=sum(x.file_size for x in members)
                if any(x.filename.startswith("/") or ".." in x.filename.split("/") for x in members):
                    rec["observations"].append("ZIP_UNSAFE_MEMBER_PATH")
                typ=Counter(x.filename.rsplit(".",1)[-1].lower() if "." in x.filename else "" for x in members)
                rec["member_extensions"]=dict(typ)
                if sum(x.file_size for x in members)>MAX_ZIP_UNCOMPRESSED:
                    rec["status"]="ZIP_UNCOMPRESSED_OVERSIZE_REVIEW"
                else:
                    bad=zf.testzip()
                    rec["status"]="STRUCTURAL_PASS_DATASET_PENDING" if bad is None else "ZIP_CRC_FAILED"
                    if bad:rec["observations"].append("CRC_FAIL_MEMBER")
                if any(re.search("manifest|receipt|checkpoint|control|report",x.filename,re.I) for x in members):
                    rec["observations"].append("ZIP_CONTAINS_CONTROL_METADATA")
                if not members:rec["status"]="EMPTY_ZIP"
        except (zipfile.BadZipFile,EOFError,RuntimeError) as err:
            rec["status"]="ZIP_PARSE_FAILED";rec["observations"].append(type(err).__name__)
        return rec
    head=blob[:8192].lstrip()
    if ext in ("json","raw") or head.startswith((b"{",b"[")):
        try:
            value=json.loads(blob.decode("utf-8-sig"))
            rec["kind"]="JSON"
            rec["json_shape"]= "object" if isinstance(value,dict) else "array" if isinstance(value,list) else "scalar"
            if isinstance(value,dict):
                rec["top_keys"]=list(value.keys())[:18]
                lower=" ".join(value.keys()).lower()
                if any(t in lower for t in ["receipt","manifest","checkpoint","download_status","coverage_certified"]):
                    rec["status"]="CONTROL_OR_DERIVED_REVIEW"
                elif any(t in lower for t in ["data","rows","stock_id","date","trade_date","result"]):
                    rec["status"]="STRUCTURAL_PASS_DATASET_PENDING"
                else:rec["status"]="JSON_SEMANTICS_REVIEW"
            elif isinstance(value,list):
                rec["json_length"]=len(value)
                rec["status"]="STRUCTURAL_PASS_DATASET_PENDING"
            else:rec["status"]="JSON_SEMANTICS_REVIEW"
            return rec
        except (ValueError,UnicodeDecodeError):
            if ext=="json":
                rec["status"]="JSON_PARSE_FAILED"
                return rec
    if ext=="html" or b"<html" in head[:2000].lower() or b"<table" in head[:2000].lower():
        rec["kind"]="HTML"
        lower=blob.lower()
        rec["table_tags"]=lower.count(b"<table")
        rec["tr_tags"]=lower.count(b"<tr")
        rec["td_tags"]=lower.count(b"<td")
        rec["status"]="STRUCTURAL_PASS_DATASET_PENDING" if rec["table_tags"] and rec["td_tags"] else "HTML_NO_TABLE_REVIEW"
        return rec
    if ext in ("csv","txt") or (ext=="raw" and (b"," in head or b"\t" in head)):
        rec["kind"]="DELIMITED_TEXT"
        txt=None
        for encoding in ("utf-8-sig","cp950","big5"):
            try:txt=blob.decode(encoding);rec["decoded_as"]=encoding;break
            except UnicodeDecodeError:pass
        if txt is None: rec["status"]="TEXT_DECODE_FAILED";return rec
        reader=csv.reader(io.StringIO(txt))
        sample=[]
        for _,fields in zip(range(4),reader):sample.append(fields)
        rec["first_rows_columns"]=[len(x) for x in sample]
        rec["status"]="STRUCTURAL_PASS_DATASET_PENDING" if sample and max(len(x) for x in sample)>1 else "TEXT_SCHEMA_REVIEW"
        return rec
    if ext=="pdf" or blob.startswith(b"%PDF"):
        rec["kind"]="PDF";rec["status"]="STRUCTURAL_PASS_DATASET_PENDING" if blob.startswith(b"%PDF") else "PDF_HEADER_FAILED";return rec
    if ext in ("xlsx","xls") or blob[:8]==b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        rec["kind"]="EXCEL";rec["status"]="FORMAT_PARSER_PENDING";return rec
    rec["kind"]="UNKNOWN";rec["status"]="FORMAT_PARSER_PENDING"
    return rec

def choose(rows,done,limit):
    buckets=defaultdict(list)
    for row in rows:
        fid=row["file_id"]
        if fid in done:continue
        if row.get("classification") in ("TEST_OR_CONTROL",):continue
        group=(row.get("source"),row["file_name"].lower().split(".")[-1], row.get("classification"))
        buckets[group].append(row)
    for b in buckets.values():
        b.sort(key=lambda x:hashlib.sha256(x["file_id"].encode()).hexdigest())
    keys=sorted(buckets,key=lambda k:(len(buckets[k]),k))
    chosen=[]
    while len(chosen)<limit and keys:
        nextkeys=[]
        for k in keys:
            if len(chosen)>=limit:break
            if buckets[k]:
                chosen.append(buckets[k].pop())
            if buckets[k]: nextkeys.append(k)
        keys=nextkeys
    return chosen

def lane(api,idx,run_id):
    manifests,quality,_,_=destinations(api)
    orig_name="v097_inventory_%s_lane%d.json"%(SRC_INVENTORY_RUN,idx)
    origins=[x for x in children(api,manifests) if x["name"]==orig_name]
    if len(origins)!=1:raise RuntimeError("Expected one original inventory "+orig_name)
    inventory=load_json(api,origins[0]["id"])
    done=set()
    for item in children(api,quality):
        if re.fullmatch(r"v097_bronze_qa_\d+_lane%d.json"%idx,item["name"]):
            old=load_json(api,item["id"])
            done.update(x["file_id"] for x in old.get("results",[]))
    chosen=choose(inventory["files"],done,BATCH_PER_LANE)
    outputs=[]
    for n,row in enumerate(chosen,1):
        size=int(row.get("size_bytes") or 0)
        if size>MAX_FILE_SIZE:
            result=dict(file_id=row["file_id"],path=row["path"],source=row["source"],
                status="LARGE_FILE_DEFERRED",bytes_expected=size,sha256="",kind="UNKNOWN")
        else:
            try:
                blob=call(lambda:api.files().get_media(fileId=row["file_id"]))
                result=qa_bytes(row,blob)
            except Exception as exc:
                result=dict(file_id=row["file_id"],path=row["path"],source=row["source"],
                    status="READ_FAILED",error=type(exc).__name__,detail=str(exc)[:100],sha256="",kind="UNKNOWN")
        outputs.append(result)
        if n%20==0:
            print("Lane %s inspected %s/%s; statuses=%s"%(idx,n,len(chosen),dict(Counter(x["status"] for x in outputs))))
    record=dict(schema=SCHEMA,run_id=run_id,lane=idx,source_inventory_run=SRC_INVENTORY_RUN,
        selected=len(chosen),prior_checked=len(done),total_candidates=len(inventory["files"]),
        output_location="PRIVATE_V097_DATA_QUALITY",results=outputs)
    save(api,quality,"v097_bronze_qa_%s_lane%d.json"%(run_id,idx),record)
    print("Lane %d: selected=%d prior=%d status=%s saved private result."%(idx,len(chosen),len(done),dict(Counter(x["status"] for x in outputs))))

def csvdata(rows,keys):
    s=io.StringIO()
    w=csv.DictWriter(s,fieldnames=keys,extrasaction="ignore")
    w.writeheader()
    for row in rows:
        norm={k:json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(dict,list)) else row.get(k,"") for k in keys}
        w.writerow(norm)
    return s.getvalue().encode("utf-8-sig")

def aggregate(api,run_id):
    _,quality,queue,coverage=destinations(api)
    listing=children(api,quality)
    lanes=[]
    for i in range(LANES):
        target=[x for x in listing if x["name"]=="v097_bronze_qa_%s_lane%d.json"%(run_id,i)]
        if len(target)!=1: raise RuntimeError("Missing/duplicated QA lane %s"%i)
        lanes.append(load_json(api,target[0]["id"]))
    allrows=[r for lane in lanes for r in lane["results"]]
    statuses=Counter(x["status"] for x in allrows)
    sources=Counter(x.get("source","") for x in allrows)
    physical=sum(bool(x.get("sha256")) for x in allrows)
    warnings=[x for x in allrows if x["status"]!="STRUCTURAL_PASS_DATASET_PENDING"]
    summary=dict(run_id=run_id,qa_level="BYTE_STRUCTURE_ONLY",inventory_count=83249,
        files_selected=len(allrows),files_hashed=physical,structural_pass=statuses["STRUCTURAL_PASS_DATASET_PENDING"],
        bronze_certified=0,migrated=0,status_count=dict(statuses),sources=dict(sources),
        warnings=len(warnings),time_utc=datetime.now(timezone.utc).isoformat(),
        limitations=["No full-population bytes audit","No source numeric/semantic certification",
           "No PIT test","No Bronze migration","No restart unless another workflow run is triggered"])
    save(api,coverage,"BRONZE_QA_%s_summary.json"%run_id,summary)
    cols=["file_id","path","source","status","kind","bytes","sha256","md5_consistent","zip_members","zip_uncompressed_bytes","member_extensions","table_tags","td_tags","tr_tags","top_keys","json_shape","decoded_as","observations","error","detail"]
    save(api,coverage,"BRONZE_QA_%s_checked.csv"%run_id,csvdata(allrows,cols),"text/csv")
    save(api,queue,"BRONZE_QA_%s_followup.csv"%run_id,csvdata(warnings,cols),"text/csv")
    print("QA aggregate complete: "+json.dumps(summary,ensure_ascii=False))

if __name__=="__main__":
    api=service(); run_id=os.environ.get("GITHUB_RUN_ID","manual")
    if os.environ.get("QA_MODE")=="aggregate":aggregate(api,run_id)
    else:lane(api,int(os.environ["QA_LANE"]),run_id)
