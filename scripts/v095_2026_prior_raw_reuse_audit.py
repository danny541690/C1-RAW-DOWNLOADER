#!/usr/bin/env python3
"""v0.95 read-only verification of 2026 raw archives retained under earlier RAW root.

Never migrates, rewrites, or elevates v0.93 claims to v0.95 PIT certification.
Uses actual file bytes for a bounded set of legacy sample archive SHA/ZIP checks.
"""
import datetime as dt,hashlib,io,json,os,pathlib,sys,zipfile,collections
from scripts.v095_2026_annual_consolidated import service,ls,MONTHS,FOLDER
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"annual_2026_prior"
YEAR_PARENT="1CAlRsbDEKTrb9BJlJ604SwYwQWRU3lpK" # prior RAW archive /2026
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
MAX_BYTE_SAMPLES=24
MAX_BYTES_PER_SAMPLE=8*1024*1024
def audit(s):
 parent={x["name"]:x["id"] for x in ls(s,YEAR_PARENT) if x.get("mimeType")==FOLDER}
 if not set(SOURCES)<=set(parent):raise RuntimeError("LEGACY_RAW_SOURCE_FOLDER_NOT_ALL_PRESENT")
 rows=[];samples=0;bytes_examined=0;sample_errors=[]
 for src in SOURCES:
  folders=[x for x in ls(s,parent[src]) if x.get("mimeType")==FOLDER]
  monthmap=collections.defaultdict(list)
  for x in folders:
   if x["name"] in MONTHS:monthmap[x["name"]].append(x)
  for month in MONTHS:
   opts=monthmap.get(month,[])
   status="LEGACY_MONTH_FOLDER_MISSING" if not opts else "LEGACY_RAW_FOLDER_PRESENT_UNVERIFIED"
   if len(opts)>1:status="DUPLICATE_MONTH_FOLDER_REVIEW"
   cell={"source":src,"month":month,"folder_count":len(opts),"files":0,
         "source_contract_verified":False,"official_date_coverage_verified":False,
         "raw_samples_byte_sha_pass":0,"raw_samples_zip_crc_pass":0,
         "state":status}
   if len(opts)==1:
    children=ls(s,opts[0]["id"])
    raw=[x for x in children if x.get("mimeType")!=FOLDER]
    cell["files"]=len(raw)
    # only inspect bounded existing zip sample; other file types await exact adapters.
    candidates=sorted([x for x in raw if x["name"].lower().endswith(".zip")
       and 0<int(x.get("size") or 0)<=MAX_BYTES_PER_SAMPLE],
       key=lambda x:("raw_final" not in x["name"].lower(),-int(x.get("size") or 0),x["name"]))
    if candidates and samples<MAX_BYTE_SAMPLES and month<="2026-08":
     x=candidates[0]
     try:
      blob=s.files().get_media(fileId=x["id"]).execute()
      if len(blob)!=int(x["size"]):raise RuntimeError("DRIVE_FILE_LENGTH_MISMATCH")
      digest=hashlib.sha256(blob).hexdigest()
      with zipfile.ZipFile(io.BytesIO(blob)) as z:
       names=z.namelist()
       if not names:raise RuntimeError("EMPTY_ZIP")
       if any(v.startswith("/") or ".." in pathlib.PurePosixPath(v).parts for v in names):
        raise RuntimeError("UNSAFE_ZIP_MEMBER_PATH")
       bad=z.testzip()
       if bad:raise RuntimeError("ZIP_CRC_INVALID")
       cell["raw_samples_zip_crc_pass"]=1
       cell["zip_member_count"]=len(names)
      cell["raw_samples_byte_sha_pass"]=1
      cell["sample_sha256"]=digest
      cell["sample_size_bytes"]=len(blob)
      samples+=1;bytes_examined+=len(blob)
      cell["state"]="SCOPED_ARCHIVE_ZIP_SHA_CRC_PASS_NOT_COMPLETE_DATASET"
     except Exception as e:
      cell["sample_failure_type"]=type(e).__name__
      sample_errors.append({"month":month,"source":src,"type":type(e).__name__})
   rows.append(cell)
 return {"schema":"JARVIS_V095_2026_PRIOR_RAW_REUSE_V1","source_months":len(rows),
   "prior_archive_folder_source_cells":sum(x["folder_count"]>0 for x in rows),
   "prior_archive_file_source_cells":sum(x["files"]>0 for x in rows),
   "prior_archive_total_file_candidates":sum(x["files"] for x in rows),
   "bounded_zip_sha_samples_pass":sum(x["raw_samples_zip_crc_pass"] for x in rows),
   "bytes_sha_checked":bytes_examined,"sample_failures":sample_errors,
   "scope":"PRIOR_RAW_ARCHIVE_CANDIDATE_ONLY_NOT_PIT_NOT_OFFICIAL_COMPLETENESS",
   "raw_data_new_downloads":0,"drive_market_data_writes":0,
   "months":{m:{"source_folders":sum(x["folder_count"]>0 for x in rows if x["month"]==m),
                "source_folders_with_files":sum(x["files"]>0 for x in rows if x["month"]==m),
                "archive_file_candidates":sum(x["files"] for x in rows if x["month"]==m)}
             for m in MONTHS},"cells":rows}
def main():
 s=service();report=audit(s)
 OUT.mkdir(exist_ok=True)
 (OUT/"reuse_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:report[k] for k in ("prior_archive_folder_source_cells",
   "prior_archive_file_source_cells","prior_archive_total_file_candidates",
   "bounded_zip_sha_samples_pass","bytes_sha_checked","sample_failures","months")},ensure_ascii=False))
 if report["sample_failures"]:return 2
 return 0
if __name__=="__main__":sys.exit(main())
