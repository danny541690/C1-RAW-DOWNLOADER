"""R3 six source OFFICIAL documentation vs 60 real native source format gate.

Official hosts must be verified by real HTTPS GET, byte SHA, correct domain.
A live landing page is NEVER an official historical native edition contract.
Reuses 60 immutable native evidence samples; emits a dataset/edition-level
review queue for each source and comprehensive HOLD explanation.
No false approvals or G2 per-file certificates without attested original API
response bytes, edition effective day, source-date and independent reviewer.
"""
from __future__ import annotations
from collections import Counter,defaultdict
from datetime import datetime,timezone
from urllib.parse import urlparse
import hashlib,json,os,re,requests
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_g2_shared_contract_engine import group_candidates
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS

RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","FinMind")
INPUT_FOLDER="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
OUTPUT_FOLDER="R3_G2_SIX_SOURCE_OFFICIAL_DATASET_APPROVAL_ISOLATED"
PILOT_RUN="44261840978"
REFERENCES={
 "TWSE":[("MI_INDEX_PUBLIC_DAILY","https://www.twse.com.tw/zh/trading/historical/mi-index.html"),
         ("MI_INDEX_PUBLIC_REPORT","https://www.twse.com.tw/zh/exchangeReport/MI_INDEX?response=html&type=5&subType=20"),
         ("A05_COMMERCIAL_DIFFERENT_DATASET","https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8")],
 "TPEx":[("DAILY_QUOTES","https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html"),
         ("OPENAPI_SWAGGER","https://www.tpex.org.tw/openapi/")],
 "MOPS":[("MOPS_HOME","https://mops.twse.com.tw/"),
         ("TWSE_IFRS_INFO","https://www.twse.com.tw/rwd/IFRS/aboutIFRS")],
 "TDCC":[("SHARE_DISTRIBUTION","https://s.tdcc.com.tw/portal/zh/smWeb/qryStock"),
         ("TDCC_MAIN","https://www.tdcc.com.tw/portal/zh/smWeb/qryStock")],
 "TAIFEX":[("FUTURES_DAILY","https://www.taifex.com.tw/cht/3/futDailyMarketView"),
           ("OPTIONS_DAILY","https://www.taifex.com.tw/cht/3/optDailyMarketView"),
           ("TAIFEX_OPENAPI","https://openapi.taifex.com.tw/")],
 "FinMind":[("DATASETS_DOCUMENTATION","https://finmind.github.io/"),
            ("STOCK_PRICE_DATASET","https://finmind.github.io/tutor/TaiwanMarket/Technical/")],
}
DOMAINS={"TWSE":("twse.com.tw",),"TPEx":("tpex.org.tw",),
         "MOPS":("twse.com.tw",),"TDCC":("tdcc.com.tw",),
         "TAIFEX":("taifex.com.tw",),"FinMind":("finmind.github.io",)}
def source_url_valid(src,url):
 u=urlparse(url)
 host=(u.hostname or "").lower()
 return u.scheme=="https" and any(host==x or host.endswith("."+x) for x in DOMAINS[src])

def fetch_landing(src,label,url):
 if not source_url_valid(src,url):return {"label":label,"url":url,"status":"REJECT_UNTRUSTED_DOMAIN"}
 item={"label":label,"url":url,"status":"HOLD_NOT_FETCHED","is_historical_dataset_native_spec":False}
 try:
  r=requests.get(url,timeout=16,headers={"User-Agent":"Mozilla/5.0 (compatible; JARVIS-R3-QualityAudit/1.0)"},allow_redirects=True,stream=True)
  item["http_status"]=r.status_code
  item["final_host"]=urlparse(r.url).hostname
  if not source_url_valid(src,r.url):
   item["status"]="HOLD_UNTRUSTED_REDIRECT";return item
  if r.status_code!=200:
   item["status"]="HOLD_HTTP_"+str(r.status_code);return item
  h=hashlib.sha256();total=0
  for chunk in r.iter_content(chunk_size=65536):
   total+=len(chunk)
   if total>2_500_000:
    item["status"]="HOLD_DOCUMENT_OVERSIZE";return item
   h.update(chunk)
  if total<60:
   item["status"]="HOLD_EMPTY_DOCUMENT";return item
  item.update({"status":"OFFICIAL_PAGE_BYTES_SHA_VERIFIED_ONLY",
      "snapshot_sha256":h.hexdigest(),"snapshot_size":total,
      "retrieved_at":datetime.now(timezone.utc).isoformat(),
      "not_certified_for_historical_era":True})
 except requests.RequestException as e:
  item["status"]="HOLD_OFFICIAL_HTTP_"+type(e).__name__
 return item

