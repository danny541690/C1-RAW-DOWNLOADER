"""Fast evidence-backed G2 certificate SHARD: 320 per-file immutable digests,
one Drive batch/one readback, no 320 individual upload roundtrips.

The actual file-level checks, official independent template approval, source
vintage PIT guard and frozen source SHA are identical to the conservative
individual-cert engine; storage is one immutable content-addressed source
shard with an independently checked per-record digest.
"""
from __future__ import annotations
import collections,json,os
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision,confirm_g2_readback
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
FOLDER="R3_G2_BATCH_CERT_SOURCE_VINTAGE_ISOLATED"
BINDING="R3_G2_NATIVE_BINDINGS_NDC_V3.json"
APPROVAL="R3_G2_APPROVED_SHARED_TEMPLATES_V1.json"

def validate_independent(review,row,binding):
 matches=[x for x in review.get("records",[]) if x.get("source_id")==row["source_id"]
          and x.get("source_sha256")==row["source_sha256"]]
 return (len(matches)==1 and matches[0].get("mismatch_count")==0 and
         matches[0].get("source_month")+"-01"==binding.get("source_data_date") and
         matches[0].get("archive_sha256")==binding.get("native_date_evidence_sha256") and
         review.get("published_archive_sha256")==binding.get("native_date_evidence_sha256") and
         binding.get("historical_backtest_eligible_before_source_publication") is False)

def run():
 api,control,quality,match,load,_,_,call=source_api()
 rf=match(api,control,APPROVAL);bf=match(api,control,BINDING)
 if not rf or not bf:raise RuntimeError("NO_APPROVED_TEMPLATE_OR_V3")
 registry=load(api,rf["id"]);bindings=load(api,bf["id"])
 if bindings.get("schema")!="R3_G2_NATIVE_BINDINGS_V1" or len(bindings.get("done",{}))!=320:
  raise RuntimeError("V3_NOT_COMPLETE_320")
 t,reason=approved_template(registry,group_candidates()[("NDC","BUSINESS_SIGNAL","NDC_SIGNAL_2024")],verify_document_factory(api,call,load))
 if not t or len(t)!=1 or t[0].get("era_basis")!="source_publication_vintage":
  raise RuntimeError("INDEPENDENT_APPROVAL_NOT_VALID:"+reason)
 candidate_rows=[];cache={};tot=0;summary=[]
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src);tot+=len(rows)
  if src!="NDC":
   summary.append({"source":src,"cohort":len(rows),"pass":0,"hold":len(rows),"reason":"NO_APPROVED_SHARED_DATASET_ERA"})
   continue
  ids={r["source_id"] for r in rows}
  if set(bindings["done"])!=ids:raise RuntimeError("NDC_V3_FROZEN_IDS_MISMATCH")
  for row in rows:
   b=bindings["done"][row["source_id"]]
   ref=b.get("independent_evidence_id")
   if not isinstance(ref,str) or not ref:raise RuntimeError("EMPTY_INDEPENDENT_NATIVE_REFERENCE")
   if ref not in cache:cache[ref]=load(api,ref)
   if not validate_independent(cache[ref],row,b):
    raise RuntimeError("NATIVE_INDEPENDENT_PER_FILE_PROOF_MISMATCH")
   v=file_decision(row,t,b)
   if v["status"]!="CANDIDATE":raise RuntimeError("NOT_FORMALLY_ELIGIBLE:"+str(v.get("reason")))
   candidate_rows.append({"source_id":row["source_id"],"source_sha256":row["source_sha256"],
     "g2_certificate":v["certificate"],"g2_certificate_sha256":v["certificate_sha256"],
     "native_review_document_id":ref})
  summary.append({"source":"NDC","cohort":len(rows),"pass":len(candidate_rows),"hold":0,
                  "source_vintage_asof":"2026-10-23","historical_pit_pre_asof_verified":False})
 if tot!=COHORT or len(candidate_rows)!=320:raise RuntimeError("FULL_CENSUS_OR_PER_FILE_CERT_COUNT_DRIFT")
 folder=match(api,quality,FOLDER)
 if not folder:folder=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
                 "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if folder["mimeType"]!="application/vnd.google-apps.folder":raise RuntimeError("QA_FOLDER_NOT_FOLDER")
 batch={"schema":"R3_G2_PER_FILE_CERTIFICATE_IMMUTABLE_SHARD_V1","run":RUN,
        "source":"NDC","original_approved_template_id":t[0]["template_id"],
        "official_document_sha256":t[0]["official_document_sha256"],
        "source_publication_asof":"2026-10-23",
        "backtest_eligible_before_source_asof":False,
        "frozen_cohort":320,"per_file_certificates":candidate_rows}
 name="r3_g2_NDC_320_native_cert_shard_run_"+RUN+".json"
 shardid=put_once(api,folder["id"],name,batch)
 read=load(api,shardid)
 if read!=batch:raise RuntimeError("OFFICIAL_SHARD_DRIVE_READBACK_NOT_EXACT")
 for entry in read["per_file_certificates"]:
  proof={"status":"CANDIDATE","certificate":entry["g2_certificate"],
        "certificate_sha256":entry["g2_certificate_sha256"]}
  if confirm_g2_readback(proof,entry["g2_certificate"])["status"]!="PASS":
   raise RuntimeError("PER_FILE_DIGEST_NOT_DURABLY_VERIFIED")
 expected_pass=sum(x["pass"] for x in summary)
 expected_hold=sum(x["hold"] for x in summary)
 if expected_pass!=320 or expected_hold!=COHORT-320:
  raise RuntimeError("SEVEN_SOURCE_COMPLETION_COUNTER_DRIFT")
 master={"schema":"R3_G2_74750_BATCH_CERTIFIED_QA_MASTER_V1","run":RUN,
         "cohort":COHORT,"g2_formal_per_file_pass":expected_pass,
         "g2_hold":expected_hold,"approved_template_count":1,
         "verified_per_file_certificate_shard_id":shardid,
         "verified_per_file_certificate_shard_sha256":digest(batch),
         "shard_exact_remote_readback":True,
         "source_summary":summary,
         "historical_vintage_backtest_before_2026_10_23_allowed":False,
         "bronze_modified":False,"silver_gold_materialized":False,
         "not_a_production_g5_master":True}
 mname="r3_g2_74750_certified_batch_master_run_"+RUN+".json"
 mid=put_once(api,folder["id"],mname,master)
 if load(api,mid)!=master:raise RuntimeError("G2_BATCH_MASTER_REMOTE_READBACK_FAILED")
 print("R3_G2_FAST_BATCH_74750="+json.dumps({
  "run":RUN,"cohort":COHORT,"g2_pass":expected_pass,"g2_hold":expected_hold,
  "NDC_2026_source_vintage_pass":320,"cert_shard_id":shardid,
  "cert_shard_sha256":digest(batch),"master_id":mid,"master_name":mname,
  "independent_native_review_documents":len(cache),
  "all_receipts_readback":True,"historical_pre_asof_backtest_allowed":False,
  "per_source":summary},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":run()
