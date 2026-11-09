#!/usr/bin/env python3
"""JARVIS 0.968 2026 server-side Drive RAW mover: SIX independent source lanes.

Drive files.copy: source v0.93 -> new R8 Bronze, no runner byte download.
No native QA, Parquet, Silver, Gold, official network intake, or paid FinMind.
Source-month listing and destination existence checks are mandatory for copy
idempotence. A per-source checkpoint and immutable receipts contain evidence.
"""
import argparse, collections, datetime as dt, hashlib, io, json, os, pathlib, random, re, sys, time
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_2026_annual_consolidated import service
from scripts.v0968_r8_raw_intake import ROOT_ID, LEGACY_ROOTS, FOLDER, categories, child_folder
BRONZE_ID="1UmfgZLO-HJQKcIn4dFTG35-fH6WoqmZp"
YEAR_ROOT=LEGACY_ROOTS["2026"]
END="2026-11-09"
MONTHS=tuple("2026-%02d"%m for m in range(1,12))
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
ARCHIVE="TDCC_ARCHIVE"
COPY_FORMATS={"ZIP","JSON","JSONL","CSV","XLSX","XLS","HTML","PARQUET"}
OUT=pathlib.Path("v0968_sixlane")
def digest(b):return hashlib.sha256(b).hexdigest()
def api(fn,attempts=4):
 for i in range(attempts):
  try:return fn()
  except HttpError as exc:
   status=getattr(exc.resp,"status",0)
   if status not in (403,429,500,502,503,504) or i==attempts-1:raise
   # 403 includes rateLimitExceeded and permission errors: pause only for retryable text.
   if status==403 and not any(k in str(exc).lower() for k in ("ratelimit","quota","userratelimit")):raise
   time.sleep(min(25,2**i+random.random()))
def ls(d,parent,limit=60000):
 result=[];token=None
 while True:
  page=api(lambda:d.files().list(q="'"+parent+"' in parents and trashed=false",
   fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime)",
   pageSize=1000,pageToken=token,supportsAllDrives=True).execute())
  if page.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SEARCH")
  result.extend(page.get("files",[]))
  if len(result)>limit:raise RuntimeError("SOURCE_LIST_LIMIT_"+str(limit))
  token=page.get("nextPageToken")
  if not token:return result
def lookup(entries,name):
 z=[v for v in entries if v["name"]==name and v.get("mimeType")==FOLDER]
 if len(z)>1:raise ValueError("AMBIGUOUS_SOURCE_FOLDER:"+name)
 return z[0] if z else None
def folder(d,parent,name):
 z=lookup(ls(d,parent,500),name)
 if z:return z["id"]
 return api(lambda:d.files().create(body={"name":name,"parents":[parent],"mimeType":FOLDER},
  fields="id").execute())["id"]
def eligible(f):
 if f.get("mimeType")==FOLDER:return False
 name=f["name"];up=name.upper()
 if not any(categories(name)==fmt for fmt in COPY_FORMATS):return False
 # Preserve daily+ only. Unknown granularity is quarantined by metadata label, not silently deleted.
 if re.search(r"(^|[_\-])(TICK|MINUTE|MINUTES|INTRADAY|SECOND)([_\-.]|$)",up):return False
 if any(x in name for x in ("逐筆成交","分鐘線","秒線")):return False
 return True
def make_json(d,dirid,name,obj):
 raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
 f=api(lambda:d.files().create(body={"name":name,"parents":[dirid]},
  media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=False),
  fields="id").execute())
 if digest(api(lambda:d.files().get_media(fileId=f["id"]).execute()))!=digest(raw):
  raise ValueError("RECEIPT_READBACK_SHA_FAILED")
 return {"id":f["id"],"sha256":digest(raw),"name":name}
def checkpoint(d,folderid,source,obj):
 name="V0968_2026_RAW_"+source+"_CHECKPOINT.json"
 existing=[x for x in ls(d,folderid,500) if x["name"]==name]
 if len(existing)>1:raise ValueError("AMBIGUOUS_CHECKPOINT")
 raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
 media=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=False)
 if existing:
  fid=api(lambda:d.files().update(fileId=existing[0]["id"],media_body=media,fields="id").execute())["id"]
 else:
  fid=api(lambda:d.files().create(body={"name":name,"parents":[folderid]},
   media_body=media,fields="id").execute())["id"]
 if digest(api(lambda:d.files().get_media(fileId=fid).execute()))!=digest(raw):
  raise ValueError("CHECKPOINT_READBACK_FAILED")
 return {"id":fid,"sha256":digest(raw)}
