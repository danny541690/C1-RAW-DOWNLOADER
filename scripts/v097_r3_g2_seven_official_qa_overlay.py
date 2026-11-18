"""Aggregate NDC320 + first TWSE/TPEx exact native official proofs, without
touching production G2/G5 Master or previous immutable NDC shard.

Checks all source IDs against frozen seven-source manifest, native cert
content SHA evidence, independently approved original docs + source vintage.
This is an additive R3 QA overlay for observed 2026 source vintages ONLY.
"""
from __future__ import annotations
import collections,hashlib,json,os
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
DEST="R3_G2_SEVEN_SOURCE_OFFICIAL_QA_COMPOSITE_ISOLATED"
PAIRS=(
 ("TWSE","R3_G2_TWSE_FIRST_SOURCE_VINTAGE_FORMAL_ISOLATED","r3_twse_margin_financing_g2_source_vintage_cert_44268565232.json","2026-11-18"),
 ("TPEx","R3_G2_TPEX_FIRST_SOURCE_VINTAGE_FORMAL_ISOLATED","r3_tpex_valuation_g2_source_vintage_cert_44267841704.json","2026-11-18"))
def main():
 api,control,quality,match,load,_,_,call=source_api()
 cohorts={};total=0
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load,src)
  assert_cohort(rows,src);total+=len(rows);cohorts[src]={r["source_id"]:r for r in rows}
 if total!=COHORT:raise RuntimeError("SEVEN_FROZEN_COHORT_DRIFT")
 ndcf=match(api,quality,"R3_G2_BATCH_CERT_SOURCE_VINTAGE_ISOLATED")
 if not ndcf:raise RuntimeError("NDC_CERT_SHARD_FOLDER_MISSING")
 ndcshard=match(api,ndcf["id"],"r3_g2_NDC_320_native_cert_shard_run_44260700121.json")
 if not ndcshard:raise RuntimeError("NDC_320_OFFICIAL_SHARD_MISSING")
 ndc=load(api,ndcshard["id"])
 entries=ndc.get("per_file_certificates",[])
 if len(entries)!=320:raise RuntimeError("NDC_CERT_320_CONFLICT")
 certs=[];by_source=collections.Counter();hashes=set();older=0
 for e in entries:
  sid=e["source_id"];source="NDC"
  base=cohorts[source].get(sid)
  proof=e.get("g2_certificate")
  if (not base or e["source_sha256"]!=base["source_sha256"] or
     not isinstance(proof,dict) or proof.get("source")!=source or
     proof.get("source_id")!=sid or proof.get("content_sha256")!=base["source_sha256"] or
     digest(proof)!=e["g2_certificate_sha256"] or
     proof.get("historical_backtest_eligible_before_source_publication") is not False or
     proof.get("source_publication_asof")!="2026-10-23"):
    raise RuntimeError("NDC_320_SOURCE_PROOF_INVALID")
  tag=(source,sid)
  if tag in hashes:raise RuntimeError("NDC_DUPLICATE")
  hashes.add(tag);by_source[source]+=1
  certs.append({"source":source,"source_id":sid,
     "source_sha256":base["source_sha256"],"certificate_sha256":e["g2_certificate_sha256"],
     "certificate_storage":ndcshard["id"],
     "source_publication_asof":"2026-10-23",
     "historical_backtest_eligible_before_asof":False})
 proof_entries=[]
 for source,folder_name,filename,asof in PAIRS:
  folder=match(api,quality,folder_name)
  if not folder:raise RuntimeError("SOURCE_CERT_FOLDER_MISSING:"+source)
  file=match(api,folder["id"],filename)
  if not file:raise RuntimeError("SOURCE_CERT_NOT_FOUND:"+source)
  cert=load(api,file["id"]);sid=cert.get("source_id")
  base=cohorts[source].get(sid)
  if (not base or cert.get("source")!=source or
      cert.get("content_sha256")!=base["source_sha256"] or
      cert.get("source_publication_asof")!=asof or
      cert.get("historical_backtest_eligible_before_source_publication") is not False or
      cert.get("status")!="G2_PASS_CANDIDATE_NOT_COMMITTED"):
    raise RuntimeError("SOURCE_CERT_OR_FROZEN_PROOF_CONFLICT:"+source)
  if (source,sid) in hashes:raise RuntimeError("SOURCE_CERT_DUPLICATE")
  hashes.add((source,sid));by_source[source]+=1
  proof_entries.append({"source":source,"source_id":sid,"source_sha256":base["source_sha256"],
     "certificate_sha256":digest(cert),"certificate_storage":file["id"],
     "source_publication_asof":asof,
     "historical_backtest_eligible_before_asof":False})
 certs+=proof_entries
 if len(certs)!=322 or by_source["NDC"]!=320 or by_source["TWSE"]!=1 or by_source["TPEx"]!=1:
  raise RuntimeError("TOTAL_NEWLY_VERIFIED_CERT_OVERLAY_DRIFT")
 summary=[{"source":s,"frozen_cohort":len(cohorts[s]),
           "qa_validated_g2_source_vintage_certificates":by_source[s],
           "hold_or_unproven":len(cohorts[s])-by_source[s]}
          for s in SOURCES]
 master={"schema":"R3_G2_SEVEN_SOURCE_OFFICIAL_CERT_QA_OVERLAY_V1",
   "run":RUN,"cohort":COHORT,"already_published_NDC_320":320,
   "new_source_vintage_certificates":2,"qa_total_g2_verified_source_vintage":322,
   "remaining_hold":COHORT-322,
   "source_summary":summary,
   "NDC_prior_immutable_shard":ndcshard["id"],
   "two_new_individual_certificates":proof_entries,
   "all_individual_ids_and_sha_from_frozen_manifest":True,
   "no_certs_overlapping":True,"source_vintage_scope_only":True,
   "historical_contemporaneous_pit_inferred":False,
   "not_an_update_to_previous_74750_master":True,
   "not_a_production_g5_master":True,
   "bronze_modified":False,"silver_gold_materialized":False}
 folder=match(api,quality,DEST)
 if not folder:
  folder=call(lambda:api.files().create(body={"name":DEST,"parents":[quality],
   "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name="r3_g2_official_322_seven_source_QA_overlay_run_"+RUN+".json"
 fid=put_once(api,folder["id"],name,master)
 if load(api,fid)!=master:raise RuntimeError("OFFICIAL_SOURCE_VINTAGE_QA_OVERLAY_READBACK_FAILED")
 print("R3_G2_SEVEN_OFFICIAL_QA_COMPOSITE="+json.dumps({
   "run":RUN,"cohort":COHORT,"NDC":320,"TWSE":1,"TPEx":1,
   "qa_verified_source_vintage_G2":322,"remaining_HOLD":COHORT-322,
   "master_id":fid,"master_name":name,"source_summary":summary,"readback":True,
   "has_not_overwritten_production_master":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
