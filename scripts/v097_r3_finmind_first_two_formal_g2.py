"""Issue two real FinMind G2 source-vintage certificates, only after independent
44277414399 proof and live byte-for-byte replay, frozen Bronze SHA, original
ZIP inventory, native 10 fields and month/date/key checks; Drive readback.
No historical PIT or Silver/Gold, no existing G5/master mutation.
"""
from __future__ import annotations
import datetime,hashlib,io,json,os,zipfile,calendar
from urllib.parse import urlparse
import requests
from googleapiclient.http import MediaIoBaseUpload
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import digest
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision,confirm_g2_readback
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
RUN=os.getenv("GITHUB_RUN_ID","manual")
ASOF="2026-11-18"
ENDPOINT="https://api.finmindtrade.com/api/v4/data"
DEST="R3_G2_FINMIND_FIRST_FORMAL_SOURCE_VINTAGE_ISOLATED"
PREVIOUS_DIR="R3_G2_TAIFEX_FINMIND_DEEP_FORMAT_DIAGNOSTIC_ISOLATED"
PREVIOUS_RUN="44277414399"
IDS=("12Ym12g1tPQgHoN-zBQSKwlX4uJUwQ1Jy","1qPOj2Q9Q-h2lHUC98RviBjy4hoKR0nwE")
FIELDS=["date","stock_id","Trading_Volume","Trading_money","open","max","min","close","spread","Trading_turnover"]
TEMPLATE_ID="FINMIND_TAIWANSTOCKPRICE_RECHECKED_2026_11_18_NATIVE_ZIP_V1"
def rerun(row,api,call,original_doc):
 blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:raise RuntimeError("BRONZE_SHA_CHANGED")
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  if z.testzip() is not None or len(z.namelist())!=2 or "manifest.json" not in z.namelist():
   raise RuntimeError("NATIVE_ZIP_INVENTORY_OR_CRC_FAILED")
  rawname=next(p for p in z.namelist() if p!="manifest.json")
  raw=z.read(rawname)
  mf=json.loads(z.read("manifest.json").decode("utf-8-sig"))
 obj=json.loads(raw.decode("utf-8-sig"))
 if len(mf.get("units",[]))!=1:raise RuntimeError("NOT_SINGLE_DATASET_UNIT")
 unit=mf["units"][0]
 ds=unit.get("dataset");stock=unit.get("stock_id");month=unit.get("month") or unit.get("period")
 if ds!="TaiwanStockPrice" or not stock or not isinstance(month,str) or len(month)!=7:
  raise RuntimeError("NATIVE_DATASET_STOCK_MONTH_MISMATCH")
 year,mo=map(int,month.split("-"))
 first=f"{year:04d}-{mo:02d}-01";last=f"{year:04d}-{mo:02d}-{calendar.monthrange(year,mo)[1]:02d}"
 rows=obj.get("data")
 if not isinstance(rows,list) or not rows or list(rows[0])!=FIELDS:
  raise RuntimeError("NATIVE_PRICE_10_FIELD_SCHEMA_FAILED")
 if any(list(a)!=FIELDS or a["stock_id"]!=stock or not first<=a["date"]<=last for a in rows):
  raise RuntimeError("NATIVE_ALL_ROWS_ID_DATE_FIELDS_MISMATCH")
 days=[x["date"] for x in rows]
 if len(days)!=len(set(days)):raise RuntimeError("NATIVE_DAILY_PRIMARY_KEY_COLLISION")
 request={"dataset":ds,"data_id":stock,"start_date":first,"end_date":last}
 headers={"User-Agent":"JARVIS-R3-Independent-G2-SourceNativeVerifier/1.0"}
 token=os.getenv("FINMIND_TOKEN","")
 if token:headers["Authorization"]="Bearer "+token
 rsp=requests.get(ENDPOINT,params=request,headers=headers,timeout=25)
 if rsp.status_code!=200 or urlparse(rsp.url).hostname!="api.finmindtrade.com":
  raise RuntimeError("FINMIND_OFFICIAL_PROVIDER_OR_HTTP_FAILED")
 live=rsp.content
 if len(live)>3*1024*1024 or hashlib.sha256(live).hexdigest()!=hashlib.sha256(raw).hexdigest():
  raise RuntimeError("FINMIND_SOURCE_NATIVE_RESPONSE_SHA_CHANGED")
 reloaded=json.loads(live)
 if reloaded.get("data")!=rows or reloaded.get("status")!=200:
  raise RuntimeError("FINMIND_FULL_ORIGINAL_DATA_ROWS_NOT_SAME")
 pre=original_doc
 if (pre.get("source_id")!=row["source_id"] or
     pre.get("frozen_outer_sha256")!=row["source_sha256"] or
     pre.get("frozen_native_sha256")!=hashlib.sha256(raw).hexdigest() or
     pre.get("row_values_equal") is not True or
     pre.get("exact_bytes_equal") is not True or
     pre.get("historical_date_window")!=[first,last] or
     pre.get("stock_id")!=stock or pre.get("dataset")!=ds or
     pre.get("remote_body_sha256")!=hashlib.sha256(raw).hexdigest()):
  raise RuntimeError("INDEPENDENT_2026_NATIVE_ORIGINAL_PROOF_MISMATCH")
 return {"raw":live,"raw_sha":hashlib.sha256(raw).hexdigest(),
         "month":month,"date":first,"stock":stock,"data_rows":len(rows),
         "native_name":rawname,"request":request}
