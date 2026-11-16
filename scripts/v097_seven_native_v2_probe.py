#!/usr/bin/env python3
"""Seven-source v0.97 source-native format V2 read-only remediation probe.
One original Bronze read per pending record, never change Bronze/old checkpoints.
Seven typed parsers + official version windows + diagnostic evidence; NO Silver release.
"""
import json,os,sys,re,zipfile,io
from collections import Counter
from scripts.v097_bronze_autopilot import source_api,parse_content,digest,SOURCES
from scripts.v097_seven_historical_format_registry import period,OFFICIAL_VERSIONS
from scripts.v097_seven_source_specific_resolvers import triage
from scripts.v097_bc_single_read_pilot import joint_audit
from scripts.v097_taifex_mops_format_diagnostics import taifex_csv_width_diagnostic,mops_zip_member_diagnostic
VERSION="seven-source-format-probe-v2-20261116"
BATCH=max(1,min(80,int(os.getenv("SOURCE_BATCH","18"))))
SKIP_READY_PARSER={
 "TWSE":("CONTENT_PARSED_ORIGIN_PIT_HOLD",),
 "TPEx":("CONTENT_PARSED_ORIGIN_PIT_HOLD",),
 "TDCC":("TDCC_HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING",),
 "TAIFEX":("TAIFEX_CSV_ENCODING_WIDTH_PASS_DATE_PIT_HOLD",),
 "NDC":("NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD",),
 "MOPS":(),
 "FinMind":()
}
def detected_name(name,blob):
 head=blob[:4096].lstrip()
 lower=name.lower()
 if lower.endswith((".json",".jsonl",".html",".htm",".csv",".zip",".pdf")):return name
 if head.startswith((b"{",b"[")):return name+".json"
 if head.startswith((b"<!DOCTYPE",b"<html",b"<table")):return name+".html"
 if head.startswith(b"PK"+bytes([3,4])):return name+".zip"
 if (b"," in head or bytes([9]) in head) and b"\0" not in head:return name+".csv"
 return name
def probe(source,row,bytes_,prior_status):
 ym=str(row["year"])+"-"+str(row["month"])
 version=period(source,ym)
 base={"source_id":row["source_id"],"bronze_sha256":row["sha"],
  "original_path":row["source_path"],"source":source,
  "historical_version":version["id"],"historical_format_notes":version["format"],
  "official_reference":OFFICIAL_VERSIONS[source]["reference"],
  "previous_parser_status":prior_status,"input_bytes_sha_checked":False,
  "official_independent_values_matched":False,"third_party_values_matched":False,
  "silver_ready_promoted":False,"silver_gold_executed":False}
 if digest(bytes_)!=row["sha"]:return {**base,"status":"HOLD_ORIGINAL_SHA_MISMATCH","resolver":"VERIFY_DRIVE_ORIGINAL_SHA"}
 base["input_bytes_sha_checked"]=True
 name=detected_name(row["source_path"].split("/")[-1],bytes_)
 try:
  if source in ("TWSE","TPEx") and name.lower().endswith(".zip"):
   b,c=joint_audit(source,row,bytes_)
   details={"bc_b_status":b["status"],"bc_c_status":c["status"],
     "table_datasets":c.get("table_datasets",{}),
     "manifest_linkage":c.get("manifest_linkage",[])[:5],
     "numerics_checked":c.get("numeric_cells_checked",0),
     "numeric_invalid":c.get("invalid_numeric_cells",0),
     "official_host_claims_in_manifest":c.get("official_host_claims_in_manifest",0)}
   status=c["status"]
  else:
   d=parse_content(source,name,bytes_,ym,row["source_path"])
   status=d.get("status","HOLD_NO_PARSER_STATUS")
   details={k:v for k,v in d.items() if k!="members"}
   if "members" in d:
    details["member_count"]=len(d["members"])
    details["member_state_summary"]=dict(Counter(str(x.get("status","UNKNOWN")) for x in d["members"]))
  if source=="TAIFEX" and name.lower().endswith(".csv") and status=="HOLD_TAIFEX_CSV_WIDTH":
   details["source_native_diagnostic"]=taifex_csv_width_diagnostic(bytes_)
  if source=="MOPS" and name.lower().endswith(".zip"):
   details["source_native_diagnostic"]=mops_zip_member_diagnostic(bytes_)
  resolver=triage(source,status)
  return {**base,"status":status,"parser_detail":details,
   "resolver":resolver["resolver"],
   "required_release_evidence":resolver["required_release_evidence"],
   "independent_source_claim_verified":False}
 except (ValueError,RuntimeError,zipfile.BadZipFile,UnicodeError,KeyError,TypeError) as e:
  return {**base,"status":"HOLD_NATIVE_PARSE_"+type(e).__name__,
     "resolver":triage(source,prior_status)["resolver"]}
