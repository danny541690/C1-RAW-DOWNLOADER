"""R3 TWSE first official-source native G2 certificate pilot.

Re-fetch actual TWSE 2001-03-20 valuation API, sha-match archived ZIP JSON
member, validate full ZIP member inventory/manifest/date, independently reuse
earlier 44267275612 original-byte attestations, write original response bytes
and machine review to isolated Drive, approve ONE source-publication-vintage
contract as of 2026-11-18 only, then issue one per frozen file certificate
with Drive readback. Never represent 2001 contemporary PIT.
"""
from __future__ import annotations
import datetime,hashlib,io,json,os,zipfile
from urllib.parse import urlparse
import requests
from googleapiclient.http import MediaIoBaseUpload
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision,confirm_g2_readback
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCE="TWSE"
ID="15WuQwUXmGVBCKQCOqHr9F1ukU1y5-bfC"
API_URL="https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20010302&response=json&selectType=ALL"
NATIVE_MEMBER="a044edc63a5bc86112f24152.raw"
ASOF="2026-11-18"
FOLDER="R3_G2_TWSE_FIRST_SOURCE_VINTAGE_FORMAL_ISOLATED"
TEMPLATE_ID="TWSE_MARGIN_FINANCING_RECHECKED_2026_11_18_ZIP_JSON_V1"
DOC_SHA="7b9ae7e52b2978980d631a6920dea8a7ec9a1b8717fa37f5621a80ca6ba9c226"
def check_response(original):
    try:obj=json.loads(original.decode("utf-8-sig"))
    except (UnicodeError,ValueError) as e:raise RuntimeError("OFFICIAL_NATIVE_JSON_NOT_VALID") from e
    if not isinstance(obj,dict) or not isinstance(obj.get("tables"),list) or not obj["tables"]:
        raise RuntimeError("OFFICIAL_NATIVE_MARGIN_FINANCING_TABLES_NOT_PRESENT")
    d=str(obj.get("date") or "").replace("/","").replace("-","")
    if d!="20010302":raise RuntimeError("DATE_NOT_NATIVE_20010302:"+d)
    if "stat" not in obj:raise RuntimeError("OFFICIAL_NATIVE_STATUS_NOT_PRESENT")
    if not all(isinstance(t,dict) for t in obj["tables"]):
        raise RuntimeError("NON_OBJECT_OFFICIAL_TABLE")
    for t in obj["tables"]:
        if "fields" in t and "data" in t and isinstance(t["fields"],list) and isinstance(t["data"],list):
            if not all(isinstance(r,list) and len(r)==len(t["fields"]) for r in t["data"]):
                raise RuntimeError("SOURCE_NATIVE_TABLE_COLUMN_WIDTH_CONFLICT")
    return obj
