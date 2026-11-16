#!/usr/bin/env python3
"""JARVIS v0.97 Bronze v2.1 DIRECT Silver-input readiness (no Silver conversion).

Read frozen 74750 and old immutable source QA; re-audit exact copy/receipt SHA
and all-known source-native semantics before granting additional Bronze READY.
Leave historical PIT/backtest eligibility FALSE. Write separate v2.1 release,
not the v1 release files. Unknown or ambiguous source-specific data stays HOLD.
"""
import json,os,sys,re,hashlib
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api
from scripts.v097_ap_silver_input_gate_all import build as old_build
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_bronze_first_batch_v3 import ck_name
from scripts.v097_bronze_first_pipeline import common,match,load_json
VERSION="v097_bronze_direct_release_v21_1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
PREFIX="v097_BRONZE_V21_SOURCE_RELEASE_"
HASH=re.compile("[0-9a-f]{64}\\Z")
def ishash(h):return isinstance(h,str) and bool(HASH.fullmatch(h))
def strict_new_candidate(src,row,old,native,copy,qa):
 """The source was already independently re-read in 0.93->0.97 V3 QA.
 Do not reparse a shape-only claim as full QA; no third-party comparison."""
 if not copy or not qa or copy.get("state")!="COPY_MATCHED_PENDING_INDEPENDENT_QA" or qa.get("state")!="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":
  return "HOLD_V3_COPY_AND_INDEPENDENT_SHA_QA"
 if copy.get("dest_id")!=row["dest_id"] or copy.get("source_path")!=row["source_path"] or copy.get("sha")!=row["sha"] or not ishash(row["sha"]):
  return "HOLD_V3_COPY_PROVENANCE_CONFLICT"
 if not old.get("receipt") or old.get("source_sha256")!=row["sha"] or old.get("destination_id")!=row["dest_id"]:
  return "HOLD_EXACT_CONTENT_RECEIPT_MISSING"
 if not native or native.get("source_id")!=row["source_id"] or native.get("bronze_sha256")!=row["sha"] or native.get("input_bytes_sha_checked") is not True:
  return "HOLD_NATIVE_BYTES_NOT_VERIFIED"
 st=str(native.get("status",""))
 if st.startswith(("HOLD_","RETRY_")):return "HOLD_HISTORICAL_FORMAT_OR_CONTENT"
 d=native.get("parser_detail",{})
 if src in ("TWSE","TPEx") and st=="C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING":
  # Dataset names and URL claims in a self-written ZIP manifest do NOT
  # independently verify actual publisher identity. Reuse source V3 SHA
  # provenance plus verified exhaustive member checks from native V2.
  if d.get("bc_c_status")!=st or d.get("numeric_invalid")!=0 or d.get("numerics_checked",0)<=0:
   return "HOLD_FULL_ARCHIVE_NUMERIC_QA"
  ds=d.get("table_datasets",{})
  if not ds or "UNRESOLVED_SCHEMA" in ds:
   return "HOLD_ARCHIVE_DATASET_IDENTITY"
  if not d.get("manifest_linkage") or not d.get("official_host_claims_in_manifest"):
   return "HOLD_ARCHIVE_SOURCE_MANIFEST_OR_HOST"
  deep=d.get("deep_content",{})
  if str(deep.get("status","")).startswith(("HOLD_","ERROR_")):
   return "HOLD_NATIVE_DEEP_CONTENT"
  # V2 B/C says *official recheck pending*: is not enough to certify
  # official download alone. Require an independent publisher receipt.
  return "HOLD_ORIGINAL_OFFICIAL_DOWNLOAD_RECEIPT_REQUIRED"
 if src=="FinMind" and st=="FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD":
  if d.get("member_count",0)>0 and d.get("rows_checked",0)>0 and d.get("unit_count",0)>0 and d.get("members_verified",0)>=2:
   return "HOLD_PROVIDER_ORIGIN_DOWNLOAD_RECEIPT_REQUIRED"
  return "HOLD_FINMIND_ARCHIVE_FULL_QA"
 if src=="MOPS":
  return "HOLD_MOPS_TABLE_FIELD_AND_ACCOUNTING_QA_NOT_PROVEN"
 if src=="TDCC":
  return "HOLD_TDCC_SECURITY_CLASS_AND_DATE_QA"
 if src=="TAIFEX":
  return "HOLD_TAIFEX_COMPLETE_CSV_DATASET_QA"
 if src=="NDC":
  return "HOLD_NDC_HISTORICAL_CELL_ORIGIN_QA"
 return "HOLD_DATASET_SPECIFIC_PROOF"
