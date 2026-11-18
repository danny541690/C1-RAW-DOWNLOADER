"""R3 NDC incremental G2: validate 320 archived JSON rows against official XLSX.

Uses the same independently live-verified government XLSX SHA and the first
10 formally approved source-vintage certificate scheme. Preserves first 10
immutable certificates and bindings, places new evidence in separate Drive
review, and writes a versioned, additive NDC binding registry. Never makes
earlier-year PIT claims or touches R1/V3/Bronze/Silver/Gold.
"""
from __future__ import annotations
import collections,datetime,hashlib,json,os,re
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_ndc_xlsx_native_crosscheck import xml_workbook,check_one
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision
DOC_SHA="c035dc5bbd3fe91ca80a620fd84828a54e8c49885a1b3aa51db5e42857772c83"
ASOF="2026-10-23"
RUN=os.getenv("GITHUB_RUN_ID","manual")
TEMPLATE_ID="NDC_2026_CAPTURED_REVISED_XLSX_5SHEET_JSON_V1"

def main():
 api,control,quality,match,load,_,_,call=source_api()
 first=match(api,quality,"R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED")
 if not first:raise RuntimeError("FIRST_REAL_SOURCE_FOLDER_MISSING")
 old=match(api,control,"R3_G2_NATIVE_BINDINGS_NDC.json")
 approvedfile=match(api,control,"R3_G2_APPROVED_SHARED_TEMPLATES_V1.json")
 if not old or not approvedfile:raise RuntimeError("FIRST_TEN_FORMAL_APPROVAL_NOT_COMMITTED")
 prev=load(api,old["id"]);reg=load(api,approvedfile["id"])
 if prev.get("schema")!="R3_G2_NATIVE_BINDINGS_V1" or len(prev.get("done",{}))!=10:
  raise RuntimeError("FIRST_TEN_BINDINGS_NOT_EXACT")
 contract=group_candidates()[("NDC","BUSINESS_SIGNAL","NDC_SIGNAL_2024")]
 active,reason=approved_template(reg,contract,verify_document_factory(api,call,load))
 if not active or len(active)!=1 or active[0]["template_id"]!=TEMPLATE_ID:
  raise RuntimeError("OFFICIAL_APPROVED_TEMPLATE_FAILED_RECHECK:"+reason)
 original_id=active[0]["official_document_drive_id"]
 official=call(lambda:api.files().get_media(fileId=original_id))
 if hashlib.sha256(official).hexdigest()!=DOC_SHA:raise RuntimeError("OFFICIAL_NATIVE_XLSX_SHA_CHANGED")
 worksheets=xml_workbook(official)
 rows=read_baseline(api,quality,match,load,"NDC");assert_cohort(rows,"NDC")
 known={r["source_id"]:r for r in rows}
 if set(prev["done"])-set(known):raise RuntimeError("PREVIOUS_APPROVED_BINDINGS_ORPHAN")
 saved=[]
 records=[]
 holds=collections.Counter()
 valid=collections.Counter()
 for row in rows:
  sid=row["source_id"]
  if sid in prev["done"]:
   # Do not overwrite/re-key any already certified old G2 provenance.
   saved.append(("REUSED",sid,None))
   valid["reused_first_pass"]+=1
   continue
  doc=None;status="HOLD";reason="UNKNOWN"
  try:
   raw=call(lambda:api.files().get_media(fileId=row["destination_id"]))
   if hashlib.sha256(raw).hexdigest()!=row["source_sha256"]:raise ValueError("BRONZE_SHA_CONFLICT")
   doc=json.loads(raw.decode("utf-8-sig"))
   ar=doc.get("source_archive") or {}
   if (doc.get("source")!="NDC" or ar.get("file_id")!=original_id or
       ar.get("sha256")!=DOC_SHA or ar.get("remote_readback_hash_verified") is not True):
    raise ValueError("HISTORIC_SOURCE_ARCHIVE_NOT_SAME_VERIFIED_VINTAGE")
   month=doc.get("month")
   if not isinstance(month,str) or not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])",month):
    raise ValueError("NATIVE_MONTH_INVALID")
   if month>ASOF[:7]:
    raise ValueError("OBSERVATION_AFTER_VERIFIED_ARCHIVE_ASOF")
   if len(doc.get("tables",[]))!=5:raise ValueError("NATIVE_FIVE_SHEETS_NOT_PRESENT")
   checked=check_one(doc,worksheets)
   if checked["mismatch_count"]:raise ValueError("NATIVE_ORIGINAL_CELL_MISMATCH")
   status="NATIVE_MATCH"
   reason="SOURCE_VINTAGE_NATIVE_VERIFIED"
   valid["new_native_match"]+=1
   valid["verified_values"]+=checked["verified_cells"]
   valid["documented_original_blanks"]+=checked["documented_native_blanks"]
   proof={"source_id":sid,"source_sha256":row["source_sha256"],
          "source_month":month,"archive_sha256":DOC_SHA,
          "verified_values":checked["verified_cells"],
          "documented_original_blanks":checked["documented_native_blanks"],
          "mismatch_count":0}
   saved.append((status,sid,proof))
  except Exception as e:
   reason=str(e) if isinstance(e,ValueError) else type(e).__name__
   holds[reason]+=1
   saved.append(("HOLD",sid,None))
  records.append({"source_id":sid,"source_sha256":row["source_sha256"],
                  "status":status,"reason":reason,
                  "source_month":doc.get("month") if isinstance(doc,dict) else None})
 review={"schema":"R3_NDC_VINTAGE_ALL_320_INDEPENDENT_NATIVE_CELL_REVIEW_V1",
         "run":RUN,"source":"NDC","official_document_drive_id":original_id,
         "published_archive_sha256":DOC_SHA,"earliest_proven_asof":ASOF,
         "original_first_10_bindings_unchanged":True,
         "records":[p for st,sid,p in saved if st=="NATIVE_MATCH"],
         "holds":dict(holds),
         "source_vintage_historical_asof_not_certified":True,
         "backtest_eligible_before_snapshot":False}
 reviewname="r3_ndc_320_native_incremental_review_run_"+RUN+".json"
 reviewid=put_once(api,first["id"],reviewname,review)
 if load(api,reviewid)!=review:raise RuntimeError("NEW_NATIVE_REVIEW_REMOTE_READBACK_FAILED")
 binds=dict(prev["done"])
 for status,sid,p in saved:
  if status!="NATIVE_MATCH":continue
  row=known[sid]
  b={"source_id":sid,"source":"NDC","source_sha256":row["source_sha256"],
     "source_document_sha256":row["source_sha256"],"source_path":row["source_path"],
     "dataset":"BUSINESS_SIGNAL","historical_era":"NDC_SIGNAL_2024",
     "native_format":"JSON","native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
     "source_data_date":p["source_month"]+"-01",
     "source_data_date_verified":True,"native_date_evidence_sha256":DOC_SHA,
     "publication_asof_verified":True,"native_layout_verified":True,
     "dataset_origin_verified":True,"independent_evidence_id":reviewid,
     "binding_version":"R3_NDC_VINTAGE_V1","source_publication_asof":ASOF,
     "source_publication_asof_verified":True,
     "historical_backtest_eligible_before_source_publication":False}
  decision=file_decision(row,active,b)
  if decision["status"]!="CANDIDATE":
   raise RuntimeError("NEW_NDC_FORMAL_GATE_FAILED:"+str(decision.get("reason")))
  binds[sid]=b
 if len(binds)!=valid["reused_first_pass"]+valid["new_native_match"]:
  raise RuntimeError("INCREMENTAL_BINDING_COUNT_DRIFT")
 # The new V2 registry is immutable, additive, and preserves all old
 # certificate digests. Old version remains available for audit/replay.
 name="R3_G2_NATIVE_BINDINGS_NDC_V2.json"
 payload={"schema":"R3_G2_NATIVE_BINDINGS_V1","registry_version":"R3_NDC_V2_INCREMENTAL",
          "source":"NDC","canonical_prior_registry_id":old["id"],
          "native_full_review_receipt_id":reviewid,"done":binds,
          "backtest_eligible_before_source_publication":False}
 new_id=put_once(api,control,name,payload)
 if load(api,new_id)!=payload:raise RuntimeError("NEW_BINDING_REGISTRY_READBACK_MISMATCH")
 out={"schema":"R3_NDC_320_G2_CANDIDATE_REVIEW_V1","run":RUN,
      "source":"NDC","total":len(rows),"previous_g2":valid["reused_first_pass"],
      "additional_formal_candidate":valid["new_native_match"],
      "remaining_native_hold":sum(holds.values()),"reasons":dict(holds),
      "verified_values":valid["verified_values"],
      "documented_original_blanks":valid["documented_original_blanks"],
      "crosscheck_receipt_id":reviewid,"binding_registry_id":new_id,
      "binding_registry_name":name,
      "source_asof":ASOF,"source_vintage_historical_pit_not_verified":True,
      "bronze_modified":False,"silver_gold_materialized":False,
      "records":records}
 receipt_name="r3_ndc_320_incremental_native_summary_run_"+RUN+".json"
 id=put_once(api,first["id"],receipt_name,out)
 if load(api,id)!=out:raise RuntimeError("INCREMENTAL_SUMMARY_READBACK_CONFLICT")
 print("R3_NDC_320_INCREMENTAL="+json.dumps({
  "run":RUN,"cohort":len(rows),"previous_g2":valid["reused_first_pass"],
  "new_native_verified":valid["new_native_match"],
  "remaining_hold":sum(holds.values()),"hold_reasons":dict(holds),
  "cells_verified":valid["verified_values"],"documented_blanks":valid["documented_original_blanks"],
  "new_binding_registry_id":new_id,"independent_review_id":reviewid,
  "readback":True},sort_keys=True),flush=True)
if __name__=="__main__":main()
