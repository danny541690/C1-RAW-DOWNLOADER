#!/usr/bin/env python3
"""R19: corrected v097-v098 population scope and real ZIP member format pilot.
Never promotes an unverified dataset contract. v0.93 and v0.98 immutable.
All logs contain aggregate-only format shape; no file ID or content exported.
"""
import argparse,collections,hashlib,io,json,pathlib,re,sys,zipfile
from v098_r11_six_source_metadata_pilot import SOURCES,service,MIME
from v098_r16_full_private_manifest import list_children,one_child

OLD={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320}
NEW={"TWSE":12346,"TPEx":14383,"MOPS":2594,"TDCC":45439,"TAIFEX":3199,"NDC":320}
OLD_FINMIND=3700
def write(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
def baseline(out):
 assert sum(OLD.values())==71050
 assert sum(NEW.values())==78281
 assert sum(OLD.values())+OLD_FINMIND==74750
 by={s:{"v097_six_official":OLD[s],"v098_six_official":NEW[s],"delta":NEW[s]-OLD[s]} for s in OLD}
 data={"status":"PASS_SCOPE_CORRECTED","official_old":71050,"official_new":78281,
       "official_delta":7231,"finmind_old_separate":3700,
       "legacy_all_sources":74750,"new_six_official":78281,
       "legacy_membership_joined":False,"finmind_separate_ledger":True,
       "by_source":by,"production_bulk_migration_allowed":False}
 write(out,data);return data
def roots(api,stat):
 root=one_child(api,"root","ChatGPT資料存取",stat)
 v98=one_child(api,root,"C1_0.98",stat)
 rec=one_child(api,v98,"99_RECOVERY",stat)
 return one_child(api,rec,"R16_PRIVATE_MANIFEST_TEST_ONLY",stat)
def all_manifest_rows(api,private,source,stat):
 entries={f["name"]:f["id"] for f in list_children(api,private,stat)}
 for year in (2026,2025,2020):
  key=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
  if key not in entries:continue
  body=api.files().get_media(fileId=entries[key]).execute()
  for line in body.splitlines():
   if line.strip():yield json.loads(line)
def candidate_size(row):
 size=int(row.get("size") or 0)
 return size>0 and size<=1024*1024 and row.get("drive_md5")
def signature(data):
 if data.startswith(b"PK\x03\x04"):return "ZIP"
 if data.startswith(b"\x1f\x8b"):return "GZIP"
 if data.lstrip().startswith((b"{",b"[")):return "JSON"
 if b"," in data[:500]:return "DELIMITED"
 return "OPAQUE"
def extract_json_shape(data):
 summary={"is_json":False,"top_level":"UNKNOWN","top_keys":[],"tables":0,
          "tables_with_header_and_rows":0,"row_width_errors":0,
          "raw_wrapper_fields":False}
 try:
  obj=json.loads(data.decode("utf-8-sig"))
 except (UnicodeError,ValueError):return summary
 summary["is_json"]=True;summary["top_level"]=type(obj).__name__
 if not isinstance(obj,dict):return summary
 summary["top_keys"]=sorted(k for k in obj if isinstance(k,str))[:24]
 summary["raw_wrapper_fields"]=bool("source" in obj and ("payload" in obj or "raw" in obj))
 tables=obj.get("tables")
 if not isinstance(tables,list):
  tables=[obj] if isinstance(obj.get("fields"),list) else []
 summary["tables"]=len(tables)
 for t in tables[:40]:
  if not isinstance(t,dict):continue
  cols=t.get("fields");rows=t.get("data")
  if not isinstance(rows,list):rows=t.get("rows")
  if isinstance(cols,list) and isinstance(rows,list):
   summary["tables_with_header_and_rows"]+=1
   summary["row_width_errors"]+=sum(1 for row in rows[:400]
                  if isinstance(row,list) and len(row)!=len(cols))
 return summary
def sample(source,out):
 stat={"api_pages":0}
 report={"source":source,"status":"START","sampled":0,"raw_bytes_md5_match":0,
   "source_profile":"UNKNOWN","archive_crc":"NOT_TESTED",
   "member_count":0,"member_extensions":{},"member_json_shape_count":0,
   "json_tables_with_header_and_rows":0,"json_row_width_errors":0,
   "raw_wrapper_found":False,
   "real_headers_semantics_certified":False,
   "official_published_time_certified":False,
   "dataset_valid_from_certified":False,
   "full_source_coverage_certified":False,
   "production_bulk_migration_allowed":False}
 try:
  api=service();private=roots(api,stat)
  candidates=[x for x in all_manifest_rows(api,private,source,stat) if candidate_size(x)]
  # Select one stable earliest visible id among bounded files, not source-specific result.
  if not candidates:
   report["status"]="NO_SAMPLE_COVERAGE_UNKNOWN"
  else:
   row=min(candidates,key=lambda x:(x.get("year") or 0,x.get("filename") or "",x["file_id"]))
   data=api.files().get_media(fileId=row["file_id"]).execute()
   if len(data)!=int(row["size"]) or hashlib.md5(data).hexdigest()!=row["drive_md5"]:
    raise ValueError("SOURCE_SIZE_OR_MD5_MISMATCH")
   report["sampled"]=report["raw_bytes_md5_match"]=1
   report["source_profile"]=signature(data)
   if signature(data)=="ZIP":
    with zipfile.ZipFile(io.BytesIO(data)) as z:
     report["archive_crc"]="PASS" if z.testzip() is None else "FAIL"
     if report["archive_crc"]!="PASS":raise ValueError("ZIP_CRC_FAILED")
     members=[x for x in z.infolist() if not x.is_dir()]
     report["member_count"]=len(members)
     report["member_extensions"]=dict(collections.Counter(
      pathlib.PurePosixPath(x.filename).suffix.lower() or "<none>" for x in members))
     for m in members[:40]:
      if m.file_size>512*1024:continue
      blob=z.read(m)
      shape=extract_json_shape(blob)
      if shape["is_json"]:
       report["member_json_shape_count"]+=1
       report["json_tables_with_header_and_rows"]+=shape["tables_with_header_and_rows"]
       report["json_row_width_errors"]+=shape["row_width_errors"]
       report["raw_wrapper_found"]|=shape["raw_wrapper_fields"]
   elif signature(data)=="JSON":
    shape=extract_json_shape(data)
    report["member_json_shape_count"]=int(shape["is_json"])
    report["json_tables_with_header_and_rows"]=shape["tables_with_header_and_rows"]
    report["json_row_width_errors"]=shape["row_width_errors"]
    report["raw_wrapper_found"]=shape["raw_wrapper_fields"]
   report["status"]="PASS_FORMAT_OBSERVATION_ONLY"
 except Exception as exc:
  report["status"]="SCAN_ERROR";report["error_class"]=type(exc).__name__
 finally:
  report["api_pages"]=stat["api_pages"];write(out,report)
  print(json.dumps({k:v for k,v in report.items() if k in
   ("source","status","source_profile","member_count","archive_crc","sampled")}))
 if report["status"]=="SCAN_ERROR":sys.exit(2)
def main():
 p=argparse.ArgumentParser();p.add_argument("mode",choices=["baseline","sample"])
 p.add_argument("--source",choices=SOURCES);p.add_argument("--out",required=True)
 a=p.parse_args()
 if a.mode=="baseline":baseline(a.out)
 else:
  if not a.source:p.error("--source required")
  sample(a.source,a.out)
if __name__=="__main__":main()
