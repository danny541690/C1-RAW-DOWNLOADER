"""Four-source first real G2 formal certification attempts, fail closed.

MOPS / TDCC / TAIFEX / FinMind. Re-read 10 real frozen Bronze each,
SHA verify, preserve native identity & dates and crosscheck narrowly scoped
primary-source format specs. A field/header match is an EVIDENCE improvement,
not an official G2 cert without exact original response/source-asof + approval.
All immutable findings saved to Google Drive with per-source remote readback.
"""
from __future__ import annotations
import collections,csv,datetime,hashlib,io,json,os,re,zipfile
from urllib.parse import urlparse
import requests
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once

RUN=os.getenv("GITHUB_RUN_ID","manual")
SOURCES=("MOPS","TDCC","TAIFEX","FinMind")
PRIOR="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
PRIOR_RUN="44261840978"
FOLDER="R3_G2_FOUR_SOURCE_FIRST_PASS_CERTIFICATION_PILOT_ISOLATED"
LIMIT=4*1024*1024
REFERENCES={
 "MOPS":[("FINANCIAL_COMPARE_OFFICIAL","https://mopsfin.twse.com.tw/compare/report"),
         ("MOPS_MAIN","https://mops.twse.com.tw/")],
 "TDCC":[("OFFICIAL_SHARE_DISTRIBUTION","https://s.tdcc.com.tw/portal/zh/smWeb/qryStock"),
         ("OFFICIAL_TDCC_HOME","https://www.tdcc.com.tw/portal/zh/smWeb/qryStock")],
 "TAIFEX":[("OFFICIAL_OPEN_DATA_FIELD_FORMAT_PDF","https://www.taifex.com.tw/file/taifex/CHINESE/11/TechDocs/30/opendata_all.pdf"),
            ("OFFICIAL_LARGE_TRADERS","https://www.taifex.com.tw/cht/3/largeTraderFutView")],
 "FinMind":[("PROVIDER_STOCK_PRICE_SCHEMA","https://finmind.github.io/DataQuality/TaiwanStockPrice/"),
            ("PROVIDER_AUTH_AND_DATASET","https://finmind.github.io/login/")]}
HOSTS={"MOPS":("twse.com.tw",),"TDCC":("tdcc.com.tw",),
       "TAIFEX":("taifex.com.tw",),"FinMind":("finmind.github.io",)}
def allowed(src,url):
 try:
  p=urlparse(url);h=(p.hostname or "").lower()
  return p.scheme=="https" and any(h==x or h.endswith("."+x) for x in HOSTS[src])
 except (TypeError,ValueError):return False
