"""Follow-up: actual official TAIFEX and FinMind endpoint checks.

Real official GET against frozen native examples, with bounded response.
No token exfiltration: never log or persist secrets. Distinguish live data
revision from frozen corruption. Exact native correspondence required for
any later source-vintage G2 issuance; partial row equality NOT a PASS.
"""
import datetime,hashlib,io,json,os,zipfile,csv,collections
from urllib.parse import urlparse
import requests
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
OUT="R3_G2_FOUR_SOURCE_ENDPOINT_ORIGINAL_PROOF_ISOLATED"
SAMPLES={
 "TAIFEX":[("1V3tY6CRlSB6JjOYld8sFPxmv2vDdg3tu","2024-01-02","https://openapi.taifex.com.tw/v1/OpenInterestOfLargeTradersFutures")],
 "FinMind":[("1qPOj2Q9Q-h2lHUC98RviBjy4hoKR0nwE","2022-05-03","https://api.finmindtrade.com/api/v4/data")]}
def bounded(url,params,allowed):
 target=urlparse(url)
 if target.scheme!="https" or target.hostname not in allowed:raise RuntimeError("NOT_ALLOWLISTED")
 result={"api_endpoint":url,"query_dataset":params.get("dataset") if params else None,"original_response_exact_sha_verified":False,
         "source_publication_asof_verified":False,"official_historical_version_proven":False}
 try:
  r=requests.get(url,params=params,timeout=23,stream=True,headers={"User-Agent":"JARVIS-R3-G2-Official-Original-Independent/1.0"})
  result["http_status"]=r.status_code
  result["final_host"]=urlparse(r.url).hostname
  if urlparse(r.url).hostname not in allowed:return {**result,"status":"HOLD_REDIRECT_UNTRUSTED"}
  if r.status_code!=200:return {**result,"status":"HOLD_HTTP_"+str(r.status_code)}
  content=bytearray()
  for chunk in r.iter_content(65536):
   content.extend(chunk)
   if len(content)>6*1024*1024:return {**result,"status":"HOLD_API_RESPONSE_LIMIT"}
  result["response_bytes"]=len(content)
  result["remote_sha256"]=hashlib.sha256(content).hexdigest()
  try:
   obj=json.loads(content)
   if isinstance(obj,list):
    result["response_row_count"]=len(obj)
    result["first_row_fields"]=list(obj[0])[:25] if obj and isinstance(obj[0],dict) else []
    result["first_row_date"]=str(obj[0].get("日期",obj[0].get("Date","")))[:16] if obj and isinstance(obj[0],dict) else None
   elif isinstance(obj,dict):
    result["response_fields"]=list(obj)[:16]
    ds=obj.get("data")
    result["response_row_count"]=len(ds) if isinstance(ds,list) else None
    if isinstance(ds,list) and ds and isinstance(ds[0],dict):
     result["first_row_fields"]=list(ds[0])[:25]
    result["response_status"]=(obj.get("status") or obj.get("msg") or obj.get("message"))
  except ValueError:result["response_status"]="NON_JSON"
  result["status"]="LIVE_RESPONSE_RETRIEVED_NOT_HISTORICALLY_CERTIFIED"
 except requests.RequestException as e:
  result["status"]="HOLD_ENDPOINT_"+type(e).__name__
 return result
def main():
 api,control,quality,match,load,_,_,call=source_api()
 folder=match(api,quality,OUT)
 if not folder:folder=call(lambda:api.files().create(body={"name":OUT,"parents":[quality],
   "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 summary=[]
 for src in ("TAIFEX","FinMind"):
  frozen=read_baseline(api,quality,match,load,src);assert_cohort(frozen,src)
  byid={r["source_id"]:r for r in frozen}
  reports=[]
  for sid,day,url in SAMPLES[src]:
   row=byid.get(sid)
   if not row:raise RuntimeError("SAMPLE_ID_NOT_FROZEN")
   blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
   if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:
    raise RuntimeError("FROZEN_SHA_DISAGREES")
   if zipfile.is_zipfile(io.BytesIO(blob)):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
     first=next((x for x in z.infolist() if not x.is_dir() and x.filename!="manifest.json"),None)
     if not first or first.file_size>3*1024*1024:raise RuntimeError("NO_BOUNDED_SOURCE_MEMBER")
     native=z.read(first)
   else:native=blob
   params=None
   hosts=("openapi.taifex.com.tw",)
   if src=="FinMind":
    params={"dataset":"TaiwanStockPrice","start_date":day,"end_date":day}
    hosts=("api.finmindtrade.com",)
   proof=bounded(url,params,hosts)
   proof.update({"source":src,"source_id":sid,"frozen_outer_sha256":row["source_sha256"],
      "native_member_sha256":hashlib.sha256(native).hexdigest(),
      "data_date_candidate":day,"verified_orig_file_bytes":True,
      "same_api_bytes_as_original_member":proof.get("remote_sha256")==hashlib.sha256(native).hexdigest(),
      "formal_G2_issued":False})
   reports.append(proof)
  document={"schema":"R3_G2_OFFICIAL_PROVIDER_ENDPOINT_RECHECK_V1","run":RUN,"source":src,
     "source_cohort":len(frozen),"source_probes":reports,
     "G2_formal_pass":0,"G2_hold":len(reports),
     "history_asof_not_proven":True,"no_silver_gold":True,"bronze_modified":False}
  name=f"r3_g2_real_endpoint_{src}_run_{RUN}.json"
  fid=put_once(api,folder["id"],name,document)
  if load(api,fid)!=document:raise RuntimeError("ENDPOINT_PROOF_REMOTE_READBACK_FAILED")
  item={"source":src,"results":reports,"receipt_id":fid,"readback":True}
  summary.append(item)
  print("R3_G2_REAL_ENDPOINT_SOURCE="+json.dumps(item,ensure_ascii=False,sort_keys=True),flush=True)
 master={"schema":"R3_G2_FOUR_SOURCE_ENDPOINT_RECHECK_MASTER_V1","run":RUN,"sources":summary,
    "formal_new_pass":0,"bronze_changed":False,"silver_gold_materialized":False}
 name=f"r3_g2_original_endpoint_master_run_{RUN}.json"
 mid=put_once(api,folder["id"],name,master)
 if load(api,mid)!=master:raise RuntimeError("ENDPOINT_MASTER_REMOTE_READBACK_FAILED")
 print("R3_G2_REAL_ENDPOINT_MASTER="+json.dumps({"run":RUN,"master_id":mid,
    "source_results":summary,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
