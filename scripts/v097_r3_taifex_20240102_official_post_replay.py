"""True TAIFEX 2024-01-02 original CSV official POST replay.

Unlike current-only OpenAPI, official historical download endpoint accepts
queryStartDate / queryEndDate. Compare entire UTF-8 / Big5 normalized data
to real frozen Bronze CSV and archive raw both ways. Official SHA + every
native row need independent readback before any G2 approval.
"""
import csv,datetime,hashlib,io,json,os,requests
from urllib.parse import urlparse
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
SID="1V3tY6CRlSB6JjOYld8sFPxmv2vDdg3tu"
SRC="TAIFEX"
API="https://www.taifex.com.tw/cht/3/largeTraderFutDown"
DAY="2024/01/02"
DEST="R3_G2_TAIFEX_FIRST_HISTORICAL_ORIGINAL_REPLAY_ISOLATED"
def normalized(raw):
 for codec in ("cp950","big5","utf-8-sig","utf-8"):
  try:
   txt=raw.decode(codec)
   rows=list(csv.reader(io.StringIO(txt)))
   rows=[tuple(c.strip() for c in row) for row in rows if any(c.strip() for c in row)]
   return rows,codec
  except (UnicodeError,csv.Error):pass
 return [],None
def main():
 api,control,quality,match,load,_,_,call=source_api()
 rows=read_baseline(api,quality,match,load,SRC);assert_cohort(rows,SRC)
 matchrows=[x for x in rows if x["source_id"]==SID]
 if len(matchrows)!=1:raise RuntimeError("FROZEN_TAIFEX_SOURCE_ID_CHANGED")
 row=matchrows[0]
 native=call(lambda:api.files().get_media(fileId=row["destination_id"]))
 if hashlib.sha256(native).hexdigest()!=row["source_sha256"]:raise RuntimeError("BRONZE_SHA_CHANGED")
 source_rows,source_encoding=normalized(native)
 if not source_rows or len(source_rows)<3:raise RuntimeError("UNREADABLE_NATIVE_TAIFEX")
 date_values={r[0] for r in source_rows[1:] if r}
 if not date_values or any(not d.startswith("2024/01/") for d in date_values):
  raise RuntimeError("BRONZE_CONTAINS_NON_JANUARY_DATE")
 first_day,last_day=min(date_values),max(date_values)
 outcome={"schema":"R3_TAIFEX_OFFICIAL_HISTORICAL_POST_NATIVE_COMPARE_V1",
  "run":RUN,"source":SRC,"source_id":SID,
  "frozen_source_sha256":row["source_sha256"],
  "official_api":API,"query_start":first_day,"query_end":last_day,
  "native_rows_including_header":len(source_rows),
  "native_encoding":source_encoding,
  "original_frozen_date_values":sorted(date_values),
  "official_response_raw_sha256":None,
  "exact_bytes_sha_match":False,"all_normalized_rows_match":False,
  "native_historical_version_attested":False,
  "historical_contemporaneous_2024_pit_attested":False,
  "formal_G2_issued":False}
 try:
  r=requests.post(API,data={"queryStartDate":first_day,"queryEndDate":last_day},
     timeout=25,headers={"User-Agent":"Mozilla/5.0 JARVIS-R3-G2-Historical-Official/1.0"})
  outcome["http_status"]=r.status_code
  outcome["redirect_host"]=urlparse(r.url).hostname
  if r.status_code!=200 or urlparse(r.url).hostname not in ("www.taifex.com.tw","taifex.com.tw"):
   outcome["status"]="HOLD_UNAVAILABLE_OR_UNTRUSTED_SOURCE"
  elif len(r.content)>4*1024*1024:
   outcome["status"]="HOLD_OFFICIAL_RESPONSE_SIZE_GUARD"
  else:
   response_rows,codec=normalized(r.content)
   outcome["official_response_encoding"]=codec
   outcome["official_response_row_count"]=len(response_rows)
   outcome["official_response_raw_sha256"]=hashlib.sha256(r.content).hexdigest()
   outcome["exact_bytes_sha_match"]=hashlib.sha256(r.content).hexdigest()==row["source_sha256"]
   outcome["all_normalized_rows_match"]=(response_rows==source_rows)
   outcome["header_match"]=response_rows[:1]==source_rows[:1]
   outcome["first_two_official_rows"]=response_rows[:2]
   outcome["status"]="OFFICIAL_COMPLETE_NATIVE_RESPONSE_VERIFIED" if response_rows==source_rows else "HOLD_OFFICIAL_RAW_RESPONSE_DIFFERS"
 except requests.RequestException as e:outcome["status"]="HOLD_OFFICIAL_HTTP_"+type(e).__name__
 folder=match(api,quality,DEST)
 if folder is None:folder=call(lambda:api.files().create(body={
     "name":DEST,"parents":[quality],"mimeType":"application/vnd.google-apps.folder"},fields="id,mimeType"))
 name=f"r3_taifex_20240102_official_original_post_compare_run_{RUN}.json"
 fid=put_once(api,folder["id"],name,outcome)
 if load(api,fid)!=outcome:raise RuntimeError("TAIFEX_ORIGINAL_COMPARE_REMOTE_READBACK_MISMATCH")
 print("R3_G2_TAIFEX_ORIGINAL_HISTORICAL_POST="+json.dumps({
  "run":RUN,"status":outcome.get("status"),"http_status":outcome.get("http_status"),
  "frozen_rows":len(source_rows),"official_rows":outcome.get("official_response_row_count"),
  "official_raw_sha":outcome.get("official_response_raw_sha256"),
  "byte_sha_equal":outcome["exact_bytes_sha_match"],
  "all_rows_equal":outcome["all_normalized_rows_match"],
  "receipt":fid,"readback":True,
  "formal_g2_pass":0
 },ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