def official(src,key,url):
 result={"purpose":key,"url":url,"status":"HOLD_UNRETRIEVED","historical_format_attested":False}
 if not allowed(src,url):return {**result,"status":"HOLD_HOST_NOT_OFFICIAL"}
 try:
  rsp=requests.get(url,timeout=13,stream=True,headers={"User-Agent":"JARVIS-R3-SourceFormat-Evidence/1.0"})
  result["http_status"]=rsp.status_code
  if not allowed(src,rsp.url):return {**result,"status":"HOLD_UNTRUSTED_REDIRECT"}
  if rsp.status_code!=200:return {**result,"status":"HOLD_HTTP_"+str(rsp.status_code)}
  h=hashlib.sha256();size=0
  for piece in rsp.iter_content(chunk_size=65536):
   if not piece:continue
   size+=len(piece)
   if size>4_000_000:return {**result,"status":"HOLD_OFFICIAL_SPEC_RESOURCE_GUARD"}
   h.update(piece)
  if size<80:return {**result,"status":"HOLD_EMPTY_OFFICIAL_SPEC"}
  return {**result,"status":"DOCUMENT_BYTES_VERIFIED_ONLY",
          "bytes":size,"sha256":h.hexdigest(),
          "observed_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "historical_format_attested":False}
 except requests.RequestException as e:
  return {**result,"status":"HOLD_HTTP_"+type(e).__name__}
def safe_decode(blob):
 for enc in ("utf-8-sig","cp950","big5"):
  try:return blob.decode(enc),enc
  except UnicodeError:continue
 return None,None
def select_native(blob):
 if zipfile.is_zipfile(io.BytesIO(blob)):
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   entries=[x for x in z.infolist() if not x.is_dir()]
   expanded=sum(x.file_size for x in entries)
   if len(entries)>160 or expanded>16_000_000:
    return {"kind":"ZIP","guard":"HOLD_ZIP_RESOURCE","member_count":len(entries),
            "total_uncompressed":expanded,"members":[]}
   if z.testzip() is not None:
    return {"kind":"ZIP","guard":"ERROR_ZIP_MEMBER_CRC","members":[]}
   members=[]
   for e in entries:
    if e.file_size>750000:
     members.append({"path":e.filename,"status":"HOLD_MEMBER_RESOURCE"});continue
    m=z.read(e)
    members.append({"path":e.filename,"sha256":hashlib.sha256(m).hexdigest(),
       "bytes":len(m),"status":"NATIVE_MEMBER_SHA_VERIFIED","contents":m})
   return {"kind":"ZIP","guard":"PASS_ARCHIVE_CRC","member_count":len(entries),"members":members}
 return {"kind":"DIRECT","guard":"PASS_DIRECT_SHA","member_count":1,
         "members":[{"path":"direct_native","sha256":hashlib.sha256(blob).hexdigest(),
                     "bytes":len(blob),"status":"NATIVE_MEMBER_SHA_VERIFIED","contents":blob}]}
def profile_member(src,member):
 out={k:v for k,v in member.items() if k!="contents"}
 data=member.get("contents")
 if data is None:return out
 txt,enc=safe_decode(data)
 out["encoding"]=enc
 if src=="TAIFEX":
  if txt is None:
   out["native_classification"]="HOLD_ENCODING";return out
  lines=txt.splitlines()
  first=[]
  try:first=list(csv.reader(lines[:min(20,len(lines))]))
  except csv.Error:pass
  hdr=next((r for r in first if len(r)>5 and any("日期" in str(v) for v in r)),[])
  out["native_headers"]=hdr[:35]
  out["first_three_rows"]=first[:3]
  if "前五大交易人買方" in hdr and "全市場未沖銷部位數" in hdr:
   out["dataset_candidate"]="LARGE_TRADER_FUTURES_POSITION"
   # Real TAIFEX official open-data specification: official 11-field schema.
   expected=("日期","商品(契約)","商品名稱(契約名稱)",
             "前五大交易人買方","前五大交易人賣方",
             "前十大交易人買方","前十大交易人賣方",
             "全市場未沖銷部位數")
   out["official_header_candidate_check"]=all(x in hdr for x in expected)
  elif "履約價格" in hdr and "買/賣權" in hdr:
   out["dataset_candidate"]="OPTIONS_DAILY"
   out["official_header_candidate_check"]=False
  elif "期貨價差委託成交概況表" in txt[:140]:
   out["dataset_candidate"]="FUTURES_SPREAD_ORDER"
   out["official_header_candidate_check"]=False
  else:
   out["dataset_candidate"]="TAIFEX_OTHER_NATIVE_CSV"
   out["official_header_candidate_check"]=False
  out["native_date_from_row_attested"]=False
 elif src=="TDCC":
  if txt is None:
   out["native_classification"]="HOLD_ENCODING";return out
  out["native_classification"]="HTML_XML" if txt.lstrip().startswith("<") else "OTHER_TEXT"
  out["first_tags"]=re.findall(r"<([a-zA-Z][\w:-]*)",txt[:3000])[:15]
  out["securities_date_hint"]=re.findall(r"(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}",txt[:15000])[:6]
  out["native_security_identity_attested"]=False
 elif src=="MOPS":
  if txt is None:
   out["native_classification"]="HOLD_ENCODING";return out
  out["native_classification"]="HTML_XML" if txt.lstrip().startswith("<") else "OTHER_TEXT"
  out["has_comparison_report_keyword"]=("比較" in txt or "財報" in txt or "Financial" in txt[:3000])
  out["filing_amendment_pit_attested"]=False
 elif src=="FinMind":
  try:obj=json.loads(txt) if txt else None
  except (ValueError,TypeError):obj=None
  out["native_classification"]="JSON" if obj is not None else "NON_JSON"
  rows=obj if isinstance(obj,list) else obj.get("data",[]) if isinstance(obj,dict) else []
  if isinstance(rows,list) and rows and isinstance(rows[0],dict):
   fields=list(rows[0]);out["headers"]=fields[:25]
   if {"date","stock_id","Trading_Volume","close"}.issubset(fields):
    out["dataset_candidate"]="TaiwanStockPrice"
    out["provider_header_candidate_check"]=True
   elif {"date","stock_id","type","value","origin_name"}.issubset(fields):
    out["dataset_candidate"]="FinMindInstitutionalOther"
    out["provider_header_candidate_check"]=False
   else:
    out["dataset_candidate"]="UnresolvedFinMind"
    out["provider_header_candidate_check"]=False
   out["observation_date_candidate"]=str(rows[0].get("date",""))[:12]
  out["origin_response_independently_verified"]=False
 return out
def main():
 api,control,quality,match,load,_,_,call=source_api()
 prior=match(api,quality,PRIOR)
 if not prior:raise RuntimeError("FOUR_SOURCE_REAL_PRIOR_SAMPLE_FOLDER_MISSING")
 target=match(api,quality,FOLDER)
 if target is None:target=call(lambda:api.files().create(body={"name":FOLDER,"parents":[quality],
       "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 if target.get("mimeType")!="application/vnd.google-apps.folder":
  raise RuntimeError("OUTPUT_NOT_FOLDER")
 sums=[]
 for src in SOURCES:
  p=match(api,prior["id"],f"r3_g2_pilot_{src}_10_run_{PRIOR_RUN}.json")
  if not p:raise RuntimeError("SOURCE_PREVIOUS_RECEIPT_MISSING_"+src)
  samples=load(api,p["id"])["samples"]
  if len(samples)!=10:raise RuntimeError("SOURCE_PILOT_TEN_CHANGED")
  originals=read_baseline(api,quality,match,load,src);assert_cohort(originals,src)
  byid={x["source_id"]:x for x in originals}
  docs=[official(src,k,u) for k,u in REFERENCES[src]]
  results=[];reason=collections.Counter();header_match=0
  for sample in samples:
   sid=sample["source_id"];r=byid.get(sid)
   if not r:raise RuntimeError("PILOT_SOURCE_ID_NOT_IN_FROZEN_COHORT")
   obj={"source_id":sid,"source_sha256":r["source_sha256"],"G2":"HOLD",
        "actual_cert_issued":False,"official_dataset_edition_approved":False}
   try:
    m=call(lambda:api.files().get(fileId=r["destination_id"],fields="id,size,mimeType"))
    if int(m.get("size") or 0)>LIMIT:raise ValueError("HOLD_RAW_SIZE_LIMIT")
    raw=call(lambda:api.files().get_media(fileId=r["destination_id"]))
    if hashlib.sha256(raw).hexdigest()!=r["source_sha256"]:
     raise ValueError("ERROR_BRONZE_SHA_MISMATCH")
    native=select_native(raw)
    profiles=[profile_member(src,v) for v in native["members"]]
    obj.update({"original_sha_verified":True,"native_archive_guard":native["guard"],
               "member_count":native["member_count"],"members":profiles})
    matches=sum(bool(x.get("official_header_candidate_check") or x.get("provider_header_candidate_check"))
                for x in profiles)
    header_match+=matches
    if native["guard"] not in ("PASS_ARCHIVE_CRC","PASS_DIRECT_SHA"):
     obj["reason"]=native["guard"]
    elif src=="TAIFEX" and matches:
     obj["reason"]="G2_NATIVE_TAIFEX_HEADER_MATCH_BUT_OFFICIAL_RESPONSE_SHA_AND_HISTORICAL_ERA_UNVERIFIED"
    elif src=="FinMind" and matches:
     obj["reason"]="G2_FINMIND_DATASET_HEADER_MATCH_BUT_EXACT_API_RESPONSE_AND_PROVIDER_ASOF_UNVERIFIED"
    elif src=="MOPS":
     obj["reason"]="G2_MOPS_NATIVE_FILING_QUERY_METHOD_CORRECTED_REPORT_PIT_UNVERIFIED"
    elif src=="TDCC":
     obj["reason"]="G2_TDCC_NATIVE_HISTORIC_SECURITY_ID_16_17_TIER_SOURCE_NOT_ATTESTED"
    else:obj["reason"]="G2_ORIGINAL_SOURCE_NATIVE_FORMAT_OR_EFFECTIVE_DATE_UNVERIFIED"
   except Exception as e:
    obj["reason"]=str(e) if isinstance(e,ValueError) else "HOLD_SOURCE_READ_"+type(e).__name__
   reason[obj["reason"]]+=1
   results.append(obj)
  if len(results)!=10:raise RuntimeError("SOURCE_SAMPLE_ACCOUNTING_DRIFT")
  report={"schema":"R3_G2_FOUR_SOURCE_TRUE_NATIVE_FIRST_CERT_ATTEMPT_V1",
    "source":src,"run":RUN,"source_cohort":len(originals),"sampled_real_files":10,
    "official_spec_documents":docs,
    "native_header_matches_to_official_candidates":header_match,
    "source_archive_evidence":results,"formal_G2_PASS":0,"formal_G2_HOLD":10,
    "reasons":dict(reason),
    "Bronze_modified":False,"Silver_or_Gold_materialized":False}
  name=f"r3_g2_four_source_{src}_10_formal_attempt_run_{RUN}.json"
  id=put_once(api,target["id"],name,report)
  if load(api,id)!=report:raise RuntimeError("FOUR_SOURCE_EVIDENCE_READBACK_FAILED_"+src)
  result={"source":src,"sample":10,"g2_pass":0,"g2_hold":10,
       "field_header_candidate_matches":header_match,
       "reasons":dict(reason),"official_docs_fetched":sum(x["status"]=="DOCUMENT_BYTES_VERIFIED_ONLY" for x in docs),
       "file_id":id,"name":name,"readback":True}
  sums.append(result)
  print("R3_G2_FOUR_SOURCE_FIRST_SOURCE="+json.dumps(result,ensure_ascii=False,sort_keys=True),flush=True)
 out={"schema":"R3_G2_FOUR_SOURCE_FIRST_FORMAL_QA_MASTER_V1","run":RUN,
    "frozen_sources":SOURCES,"real_sample_total":40,
    "new_formal_PASS":0,"HOLD":40,"NDC_TWSE_TPEx_322_prior_unmodified":True,
    "sources":sums,"Bronze_modified":False,"Silver_or_Gold_materialized":False,
    "not_G5_production_master":True}
 name=f"r3_g2_four_source_first_formal_master_run_{RUN}.json"
 mid=put_once(api,target["id"],name,out)
 if load(api,mid)!=out:raise RuntimeError("FOUR_SOURCE_MASTER_NOT_READBACK")
 print("R3_G2_FOUR_SOURCE_FIRST_MASTER="+json.dumps({
  "run":RUN,"samples":40,"pass":0,"hold":40,"master_id":mid,
  "master_name":name,"sources":sums,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
