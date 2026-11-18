"""R3 six-source 60 REAL native G2 pilot: archived bytes, ZIP members, field/PIT identity.

This is a genuine source-native gate, not a synthetic test or an automatic
official template approval. Reuses real 70 earlier frozen picks (10/source),
samples source-native archive members and existing V3 schema evidence,
verifies SHA, classifies actual dataset and enumerates missing proofs.
No edits of Bronze, approved NDC registry, production G5 or Silver/Gold.
"""
from __future__ import annotations
import collections,csv,datetime,hashlib,io,json,os,re,sys,zipfile
from scripts.v097_bronze_autopilot import source_api, classify_dataset
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import digest,COHORT
from scripts.v097_g2g3_formal_contracts_v2 import catalog
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","FinMind")
PRIOR="44251892156"
OUT="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
PRIORF="R3_G2_NATIVE_FORMAT_EVIDENCE_CANDIDATES"
MAX_RAW=3*1024*1024
MAX_EXPANDED=16*1024*1024
MAX_MEMBERS=100
MAX_MEMBER=2*1024*1024
DOCS={
 "TWSE":{"url":"https://www.twse.com.tw/zh/trading/historical/mi-index.html","note":"Official public MI_INDEX multi-table is NOT automatically A05 commercial format"},
 "TPEx":{"url":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html","note":"Official daily quotations page is not a ZIP historical dataset-era native spec"},
 "MOPS":{"url":"https://mops.twse.com.tw/","note":"Publication and amendments, accounting regime and filing schema must be individually tied"},
 "TDCC":{"url":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock","note":"Historical 16/17 distribution tiers need source-specific evidence"},
 "TAIFEX":{"url":"https://www.taifex.com.tw/cht/3/futDailyMarketView","note":"Actual spread-order turnover is a different dataset from futures daily OHLCV"},
 "FinMind":{"url":"https://finmind.github.io/","note":"FinMind is a data provider, not a market regulatory agency; provider dataset/version PIT needed"},
}
def decode(b):
 for enc in ("utf-8-sig","cp950","big5"):
  try:return b.decode(enc),enc
  except UnicodeDecodeError:continue
 return None,None
def content_profile(data,source,label):
 info={"format":"UNKNOWN","member_sha256":hashlib.sha256(data).hexdigest(),
       "dataset_name_candidate":None,"native_fields_candidate":[],
       "date_fields_candidate":[],"source_native_provenance":None,
       "header_semantics_verified":False,"source_date_verified":False,
       "official_native_edition_verified":False}
 if not data:return {**info,"format":"EMPTY"}
 txt,encoding=decode(data[:min(len(data),MAX_MEMBER)])
 info["encoding"]=encoding
 if data.lstrip().startswith((b"{",b"[")):
  try:
   obj=json.loads(txt) if txt else None
   info["format"]="JSON"
   if isinstance(obj,dict):
    info["native_fields_candidate"]=list(obj)[:40]
    info["dataset_name_candidate"]=obj.get("dataset")
    info["source_native_provenance"]={x:obj.get(x) for x in ("source","source_archive","source_url","source_date","request_url") if x in obj}
    datafield=obj.get("data")
    if isinstance(datafield,list) and datafield and isinstance(datafield[0],dict):
     info["native_fields_candidate"]=list(datafield[0])[:40]
     info["row_count"]=len(datafield)
     info["date_fields_candidate"]=[x for x in info["native_fields_candidate"] if "date" in x.lower() or "日期" in x or "年月" in x]
   elif isinstance(obj,list) and obj and isinstance(obj[0],dict):
    info["native_fields_candidate"]=list(obj[0])[:40]
    info["row_count"]=len(obj)
  except (ValueError,TypeError):info["format"]="JSON_PARSE_CANDIDATE_ERROR"
 elif data.startswith(b"PK\x03\x04"):
  info["format"]="NESTED_ZIP_NOT_PARSED"
 elif txt is not None:
  l=txt.lstrip()
  if l.startswith("<"):
   info["format"]="HTML_XML"
   # For structural type only. Never assume source security ID/date from HTML markup.
   info["table_count_candidate"]=len(re.findall(r"<table\\b",txt,re.I))
   info["date_fields_candidate"]=list(dict.fromkeys(re.findall(r"(?:民國)?\\d{2,4}[-/]\\d{1,2}[-/]\\d{1,2}",txt)))[:5]
  else:
   info["format"]="CSV_TEXT"
   lines=txt.splitlines()
   try:
    parsed=list(csv.reader(lines[:min(len(lines),8)]))
    info["header_lines_candidates"]=parsed[:3]
    info["native_fields_candidate"]=next((r for r in parsed if len(r)>3),[])[:50]
    info["date_fields_candidate"]=[x for x in info["native_fields_candidate"] if "date" in x.lower() or "日期" in x or "年月" in x]
    info["sample_rows"]=len(lines)
   except csv.Error:info["csv_header_parse_error"]=True
 return info

def inspect_blob(blob,source,path):
 outer={"source_format":"UNKNOWN","outer_sha256":hashlib.sha256(blob).hexdigest(),
        "dataset_from_name_candidate":classify_dataset(source,path),
        "selected_archive_member_evidence":[]}
 if zipfile.is_zipfile(io.BytesIO(blob)):
  outer["source_format"]="ZIP"
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   members=[x for x in z.infolist() if not x.is_dir()]
   expanded=sum(x.file_size for x in members)
   outer["members_count"]=len(members)
   outer["expanded_bytes"]=expanded
   if len(members)>MAX_MEMBERS or expanded>MAX_EXPANDED:
    outer["zip_guard"]="HOLD_ZIP_LIMIT"
    return outer
   outer["zip_guard"]="PASS_ZIP_BOUND"
   bad=z.testzip()
   outer["zip_crc_pass"]=bad is None
   if bad is not None:
    outer["zip_guard"]="HOLD_ZIP_CRC"
    return outer
   for m in members[:min(3,len(members))]:
    if m.file_size>MAX_MEMBER:
     outer["selected_archive_member_evidence"].append({"member_size":m.file_size,"reason":"HOLD_MEMBER_TOO_LARGE"})
     continue
    raw=z.read(m)
    p=content_profile(raw,source,m.filename)
    p["member_path"]=m.filename
    p["member_byte_count"]=len(raw)
    p["member_name_dataset_candidate"]=classify_dataset(source,m.filename)
    outer["selected_archive_member_evidence"].append(p)
   outer["native_member_profiling_complete"]=len(members)<=3 and all(m.file_size<=MAX_MEMBER for m in members)
 else:
  outer["source_format"]="DIRECT_NATIVE"
  outer["selected_archive_member_evidence"]=[content_profile(blob,source,path)]
  outer["native_member_profiling_complete"]=True
 return outer

def main():
 api,control,quality,match,load,_,_,call=source_api()
 sourcefolder=match(api,quality,PRIORF)
 if not sourcefolder:raise RuntimeError("PRIOR_REAL_70_SOURCE_FOLDER_MISSING")
 output=match(api,quality,OUT)
 if not output:
  output=call(lambda:api.files().create(body={"name":OUT,"parents":[quality],
    "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if output.get("mimeType")!="application/vnd.google-apps.folder":raise RuntimeError("OUTPUT_PATH_NOT_FOLDER")
 run=os.getenv("GITHUB_RUN_ID","manual")
 baseline=0;reports=[];allpass=0;allhold=0
 for src in SOURCES:
  rows=read_baseline(api,quality,match,load,src);assert_cohort(rows,src);baseline+=len(rows)
  byid={x["source_id"]:x for x in rows}
  prev=match(api,sourcefolder["id"],f"r3_g2_native_candidates_{src}_run_{PRIOR}.json")
  if not prev:raise RuntimeError("PREVIOUS_SHA_VERIFIED_SAMPLES_MISSING_"+src)
  samples=load(api,prev["id"])["records"]
  if len(samples)!=10:raise RuntimeError("SAMPLE_TEN_DRIFT_"+src)
  seen=set();result=[];counts=collections.Counter()
  for sample in samples:
   sid=sample["source_id"]
   if sid in seen or sid not in byid:raise RuntimeError("SAMPLE_NOT_UNIQUE_OR_FROZEN_ORPHAN")
   seen.add(sid);row=byid[sid]
   item={"source_id":sid,"source_sha256":row["source_sha256"],
      "destination_file_id":row["destination_id"],"official_reference_candidate":DOCS[src]["url"],
      "sample_origin":"REAL_FROZEN_BRONZE_FROM_PREVIOUS_RUN_"+PRIOR,
      "status":"HOLD","g2_formal_certificate_issued":False,"official_shared_template_approved":False}
   try:
    size=int(call(lambda:api.files().get(fileId=row["destination_id"],fields="id,size"))["size"])
    if size<=0 or size>MAX_RAW:
     item["reason"]="HOLD_RAW_BYTE_GUARD";counts[item["reason"]]+=1;result.append(item);continue
    blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
    item["bronze_sha_match"]=hashlib.sha256(blob).hexdigest()==row["source_sha256"]
    if not item["bronze_sha_match"]:
     item["reason"]="HOLD_SHA_MISMATCH";counts[item["reason"]]+=1;result.append(item);continue
    profile=inspect_blob(blob,src,str(row.get("source_path") or ""))
    item["native_profile"]=profile
    # Candidate profiling is not an approved dataset-era binding or official-spec document.
    if profile.get("zip_guard") in ("HOLD_ZIP_LIMIT","HOLD_ZIP_CRC"):
     reason=profile["zip_guard"]
    elif src=="TAIFEX" and any("價差" in str(m.get("native_fields_candidate") or m.get("header_lines_candidates")) for m in profile["selected_archive_member_evidence"]):
     reason="HOLD_TAIFEX_SPREAD_ORDER_NOT_FUTURES_DAILY_DATASET"
    elif profile.get("source_format")=="ZIP" and not profile.get("native_member_profiling_complete"):
     reason="HOLD_ZIP_REMAINING_MEMBERS_AND_ERA_SPEC"
    else:
     reason="HOLD_DATASET_ERA_ORIGINAL_SPEC_AND_PIT_PROOF"
    item["reason"]=reason
    counts["SHA_MATCH"]+=1
    counts["NATIVE_PROFILED"]+=1
    counts[reason]+=1
   except Exception as e:
    item["reason"]="HOLD_READ_OR_PARSE_ERROR_"+type(e).__name__
    counts[item["reason"]]+=1
   result.append(item)
  if len(result)!=10 or sum(1 for q in result if q["status"]=="PASS")!=0:
   raise RuntimeError("SIX_SOURCE_SAMPLE_ACCOUNTING_OR_UNAUTHORIZED_PASS")
  shard={"schema":"R3_G2_SIX_SOURCE_REAL_NATIVE_10PILOT_V1","source":src,
    "source_cohort":len(rows),"run":run,"samples":result,"counts":dict(counts),
    "official_document_candidate":DOCS[src],
    "formal_shared_template_approved":0,"formal_g2_pass":0,"formal_g2_hold":10,
    "baseline_read_only":True,"silver_gold_materialized":False}
  name=f"r3_g2_pilot_{src}_10_run_{run}.json"
  fileid=put_once(api,output["id"],name,shard)
  if load(api,fileid)!=shard:raise RuntimeError("DRIVE_PER_SOURCE_READBACK_MISMATCH_"+src)
  source_result={"source":src,"sample":10,"g2_pass":0,"g2_hold":10,
   "sha_verified":counts["SHA_MATCH"],"native_profiled":counts["NATIVE_PROFILED"],
   "reason_counts":dict(counts),"receipt_id":fileid,"receipt_name":name,
   "remote_readback_verified":True}
  reports.append(source_result);allhold+=10
  print("R3_G2_SIX_SOURCE_10_SAMPLE="+json.dumps(source_result,ensure_ascii=False,sort_keys=True),flush=True)
 if baseline!=COHORT-320 or allhold!=60:raise RuntimeError("FROZEN_6_SOURCE_COHORT_DRIFT")
 result={"schema":"R3_G2_6SOURCE_60_REAL_SAMPLE_QA_MASTER_V1","run":run,
   "real_source_samples":60,"g2_formal_pass":allpass,"g2_formal_hold":allhold,
   "NDC_prior_formal_pass_reused_not_modified":320,
   "source_summary":reports,"official_approval_not_inferred_from_candidate":True,
   "all_source_receipts_readback_verified":True,"bronze_modified":False,
   "silver_gold_materialized":False,"not_production_master":True}
 name=f"r3_g2_6source_60_real_master_run_{run}.json"
 mid=put_once(api,output["id"],name,result)
 if load(api,mid)!=result:raise RuntimeError("SIX_SOURCE_MASTER_READBACK_FAILED")
 print("R3_G2_SIX_SOURCE_REAL_MASTER="+json.dumps({
  "run":run,"samples":60,"pass":allpass,"hold":allhold,"sources":reports,
  "master_id":mid,"master_name":name,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
