"""Immutable R3 seven-source G2 QA overlay 324 (previous 322 + FinMind 2).
Does not overwrite existing 322 QA, primary production G5 or Bronze.
"""
import json,os,hashlib
from collections import Counter
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
NEW_FOLDER="R3_G2_FINMIND_FIRST_FORMAL_SOURCE_VINTAGE_ISOLATED"
OLD_FOLDER="R3_G2_SEVEN_SOURCE_OFFICIAL_QA_COMPOSITE_ISOLATED"
OUT="R3_G2_SEVEN_SOURCE_QA_324_IMMUTABLE_ISOLATED"
OLD_NAME="r3_g2_official_322_seven_source_QA_overlay_run_44269047906.json"
NEW_NAME="r3_finmind_first_two_g2_source_vintage_master_run_44278523779.json"
def main():
 api,control,quality,match,load,_,_,call=source_api()
 oldfolder=match(api,quality,OLD_FOLDER);newfolder=match(api,quality,NEW_FOLDER)
 if not oldfolder or not newfolder:raise RuntimeError("REQUIRED_PREVIOUS_QA_FOLDERS_MISSING")
 old=match(api,oldfolder["id"],OLD_NAME);new=match(api,newfolder["id"],NEW_NAME)
 if not old or not new:raise RuntimeError("REQUIRED_IMMUTABLE_322_AND_NEW_2_MASTERS_MISSING")
 existing=load(api,old["id"]);latest=load(api,new["id"])
 if existing.get("qa_total_g2_verified_source_vintage")!=322 or latest.get("formally_certified_new_files")!=2:
  raise RuntimeError("PREVIOUS_QA_COUNTS_NOT_VERIFIED")
 counts={x["source"]:x["qa_validated_g2_source_vintage_certificates"] for x in existing["source_summary"]}
 if counts!={"TWSE":1,"TPEx":1,"MOPS":0,"TDCC":0,"TAIFEX":0,"NDC":320,"FinMind":0}:
  raise RuntimeError("SEVEN_PREVIOUS_SOURCE_PROOFS_CHANGED")
 cohort=0;finrows=None
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src);cohort+=len(rows)
  if src=="FinMind":finrows={x["source_id"]:x for x in rows}
 if cohort!=COHORT:raise RuntimeError("FROZEN_74750_COHORT_NOT_SAME")
 validated=[]
 for x in latest["certificates"]:
  sid=x["source_id"];r=finrows.get(sid)
  if not r or x["source_sha256"]!=r["source_sha256"]:
   raise RuntimeError("NEW_FINMIND_CERT_BROKEN_FROZEN_ID_SHA")
  cert=load(api,x["certificate_id"])
  if (digest(cert)!=x["certificate_sha256"] or
      cert.get("source_id")!=sid or cert.get("content_sha256")!=r["source_sha256"] or
      cert.get("source")!="FinMind" or
      cert.get("historical_backtest_eligible_before_source_publication") is not False or
      cert.get("source_publication_asof")!="2026-11-18"):
   raise RuntimeError("NEW_CERT_NOT_REAL_G2_SOURCE_VINTAGE")
  validated.append({"source_id":sid,"certificate_id":x["certificate_id"],"sha256":x["certificate_sha256"]})
 if len(set(x["source_id"] for x in validated))!=2:raise RuntimeError("DUPLICATE_FINMIND_ADD_ON")
 counts["FinMind"]=2
 summary=[{"source":src,"frozen_cohort":next(x["frozen_cohort"] for x in existing["source_summary"] if x["source"]==src),
            "g2_verified_source_vintage":counts[src],
            "still_unproven":next(x["frozen_cohort"] for x in existing["source_summary"] if x["source"]==src)-counts[src]} for src in SOURCES]
 if sum(x["g2_verified_source_vintage"] for x in summary)!=324:raise RuntimeError("SEVEN_SOURCE_TOTAL_NOT_324")
 master={"schema":"R3_G2_SEVEN_SOURCE_FROZEN_324_SOURCE_VINTAGE_QA_OVERLAY_V1",
  "run":RUN,"previous_322_source_qa_master_id":old["id"],
  "new_finmind_2_formal_master_id":new["id"],
  "new_finmind_individual_certificates":validated,"cohort":COHORT,
  "verified_g2_source_vintage_pass":324,"remaining_hold":COHORT-324,
  "source_summary":summary,"new_source_native_shared_template_count":1,
  "no_historical_2000_2022_contemporaneous_pit":True,
  "not_production_g5_or_silver_ready":True,
  "bronze_modified":False,"silver_gold_materialized":False}
 folder=match(api,quality,OUT)
 if not folder:folder=call(lambda:api.files().create(body={"name":OUT,"parents":[quality],
    "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name="r3_g2_74750_324_official_source_vintage_qa_master_run_"+RUN+".json"
 fid=put_once(api,folder["id"],name,master)
 if load(api,fid)!=master:raise RuntimeError("LATEST_SEVEN_G2_MASTER_NOT_REMOTE_READBACK")
 print("R3_G2_324_SEVEN_QA_MASTER="+json.dumps({
  "run":RUN,"cohort":COHORT,"certified":324,"hold":COHORT-324,
  "seven_source_counts":counts,"master_id":fid,"new_finmind_certs":validated,
  "readback_verified":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