def worker(source):
 if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inf=match(api,quality,"v097_AP_INPUT_"+source+".json")
 cf=match(api,control,"v097_AP_CHECKPOINT_"+source+".json")
 if not inf or not cf:raise RuntimeError("FROZEN_INPUT_OR_CHECKPOINT_MISSING")
 rows=load_json(api,inf["id"])["rows"];old=load_json(api,cf["id"])["done"]
 targeted=[r for r in rows if old.get(r["source_id"],{}).get("status") not in SKIP_READY_PARSER[source]]
 name="v097_SEVEN_FORMAT_V2_CK_"+source+".json"
 f=match(api,control,name)
 checkpoint=load_json(api,f["id"]) if f else {"schema":"v097_seven_format_v2_checkpoint",
       "source":source,"version":VERSION,"done":{}}
 if checkpoint.get("version")!=VERSION:raise RuntimeError("CHECKPOINT_VERSION_MISMATCH")
 ids={x["source_id"] for x in targeted}
 if set(checkpoint["done"])-ids:raise RuntimeError("SOURCE_SCOPE_CHANGED_OR_ORPHANS")
 batch=[x for x in targeted if x["source_id"] not in checkpoint["done"]][:BATCH]
 fresh={}
 for row in batch:
  sid=row["source_id"]
  try:
   blob=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   fresh[sid]=probe(source,row,blob,old.get(sid,{}).get("status","NOT_EXAMINED"))
  except Exception as e:
   fresh[sid]={"source_id":sid,"source":source,"status":"RETRY_SOURCE_READ_"+type(e).__name__,
      "attempts":1,"silver_ready_promoted":False}
 checkpoint["done"].update(fresh);checkpoint["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 if fresh:upsert(api,control,name,checkpoint)
 status_counts=Counter(x["status"] for x in fresh.values())
 print("SEVEN_SOURCE_V2_PROGRESS="+json.dumps({"source":source,"total_targets":len(targeted),
     "already_done":len(checkpoint["done"]),"new_this_batch":len(fresh),
     "remaining":len(targeted)-len(checkpoint["done"]),
     "statuses":dict(status_counts),"silver_promoted":0},ensure_ascii=False),flush=True)
def selftest():
 from scripts.v097_bronze_autopilot import digest
 assert set(SKIP_READY_PARSER)==set(SOURCES)
 sample=json.dumps({"date":"2026-11-13","tables":[{"fields":["代號","收盤","開盤","最高","最低","成交股數"],
                  "data":[["2330","100","98","102","97","1000"]]}]},ensure_ascii=False).encode()
 for s in SOURCES:
  row={"source_id":"test","sha":digest(sample),"source_path":"2026/"+s+"/2026-11/sample.raw","year":"2026","month":"11"}
  o=probe(s,row,sample,"HOLD_UNRECOGNIZED_EXTENSION")
  assert o["historical_version"] and o["input_bytes_sha_checked"] is True
  assert o["silver_ready_promoted"] is False and not o["official_independent_values_matched"]
  assert "resolver" in o
  assert probe(s,row,b"tamper","X")["status"]=="HOLD_ORIGINAL_SHA_MISMATCH"
 assert detected_name("foo.raw",sample).endswith(".json")
 assert taifex_csv_width_diagnostic(b"date,product,volume\n20261113,TX,100,\n")["header_width"]==3
 print("SEVEN_SOURCE_NATIVE_V2_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:worker(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
