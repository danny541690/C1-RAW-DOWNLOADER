"""R3 seven-source template-vs-frozen-database reconciliation.

Always creates exactly seven source-owned libraries; each has dataset historical
date versions with fields, aliases, key and official evidence state.
Source path dates are LOOKUP HINTS, NEVER official dates or G2 certificates.
Reuses independently approved NDC 320 binding and 60 real verified native
samples; does not fabricate official evidence, mutate Bronze, Silver or Gold.
"""
from __future__ import annotations
import collections,datetime,json,os,re
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_g2g3_formal_contracts_v2 import contract
from scripts.v097_r3_g2_seven_source_periodic_templates import library_set
from scripts.v097_r3_g2_shared_contract_engine import approved_template,file_decision,group_candidates
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import SOURCES,COHORT,digest
from scripts.v097_seven_historical_format_registry import period

RUN=os.getenv("GITHUB_RUN_ID","manual")
TARGET="R3_G2_SEVEN_SOURCE_PERIODIC_TEMPLATE_COMPARE_ISOLATED"
APPROVAL="R3_G2_APPROVED_SHARED_TEMPLATES_V1.json"
PRIOR="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
DATE_RE=re.compile(r"(20\\d{2})[-_/]?(0[1-9]|1[0-2])")
NDC_BINDING="R3_G2_NATIVE_BINDINGS_NDC_V3.json"
PILOT_RUN="44261840978"

def path_month(path):
 m=DATE_RE.search(str(path))
 return m.group(1)+"-"+m.group(2) if m else None

