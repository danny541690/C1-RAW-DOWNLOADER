#!/usr/bin/env python3
"""JARVIS v0.96 R8: incremental v0.93 source registry into NEW LIFECYCLE root.

NO official HTTP, financial data mutation, paid FinMind calls, full Silver or Gold.
Reads source folders with Google Drive pagination; remembers original file IDs and
metadata, SHA-validates bounded actual original bytes, and persists immutable
receipt with verified SHA readback to R8 only. Never touch pre-R8 output trees.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib,re,time,zipfile
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_2026_annual_consolidated import service
ROOT_ID="1EMiLsGJVUPdjPLbN87bKqANpdj6aP5AA"
LEGACY_ROOTS={"2025":"1VB9s43UHEQeZbPbLHOCcFAQewUDfjBOm",
              "2026":"1CAlRsbDEKTrb9BJlJ604SwYwQWRU3lpK"}
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","TDCC_ARCHIVE")
MONTHS=("2025-01","2026-10")
FOLDER="application/vnd.google-apps.folder"
SCHEMA="JARVIS_V0968_R8_V093_SOURCE_INDEX_V1"
MAX_SOURCE_FOLDERS=70
MAX_MONTH_FILES=2500
MAX_SOURCE_SAMPLE=2
MAX_SAMPLE_BYTES=3_000_000
OUT=pathlib.Path("v0968_r8")
def sha(b):return hashlib.sha256(b).hexdigest()
def list_files(d,parent,max_items):
 rows=[];token=None
 while True:
  page=d.files().list(q="'"+parent+"' in parents and trashed=false",pageSize=250,
   fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime,parents)",pageToken=token).execute()
  if page.get("incompleteSearch"):raise ValueError("DRIVE_PARTIAL_SEARCH")
  rows+=page.get("files",[])
  token=page.get("nextPageToken")
  if len(rows)>max_items:
   return rows[:max_items],True
  if not token:return rows,False
def find_one(entries,name,folder=True):
 found=[x for x in entries if x["name"]==name and (not folder or x.get("mimeType")==FOLDER)]
 return found[0] if len(found)==1 else None
def categories(name):
 suffix=pathlib.PurePosixPath(name).suffix.lower()
 return {".csv":"CSV",".zip":"ZIP",".json":"JSON",".jsonl":"JSONL",
  ".xlsx":"XLSX",".xls":"XLS",".html":"HTML",".htm":"HTML",".parquet":"PARQUET"}.get(suffix,"UNRECOGNIZED")
def prove_sample(d,row):
 if row["size_bytes"]<=0 or row["size_bytes"]>MAX_SAMPLE_BYTES:
  return {"proof":"SKIPPED_SIZE_CAP","source_sha256":None}
 data=d.files().get_media(fileId=row["file_id"]).execute()
 if len(data)!=row["size_bytes"]:raise ValueError("FILE_SIZE_MISMATCH")
 if row["md5"] and hashlib.md5(data).hexdigest()!=row["md5"]:
  raise ValueError("DRIVE_MD5_MISMATCH")
 if row["format"]=="ZIP":
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   members=z.infolist()
   if len(members)>300 or sum(m.file_size for m in members)>75_000_000:
    return {"proof":"SHA_SIZE_MD5_ONLY_ZIP_MEMBER_LIMIT","source_sha256":sha(data)}
   if z.testzip():raise ValueError("ZIP_CRC_BAD")
  return {"proof":"SHA_SIZE_MD5_ZIP_CRC_PASS_NATIVE_PENDING","source_sha256":sha(data)}
 if row["format"]=="JSON":
  json.loads(data)
  return {"proof":"SHA_SIZE_MD5_JSON_PARSE_PASS_NATIVE_PENDING","source_sha256":sha(data)}
 return {"proof":"SHA_SIZE_MD5_PASS_NATIVE_PENDING","source_sha256":sha(data)}
def child_folder(d,parent,name):
 items,truncated=list_files(d,parent,500)
 if truncated:raise ValueError("R8_TARGET_FOLDER_DISCOVERY_TRUNCATED")
 matches=[x for x in items if x["name"]==name]
 if len(matches)!=1 or matches[0]["mimeType"]!=FOLDER:
  raise ValueError("R8_TARGET_FOLDER_NOT_EXACT:"+name)
 return matches[0]["id"]
def publish(d,folder,basename,payload):
 blob=(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
 name=basename+"_"+sha(blob)[:20]+".json"
 found,t=list_files(d,folder,800)
 if t:raise ValueError("R8_PUBLISH_FOLDER_TOO_MANY")
 existing=[x for x in found if x["name"]==name]
 if len(existing)>1:raise ValueError("DUPLICATE_OUTPUT_NAME")
 if existing:fid=existing[0]["id"];action="REUSED"
 else:
  fid=d.files().create(body={"name":name,"parents":[folder]},
    media_body=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/json",resumable=False),
    fields="id").execute()["id"];action="CREATED"
 remote=d.files().get_media(fileId=fid).execute()
 if sha(remote)!=sha(blob):raise ValueError("REMOTE_HASH_MISMATCH")
 return {"id":fid,"sha256":sha(blob),"name":name,"state":action,"readback":"PASS"}
def main():
 d=service()
 control=child_folder(d,ROOT_ID,"00_SYSTEM_CONTROL")
 registry=child_folder(d,control,"02_REGISTRIES")
 runroot=child_folder(d,control,"03_RUN_MANIFESTS")
 # each source file is a referenced legacy original, never a copied R8 raw object
 rows=[];errors=[];source_stats=[];partial=False;verified=0
 for year in ("2025","2026"):
  base,root_partial=list_files(d,LEGACY_ROOTS[year],MAX_SOURCE_FOLDERS)
  if root_partial:
   errors.append({"year":year,"error":"LEGACY_SOURCE_LIST_PARTIAL"});partial=True
  for source in SOURCES:
   src=find_one(base,source)
   if not src:
    if source!="TDCC_ARCHIVE":errors.append({"year":year,"source":source,"state":"SOURCE_FOLDER_NOT_FOUND"})
    continue
   months,p=list_files(d,src["id"],MAX_SOURCE_FOLDERS)
   if p:partial=True;errors.append({"year":year,"source":source,"state":"MONTH_FOLDER_LIST_TRUNCATED"})
   for ym in MONTHS:
    if not ym.startswith(year):continue
    m=find_one(months,ym)
    if not m:
     errors.append({"year":year,"source":source,"month":ym,"state":"LEGACY_MONTH_FOLDER_NOT_FOUND_NOT_OFFICIAL_MISSING"})
     continue
    files,trunc=list_files(d,m["id"],MAX_MONTH_FILES)
    if trunc:partial=True
    n=0
    for f in files:
     if f["mimeType"]==FOLDER:continue
     item={"source":"TDCC" if source=="TDCC_ARCHIVE" else source,
      "legacy_source_folder":source,"month_folder":ym,"file_id":f["id"],
      "name":f["name"],"size_bytes":int(f.get("size") or 0),
      "md5":f.get("md5Checksum"),"format":categories(f["name"]),
      "modified_time":f.get("modifiedTime"),"legacy_folder_id":m["id"],
      "dataset_id":None,"source_sha256":None,"sha_status":"UNPROVEN",
      "pit_certified":False,"copied_to_r8":False,"source_class":"LEGACY_V093"}
     rows.append(item);n+=1
    source_stats.append({"source":source,"month":ym,"objects":n,
      "folder_fully_listed":not trunc,"source_folder_id":src["id"]})
    if trunc:errors.append({"source":source,"month":ym,"state":"MONTH_FILE_COUNT_TRUNCATED_INCOMPLETE"})
 if len({x["file_id"] for x in rows})!=len(rows):
  raise ValueError("DUPLICATED_SOURCE_FILE_ID")
 for source in ("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC"):
  candidates=sorted((x for x in rows if x["source"]==source and x["format"] in ("ZIP","JSON","CSV","HTML")),key=lambda x:x["size_bytes"])
  for row in candidates[:MAX_SOURCE_SAMPLE]:
   try:
    z=prove_sample(d,row)
    row["sha_status"]=z["proof"];row["source_sha256"]=z["source_sha256"]
    verified+=int(bool(z["source_sha256"]))
   except Exception as exc:
    row["sha_status"]="BYTE_SAMPLE_FAILED"
    errors.append({"source":source,"month":row["month_folder"],"file_id":row["file_id"],
      "state":"SAMPLE_VALIDATION_ERROR","reason":type(exc).__name__+":"+str(exc)[:130]})
 root_desc={"schema":"JARVIS_V0968_R8_SOURCE_CATALOG_V1","data_sources":{
  "TWSE":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC"},
  "TPEx":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC"},
  "MOPS":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC"},
  "TDCC":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC","special_cases":["TDCC_ARCHIVE_THIRD_PARTY_MIRROR_UNVERIFIED_OFFICIAL"]},
  "TAIFEX":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC"},
  "NDC":{"role":"OFFICIAL_PRIMARY","authorization":"PUBLIC"},
  "FINMIND_FREE":{"role":"SUPPLEMENTAL","enabled":False,"authorization":"NO_TOKEN_ON_THIS_JOB"},
  "FINMIND_BACKER":{"role":"SUPPLEMENTAL_BACKFILL","enabled":False,"subscription_confirmed":False,
    "authorization":"NOT_CONFIGURED","paid_api_calls":0,"dataset_entitlements":"VERIFY_BEFORE_USING"},
  "XQ_MANUAL":{"role":"USER_UPLOADED_SUPPLEMENTAL","enabled":False}}}
 summary={"schema":"JARVIS_V0968_R8_INTAKE_REPORT_V1","requested_months":MONTHS,
  "legacy_files_indexed":len(rows),"actual_byte_sha_verified":verified,
  "source_month_summary":source_stats,"errors":errors,"incomplete":partial,
  "legacy_originals_modified":0,"legacy_originals_copied":0,
  "paid_finmind_calls":0,"official_download_requests":0,"raw_market_parquet_partitions":0,
  "silver_partitions":0,"gold_indicators":0,"historical_pit_certified":False,
  "verified_full_year_or_full_market_coverage":False}
 manifest={"schema":SCHEMA,"source_rows":rows,"source_months":MONTHS,
   "original_id_only":True,"format_adapter_version":"v0968_r8_1"}
 receipts={"source_catalog":publish(d,registry,"V0968_SOURCE_CATALOG",root_desc),
           "source_manifest":publish(d,runroot,"V0968_V093_RAW_INTAKE",manifest),
           "intake_report":publish(d,runroot,"V0968_INTAKE_REPORT",summary)}
 OUT.mkdir(exist_ok=True)
 (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
 (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
 (OUT/"receipts.json").write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"run_report":{k:v for k,v in summary.items() if k not in ("errors","source_month_summary")},
  "by_source":dict(collections.Counter(x["source"] for x in rows)),"error_counts":dict(collections.Counter(e["state"] for e in errors if "state" in e)),
  "receipts":receipts},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