def main():
 api,control,quality,match,load,_,_,call=source_api()
 frozen=read_baseline(api,quality,match,load,"FinMind");assert_cohort(frozen,"FinMind")
 allrows={r["source_id"]:r for r in frozen}
 oldfolder=match(api,quality,PREVIOUS_DIR)
 if not oldfolder:raise RuntimeError("INDEPENDENT_PREVIOUS_DIR_MISSING")
 folder=match(api,quality,DEST)
 if not folder:folder=call(lambda:api.files().create(body={"name":DEST,
   "parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if folder.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("DESTINATION_IS_NOT_FOLDER")
 prepared=[]
 for sid in IDS:
  row=allrows.get(sid)
  if not row:raise RuntimeError("FROZEN_FILE_SOURCE_ID_MISSING")
  prevfile=match(api,oldfolder["id"],f"r3_finmind_reproducible_{sid[:10]}_run_{PREVIOUS_RUN}.json")
  if not prevfile:raise RuntimeError("INDEPENDENT_2026_RECHECK_DOC_NOT_FOUND")
  prev=load(api,prevfile["id"])
  result=rerun(row,api,call,prev)
  prepared.append((row,prevfile,result))
 official_sha=prepared[0][2]["raw_sha"]
 document_name="r3_finmind_stock_price_official_2026_vintage_raw_"+official_sha+".json"
 document=match(api,folder["id"],document_name)
 if not document:
  document=call(lambda:api.files().create(body={"name":document_name,"parents":[folder["id"]]},
     media_body=MediaIoBaseUpload(io.BytesIO(prepared[0][2]["raw"]),
       mimetype="application/json",resumable=False),fields="id,size,mimeType"))
 if hashlib.sha256(call(lambda:api.files().get_media(fileId=document["id"]))).hexdigest()!=official_sha:
  raise RuntimeError("PROVIDER_ORIGINAL_DOCUMENT_READBACK_FAILED")
 reviewer_id="R3_FINMIND_INDEPENDENT_NATIVE_VERIFIED_44277414399_AND_"+RUN
 review={"schema":"R3_G2_FINMIND_ORIGINAL_API_SOURCE_VINTAGE_INDEPENDENT_REVIEW_V1",
   "template_id":TEMPLATE_ID,"approval_status":"APPROVED","reviewer_id":reviewer_id,
   "official_document_sha256":official_sha,
   "provider_api_origin":ENDPOINT,"independent_review_run":PREVIOUS_RUN,
   "second_verification_run":RUN,"native_dataset":"TaiwanStockPrice",
   "required_columns":FIELDS,"fully_verified_native_responses":[
     {"source_id":r["source_id"],"outer_bronze_sha256":r["source_sha256"],
      "remote_native_sha256":p["raw_sha"],"stock_id":p["stock"],"month":p["month"],
      "full_row_count":p["data_rows"]} for r,_,p in prepared],
   "verified_asof":ASOF,"never_before_snapshot_PIT":True,"bronze_immutable":True}
 reviewid=put_once(api,folder["id"],"r3_finmind_independent_approval_review_run_"+RUN+".json",review)
 if load(api,reviewid)!=review:raise RuntimeError("INDEPENDENT_APPROVAL_REVIEW_DRIVE_READBACK_FAILED")
 review_sha=hashlib.sha256(call(lambda:api.files().get_media(fileId=reviewid))).hexdigest()
 template={"source":"FinMind","dataset":"TaiwanStockPrice","historical_era":"FINMIND_DATASET_VERSIONED_API",
  "template_id":TEMPLATE_ID,"contract_version":"R3_FINMIND_2026_RECHECKED_NATIVE_V1",
  "native_format":"ZIP_JSON","native_layout_id":"FINMIND_PRICE_ZIP_MANIFEST_V4_PRICE10",
  "era_basis":"source_publication_vintage",
  "official_dataset_start_date":ASOF,"effective_start_day":ASOF,"effective_end_day":ASOF,
  "required_fields":FIELDS,"optional_fields":[],
  "approved_aliases":{},"primary_key":["date","stock_id"],
  "official_reference":"https://finmind.github.io/tutor/TaiwanMarket/Technical/",
  "official_document_drive_id":document["id"],"official_document_sha256":official_sha,
  "official_document_origin_verified":True,
  "independent_reviewer_id":reviewer_id,
  "independent_review_record_id":reviewid,"independent_review_sha256":review_sha,
  "publication_asof_verified":True,"approval_status":"APPROVED",
  "historical_backtest_eligible_before_asof":False,
  "earliest_verified_source_snapshot_day":ASOF}
 templates,reason=approved_template({"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[template]},
   group_candidates()[("FinMind","TaiwanStockPrice","FINMIND_DATASET_VERSIONED_API")],
   verify_document_factory(api,call,load))
 if not templates:raise RuntimeError("FINMIND_TEMPLATE_APPROVAL_FAILED:"+reason)
 issued=[]
 for row,prevfile,p in prepared:
  b={"source_id":row["source_id"],"source":"FinMind",
    "source_sha256":row["source_sha256"],"source_document_sha256":row["source_sha256"],
    "source_path":row["source_path"],"dataset":"TaiwanStockPrice",
    "historical_era":"FINMIND_DATASET_VERSIONED_API","native_format":"ZIP_JSON",
    "native_layout_id":"FINMIND_PRICE_ZIP_MANIFEST_V4_PRICE10",
    "source_data_date":p["date"],"source_data_date_verified":True,
    "native_date_evidence_sha256":p["raw_sha"],
    "publication_asof_verified":True,"native_layout_verified":True,
    "dataset_origin_verified":True,"independent_evidence_id":prevfile["id"],
    "binding_version":"R3_FINMIND_2026_RECHECKED_NATIVE_V1",
    "source_publication_asof":ASOF,"source_publication_asof_verified":True,
    "historical_backtest_eligible_before_source_publication":False}
  verdict=file_decision(row,templates,b)
  if verdict["status"]!="CANDIDATE":raise RuntimeError("FINMIND_FILE_G2_NOT_CANDIDATE:"+str(verdict))
  record={"template":template,"binding":b,"source_id":row["source_id"],
          "source_sha256":row["source_sha256"],"native_sha256":p["raw_sha"],
          "independent_native_evidence_id":prevfile["id"],
          "certificate_sha256":verdict["certificate_sha256"]}
  regid=put_once(api,folder["id"],f"r3_finmind_price_native_binding_{row['source_id'][:12]}_run_{RUN}.json",record)
  if load(api,regid)!=record:raise RuntimeError("NATIVE_BINDING_DRIVE_READBACK_FAILED")
  certid=put_once(api,folder["id"],f"r3_finmind_price_per_file_g2_cert_{row['source_id'][:12]}_run_{RUN}.json",verdict["certificate"])
  if confirm_g2_readback(verdict,load(api,certid))["status"]!="PASS":
   raise RuntimeError("FINMIND_G2_CERT_REMOTE_READBACK_NOT_PASS")
  issued.append({"source_id":row["source_id"],"source_sha256":row["source_sha256"],
     "stock_id":p["stock"],"month":p["month"],"rows":p["data_rows"],
     "native_sha256":p["raw_sha"],"binding_id":regid,
     "certificate_id":certid,"certificate_sha256":verdict["certificate_sha256"]})
 master={"schema":"R3_G2_FINMIND_FIRST_TWO_REAL_SOURCE_VINTAGE_APPROVAL_V1",
  "run":RUN,"status":"ISOLATED_FORMAL_G2_CERTIFICATES_REMOTE_VERIFIED",
  "formal_shared_template_count":1,"formally_certified_new_files":len(issued),
  "template":template,"approval_review_id":reviewid,"official_raw_document_id":document["id"],
  "source_vintage_only_asof":ASOF,"not_historical_2000_or_2022_pit":True,
  "certificates":issued,"previous_322_qa_unchanged":True,
  "bronze_modified":False,"silver_gold_materialized":False}
 mid=put_once(api,folder["id"],"r3_finmind_first_two_g2_source_vintage_master_run_"+RUN+".json",master)
 if load(api,mid)!=master:raise RuntimeError("FINMIND_FIRST_TWO_MASTER_READBACK_FAILED")
 print("R3_FINMIND_FIRST_TWO_G2_PASS="+json.dumps({"run":RUN,"new_g2_pass":len(issued),
    "approved_templates":1,"certificate_ids":[x["certificate_id"] for x in issued],
    "source_ids":[x["source_id"] for x in issued],
    "master_id":mid,"official_document_id":document["id"],
    "review_id":reviewid,"all_readbacks":True,
    "source_vintage_asof":ASOF,"historical_PIT_attested":False,
    "not_production_master":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