def native_identity(src,profile):
 members=profile.get("selected_archive_member_evidence") or []
 identities=[]
 for m in members:
  fields=[str(x).strip() for x in (m.get("native_fields_candidate") or [])]
  row={"member_sha256":m.get("member_sha256"),"format":m.get("format"),
       "observed_fields":fields[:35],"member_path":m.get("member_path"),
       "date_fields":m.get("date_fields_candidate") or [],
       "dataset_guess":None,"dataset_verified":False,"official_era_verified":False}
  f=set(fields);path=str(row["member_path"] or "")
  if src=="TWSE":
   if "foreign_holdings_" in path:row["dataset_guess"]="FOREIGN_HOLDING"
   elif "tables" in f and "date" in f:row["dataset_guess"]="MIXED_MARKET_REPORT_CONTAINS_SEVERAL_DATASETS"
  elif src=="TPEx":
   if "valuation_" in path:row["dataset_guess"]="VALUATION"
   elif "tables" in f:row["dataset_guess"]="MIXED_REPORT_UNCLASSIFIED"
  elif src=="MOPS":
   row["dataset_guess"]="MOPS_FILING_TYPE_UNVERIFIED"
  elif src=="TDCC":
   row["dataset_guess"]="SHAREHOLDING_DISTRIBUTION_CANDIDATE"
  elif src=="TAIFEX":
   t=" ".join(fields)
   if "期貨價差委託成交概況表" in t:row["dataset_guess"]="FUTURES_SPREAD_ORDER_TRADING"
   elif {"履約價格","買/賣權"}.issubset(f):row["dataset_guess"]="OPTIONS_DAILY"
   elif "前五大交易人買方" in t:row["dataset_guess"]="LARGE_TRADER"
   elif "交易日期" in f:row["dataset_guess"]="OTHER_TAIFEX_DAILY"
  elif src=="FinMind":
   if {"date","stock_id","Trading_Volume","close"}.issubset(f):
    row["dataset_guess"]="TaiwanStockPrice"
   elif {"date","stock_id","type","value","origin_name"}.issubset(f):
    row["dataset_guess"]="INSTITUTIONAL_OR_OTHER_PROVIDER_SERIES"
  identities.append(row)
 return identities

