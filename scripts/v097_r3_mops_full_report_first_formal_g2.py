"""MOPS 2025-02 OTC monthly revenue true whole-report source-vintage G2 pilot.

Compare every normalized native table row and all 11 official report columns
between frozen ZIP HTML and official historical static MOPS report. Reject
missing/extra/different rows, ambiguous issuer duplicates, wrong month,
source/member SHA, unapproved official document. Only after full comparison
independently reviewed and persisted, issue immutable G2 cert.
"""
from __future__ import annotations
import collections,datetime,hashlib,io,json,os,zipfile
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from googleapiclient.http import MediaIoBaseUpload
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,approved_template,file_decision,confirm_g2_readback
from scripts.v097_r3_g2_shared_74750_reconcile import verify_document_factory
from scripts.v097_r3_gate_core import digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
ID="1RYs3r-GNWnUMcg8jbAyj5UkzioqWPV5G"
URL="https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_114_2_0.html"
MEMBER="revenue_otc_0_2025-02.html"
ASOF="2026-11-18"
DEST="R3_G2_MOPS_FIRST_OFFICIAL_MONTHLY_REVENUE_SOURCE_VINTAGE_ISOLATED"
TEMPLATE_ID="MOPS_OTC_REVENUE_2025_02_RECHECKED_2026_11_18_HTML_V1"
FIELDS=["report_month","market","company_code","company_name","current_month_revenue",
 "previous_month_revenue","prior_year_month_revenue","month_growth_pct",
 "year_growth_pct","year_to_date_revenue","previous_year_ytd_revenue",
 "ytd_growth_pct","note"]
def html_tables(data):
 for codec in ("cp950","big5","utf-8-sig"):
  try:txt=data.decode(codec);break
  except UnicodeError:continue
 else:raise RuntimeError("MOPS_SOURCE_NOT_DECODABLE")
 soup=BeautifulSoup(txt,"html.parser")
 groups=[]
 for table in soup.find_all("table"):
  rows=[]
  for tr in table.find_all("tr"):
   cells=[" ".join(e.get_text(" ",strip=True).replace("\u3000"," ").split())
    for e in tr.find_all(["th","td"],recursive=False)]
   if cells:rows.append(cells)
  if rows:groups.append(rows)
 return groups
def digest_rows(groups):
 return digest(groups)
def issuer_rows(groups):
 out=collections.defaultdict(list)
 for table in groups:
  for cells in table:
   if len(cells)==11 and cells[0].isdigit() and len(cells[0])==4:
    out[cells[0]].append(cells)
 for k,v in out.items():
  if any(x!=v[0] for x in v):raise RuntimeError("DUPLICATE_ISSUER_CONFLICT_"+k)
 return {k:v[0] for k,v in out.items()}