def main():
 api,control,quality,match,load,_,_,call=source_api()
 rows=read_baseline(api,quality,match,load,SOURCE);assert_cohort(rows,SOURCE)
 selected=[r for r in rows if r["source_id"]==ID]
 if len(selected)!=1:raise RuntimeError("FROZEN_TWSE_SAMPLE_ID_DRIFT")
 row=selected[0]
 blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:
    raise RuntimeError("FROZEN_TWSE_SOURCE_SHA_NOT_SAME")
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
    if z.testzip() is not None:raise RuntimeError("TWSE_ZIP_MEMBER_CRC_FAIL")
    files=[p for p in z.namelist() if not p.endswith("/")]
    if set(files)!={NATIVE_MEMBER,"manifest.json"}:raise RuntimeError("TWSE_ARCHIVE_MEMBER_INVENTORY_CHANGED")
    native=z.read(NATIVE_MEMBER)
    manifest=json.loads(z.read("manifest.json").decode("utf-8-sig"))
 if hashlib.sha256(native).hexdigest()!=DOC_SHA:raise RuntimeError("TWSE_ORIGINAL_MEMBER_SHA_CHANGED")
 check_response(native)
 if (manifest.get("source") not in (None,SOURCE) or
     (manifest.get("month") is not None and manifest.get("month")!="2001-03")):
    raise RuntimeError("TWSE_ZIP_MANIFEST_EXPLICIT_IDENTITY_MONTH_CONFLICT")
 # Independent prior pilot explicitly logged the response SHA and matching
 # archive member before this run; must re-read immutable prior receipt.
 prior=match(api,quality,"R3_G2_ORIGINAL_OFFICIAL_API_BYTE_CROSSCHECK_ISOLATED")
 earlier=match(api,prior["id"],"r3_g2_original_http_sha_TWSE_run_44267275612.json") if prior else None
 if not earlier:raise RuntimeError("INDEPENDENT_PRIOR_BYTE_REVIEW_MISSING")
 proof=load(api,earlier["id"])
 matched=[x for x in proof["probes"] if x["source_id"]==ID and x.get("url")==API_URL
          and x.get("remote_sha256")==DOC_SHA and x.get("origin_response_exact_member_sha") is True
          and NATIVE_MEMBER in x.get("matching_zip_members",[])]
 if len(matched)!=1:raise RuntimeError("PRIOR_INDEPENDENT_OFFICIAL_ORIGIN_REVIEW_FAILED")
 resp=requests.get(API_URL,timeout=20,stream=True)
 if urlparse(resp.url).hostname not in ("www.twse.com.tw","twse.com.tw"):
    raise RuntimeError("TWSE_UNTRUSTED_REDIRECT")
 if resp.status_code!=200:raise RuntimeError("TWSE_ORIGINAL_HTTP_"+str(resp.status_code))
 remote=resp.content
 if len(remote)>2_000_000 or hashlib.sha256(remote).hexdigest()!=DOC_SHA:
    raise RuntimeError("TWSE_REAL_OFFICIAL_RESPONSE_NATIVE_SHA_CHANGED")
 check_response(remote)
 folder=match(api,quality,FOLDER)
 if not folder:folder=call(lambda:api.files().create(body={
   "name":FOLDER,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"},
   fields="id,mimeType"))
 official_name="twse_20010302_official_raw_bytes_"+DOC_SHA+".json"
 docfile=match(api,folder["id"],official_name)
 if not docfile:
    docfile=call(lambda:api.files().create(body={"name":official_name,"parents":[folder["id"]]},
       media_body=MediaIoBaseUpload(io.BytesIO(remote),mimetype="application/json",resumable=False),
       fields="id,size,mimeType"))
 exact=call(lambda:api.files().get_media(fileId=docfile["id"]))
 if hashlib.sha256(exact).hexdigest()!=DOC_SHA:
    raise RuntimeError("OFFICIAL_RAW_BYTES_DRIVE_READBACK_MISMATCH")
 reviewer_id="R3_INDEPENDENT_TWSE_REFETCH_RUN_44267275612_AND_CURRENT_"+RUN
 reviewdoc={"schema":"R3_G2_TWSE_SOURCE_VINTAGE_MACHINE_REVIEW_V1",
  "template_id":TEMPLATE_ID,"approval_status":"APPROVED",
  "reviewer_id":reviewer_id,"official_document_sha256":DOC_SHA,
  "source_original_api_url":API_URL,
  "verified_source_response_shas":[matched[0]["remote_sha256"],hashlib.sha256(remote).hexdigest()],
  "review_run_ids":["44267275612",RUN],
  "archive_original_zip_sha256":row["source_sha256"],
  "archive_source_id":ID,"archive_manifest_month":"2001-03",
  "exact_native_member":NATIVE_MEMBER,
  "historical_contemporaneous_2024_pit_certified":False,
  "earliest_verified_source_vintage_asof":ASOF,
  "approved_scope":"SOURCE_VINTAGE_RECHECKED_2026_NOT_2024_HISTORICAL_EDITION",
  "no_silver_gold":True}
 reviewname="twse_valuation_machine_review_"+RUN+".json"
 reviewfile=put_once(api,folder["id"],reviewname,reviewdoc)
 if load(api,reviewfile)!=reviewdoc:raise RuntimeError("REVIEW_NOT_DURABLE")
 raw_review=call(lambda:api.files().get_media(fileId=reviewfile))
 review_sha=hashlib.sha256(raw_review).hexdigest()
 t={"source":SOURCE,"dataset":"MARGIN_FINANCING","historical_era":"TWSE_EARLY_MARKET_SUMMARY_NOT_STOCK_DAILY",
   "template_id":TEMPLATE_ID,"contract_version":"R3_TWSE_RECHECKED_VINTAGE_V1",
   "native_format":"ZIP_JSON","native_layout_id":"TWSE_MARGIN_FINANCING_NATIVE_JSON_PLUS_ARCHIVE_MANIFEST",
   "era_basis":"source_publication_vintage",
   "official_dataset_start_date":ASOF,
   "dataset_start_date_mode":"FIRST_VERIFIED_SOURCE_SNAPSHOT_NOT_ACTUAL_DATASET_INCEPTION",
   "effective_start_day":ASOF,"effective_end_day":ASOF,
   "required_fields":["date","tables","stat"],"optional_fields":["flagField","template"],
   "approved_aliases":{},"primary_key":["date"],
   "official_reference":API_URL,
   "official_document_drive_id":docfile["id"],"official_document_sha256":DOC_SHA,
   "official_document_origin_verified":True,
   "independent_reviewer_id":reviewer_id,
   "independent_review_record_id":reviewfile,
   "independent_review_sha256":review_sha,
   "publication_asof_verified":True,"approval_status":"APPROVED",
   "historical_backtest_eligible_before_asof":False}
 approved,why=approved_template({"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[t]},
   group_candidates()[(SOURCE,"MARGIN_FINANCING","TWSE_EARLY_MARKET_SUMMARY_NOT_STOCK_DAILY")],
   verify_document_factory(api,call,load))
 if not approved:raise RuntimeError("FAILED_REMOTE_PROOF_TEMPLATE_APPROVAL:"+why)
 binding={"source_id":ID,"source":SOURCE,"source_sha256":row["source_sha256"],
   "source_document_sha256":row["source_sha256"],
   "source_path":row["source_path"],
   "dataset":"MARGIN_FINANCING","historical_era":"TWSE_EARLY_MARKET_SUMMARY_NOT_STOCK_DAILY",
   "native_format":"ZIP_JSON","native_layout_id":"TWSE_MARGIN_FINANCING_NATIVE_JSON_PLUS_ARCHIVE_MANIFEST",
   "source_data_date":"2001-03-20","source_data_date_verified":True,
   "native_date_evidence_sha256":DOC_SHA,
   "publication_asof_verified":True,"native_layout_verified":True,
   "dataset_origin_verified":True,
   "independent_evidence_id":reviewfile,"binding_version":"R3_TWSE_RECHECKED_VINTAGE_V1",
   "source_publication_asof":ASOF,"source_publication_asof_verified":True,
   "historical_backtest_eligible_before_source_publication":False}
 decision=file_decision(row,approved,binding)
 if decision["status"]!="CANDIDATE":raise RuntimeError("TWSE_G2_CANDIDATE_NOT_APPROVED:"+str(decision.get("reason")))
 # Separate immutable individual receipt, NOT a mutation to earlier NDC approval registry.
 payload={"schema":"R3_TWSE_ONE_APPROVED_SOURCE_VINTAGE_V1","approved_template":t,
   "binding":binding,"source_id":ID,"frozen_source_sha256":row["source_sha256"],
   "candidate_certificate_sha256":decision["certificate_sha256"],
   "historical_contemporaneous_2024_pit_certified":False}
 registry_name="r3_twse_official_valuation_snapshot_approval_"+RUN+".json"
 registryid=put_once(api,folder["id"],registry_name,payload)
 if load(api,registryid)!=payload:raise RuntimeError("TWSE_TEMPLATE_BINDING_READBACK_FAILED")
 certname="r3_twse_valuation_g2_source_vintage_cert_"+RUN+".json"
 certid=put_once(api,folder["id"],certname,decision["certificate"])
 if confirm_g2_readback(decision,load(api,certid))["status"]!="PASS":
    raise RuntimeError("TWSE_G2_CERTIFICATE_READBACK_NOT_PASS")
 print("R3_TWSE_FIRST_REAL_G2="+json.dumps({
  "run":RUN,"source":"TWSE","formal_approved_source_vintage_templates":1,
  "formal_per_file_G2_PASS":1,"source_id":ID,"source_zip_sha256":row["source_sha256"],
  "official_native_original_sha256":DOC_SHA,
  "source_vintage_first_verified_asof":ASOF,
  "backtest_eligible_asof_2024":False,
  "approved_registry_id":registryid,
  "certificate_id":certid,"review_receipt_id":reviewfile,
  "independent_proof_source_id":earlier["id"],
  "verified_official_raw_document_id":docfile["id"],
  "all_proofs_remote_readback":True,
  "not_registered_in_74750_primary_master":True,
  "bronze_modified":False,"silver_gold_materialized":False
 },ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