def main():
 api,control,quality,match,load,_,_,call=source_api()
 registry_file=match(api,control,APPROVAL)
 official=load(api,registry_file["id"]) if registry_file else {"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[]}
 if not isinstance(official,dict) or not isinstance(official.get("templates"),list):
  raise RuntimeError("FORMAL_OFFICIAL_REGISTRY_MALFORMED")
 libraries=library_set(official)
 official_checks=collections.defaultdict(list)
 checker=verify_document_factory(api,call,load)
 for t in group_candidates().values():
  a,r=approved_template(official,t,checker)
  official_checks[(t["source"],t["dataset"],t["historical_era"])].extend(a or [])
 target=match(api,quality,TARGET)
 if not target:
  target=call(lambda:api.files().create(body={"name":TARGET,"parents":[quality],
    "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if target.get("mimeType")!="application/vnd.google-apps.folder":
  raise RuntimeError("TARGET_NOT_DIRECTORY")
 earlier=match(api,quality,PRIOR)
 nfile=match(api,control,NDC_BINDING)
 if not nfile:raise RuntimeError("NDC_320_FORMAL_BINDINGS_MISSING")
 ndc=load(api,nfile["id"])
 if len(ndc.get("done",{}))!=320:raise RuntimeError("NDC_320_DRIFT")
 source_reports=[];total=0;formal_total=0
 for src in SOURCES:
  tpl=libraries[src]
  template_name=f"r3_g2_shared_source_template_{src}_run_{RUN}.json"
  tid=put_once(api,target["id"],template_name,tpl)
  if load(api,tid)!=tpl:raise RuntimeError("SOURCE_TEMPLATE_READBACK_"+src)
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src)
  total+=len(rows)
  sourcecount=collections.Counter();rowsout=[]
  native_samples={}
  if src!="NDC":
   if earlier is None:raise RuntimeError("PRIOR_SIX_NATIVE_SAMPLE_MISSING")
   sf=match(api,earlier["id"],f"r3_g2_pilot_{src}_10_run_{PILOT_RUN}.json")
   if not sf:raise RuntimeError("PRIOR_SOURCE_PILOT_RECEIPT_MISSING_"+src)
   samples=load(api,sf["id"])["samples"]
   if len(samples)!=10:raise RuntimeError("PRIOR_REAL_NATIVE_SAMPLES_NOT_TEN_"+src)
   native_samples={r["source_id"]:r for r in samples}
  fullrows=0
  for row in rows:
   sid=row["source_id"]
   binding=ndc["done"].get(sid) if src=="NDC" else None
   hint=path_month(row.get("source_path"))
   # Source-wide period matching is useful lookup, but is NOT dataset / native
   # format attestation. File release is ONLY from independently approved bind.
   era=None
   if hint:
    try:era=period(src,hint)["id"]
    except ValueError:pass
   if src=="NDC" and isinstance(binding,dict):
    key=(src,binding.get("dataset"),binding.get("historical_era"))
    matched=official_checks.get(key,[])
    candidate=file_decision(row,matched,binding)
    # Actual G2 cert was already independently emitted and read back in
    # 44260700121. Do not re-label without matching that immutable receipt.
    if (candidate["status"]=="CANDIDATE" and
        binding.get("historical_backtest_eligible_before_source_publication") is False):
     verdict="REUSE_FORMAL_G2_EVIDENCE"
     note="SEE_PRIOR_IMMUTABLE_NDC_320_CERT_SHARD_44260700121"
     sourcecount["PREVIOUS_CERTIFIED_BINDINGS"]+=1
    else:
     verdict="HOLD"
     note="NDC_FORMAL_TEMPLATE_OR_BINDING_CHANGED"
     sourcecount["NDC_FORMAL_CONFLICT"]+=1
   elif sid in native_samples and native_samples[sid].get("bronze_sha_match") is True:
    verdict="HOLD"
    note="REAL_NATIVE_PROFILED_OFFICIAL_DATASET_EDITION_PROOF_MISSING"
    sourcecount["PRIOR_REAL_NATIVE_SAMPLE_SHA_MATCH"]+=1
   else:
    verdict="HOLD"
    note="SOURCE_PATH_ERA_LOOKUP_ONLY_DATASET_DATE_NATIVE_PROOF_MISSING" if era else "NO_VERIFIED_DATASET_DATE_OR_FORMAT"
   sourcecount[verdict]+=1
   if era:sourcecount["SOURCE_ERA_CANDIDATE"]+=1
   if hint:sourcecount["PATH_MONTH_HINT"]+=1
   rowsout.append({"source_id":sid,"source_sha256":row["source_sha256"],
     "dataset":binding.get("dataset") if isinstance(binding,dict) else None,
     "path_month_hint_not_verified":hint,"source_era_candidate_not_attested":era,
     "verified_source_data_date":binding.get("source_data_date") if isinstance(binding,dict) else None,
     "matched_template":candidate.get("certificate",{}).get("template_id") if verdict=="REUSE_FORMAL_G2_EVIDENCE" else None,
     "status":verdict,"reason":note})
   fullrows+=1
  if fullrows!=len(rows):raise RuntimeError("PER_SOURCE_ROW_COUNT_DRIFT")
  report={"schema":"R3_G2_SOURCE_LIBRARY_DATABASE_COMPARE_V1",
   "source":src,"run":RUN,"source_cohort":len(rows),
   "source_template_id":tid,"source_template_name":template_name,
   "dataset_count":len(tpl["datasets"]),
   "historical_period_count":tpl["candidate_periods"],
   "candidate_dataset_era_combinations":tpl["candidate_matrix_count"],
   "official_approved_editions":sum(len(a) for k,a in official_checks.items() if k[0]==src),
   "reconciliation_counts":dict(sourcecount),
   "prior_native_samples_used":len(native_samples),
   "per_frozen_file_comparison":rowsout,
   "path_derived_eras_are_NOT_official_format_proofs":True,
   "all_bronze_read_only":True,"silver_gold_materialized":False}
  name=f"r3_g2_template_compare_{src}_{len(rows)}_run_{RUN}.json"
  rid=put_once(api,target["id"],name,report)
  if load(api,rid)!=report:raise RuntimeError("SOURCE_COMPARE_READBACK_"+src)
  previous=sourcecount["REUSE_FORMAL_G2_EVIDENCE"]
  formal_total+=previous
  summary={"source":src,"cohort":len(rows),
    "datasets":len(tpl["datasets"]),"era_periods":tpl["candidate_periods"],
    "candidate_combinations":tpl["candidate_matrix_count"],
    "verified_formal_g2_prior":previous,"hold":sourcecount["HOLD"],
    "path_date_hints":sourcecount["PATH_MONTH_HINT"],
    "native_real_10_samples_reused":len(native_samples),
    "source_template_id":tid,"compare_receipt_id":rid,
    "source_template_readback":True,"compare_readback":True}
  source_reports.append(summary)
  print("R3_G2_PERIODIC_SOURCE="+json.dumps(summary,ensure_ascii=False,sort_keys=True),flush=True)
 if total!=COHORT or formal_total!=320:
  raise RuntimeError("74750_COHORT_OR_320_APPROVED_NDC_EVIDENCE_DRIFT")
 if sum(x["hold"] for x in source_reports)!=COHORT-formal_total:
  raise RuntimeError("NONPASS_TOTAL_DRIFT")
 master={"schema":"R3_G2_SEVEN_SOURCE_PERIODIC_TEMPLATE_DATABASE_MASTER_V1",
  "run":RUN,"seven_source_libraries":7,
  "candidate_dataset_era_combinations":sum(x["candidate_combinations"] for x in source_reports),
  "seven_source_periodic_templates_created":True,
  "cohort":COHORT,"reused_existing_formal_g2":formal_total,
  "newly_issued_formal_g2":0,"g2_hold":COHORT-formal_total,
  "source_reports":source_reports,
  "path_based_month_never_formal_verified_date":True,
  "prior_ndc_320_cert_master_run":"44260700121",
  "approval_registry_id":registry_file["id"] if registry_file else None,
  "bronze_modified":False,"silver_gold_materialized":False,
  "not_production_g5_master":True}
 name=f"r3_g2_seven_source_periodic_templates_master_run_{RUN}.json"
 mid=put_once(api,target["id"],name,master)
 if load(api,mid)!=master:raise RuntimeError("SEVEN_SOURCE_MASTER_READBACK_FAILED")
 print("R3_G2_PERIODIC_SEVEN_MASTER="+json.dumps({
  "run":RUN,"cohort":COHORT,"seven_source_libraries":7,
  "candidate_matrix":master["candidate_dataset_era_combinations"],
  "formal_reused":formal_total,"new_g2":0,"hold":COHORT-formal_total,
  "master_id":mid,"master_name":name,"readback":True,
  "sources":source_reports},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