def run(source,limit,seconds):
 started=time.monotonic();d=service()
 ctl=child_folder(d,ROOT_ID,"00_SYSTEM_CONTROL")
 ckfolder=child_folder(d,ctl,"04_CHECKPOINTS")
 runfolder=child_folder(d,ctl,"03_RUN_MANIFESTS")
 receiptroot=folder(d,runfolder,"V0968_2026_RAW_SIX_LANES")
 receiptdir=folder(d,receiptroot,source)
 v093=ls(d,YEAR_ROOT,100)
 rootparts=([source,ARCHIVE] if source=="TDCC" else [source])
 srcfolders={name:lookup(v093,name) for name in rootparts}
 summary={"schema":"V0968_2026_RAW_SIXLANE_V1","source":source,"months":MONTHS,"cutoff":END,
  "runner_downloads":0,"official_http_downloads":0,"finmind_backer_calls":0,
  "data_quality_checked":False,"parquet_created":0,"gold_created":0,
  "new_copies":0,"existing_copies":0,"copied_bytes":0,"candidate_files":0,
  "excluded_intraday":0,"source_months_seen":0,"source_months_absent":[],
  "failed_files":[],"raw_inventory_complete":False,"remaining_files":None,
  "source_originals_mutated":False,"phase":"COPY_FIRST_ONLY"}
 records=[];remaining=0;stop=False
 for sourcename,sourcefolder in srcfolders.items():
  if not sourcefolder:
   summary["source_months_absent"].append({"source":sourcename,"state":"SOURCE_FOLDER_NOT_FOUND"})
   continue
  months={x["name"]:x for x in ls(d,sourcefolder["id"],200) if x.get("mimeType")==FOLDER}
  for ym in MONTHS:
   if ym not in months:
    summary["source_months_absent"].append({"source":sourcename,"month":ym,"state":"LEGACY_MONTH_ABSENT_NOT_OFFICIAL_MISSING"})
    continue
   sourcefiles=sorted(ls(d,months[ym]["id"]),key=lambda x:(x["name"],x["id"]))
   summary["source_months_seen"]+=1
   available=[x for x in sourcefiles if eligible(x)]
   summary["excluded_intraday"]+=sum(x.get("mimeType")!=FOLDER and not eligible(x) for x in sourcefiles)
   summary["candidate_files"]+=len(available)
   targetsrc=folder(d,BRONZE_ID,source) # six source dirs, archive also stays with TDCC
   targetyear=folder(d,targetsrc,"2026")
   targetmonth=folder(d,targetyear,ym)
   targetset={x["name"]:x for x in ls(d,targetmonth)}
   for file in available:
    targetname="V093_ORIGINAL_"+digest(file["id"].encode())[:16]+"_"+file["name"]
    existing=targetset.get(targetname)
    if existing:
     if str(existing.get("size",""))==str(file.get("size","")) and (not file.get("md5Checksum") or existing.get("md5Checksum")==file["md5Checksum"]):
      summary["existing_copies"]+=1
     else:
      summary["failed_files"].append({"source":sourcename,"month":ym,"id":file["id"],"reason":"EXISTING_COPY_SIZE_MD5_MISMATCH"})
      remaining+=1
     continue
    if summary["new_copies"]>=limit or time.monotonic()-started>seconds:
     remaining+=1;stop=True
     continue
    try:
     copied=api(lambda:d.files().copy(fileId=file["id"],
       body={"name":targetname,"parents":[targetmonth]},
       fields="id,name,size,md5Checksum",supportsAllDrives=True).execute())
     if str(copied.get("size",""))!=str(file.get("size","")) or (file.get("md5Checksum") and copied.get("md5Checksum")!=file.get("md5Checksum")):
      raise ValueError("COPY_SIZE_MD5_MISMATCH")
     summary["new_copies"]+=1
     summary["copied_bytes"]+=int(file.get("size") or 0)
     targetset[targetname]=copied
     records.append({"legacy_file_id":file["id"],"new_file_id":copied["id"],
      "source":sourcename,"month":ym,"name":file["name"],"size":file.get("size"),
      "drive_md5":file.get("md5Checksum"),"state":"COPIED_METADATA_MATCH_NATIVE_QA_PENDING"})
    except Exception as e:
     summary["failed_files"].append({"source":sourcename,"month":ym,"id":file["id"],"reason":str(e)[:160]})
     remaining+=1
    if len(records)>=100:
     # crash-safe immutable receipts every 100 copies
     payload={"schema":"V0968_2026_RAW_COPY_RECEIPT_V1","source":source,"items":records}
     stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
     make_json(d,receiptdir,"RAW_RECEIPT_"+stamp+"_"+digest(json.dumps(payload).encode())[:8]+".json",payload)
     records=[]
 if records:
  payload={"schema":"V0968_2026_RAW_COPY_RECEIPT_V1","source":source,"items":records}
  stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
  make_json(d,receiptdir,"RAW_RECEIPT_"+stamp+"_"+digest(json.dumps(payload).encode())[:8]+".json",payload)
 summary["remaining_files"]=remaining
 summary["raw_inventory_complete"]=remaining==0 and not summary["failed_files"] and not summary["source_months_absent"]
 summary["elapsed_seconds"]=round(time.monotonic()-started,2)
 c=checkpoint(d,ckfolder,source,summary)
 OUT.mkdir(exist_ok=True)
 (OUT/(source+".json")).write_text(json.dumps({"summary":summary,"checkpoint":c},ensure_ascii=False,indent=2)+"\n")
 print("JARVIS_V0968_SIXLANE_RESULT="+json.dumps({"source":source,"new":summary["new_copies"],
  "existing":summary["existing_copies"],"candidates":summary["candidate_files"],
  "remaining":remaining,"errors":len(summary["failed_files"]),"missing_months":len(summary["source_months_absent"]),
  "complete":summary["raw_inventory_complete"],"checkpoint":c},ensure_ascii=False),flush=True)
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--source",required=True,choices=SOURCES)
 parser.add_argument("--limit",type=int,default=600)
 parser.add_argument("--seconds",type=int,default=1050)
 args=parser.parse_args()
 if not 1<=args.limit<=1200 or not 60<=args.seconds<=1800:raise ValueError("BATCH_BUDGET_BAD")
 run(args.source,args.limit,args.seconds)