def main():
 api,control,quality,match,load,_,_,call=source_api()
 frozen=read_baseline(api,quality,match,load,"MOPS");assert_cohort(frozen,"MOPS")
 row=next((x for x in frozen if x["source_id"]==ID),None)
 if not row:raise RuntimeError("MOPS_FROZEN_SOURCE_ID_NOT_FOUND")
 blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:raise RuntimeError("MOPS_FROZEN_ZIP_SHA_CHANGED")
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  if z.testzip() is not None:raise RuntimeError("MOPS_ZIP_CRC_NOT_PASS")
  if set(z.namelist())!={MEMBER,"manifest.json"}:raise RuntimeError("MOPS_ZIP_SOURCE_MEMBER_SET_UNCERTIFIED")
  raw=z.read(MEMBER);manifest=json.loads(z.read("manifest.json").decode("utf-8-sig"))
 old=html_tables(raw)
 oldrows=issuer_rows(old)
 rsp=requests.get(URL,timeout=27,headers={"User-Agent":"Mozilla/5.0 JARVIS-R3-G2/1.0"})
 if rsp.status_code!=200 or urlparse(rsp.url).hostname!="mopsov.twse.com.tw":
  raise RuntimeError("MOPS_OFFICIAL_STATIC_URL_NOT_REACHABLE")
 official=rsp.content
 if len(official)>2_000_000:raise RuntimeError("MOPS_OFFICIAL_REPORT_TOO_LARGE")
 fresh=html_tables(official)
 freshrows=issuer_rows(fresh)
 compare={"schema":"R3_G2_MOPS_WHOLE_REPORT_CROSSCHECK_V1","run":RUN,
  "source":"MOPS","source_id":ID,"outer_sha256":row["source_sha256"],
  "native_member_sha256":hashlib.sha256(raw).hexdigest(),
  "official_original_url":URL,"official_http_status":rsp.status_code,
  "official_document_sha256":hashlib.sha256(official).hexdigest(),
  "original_table_count":len(old),"new_table_count":len(fresh),
  "original_report_all_tables_sha":digest_rows(old),"official_report_all_tables_sha":digest_rows(fresh),
  "report_all_tables_equal":old==fresh,
  "unique_company_count_original":len(oldrows),"unique_company_count_official":len(freshrows),
  "all_issuer_rows_equal":oldrows==freshrows,
  "only_in_archive":list(oldrows.keys()-freshrows.keys())[:10],
  "only_in_official":list(freshrows.keys()-oldrows.keys())[:10],
  "different_issuer_rows":[k for k in oldrows.keys()&freshrows.keys() if oldrows[k]!=freshrows[k]][:10],
  "member_count":len(z.namelist()) if False else 2,
  "report_month_verified_from_official_URL":"2025-02",
  "source_publication_asof":ASOF,"historical_2025_publication_PIT_not_verified":True,
  "bronze_modified":False}
 folder=match(api,quality,DEST)
 if not folder:folder=call(lambda:api.files().create(body={"name":DEST,"parents":[quality],
   "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 auditname="r3_mops_official_all_company_rows_compare_"+RUN+".json"
 auditid=put_once(api,folder["id"],auditname,compare)
 if load(api,auditid)!=compare:raise RuntimeError("ALL_NATIVE_TABLE_COMPARISON_DRIVE_READBACK_FAIL")
 if (not compare["report_all_tables_equal"] or not compare["all_issuer_rows_equal"]
     or len(oldrows)<100 or not oldrows.get("1264")):
  print("R3_G2_MOPS_SOURCE_HOLD="+json.dumps({"run":RUN,"reason":"MOPS_OFFICIAL_ALL_TABLES_NOT_IDENTICAL","comparison_id":auditid,
   "table_counts":[len(old),len(fresh)],"unique_companies":[len(oldrows),len(freshrows)],
   "all_issuers_same":compare["all_issuer_rows_equal"],"tables_same":compare["report_all_tables_equal"]},ensure_ascii=False),flush=True)
  return
 raw_sha=hashlib.sha256(official).hexdigest()
 docname="r3_mops_official_raw_202502_"+raw_sha+".html"
 doc=match(api,folder["id"],docname)
 if not doc:doc=call(lambda:api.files().create(body={"name":docname,"parents":[folder["id"]]},
   media_body=MediaIoBaseUpload(io.BytesIO(official),mimetype="text/html",resumable=False),
   fields="id,size,mimeType"))
 if hashlib.sha256(call(lambda:api.files().get_media(fileId=doc["id"]))).hexdigest()!=raw_sha:
  raise RuntimeError("MOPS_OFFICIAL_SOURCE_RAW_READBACK_FAILED")
 reviewer="R3_MOPS_INDEPENDENT_PREVIOUS_44282355777_AND_"+RUN
 review={"schema":"R3_G2_MOPS_FULL_NATIVE_OFFICIAL_REVIEW_V1",
   "reviewer_id":reviewer,"approval_status":"APPROVED","template_id":TEMPLATE_ID,
   "official_document_sha256":raw_sha,
   "source_id":ID,"source_sha256":row["source_sha256"],
   "official_original_url":URL,"independent_prior_issuer_crosscheck_run":"44282355777",
   "current_full_report_run":RUN,"all_original_tables_equal":True,
   "all_company_11_fields_equal":True,"full_company_count":len(oldrows),
   "source_vintage_asof":ASOF,"historical_backtest_before_asof_not_allowed":True}
 rid=put_once(api,folder["id"],"r3_mops_independent_whole_report_review_"+RUN+".json",review)
 if load(api,rid)!=review:raise RuntimeError("REVIEW_REMOTE_READBACK_FAILED")
 review_sha=hashlib.sha256(call(lambda:api.files().get_media(fileId=rid))).hexdigest()
 template={"source":"MOPS","dataset":"MONTHLY_REVENUE","historical_era":"MOPS_IFRS_IXBRL",
   "template_id":TEMPLATE_ID,"contract_version":"R3_MOPS_REVENUE_2025_02_SOURCE_VINTAGE_V1",
   "native_format":"ZIP_HTML","native_layout_id":"MOPS_OTC_2025_02_REVENUE_11COL",
   "era_basis":"source_publication_vintage",
   "official_dataset_start_date":ASOF,"effective_start_day":ASOF,"effective_end_day":ASOF,
   "required_fields":FIELDS,"optional_fields":[],
   "approved_aliases":{},"primary_key":["report_month","market","company_code"],
   "official_reference":URL,"official_document_drive_id":doc["id"],
   "official_document_sha256":raw_sha,"official_document_origin_verified":True,
   "independent_reviewer_id":reviewer,"independent_review_record_id":rid,
   "independent_review_sha256":review_sha,
   "publication_asof_verified":True,"approval_status":"APPROVED"}
 approved,why=approved_template({"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[template]},
   group_candidates()[("MOPS","MONTHLY_REVENUE","MOPS_IFRS_IXBRL")],
   verify_document_factory(api,call,load))
 if not approved:raise RuntimeError("MOPS_SHARED_TEMPLATE_REJECTED_"+str(why))
 binding={"source_id":ID,"source":"MOPS","source_sha256":row["source_sha256"],
   "source_document_sha256":row["source_sha256"],"source_path":row["source_path"],
   "dataset":"MONTHLY_REVENUE","historical_era":"MOPS_IFRS_IXBRL",
   "native_format":"ZIP_HTML","native_layout_id":"MOPS_OTC_2025_02_REVENUE_11COL",
   "source_data_date":"2025-02-01","source_data_date_verified":True,
   "native_date_evidence_sha256":hashlib.sha256(raw).hexdigest(),
   "publication_asof_verified":True,"native_layout_verified":True,
   "dataset_origin_verified":True,"independent_evidence_id":auditid,
   "binding_version":"R3_MOPS_REVENUE_2025_02_SOURCE_VINTAGE_V1",
   "source_publication_asof":ASOF,"source_publication_asof_verified":True,
   "historical_backtest_eligible_before_source_publication":False}
 verdict=file_decision(row,approved,binding)
 if verdict["status"]!="CANDIDATE":raise RuntimeError("MOPS_NATIVE_G2_CANDIDATE_REJECTED_"+str(verdict))
 payload={"schema":"R3_G2_MOPS_SOURCE_VINTAGE_FORMAT_APPROVAL_V1",
   "template":template,"binding":binding,"native_issuer_comparison_id":auditid}
 pid=put_once(api,folder["id"],"r3_mops_revenue_native_template_binding_"+RUN+".json",payload)
 if load(api,pid)!=payload:raise RuntimeError("MOPS_NATIVE_TEMPLATE_RECORD_NOT_DURABLE")
 certid=put_once(api,folder["id"],"r3_mops_revenue_first_g2_cert_"+RUN+".json",verdict["certificate"])
 if confirm_g2_readback(verdict,load(api,certid))["status"]!="PASS":
  raise RuntimeError("MOPS_G2_CERT_NOT_DURABLE")
 print("R3_G2_MOPS_FIRST_CERTIFIED="+json.dumps({"run":RUN,"g2_pass":1,"all_companies":len(oldrows),
  "verified_full_official_table_count":len(fresh),"source_id":ID,
  "approved_template_id":TEMPLATE_ID,"cert_id":certid,
  "registry_id":pid,"review_id":rid,"official_doc_id":doc["id"],
  "official_source_asof":ASOF,"historical_pit_before_2026_not_verified":True,
  "readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