def decision(src,row,formal,old,native,copy,qa):
 if formal.get("status")==READY:return "READY_PRESERVED_FORMAL_V1"
 if old.get("status")==READY:
  # Old gate passed its separate receipt check; protect its provenance
  # with an independent V3 source/destination SHA and QA before v2.1.
  if copy and qa and copy.get("state")=="COPY_MATCHED_PENDING_INDEPENDENT_QA" and qa.get("state")=="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS" and copy.get("sha")==row["sha"] and copy.get("dest_id")==row["dest_id"] and old.get("source_sha256")==row["sha"] and old.get("receipt"):
   return "READY_NEW_V21_FROM_EXISTING_SOURCE_GATE_AND_V3_QA"
  return "HOLD_OLD_GATE_V3_SHA_RECEIPT_CONFLICT"
 return strict_new_candidate(src,row,old,native,copy,qa)
def selftest():
 row={"source_id":"x","dest_id":"dest","sha":"a"*64,"source_path":"2026/TWSE/2026-11/file.zip"}
 old={"status":"HOLD","receipt":"receipt","source_sha256":"a"*64,"destination_id":"dest"}
 copy={"state":"COPY_MATCHED_PENDING_INDEPENDENT_QA","source_path":row["source_path"],"dest_id":"dest","sha":"a"*64}
 qa={"state":"BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"}
 n={"source_id":"x","bronze_sha256":"a"*64,"input_bytes_sha_checked":True,"status":"C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING","parser_detail":{"bc_c_status":"C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING","numerics_checked":15,"numeric_invalid":0,"table_datasets":{"QUOTES":1},"manifest_linkage":[{"x":1}],"official_host_claims_in_manifest":1}}
 assert decision("TWSE",row,{"status":READY},old,None,None,None)=="READY_PRESERVED_FORMAL_V1"
 assert decision("TWSE",row,{"status":"HOLD"},{**old,"status":READY},n,copy,qa)=="READY_NEW_V21_FROM_EXISTING_SOURCE_GATE_AND_V3_QA"
 assert decision("TWSE",row,{"status":"HOLD"},old,n,copy,qa)=="HOLD_ORIGINAL_OFFICIAL_DOWNLOAD_RECEIPT_REQUIRED"
 assert decision("TWSE",row,{"status":"HOLD"},old,{**n,"bronze_sha256":"f"*64},copy,qa)=="HOLD_NATIVE_BYTES_NOT_VERIFIED"
 assert decision("TWSE",row,{"status":"HOLD"},old,n,copy,{**qa,"state":"HOLD"})=="HOLD_V3_COPY_AND_INDEPENDENT_SHA_QA"
 assert decision("TWSE",row,{"status":"HOLD"},old,{**n,"status":"HOLD_BAD_ZIP"},copy,qa)=="HOLD_HISTORICAL_FORMAT_OR_CONTENT"
 print("BRONZE_V21_DIRECT_RELEASE_NEGATIVE_TESTS_PASS")
