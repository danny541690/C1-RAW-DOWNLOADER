"""R3 immutable seven source 325 G2 QA overlay after real approved MOPS.

Prior 324 unaffected. Verify MOPS 2025-02 period-company-universe/
2026 late IPO exclusions, 2 source renames, 857 numeric same, old source SHA,
new per-file cert SHA and independent official evidence.
"""
import json,os,hashlib
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import COHORT,SOURCES,digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
PRIOR="1l6OD1y79u6nNCKK9bPHIfJCopZxeltf6"
MOPS_APPROVAL="1z4HDCfB4ZREqnsNGlfn3bJKSaPdkiYJc"
MOPS_CERT="11EGW0t8QhnJex8YJa3yudP4Zshx394Cn"
MOPS_REVIEW="1oBzDccIZ9QozW_mq0gfljpTwrKnPZHZF"
OUT="R3_G2_SEVEN_SOURCE_QA_325_OFFICIAL_IMMUTABLE_ISOLATED"
def main():
 api,control,quality,match,load,_,_,call=source_api()
 prior=load(api,PRIOR)
 if prior.get("cohort")!=COHORT or prior.get("verified_g2_source_vintage_pass")!=324:
  raise RuntimeError("PRIOR_324_QA_DRIFT")
 reg=load(api,MOPS_APPROVAL);cert=load(api,MOPS_CERT);review=load(api,MOPS_REVIEW)
 template=reg.get("template");binding=reg.get("binding")
 if not isinstance(template,dict) or not isinstance(binding,dict):
  raise RuntimeError("MOPS_APPROVAL_NOT_DURABLE")
 sid=binding.get("source_id")
 if (sid!="1RYs3r-GNWnUMcg8jbAyj5UkzioqWPV5G" or
    template.get("template_id")!="MOPS_OTC_REVENUE_2025_02_HISTORIC_IDENTITY_2026_RECHECKED_V2" or
    cert.get("source_publication_asof")!="2026-11-18" or
    cert.get("historical_backtest_eligible_before_source_publication") is not False or
    cert.get("source")!="MOPS" or cert.get("source_id")!=sid or
    cert.get("content_sha256")!=binding.get("source_sha256") or
    review.get("all_historic_market_members_857_numeric_fields_equal") is not True):
  raise RuntimeError("MOPS_HISTORICAL_MEMBER_SOURCE_PROOF_CONFLICT")
 frozen=0;cohorts={}
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src)
  frozen+=len(rows);cohorts[src]={x["source_id"]:x for x in rows} if src=="MOPS" else None
 if frozen!=COHORT or sid not in cohorts["MOPS"] or cohorts["MOPS"][sid]["source_sha256"]!=cert["content_sha256"]:
  raise RuntimeError("MOPS_G2_CERT_NOT_IN_FROZEN_74750")
 source_counts={x["source"]:x["g2_verified_source_vintage"] for x in prior["source_summary"]}
 expected={"NDC":320,"TWSE":1,"TPEx":1,"FinMind":2,"MOPS":0,"TDCC":0,"TAIFEX":0}
 if source_counts!=expected:raise RuntimeError("PREVIOUS_SEVEN_SOURCE_BREAKDOWN_CHANGED")
 source_counts["MOPS"]+=1
 overall=[{"source":x["source"],"frozen_cohort":x["frozen_cohort"],
   "g2_verified_source_vintage":source_counts[x["source"]],
   "not_yet_verified":x["frozen_cohort"]-source_counts[x["source"]]} for x in prior["source_summary"]]
 if sum(x["g2_verified_source_vintage"] for x in overall)!=325:raise RuntimeError("EXPECTED_ONE_NEW_G2_ONLY")
 payload={"schema":"R3_G2_SEVEN_SOURCE_OFFICIAL_325_IMMUTABLE_QA_V1",
  "run":RUN,"cohort":COHORT,"formal_source_vintage_g2_pass":325,
  "g2_hold":COHORT-325,"previous_324_master_id":PRIOR,
  "new_mops_source_id":sid,"new_mops_per_file_certificate_id":MOPS_CERT,
  "new_mops_per_file_certificate_sha256":digest(cert),
  "new_mops_approved_template_binding_id":MOPS_APPROVAL,
  "new_mops_independent_official_review_id":MOPS_REVIEW,
  "mops_2025_02_857_company_numeric_rows_verified":True,
  "mops_2026_late_official_ipo_codes_excluded":["2249","6825","6898","6938"],
  "mops_2026_renamed_company_names_not_backfilled_into_2025":["3489","6474"],
  "source_summary":overall,
  "historical_PIT_before_2026_not_certified":True,
  "not_production_G5_master":True,
  "bronze_modified":False,"silver_gold_materialized":False}
 folder=match(api,quality,OUT)
 if not folder:folder=call(lambda:api.files().create(body={
  "name":OUT,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name="r3_g2_seven_source_325_official_qa_master_run_"+RUN+".json"
 id=put_once(api,folder["id"],name,payload)
 if load(api,id)!=payload:raise RuntimeError("G2_325_REMOTE_MASTER_READBACK_FAILED")
 print("R3_G2_SEVEN_SOURCE_325="+json.dumps({
   "run":RUN,"cohort":COHORT,"pass":325,"hold":COHORT-325,
   "source_breakdown":source_counts,"master_file_id":id,
   "new_mops_g2_certificate_id":MOPS_CERT,
   "official_source_vintage_only":True,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
