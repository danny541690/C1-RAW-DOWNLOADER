#!/usr/bin/env python3
"""v0.968 R8 2026-01-01 -> 2026-11-09 RAW-ONLY acquisition.

Download/reuse precedes QC/Parquet: native source files are *copied as bytes*
from v0.93 Drive to independent R8 Bronze. No semantic validation, no Silver,
no Gold, no PIT claims. Source-only metadata inventory for entire requested
2026 horizon, source-month gaps logged for dedicated official fetch follow-up.
Bounded per run, restart-safe file IDs, excludes TAIFEX tick/minute exports.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,re,time
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_2026_annual_consolidated import service
from scripts.v0968_r8_raw_intake import ROOT_ID,LEGACY_ROOTS,FOLDER,list_files,find_one,child_folder,categories,publish
YEAR_ROOT=LEGACY_ROOTS["2026"]
SOURCES=("TWSE","TPEx","MOPS","TDCC","TDCC_ARCHIVE","TAIFEX","NDC")
MONTHS=tuple("2026-%02d"%m for m in range(1,12))
CUTOFF="2026-11-09"
BRONZE_ID="1UmfgZLO-HJQKcIn4dFTG35-fH6WoqmZp"
MAX_COPIES=min(int(os.environ.get("V0968_RAW_BATCH_LIMIT","18")),40)
MAX_SOURCE_FILE_BYTES=20_000_000
OUTPUT=pathlib.Path("v0968_2026_raw")
def list_folder(d,parent,limit=15000):
 rows,partial=list_files(d,parent,limit)
 return rows,partial
def ensure_folder(d,parent,name):
 children,partial=list_folder(d,parent,200)
 if partial:raise ValueError("DESTINATION_FOLDER_LIST_INCOMPLETE")
 found=[f for f in children if f["name"]==name]
 if len(found)>1 or (found and found[0]["mimeType"]!=FOLDER):
  raise ValueError("DESTINATION_FOLDER_CONFLICT:"+name)
 if found:return found[0]["id"]
 return d.files().create(body={"name":name,"parents":[parent],"mimeType":FOLDER},
                          fields="id").execute()["id"]
def eligible(file):
 name=file["name"];typ=categories(name);size=int(file.get("size") or 0)
 if file["mimeType"]==FOLDER or typ not in ("ZIP","JSON","CSV","JSONL","XLSX","XLS","HTML"):return False
 if size<=0 or size>MAX_SOURCE_FILE_BYTES:return False
 # User wants daily and above; TAIFEX TICK exports include intraday orders and are excluded.
 if name.upper().startswith(("TICK_","TICK-")):return False
 return True
def main():
 now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
 if now<CUTOFF:raise RuntimeError("FUTURE_DATA_CUTOFF")
 d=service()
 srcs,p=list_folder(d,YEAR_ROOT,100)
 if p:raise ValueError("SOURCE_ROOT_LIST_INCOMPLETE")
 source_entries={x["name"]:x for x in srcs if x["mimeType"]==FOLDER}
 candidates=[];issues=[];units=[]
 # Complete source/month metadata discovery, but cap copies to preserve free Drive quota.
 for source in SOURCES:
  folder=source_entries.get(source)
  if not folder:
   issues.append({"source":source,"state":"LEGACY_SOURCE_FOLDER_ABSENT_NOT_OFFICIAL_MISSING"})
   continue
  mfolders,partial=list_folder(d,folder["id"],100)
  if partial:issues.append({"source":source,"state":"MONTH_DIRECTORY_LIST_INCOMPLETE"})
  byname={x["name"]:x for x in mfolders if x["mimeType"]==FOLDER}
  for month in MONTHS:
   fm=byname.get(month)
   if not fm:
    issues.append({"source":source,"month":month,"state":"NO_V093_MONTH_FOLDER_OFFICIAL_NOT_CHECKED"})
    units.append({"source":source,"month":month,"eligible_file_count":None,"listing_complete":False})
    continue
   rows,partial=list_folder(d,fm["id"])
   allowed=[x for x in rows if eligible(x)]
   units.append({"source":source,"month":month,"eligible_file_count":len(allowed),
     "listing_complete":not partial,"raw_source_kind":"REUSED_LEGACY_NOT_OFFICIAL_PROOF"})
   if partial:issues.append({"source":source,"month":month,"state":"FILE_LIST_TRUNCATED"})
   if not allowed:
    issues.append({"source":source,"month":month,"state":"NO_SUPPORTED_RAW_FILES_IN_FOLDER"})
   # Prioritize monthly archives/native source JSON; avoid old large tick detail flood.
   allowed.sort(key=lambda f:(0 if categories(f["name"])=="ZIP" else 1,
                               0 if categories(f["name"])=="JSON" else 1,
                               int(f.get("size") or 0),f["name"]))
   for f in allowed:
    candidates.append({"source":source,"month":month,"file":f,"legacy_folder_id":fm["id"]})
 # round-robin one item per source-month before deeper source copies
 candidates.sort(key=lambda c:(c["month"], 0 if categories(c["file"]["name"])=="ZIP" else 1,
                           c["source"],c["file"]["name"]))
 done=[];blocked=[];created=0;reused=0;sampled_unit=set()
 for candidate in candidates:
  source,month,f=candidate["source"],candidate["month"],candidate["file"]
  key=(source,month)
  if key in sampled_unit:continue
  sampled_unit.add(key)
  if len(done)>=MAX_COPIES:break
  canonical="TDCC" if source=="TDCC_ARCHIVE" else source
  parent=ensure_folder(d,BRONZE_ID,canonical)
  yr=ensure_folder(d,parent,"2026")
  dest=ensure_folder(d,yr,month)
  tag=hashlib.sha256(f["id"].encode()).hexdigest()[:16]
  target="V093_ORIGINAL_"+tag+"_"+f["name"]
  exists,partial=list_folder(d,dest,1000)
  if partial:raise RuntimeError("DESTINATION_INDEX_NOT_COMPLETE")
  exact=[x for x in exists if x["name"]==target]
  if len(exact)>1:raise RuntimeError("AMBIGUOUS_COPIED_NAME")
  if exact:
   # A prior batch already secured this source-month sample: do not consume
   # this batch's quota and do not duplicate it.
   previous=exact[0]
   if str(previous.get("size",""))!=str(f.get("size","")) or (
       f.get("md5Checksum") and previous.get("md5Checksum")!=f["md5Checksum"]):
    blocked.append({"source":source,"month":month,"legacy_file_id":f["id"],
     "target_file_id":previous.get("id"),"state":"EXISTING_RAW_METADATA_MISMATCH"})
   else:reused+=1
   continue
  else:
   try:
    item=d.files().copy(fileId=f["id"],body={"name":target,"parents":[dest]},
       fields="id,name,size,md5Checksum,mimeType").execute()
    action="COPIED_NATIVE_BYTES_TO_R8_BRONZE";created+=1
   except Exception as exc:
    blocked.append({"source":source,"month":month,"legacy_file_id":f["id"],
       "state":"RAW_COPY_FAILED","reason":type(exc).__name__+":"+str(exc)[:160]})
    continue
  if str(item.get("size",""))!=str(f.get("size","")) or (f.get("md5Checksum") and item.get("md5Checksum")!=f["md5Checksum"]):
   blocked.append({"source":source,"month":month,"legacy_file_id":f["id"],
    "target_file_id":item.get("id"),"state":"COPY_METADATA_SIZE_MD5_MISMATCH"})
   continue
  done.append({"source":canonical,"legacy_source":source,"month":month,
   "legacy_file_id":f["id"],"target_file_id":item["id"],
   "original_name":f["name"],"target_name":target,"bytes":int(f["size"]),
   "legacy_drive_md5":f.get("md5Checksum"),"target_drive_md5":item.get("md5Checksum"),
   "state":action,"raw_type":categories(f["name"]),"actual_byte_sha_verified":False,
   "native_semantic_schema_checked":False,"historical_pit_certified":False})
 summary={"schema":"JARVIS_V0968_R8_2026_RAW_ONLY_V1","date_range":"2026-01-01..2026-11-09",
   "requested_months":list(MONTHS),"sources":list(SOURCES),
   "source_month_units":units,"legacy_candidates_discovered":len(candidates),
   "r8_raw_copies_created":created,"r8_raw_copies_reused":reused,
   "r8_raw_copies_metadata_accepted":len(done),"r8_raw_bytes":sum(x["bytes"] for x in done),
   "download_or_copy_errors":blocked,"legacy_gaps_and_empty_months":issues,
   "download_scope":"REUSE_NATIVE_V093_RAW_ONLY_OFFICIAL_BACKFILL_UNIMPLEMENTED",
   "upstream_modified":0,"finmind_backer_called":False,
   "formal_native_quality_checked":0,"parquet_partitions_created":0,
   "silver_partitions_created":0,"gold_factors_created":0,
   "full_2026_coverage_certified":False,"PIT_certified":False,
   "next_step":"FINISH_REMAINING_NATIVE_RAW_MONTHS_THEN_INDEPENDENT_QA"}
 control=child_folder(d,ROOT_ID,"00_SYSTEM_CONTROL")
 runs=child_folder(d,control,"03_RUN_MANIFESTS")
 receipts=child_folder(d,ROOT_ID,"01_DATA_SOURCES")
 receipts=child_folder(d,receipts,"13_DOWNLOAD_RECEIPTS")
 receipt=publish(d,runs,"V0968_R8_2026_RAW_ONLY",{"summary":summary,"copied_files":done})
 error_receipt=publish(d,receipts,"V0968_R8_2026_RAW_GAPS",{"gaps":issues,"failed_copies":blocked,
  "source_month_units":units,"official_data_downloads":0})
 OUTPUT.mkdir(exist_ok=True)
 result={"summary":{k:v for k,v in summary.items() if k not in ("source_month_units","legacy_gaps_and_empty_months","download_or_copy_errors")},
  "by_source":dict(collections.Counter(x["source"] for x in done)),"issue_count":len(issues)+len(blocked),
  "manifest_receipt":receipt,"gap_receipt":error_receipt}
 (OUTPUT/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
