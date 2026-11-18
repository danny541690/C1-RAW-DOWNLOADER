"""R3 TDCC: confirm 15 shareholder tiers + seq16 TOTAL, not 16 tiers.

10 real frozen source HTML with SHA, 5-native-header, 15 tiers, numeric
shareholder/share reconciliation and rounding allowance. Official OpenAPI
1-5 is an independent CURRENT format reference; never claim historical
native-version identity or period dates from a web page dropdown.
"""
from __future__ import annotations
import collections,hashlib,json,os,re,requests
from bs4 import BeautifulSoup
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
IN="R3_G2_SIX_SOURCE_REAL_SMALL_PILOT_ISOLATED"
OLD="44261840978"
DEST="R3_G2_TDCC_NATIVE_15_TIERS_ONE_TOTAL_CONTRACT_ISOLATED"
OFFICIAL="https://openapi.tdcc.com.tw/v1/opendata/1-5"
def parse(blob):
 try:s=blob.decode("utf-8-sig")
 except UnicodeError:s=blob.decode("cp950")
 soup=BeautifulSoup(s,"html.parser")
 tables=[]
 for table in soup.find_all("table"):
  rows=[]
  for tr in table.find_all("tr"):
   vals=[" ".join(e.get_text(" ",strip=True).replace("\u3000"," ").split())
       for e in tr.find_all(["th","td"],recursive=False)]
   if vals:rows.append(vals)
  if rows:tables.append(rows)
 candidate=[t for t in tables if t and len(t[0])==5 and t[0][0]=="序" and
            t[0][1]=="持股/單位數分級"]
 if len(candidate)!=1:raise RuntimeError("NO_UNIQUE_TDCC_NATIVE_HEADER")
 t=candidate[0]
 if len(t)!=17:raise RuntimeError("TDCC_EXPECT_1_HEADER_15_BANDS_PLUS_TOTAL")
 bands=t[1:16];total=t[16]
 if [r[0] for r in bands]!=[str(i) for i in range(1,16)]:
  raise RuntimeError("TDCC_NATIVE_TIERS_1_TO_15_NOT_IN_ORDER")
 if total[0]!="16" or "合" not in total[1] or "計" not in total[1]:
  raise RuntimeError("TDCC_ROW_16_NOT_RECOGNIZED_AS_TOTAL")
 if any(len(r)!=5 for r in bands+[total]):raise RuntimeError("TDCC_NATIVE_5_COLUMN_COUNT_MISMATCH")
 number=lambda x:int(x.replace(",",""))
 holders=sum(number(x[2]) for x in bands)
 shares=sum(number(x[3]) for x in bands)
 ratio=sum(float(x[4]) for x in bands)
 if holders!=number(total[2]) or shares!=number(total[3]):
  raise RuntimeError("TDCC_FROZEN_ORIGINAL_TIER_TOTAL_RECONCILIATION_BAD")
 if abs(ratio-100)>0.2 or float(total[4])!=100:
  raise RuntimeError("TDCC_RATIO_ROUNDING_OUTSIDE_15_BAND_TOLERANCE")
 sel=soup.find("select",{"name":"scaDate"})
 options=[str(x.get("value") or x.get_text(" ",strip=True)) for x in sel.find_all("option")] if sel else []
 selected=[str(x.get("value") or x.get_text(" ",strip=True)) for x in sel.find_all("option") if x.has_attr("selected")] if sel else []
 return {"native_column_names":t[0],"tier_count":15,
  "total_native_row_sequence":"16","total_native_row_label":total[1],
  "unique_tier_names":[x[1] for x in bands],
  "total_holder_count":holders,"total_share_count":shares,
  "tier_ratio_sum":round(ratio,4),"official_total_ratio":float(total[4]),
  "rounding_delta_pct":round(100-ratio,4),
  "total_matches_native_frozen":True,
  "form_selected_dates":selected[:3],"form_available_date_first":options[:3],
  "source_date_not_proven_by_date_dropdown":True,
  "example_first_band":bands[0],"example_last_band":bands[-1]}