def source(src):
 if src not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,_,_=source_api()
 orig_name="v097_AP_INPUT_"+src+".json"
 inp=match(api,quality,orig_name)
 if not inp:raise RuntimeError("MISSING_FROZEN_INPUT")
 rows=load_json(api,inp["id"])["rows"]
 if len(rows)!=len({r["source_id"] for r in rows}):raise RuntimeError("DUPLICATE_FROZEN_ID")
 byid={r["source_id"]:r for r in rows}
 rid,formal=latest_complete(api,quality,match,load_json)
 fby={r["source_id"]:r for r in formal[src]["records"]}
 if set(fby)!=set(byid):raise RuntimeError("FORMAL_SOURCE_ID_COHORT_CONFLICT")
 f=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+src+".json")
 native=load_json(api,f["id"]).get("done",{}) if f else {}
 v3copy={};v3qa={}
 for lane in range(6):
  c=match(api,control,ck_name("COPY",lane))
  q=match(api,control,ck_name("QA",lane))
  if not c or not q:raise RuntimeError("MISSING_V3_COPY_QA_CHECKPOINT")
  co=load_json(api,c["id"]).get("done",{})
  qa=load_json(api,q["id"]).get("done",{})
  for sid,value in co.items():
   if sid in byid:
    if sid in v3copy:raise RuntimeError("DUPLICATE_SOURCE_V3_COPY")
    v3copy[sid]=value;v3qa[sid]=qa.get(sid)
 prior=old_build(src,api,control,quality,match,load_json)
 oby={x["source_id"]:x for x in prior["records"]}
 if set(oby)!=set(byid):raise RuntimeError("OLD_GATE_SOURCE_COHORT_CONFLICT")
 final=[];counts=Counter()
 for row in rows:
  sid=row["source_id"]
  state=decision(src,row,fby[sid],oby[sid],native.get(sid),v3copy.get(sid),v3qa.get(sid))
  approved=state.startswith("READY_")
  counts["BRONZE_READY_FOR_SILVER" if approved else "HOLD"]+=1
  counts[state]+=1
  final.append({"source_id":sid,"source":src,"source_sha256":row["sha"],"destination_id":row["dest_id"],
    "source_path":row["source_path"],"status":READY if approved else "HOLD",
    "decision_detail":state,"receipt":oby[sid].get("receipt"),
    "source_gate_version":VERSION,"silver_input_only":approved,
    "pit_backtest_approved":False,"silver_gold_executed":False})
 if len(final)!=len(rows):raise RuntimeError("RELEASE_COHORT_COUNT_CONFLICT")
 existing=sum(r["status"]==READY for r in fby.values())
 current=counts["BRONZE_READY_FOR_SILVER"]
 if current<existing:raise RuntimeError("EXISTING_READY_MUST_BE_PRESERVED")
 report={"schema":VERSION,"run":RUN,"source":src,"reference_formal_run":rid,
  "created_at":datetime.now(timezone.utc).isoformat(),"cohort":len(rows),
  "ready":current,"hold":len(rows)-current,"newly_ready":current-existing,
  "counts":dict(counts),"release_mode":"DIRECT_IF_VERIFIED_NO_SHADOW_ONLY",
  "third_party_required":False,"pit_backtest_approved":False,
  "silver_gold_executed":False,"raw_modified":False,"records":final}
 if RUN!="manual":put_once(api,quality,PREFIX+src+"_"+RUN+".json",report)
 print("BRONZE_V21_SOURCE_RELEASE="+json.dumps({k:v for k,v in report.items() if k!="records"},ensure_ascii=False),flush=True)
def final():
 api,control,quality,match,load_json,put_once,_,_=source_api()
 counts=Counter();details={}
 seen=set()
 for src in SOURCES:
  f=match(api,quality,PREFIX+src+"_"+RUN+".json")
  if not f:raise RuntimeError("MISSING_SOURCE_RELEASE_"+src)
  r=load_json(api,f["id"])
  if r["run"]!=RUN or r["source"]!=src or r["schema"]!=VERSION or r["silver_gold_executed"] is not False:
   raise RuntimeError("SOURCE_RELEASE_IDENTITY_CONFLICT")
  rr=r["records"];ids=[x["source_id"] for x in rr]
  if len(ids)!=len(set(ids)) or set(ids)&seen:raise RuntimeError("RELEASE_DUPLICATE_IDS")
  seen.update(ids)
  if len(ids)!=r["cohort"]:raise RuntimeError("SOURCE_RELEASE_COUNT_CONFLICT")
  c=Counter(x["status"] for x in rr)
  if c[READY]!=r["ready"] or c["HOLD"]!=r["hold"]:raise RuntimeError("SOURCE_RELEASE_COUNT_MISMATCH")
  counts.update(c);details[src]={k:r[k] for k in ("ready","hold","newly_ready","cohort")}
 if len(seen)!=74750 or counts[READY]+counts["HOLD"]!=74750:raise RuntimeError("FULL_RELEASE_COHORT_NOT_74750")
 result={"schema":VERSION,"run":RUN,"cohort":74750,
  "ready":counts[READY],"hold":counts["HOLD"],
  "newly_ready":sum(d["newly_ready"] for d in details.values()),
  "by_source":details,"silver_input_eligible":True,
  "silver_gold_executed":False,"pit_backtest_approved":False,
  "formal_v1_unchanged":True,"published_v21_signed_receipts":True}
 if RUN!="manual":put_once(api,quality,"v097_BRONZE_V21_FINAL_RELEASE_"+RUN+".json",result)
 print("BRONZE_V21_FINAL_RELEASE="+json.dumps(result,ensure_ascii=False),flush=True)
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2 and sys.argv[1]=="final":final()
 elif len(sys.argv)==2 and sys.argv[1] in SOURCES:source(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE | final")
