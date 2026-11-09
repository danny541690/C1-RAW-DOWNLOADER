#!/usr/bin/env python3
"""R8 status consolidation: immutable checkpoint, quality exception ledger.

Never converts metadata coverage into native data completeness. Integrates
an evidence-based follow-up that resolved the Oct 2026 TDCC 2500-file cap.
"""
import collections,json,pathlib
from scripts.v095_2026_annual_consolidated import service
from scripts.v0968_r8_raw_intake import ROOT_ID,child_folder,publish
REPORT_ID="1gziedLDFDXv6V5T1pyraMp9JLBKObyj8"
DELTA_ID="1M52z_ebtf9g6C5OVcN15aKvEZ4R1qPxf"
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
MONTHS=("2025-01","2026-10")
OUT=pathlib.Path("v0968_checkpoint")
def main():
 d=service()
 report=json.loads(d.files().get_media(fileId=REPORT_ID).execute())
 delta=json.loads(d.files().get_media(fileId=DELTA_ID).execute())
 if report.get("schema")!="JARVIS_V0968_R8_INTAKE_REPORT_V1" or delta.get("schema")!="JARVIS_V0968_R8_TDCC_INDEX_DELTA_V1":
  raise ValueError("WRONG_PARENT_RUN")
 if delta.get("listing_complete") is not True or delta["base_tdcc_month_count"]!=2500:
  raise ValueError("TDCC_DELTA_NOT_CERTIFIED_FOR_LISTING")
 units={}
 for rec in report["source_month_summary"]:
  key=(rec["month"],"TDCC" if rec["source"]=="TDCC_ARCHIVE" else rec["source"])
  unit=units.setdefault(key,{"candidate_source_files":0,"underlying_folders":[],"listing_complete":True})
  unit["candidate_source_files"]+=rec["objects"]
  unit["underlying_folders"].append(rec["source"])
  unit["listing_complete"]=unit["listing_complete"] and rec["folder_fully_listed"]
 units[("2026-10","TDCC")]["listing_complete"]=True
 # no mere absence can prove official missing or closure
 result=[]
 for ym in MONTHS:
  for source in SOURCES:
   x=units.get((ym,source))
   if not x:
    status="LEGACY_MONTH_FOLDER_NOT_FOUND"
    count=0;complete=False;origins=[]
   else:
    count=x["candidate_source_files"]
    complete=x["listing_complete"]
    status=("LEGACY_METADATA_LISTED_NATIVE_UNVERIFIED" if count>0 and complete
      else "LEGACY_FOLDER_EMPTY_NATIVE_UNVERIFIED" if complete
      else "LEGACY_METADATA_PARTIAL")
    origins=x["underlying_folders"]
   result.append({"source":source,"month":ym,"source_file_count":count,
     "legacy_listing_complete":complete,"status":status,
     "old_source_folders":origins,"official_expected_units":None,
     "source_bytes_fully_sha_verified":False,"pit_verified":False,
     "raw_parquet_complete":False,"gold_ready":False})
 issues=[]
 for row in result:
  if row["status"]=="LEGACY_MONTH_FOLDER_NOT_FOUND":
   issues.append({"source":row["source"],"month":row["month"],
     "code":"SOURCE_MONTH_FOLDER_ABSENT_IN_V093",
     "severity":"P2","disposition":"INVESTIGATE_SOURCE_MAPPING_NOT_OFFICIAL_DOWNLOAD"})
  if row["status"]=="LEGACY_FOLDER_EMPTY_NATIVE_UNVERIFIED":
   issues.append({"source":row["source"],"month":row["month"],
     "code":"LEGACY_MONTH_HAS_NO_DIRECT_FILES",
     "severity":"P2","disposition":"SEARCH_ARCHIVE_OR_CHILDREN_BEFORE_OFFICIAL_BACKFILL"})
 root_ctl=child_folder(d,ROOT_ID,"00_SYSTEM_CONTROL")
 ck_folder=child_folder(d,root_ctl,"04_CHECKPOINTS")
 dq=child_folder(d,ROOT_ID,"03_DATA_QUALITY")
 quality=child_folder(d,dq,"01_INTAKE_EXCEPTIONS")
 checkpoint={"schema":"JARVIS_V0968_R8_CHECKPOINT_V1","parent_intake_report_id":REPORT_ID,
  "tdcc_pagination_resolution_id":DELTA_ID,
  "source_month_units":result,"source_months":list(MONTHS),
  "source_month_listing_completed":sum(x["legacy_listing_complete"] for x in result),
  "source_month_listing_absent":sum(x["status"]=="LEGACY_MONTH_FOLDER_NOT_FOUND" for x in result),
  "source_month_native_schema_certified":0,"official_source_completeness_certified":0,
  "market_data_parquet_partitions":0,"gold_indicators":0,
  "finmind_backer_enabled":False,"legacy_originals_modified":0,"historical_pit":False,
  "next_action":"VERIFY_ACTUAL_SOURCE_BYTES_AND_NATIVE_DATASET_SCHEMAS"}
 exceptions={"schema":"JARVIS_V0968_R8_EXCEPTION_LEDGER_V1","source_checkpoint_id":None,
  "issues":issues,"issue_count":len(issues),"closed_issue_counts":{
    "TDCC_2026_10_PAGINATION_CAP_FALSE_ALARM":1},
  "close_evidence_id":DELTA_ID,
  "official_absence_inferred":False}
 receipt_ck=publish(d,ck_folder,"V0968_R8_RAW_CHECKPOINT",checkpoint)
 exceptions["source_checkpoint_id"]=receipt_ck["id"]
 receipt_ex=publish(d,quality,"V0968_R8_SOURCE_EXCEPTION_LEDGER",exceptions)
 final={"checkpoint":receipt_ck,"exception_ledger":receipt_ex,
  "listed_units":checkpoint["source_month_listing_completed"],"total_units":len(result),
  "legacy_months_absent":checkpoint["source_month_listing_absent"],"open_exceptions":len(issues),
  "closed_previous_false_alarm":1,"native_schema_verified_units":0}
 OUT.mkdir(exist_ok=True)
 (OUT/"result.json").write_text(json.dumps(final,indent=2,ensure_ascii=False)+"\n")
 print(json.dumps(final,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