def official_api_probe():
 try:
  r=requests.get(OFFICIAL,timeout=19,headers={"User-Agent":"JARVIS-R3-TDCC-SchemaProof/1.0"},stream=True)
  h={"http_status":r.status_code,"final_host":__import__("urllib.parse",fromlist=["urlparse"]).urlparse(r.url).hostname}
  if h["final_host"]!="openapi.tdcc.com.tw" or r.status_code!=200:return h
  buf=bytearray()
  for piece in r.iter_content(65536):
   buf.extend(piece)
   if len(buf)>5*1024*1024:
    return {**h,"status":"RESPONSE_OVERSIZE_HOLD"}
  h["response_sha256"]=hashlib.sha256(buf).hexdigest()
  h["response_bytes"]=len(buf)
  try:
   obj=json.loads(buf)
   rows=obj if isinstance(obj,list) else obj.get("data",[]) if isinstance(obj,dict) else []
   h["rows"]=len(rows)
   h["fields"]=list(rows[0])[:25] if rows and isinstance(rows[0],dict) else []
   h["official_current_published_date_2000_2026_not_inferred"]=True
  except (ValueError,TypeError):h["status"]="NON_JSON"
  return h
 except requests.RequestException as exc:return {"status":"REQUEST_"+type(exc).__name__}
def main():
 api,control,quality,match,load,_,_,call=source_api()
 frozen=read_baseline(api,quality,match,load,"TDCC");assert_cohort(frozen,"TDCC")
 index={r["source_id"]:r for r in frozen}
 prior=match(api,quality,IN)
 if not prior:raise RuntimeError("PRIOR_REAL_TDCC_EVIDENCE_FOLDER_MISSING")
 old=match(api,prior["id"],f"r3_g2_pilot_TDCC_10_run_{OLD}.json")
 if not old:raise RuntimeError("TDCC_REAL_SAMPLES_MISSING")
 samples=load(api,old["id"])["samples"]
 if len(samples)!=10:raise RuntimeError("TDCC_TEN_SAMPLES_DRIFT")
 results=[]
 for smp in samples:
  row=index[smp["source_id"]]
  blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
  if hashlib.sha256(blob).hexdigest()!=row["source_sha256"]:
   raise RuntimeError("TDCC_FROZEN_SOURCE_SHA_MISMATCH")
  native=parse(blob)
  m=re.search(r"distribution_(\d{8})_([^_]+)_",str(row.get("source_path")))
  if not m:raise RuntimeError("TDCC_SOURCE_PATH_DATE_STOCK_UNRECOGNIZED")
  detail={"source_id":row["source_id"],"outer_sha256":row["source_sha256"],
   "source_path_date_candidate":m.group(1),"source_path_stock_candidate":m.group(2),
   "native_format_report":native,
   "status":"NATIVE_SEMANTIC_15_BANDS_TOTAL_PASS_OFFICIAL_HISTORICAL_ORIGIN_HOLD",
   "formal_g2_pass":False}
  results.append(detail)
 if len(results)!=10:raise RuntimeError("TEN_TDCC_NOT_FULLY_INSPECTED")
 probe=official_api_probe()
 obj={"schema":"R3_G2_TDCC_NATIVE_15_TIER_PLUS_TOTAL_QA_V1",
   "run":RUN,"native_samples_checked":10,
   "all_shas_matched":True,"native_format_pass_count":10,
   "official_source_historical_sha_unchanged_verified":False,
   "approved_historical_template_count":0,"formal_G2_PASS":0,
   "official_latest_openapi_1_5_schema":probe,
   "data":results,"bronze_modified":False,"silver_gold_materialized":False}
 obj=json.loads(json.dumps(obj,ensure_ascii=False))
 folder=match(api,quality,DEST)
 if not folder:folder=call(lambda:api.files().create(body={"name":DEST,"parents":[quality],
  "mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name="r3_tdcc_15_tiers_and_seq16_total_10_frozen_run_"+RUN+".json"
 mid=put_once(api,folder["id"],name,obj)
 if load(api,mid)!=obj:raise RuntimeError("TDCC_TEN_EVIDENCE_REMOTE_READBACK_FAILED")
 print("R3_TDCC_SEMANTIC_10="+json.dumps({"run":RUN,"source":"TDCC",
  "native_15band_and_total_pass":10,"official_historical_response_matches":False,
  "new_G2_pass":0,"official_current_openapi":probe,
  "receipt_id":mid,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
