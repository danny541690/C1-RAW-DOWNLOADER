#!/usr/bin/env python3
"""R8 v0.968 resume only truncated 2026-10 TDCC v0.93 metadata page.

A NEW delta receipt is used, leaving previously verified manifest immutable.
This is metadata index recovery, not official download / native schema proof.
"""
import collections,datetime as dt,hashlib,json,os,pathlib
from scripts.v095_2026_annual_consolidated import service
from scripts.v0968_r8_raw_intake import list_files,categories,publish,ROOT_ID,child_folder,FOLDER
BASE_MANIFEST_ID="1meNyElpF8w9vp3BGeYvn5tqftmu14O_X"
TDCC_MONTH_FOLDER_ID="1ANXWLCybB4UfqACWPQAXY_tnnDZpZ3Pn"
MAX_FILES=40000
OUT=pathlib.Path("v0968_r8_delta")
def main():
 d=service()
 base=json.loads(d.files().get_media(fileId=BASE_MANIFEST_ID).execute())
 if base.get("schema")!="JARVIS_V0968_R8_V093_SOURCE_INDEX_V1":raise ValueError("PARENT_MANIFEST_BAD")
 indexed={r["file_id"] for r in base["source_rows"]}
 source,partial=list_files(d,TDCC_MONTH_FOLDER_ID,MAX_FILES)
 delta=[]
 for f in source:
  if f["id"] in indexed or f["mimeType"]==FOLDER:continue
  delta.append({"source":"TDCC","legacy_source_folder":"TDCC","month_folder":"2026-10",
   "file_id":f["id"],"name":f["name"],"size_bytes":int(f.get("size") or 0),
   "md5":f.get("md5Checksum"),"format":categories(f["name"]),
   "modified_time":f.get("modifiedTime"),"legacy_folder_id":TDCC_MONTH_FOLDER_ID,
   "dataset_id":None,"source_sha256":None,"sha_status":"UNPROVEN",
   "pit_certified":False,"copied_to_r8":False,"source_class":"LEGACY_V093"})
 if len({r["file_id"] for r in delta})!=len(delta):raise ValueError("DELTA_FILE_ID_DUPLICATE")
 desc={"schema":"JARVIS_V0968_R8_TDCC_INDEX_DELTA_V1","parent_manifest_id":BASE_MANIFEST_ID,
  "legacy_source_month":"2026-10","source":"TDCC","legacy_month_folder_id":TDCC_MONTH_FOLDER_ID,
  "base_tdcc_month_count":sum(x["source"]=="TDCC" and x["month_folder"]=="2026-10" and x["legacy_source_folder"]=="TDCC" for x in base["source_rows"]),
  "delta_count":len(delta),"listed_file_count":len(source),"listing_complete":not partial,
  "source_rows":delta,"originals_copied":0,"official_downloads":0,
  "raw_market_parquet_partitions":0,"PIT_certified":False}
 control=child_folder(d,ROOT_ID,"00_SYSTEM_CONTROL")
 manifest_folder=child_folder(d,control,"03_RUN_MANIFESTS")
 receipt=publish(d,manifest_folder,"V0968_R8_TDCC_202610_INDEX_DELTA",desc)
 summary={"schema":"JARVIS_V0968_R8_DELTA_REPORT_V1",
   "base_tdcc_202610_count":desc["base_tdcc_month_count"],
   "new_tdcc_202610_files":len(delta),
   "total_tdcc_202610":len(delta)+desc["base_tdcc_month_count"],
   "folder_listing_complete":not partial,
   "source_coverage_certified":False,"raw_byte_sha_verified_in_delta":0,
   "source_file_ids_are_refs_only":True,"receipt":receipt}
 OUT.mkdir(exist_ok=True)
 (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
