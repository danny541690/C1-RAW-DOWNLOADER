"""NDC 2026-08 last native G2 gap: official Excel '…' is a documented null.

Never overwrite V1/V2 binding or Bronze. Independently compare all five native
worksheets and eight explicit ellipsis tokens against the source gaps ledger;
issue one durable source-vintage G2 certificate with no historical PIT claim.
"""
import hashlib,json,os
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_ndc_xlsx_native_crosscheck import xml_workbook,check_one
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision,confirm_g2_readback
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
DOC_SHA="c035dc5bbd3fe91ca80a620fd84828a54e8c49885a1b3aa51db5e42857772c83"
def main():
 api,control,quality,match,load,_,_,call=source_api()
 prev=match(api,control,"R3_G2_NATIVE_BINDINGS_NDC_V2.json")
 approvedfile=match(api,control,"R3_G2_APPROVED_SHARED_TEMPLATES_V1.json")
 if not prev or not approvedfile:raise RuntimeError("PRIOR_NDC_APPROVAL_OR_V2_NOT_COMMITTED")
 v2=load(api,prev["id"])
 if len(v2["done"])!=319:raise RuntimeError("EXPECTED_319_NDC_V2_BINDINGS")
 root=load(api,approvedfile["id"])
 selected,reason=approved_template(root,group_candidates()[("NDC","BUSINESS_SIGNAL","NDC_SIGNAL_2024")],verify_document_factory(api,call,load))
 if not selected or len(selected)!=1:raise RuntimeError("OFFICIAL_VINTAGE_APPROVAL_LOST:"+reason)
 t=selected[0]
 data=read_baseline(api,quality,match,load,"NDC");assert_cohort(data,"NDC")
 missing=[x for x in data if x["source_id"] not in v2["done"]]
 if len(missing)!=1:raise RuntimeError("EXPECTED_ONLY_ONE_NATIVE_HOLD")
 row=missing[0]
 native=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(native).hexdigest()!=row["source_sha256"]:raise RuntimeError("SOURCE_SHA_CHANGED")
 doc=json.loads(native.decode("utf-8-sig"))
 ar=doc.get("source_archive") or {}
 if (doc.get("source")!="NDC" or doc.get("month")!="2026-08" or
     ar.get("sha256")!=DOC_SHA or ar.get("file_id")!=t["official_document_drive_id"]):
  raise RuntimeError("SOURCE_PUBLISHED_ORIGINAL_NOT_VERIFIED")
 workbook=call(lambda:api.files().get_media(fileId=ar["file_id"]))
 if hashlib.sha256(workbook).hexdigest()!=DOC_SHA:raise RuntimeError("OFFICIAL_XLSX_SHA_CHANGED")
 detail=check_one(doc,xml_workbook(workbook))
 if (detail["mismatch_count"]!=0 or detail.get("native_source_missing_markers")!=8 or
     len(doc.get("gaps") or [])!=8):
  raise RuntimeError("NATIVE_ELLIPSIS_NOT_PROVEN_OR_OTHER_MISMATCH")
 folder=match(api,quality,"R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED")
 evidence={"schema":"R3_NDC_202608_SOURCE_NATIVE_MISSING_MARKER_REVIEW_V1",
   "run":RUN,"published_archive_sha256":DOC_SHA,"earliest_verified_source_asof":"2026-10-23",
   "records":[{"source_id":row["source_id"],"source_sha256":row["source_sha256"],
     "source_month":"2026-08","archive_sha256":DOC_SHA,"mismatch_count":0,
     "verified_values":detail["verified_cells"],
     "documented_original_marker_count":detail["native_source_missing_markers"]}],
   "original_ellipsis_native_token":"…","missing_is_not_numeric_zero":True,
   "historical_pit_verified":False,"backtest_eligible_before_asof":False}
 reviewname="r3_ndc_202608_literal_missing_marker_review_run_"+RUN+".json"
 evidence_id=put_once(api,folder["id"],reviewname,evidence)
 if load(api,evidence_id)!=evidence:raise RuntimeError("MISSING_MARKER_REVIEW_READBACK_FAILED")
 b={"source_id":row["source_id"],"source":"NDC",
    "source_sha256":row["source_sha256"],"source_document_sha256":row["source_sha256"],
    "source_path":row["source_path"],"dataset":"BUSINESS_SIGNAL",
    "historical_era":"NDC_SIGNAL_2024","native_format":"JSON",
    "native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
    "source_data_date":"2026-08-01","source_data_date_verified":True,
    "native_date_evidence_sha256":DOC_SHA,"publication_asof_verified":True,
    "native_layout_verified":True,"dataset_origin_verified":True,
    "independent_evidence_id":evidence_id,"binding_version":"R3_NDC_VINTAGE_V1",
    "source_publication_asof":"2026-10-23","source_publication_asof_verified":True,
    "historical_backtest_eligible_before_source_publication":False}
 candidate=file_decision(row,selected,b)
 if candidate["status"]!="CANDIDATE":raise RuntimeError("ONE_FILE_G2_CANDIDATE_FAILED:"+str(candidate.get("reason")))
 bind=dict(v2["done"]);bind[row["source_id"]]=b
 if len(bind)!=320:raise RuntimeError("NDC_FROZEN_BINDING_320_COUNT_DRIFT")
 name="R3_G2_NATIVE_BINDINGS_NDC_V3.json"
 registry={"schema":"R3_G2_NATIVE_BINDINGS_V1","registry_version":"R3_NDC_V3_NATIVE_MISSING_MARKER_APPROVED",
           "source":"NDC","previous_v2_file_id":prev["id"],
           "single_native_null_review_id":evidence_id,
           "backtest_eligible_before_source_publication":False,"done":bind}
 rid=put_once(api,control,name,registry)
 if load(api,rid)!=registry:raise RuntimeError("NDC_V3_BINDING_REGISTRY_READBACK_FAILED")
 qa=match(api,quality,"R3_G2_COMMON_TEMPLATE_RECONCILE_ISOLATED")
 certname="g2_cert_"+digest(["NDC",row["source_id"],row["source_sha256"]])+".json"
 cid=put_once(api,qa["id"],certname,candidate["certificate"])
 if confirm_g2_readback(candidate,load(api,cid))["status"]!="PASS":
  raise RuntimeError("G2_LAST_CERT_REMOTE_READBACK_FAILED")
 print("R3_NDC_LAST_G2_MISSING_MARKER="+json.dumps({
  "run":RUN,"NDC_total_bindings":320,"new_certificates":1,
  "source_month":"2026-08",
  "verified_values":detail["verified_cells"],
  "documented_native_missing_ellipsis":detail["native_source_missing_markers"],
  "missing_not_zero":True,"cert_id":cid,"v3_bind_registry_id":rid,
  "review_receipt_id":evidence_id,"readback":True,
  "historical_pit_verified":False},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