def main():
 api,control,quality,match,load,_,_,call=source_api()
 old=match(api,quality,INPUT_FOLDER)
 if not old:raise RuntimeError("REAL_60_SOURCE_CENSUS_MISSING")
 folder=match(api,quality,OUTPUT_FOLDER)
 if not folder:
  folder=call(lambda:api.files().create(body={"name":OUTPUT_FOLDER,"parents":[quality],
           "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if folder.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("INVALID_DESTINATION")
 summary=[];tot=0;status=Counter()
 candidates=group_candidates()
 for src in SOURCES:
  prior=match(api,old["id"],f"r3_g2_pilot_{src}_10_run_{PILOT_RUN}.json")
  if not prior:raise RuntimeError("SOURCE_PROVENANCE_60_MISSING_"+src)
  proof=load(api,prior["id"])
  samples=proof["samples"]
  if len(samples)!=10 or any(x.get("bronze_sha_match") is not True for x in samples):
   raise RuntimeError("SOURCE_SAMPLE_OR_SHA_NOT_VERIFIED_"+src)
  docs=[fetch_landing(src,k,u) for k,u in REFERENCES[src]]
  templ=[x for k,x in candidates.items() if k[0]==src]
  byds=defaultdict(list);rows=[];notes=Counter()
  for sample in samples:
   identities=native_identity(src,sample.get("native_profile") or {})
   sample_ds=sorted({x["dataset_guess"] for x in identities if x["dataset_guess"]})
   reason="G2_OFFICIAL_DATASET_ERA_PROOF_UNBOUND_TO_FROZEN_SHA"
   if len(sample_ds)>1:
    reason="G2_ARCHIVE_CONTAINS_MULTIPLE_DATASETS_NEEDS_MEMBER_CONTRACTS"
   if src=="TAIFEX" and any(x.get("dataset_guess")=="FUTURES_SPREAD_ORDER_TRADING" for x in identities):
    reason="G2_SPREAD_ORDER_NOT_OHLCV_DATASET"
   if src=="MOPS":
    reason="G2_FILING_NATIVE_REPORT_TYPE_TAXONOMY_AND_PIT_UNVERIFIED"
   if src=="TDCC":
    reason="G2_WEEKLY_ISSUER_SECURITY_ID_AND_HISTORIC_TIER_UNVERIFIED"
   if src=="FinMind":
    reason="G2_PROVIDER_API_DATASET_VERSION_AND_ORIGIN_UNVERIFIED"
   notes[reason]+=1
   for ds in sample_ds:byds[ds].append(sample["source_id"])
   rows.append({"source_id":sample["source_id"],
       "bronze_sha256":sample["source_sha256"],
       "native_member_dataset_candidates":identities,
       "candidate_datasets":sample_ds,"official_reference_sources":len(docs),
       "formal_g2_status":"HOLD","hold_reason":reason,
       "official_template_autoapproved":False})
  report={"schema":"R3_G2_SIX_SOURCE_OFFICIAL_PROOF_ATTEMPT_V1","run":RUN,
      "source":src,"historical_dataset_era_candidates":len(templ),
      "data_date_and_origins_not_backfilled_from_filename":True,
      "real_native_files_checked":10,"real_bronze_sha_match":10,
      "official_document_fetch_evidence":docs,
      "dataset_group_candidates":{k:{"sample_count":len(v)} for k,v in byds.items()},
      "sample_records":rows,"hold_reasons":dict(notes),"formal_approved_templates":0,
      "formal_g2_pass":0,"formal_g2_hold":10,
      "why_official_page_does_not_certify_native_edition":"Official web landing pages do not individually identify these frozen files, their actual dataset and historical effective layout.",
      "bronze_modified":False,"silver_gold_materialized":False}
  name=f"r3_g2_official_attempt_{src}_10_run_{RUN}.json"
  rid=put_once(api,folder["id"],name,report)
  if load(api,rid)!=report:raise RuntimeError("OFFICIAL_DATASET_GATE_DRIVE_READBACK_"+src)
  status.update(x["status"] for x in docs);tot+=10
  row={"source":src,"samples":10,"g2_pass":0,"g2_hold":10,
       "historical_candidate_count":len(templ),
       "official_pages_sha_verified":sum(x["status"]=="OFFICIAL_PAGE_BYTES_SHA_VERIFIED_ONLY" for x in docs),
       "datasets_observed":sorted(byds),"hold_reasons":dict(notes),
       "report_file_id":rid,"remote_readback":True}
  summary.append(row)
  print("R3_G2_SIX_OFFICIAL_SOURCE="+json.dumps(row,ensure_ascii=False,sort_keys=True),flush=True)
 if tot!=60:raise RuntimeError("SIX_SOURCE_FROZEN_60_COUNT_DRIFT")
 master={"schema":"R3_G2_SIX_SOURCE_OFFICIAL_PROOF_ATTEMPT_MASTER_V1",
   "run":RUN,"six_sources":len(SOURCES),"real_pilot_files":60,
   "six_source_formal_g2_pass":0,"six_source_g2_hold":60,
   "NDC_existing_source_vintage_320_unchanged":True,
   "six_official_document_fetch_status":dict(status),
   "sources":summary,"no_bronze_changes":True,
   "no_silver_gold":True,"no_production_g5_writer":True}
 mname=f"r3_g2_six_source_official_master_run_{RUN}.json"
 mid=put_once(api,folder["id"],mname,master)
 if load(api,mid)!=master:raise RuntimeError("SIX_OFFICIAL_MASTER_READBACK_FAILED")
 print("R3_G2_SIX_OFFICIAL_MASTER="+json.dumps({
   "run":RUN,"six_sources":6,"samples":60,"pass":0,"hold":60,
   "official_document_fetch_status":dict(status),
   "master_id":mid,"master_name":mname,
   "remote_readback":True,"sources":summary},ensure_ascii=False,sort_keys=True),flush=True)

if __name__=="__main__":main()
