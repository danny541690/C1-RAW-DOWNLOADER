"""TDCC official OpenAPI /1-5 bounded full schema and exact 20261008 2365
native source query. Parse genuine large JSON safely; current API return need
exact security id + historical week + all native tier values before G2.
Never use current-week snapshot as if it were 2026-10-08.
"""
import hashlib,json,os,re,requests
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_r3_tdcc_semantic_15band_contract import parse
RUN=os.getenv("GITHUB_RUN_ID","manual")
URL="https://openapi.tdcc.com.tw/v1/opendata/1-5"
SID="1pSZLlDcTK1hPofAwesE8mcs90QPySVOw"
DEST="R3_G2_TDCC_OFFICIAL_LARGE_OPENAPI_EXACT_WEEKLY_ISOLATED"
MAX=45*1024*1024
def main():
 api,control,quality,match,load,_,_,call=source_api()
 frozen=read_baseline(api,quality,match,load,"TDCC");assert_cohort(frozen,"TDCC")
 row=next(x for x in frozen if x["source_id"]==SID)
 blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:raise RuntimeError("FROZEN_TDCC_SOURCE_CHANGED")
 source=parse(blob)
 result={"schema":"R3_TDCC_OFFICIAL_OPENAPI_MATCH_HISTORICAL_NATIVE_V1",
   "run":RUN,"source_id":SID,"source_sha256":row["source_sha256"],
   "target_week":"20261008","target_security":"2365",
   "native_tier_count":source["tier_count"],
   "native_total_holders":source["total_holder_count"],
   "native_total_shares":source["total_share_count"],
   "native_ratio_sum":source["tier_ratio_sum"],
   "native_tier_values":source["unique_tier_names"],
   "official_api_url":URL,"full_source_week_and_security_verified":False,
   "official_tier_cells_equal_original":False,"formal_g2_issued":False}
 try:
  response=requests.get(URL,timeout=50,stream=True,headers={"User-Agent":"JARVIS-R3-TDCC-SourceSemantics/1.0"})
  result["http_status"]=response.status_code
  result["final_host"]=urlparse(response.url).hostname
  if response.status_code!=200 or result["final_host"]!="openapi.tdcc.com.tw":
   result["status"]="OFFICIAL_HTTP_OR_HOST_NOT_VERIFIED"
  else:
   body=bytearray()
   for chunk in response.iter_content(131072):
    body.extend(chunk)
    if len(body)>MAX:break
   result["bytes_received"]=len(body)
   if len(body)>MAX:result["status"]="OFFICIAL_API_MORE_THAN_45MB_HOLD"
   else:
    result["official_response_sha256"]=hashlib.sha256(body).hexdigest()
    try:obj=json.loads(body)
    except (ValueError,TypeError):obj=None
    data=obj if isinstance(obj,list) else obj.get("data") if isinstance(obj,dict) else None
    if not isinstance(data,list):
     result["status"]="OFFICIAL_JSON_ARRAY_NOT_EXTRACTED"
     result["response_object_keys"]=list(obj)[:20] if isinstance(obj,dict) else []
    else:
     result["official_total_rows"]=len(data)
     first=next((r for r in data if isinstance(r,dict)),None)
     result["official_native_field_names"]=list(first)[:30] if first else []
     def candidate(r):
      return any("2365"==str(v).strip() for k,v in r.items() if any(z in k.lower() for z in ("證券代號","證券","stock","code")))
     in_stock=[r for r in data if isinstance(r,dict) and candidate(r)]
     result["rows_with_stock_2365"]=len(in_stock)
     date_keys=lambda rr:[str(v) for k,v in rr.items() if any(z in k.lower() for z in ("日期","date","資料日"))]
     result["distinct_2365_date_candidates"]=sorted({v for rr in in_stock for v in date_keys(rr)})[:30]
     exact=[rr for rr in in_stock if any("20261008" in v.replace("/","").replace("-","") or
               "1151008" in v.replace("/","").replace("-","") for v in date_keys(rr))]
     result["exact_week_2365_records"]=len(exact)
     result["exact_week_sample_rows"]=exact[:4]
     result["official_stock_2365_sample"]=in_stock[:2]
     result["status"]="HOLD_DATASET_FORMAT_NATIVE_MAPPED_BUT_EXACT_WEEK_CONTENT_NOT_VALIDATED"
 except requests.RequestException as e:
  result["status"]="OFFICIAL_OPENAPI_REQUEST_"+type(e).__name__
 folder=match(api,quality,DEST)
 if not folder:folder=call(lambda:api.files().create(body={"name":DEST,
   "parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 result=json.loads(json.dumps(result,ensure_ascii=False))
 name=f"r3_tdcc_official_1_5_2365_week_20261008_run_{RUN}.json"
 rid=put_once(api,folder["id"],name,result)
 if load(api,rid)!=result:raise RuntimeError("OFFICIAL_TDCC_CENSUS_READBACK_FAILED")
 print("R3_G2_TDCC_OFFICIAL_45MB_QUERY="+json.dumps({
  "run":RUN,"http":result.get("http_status"),"status":result.get("status"),
  "official_total_rows":result.get("official_total_rows"),
  "fields":result.get("official_native_field_names"),
  "stock_2365_rows":result.get("rows_with_stock_2365"),
  "exact_week_2365_rows":result.get("exact_week_2365_records"),
  "receipt_id":rid,"formal_g2_pass":0,
  "remote_readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
