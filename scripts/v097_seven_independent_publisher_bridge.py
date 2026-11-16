#!/usr/bin/env python3
"""JARVIS v0.97 seven-source independently fetched publisher evidence, safe pilot.

Publishes immutable per-run provenance receipts (URL, host, HTTP, UTC, SHA).
TWSE/TPEx additionally reuse actual dated stock-close numeric 3-way witness.
TDCC additionally runs independently fetched matched-date stock query control.
Others are publisher-document + source-original SHA evidence ONLY, not numeric proof.
NEVER claims whole-file triple match, PIT, or official Silver release.
"""
import datetime,hashlib,json,os,re,sys,time
from collections import Counter
from urllib.parse import urlparse
import requests
from scripts.v097_bronze_autopilot import SOURCES,source_api,digest
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
MAX_BYTES=6*1024*1024
TIMEOUT=(8,24)
MAX_ATTEMPTS=3
UA="JARVIS-v097-Official-Provenance-Pilot/1.0"
SOURCE_PUBLISHERS={
 "TWSE":{"twse.com.tw","www.twse.com.tw","openapi.twse.com.tw"},
 "TPEx":{"tpex.org.tw","www.tpex.org.tw"},
 "MOPS":{"twse.com.tw","www.twse.com.tw","mops.twse.com.tw","mopsfin.twse.com.tw"},
 "TDCC":{"tdcc.com.tw","www.tdcc.com.tw","original-www.tdcc.com.tw"},
 "TAIFEX":{"taifex.com.tw","www.taifex.com.tw"},
 "NDC":{"ndc.gov.tw","www.ndc.gov.tw","ws.ndc.gov.tw"},
 "FinMind":{"finmind.github.io","api.finmindtrade.com"}}
# Exact documented publisher pages; these are version-reference witnesses, not
# the original trading-date source payload. FinMind is provider not TW regulator.
PAGES={
 "TWSE":"https://www.twse.com.tw/zh/trading/historical/mi-index.html",
 "TPEx":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html",
 "MOPS":"https://www.twse.com.tw/rwd/IFRS/aboutIFRS",
 "TDCC":"https://original-www.tdcc.com.tw/portal/zh/smWeb/qryStock",
 "TAIFEX":"https://www.taifex.com.tw/cht/3/futDailyMarketView",
 "NDC":"https://www.ndc.gov.tw/nc_335_2236",
 "FinMind":"https://finmind.github.io/tutor/TaiwanMarket/Technical/"}
WORDS={"TWSE":("證券","交易"),"TPEx":("上櫃","交易"),"MOPS":("IFRS","財務"),
 "TDCC":("集保","股權"),"TAIFEX":("期貨","交易"),
 "NDC":("景氣","對策"),"FinMind":("TaiwanStockPrice","資料")}
def allow(source,url):
 p=urlparse(url)
 return p.scheme=="https" and p.hostname in SOURCE_PUBLISHERS[source] and not p.username
def live_page(source,url,session):
 if not allow(source,url):return {"status":"REJECTED_PUBLISHER_URL"}
 for attempt in range(MAX_ATTEMPTS):
  try:
   # Refuse off-publisher redirect; never leak upstream credentials.
   r=session.get(url,headers={"User-Agent":UA,"Accept":"text/html,application/json"},
      timeout=TIMEOUT,allow_redirects=False,stream=True)
   if r.status_code in (301,302,303,307,308):
    loc=r.headers.get("Location","")
    from urllib.parse import urljoin
    redirect=urljoin(url,loc)
    if not allow(source,redirect):return {"status":"HOLD_REDIRECT_TO_UNTRUSTED_HOST","http":r.status_code}
    url=redirect;continue
   if r.status_code in (429,500,502,503,504):raise requests.HTTPError("transient:"+str(r.status_code))
   if r.status_code!=200:return {"status":"HOLD_OFFICIAL_HTTP_"+str(r.status_code),"http":r.status_code}
   body=b""
   for chunk in r.iter_content(chunk_size=65536):
    body+=chunk
    if len(body)>MAX_BYTES:return {"status":"HOLD_OFFICIAL_PAGE_SIZE_LIMIT"}
   if not body:return {"status":"HOLD_OFFICIAL_PAGE_EMPTY"}
   sample=body[:MAX_BYTES].decode("utf-8","replace")
   found=[term for term in WORDS[source] if term.lower() in sample.lower()]
   status="PUBLISHER_FORMAT_DOCUMENT_RETRIEVED" if found else "HOLD_PUBLISHER_DOCUMENT_TYPE_NOT_CONFIRMED"
   return {"status":status,"official_url":url,"publisher_host":urlparse(url).hostname,
    "http":200,"retrieved_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "payload_sha256":hashlib.sha256(body).hexdigest(),
    "payload_bytes":len(body),"matched_document_markers":found,
    "independent_historical_numeric_value_proven":False,
    "publication_asof_proven":False}
  except (requests.RequestException,TimeoutError,OSError) as e:
   if attempt==MAX_ATTEMPTS-1:
    return {"status":"RETRY_OFFICIAL_PAGE_"+type(e).__name__,"attempts":MAX_ATTEMPTS}
   time.sleep(min(2**attempt,4))
 return {"status":"HOLD_OFFICIAL_REDIRECT_LOOP"}
def sample_original(source,api,quality,control,match,load_json,call):
 f=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 if not f or not inp:return {"status":"HOLD_NO_BRONZE_OR_CHECKPOINT"}
 ck=load_json(api,f["id"])["done"]
 rows={x["source_id"]:x for x in load_json(api,inp["id"])["rows"]}
 # Only read ONE exact Bronze original to sample publisher-document comparison.
 for sid in list(ck)[:12]:
  row=rows.get(sid)
  if not row:continue
  try:
   raw=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   if digest(raw)!=row["sha"]:return {"status":"HOLD_BRONZE_HASH_CHANGED","source_id":sid}
   return {"status":"BRONZE_ORIGINAL_SHA_RECHECK_PASS",
    "source_id":sid,"original_sha256":row["sha"],
    "previous_status":ck[sid].get("status"),"source_path":row.get("source_path"),
    "third_party_numerical_evidence":False}
  except Exception as e:
   return {"status":"RETRY_BRONZE_READ_"+type(e).__name__,"source_id":sid}
 return {"status":"HOLD_NO_SAMPLE_ELIGIBLE"}
def run(source):
 if source not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 session=requests.Session()
 doc=live_page(source,PAGES[source],session)
 original=sample_original(source,api,quality,control,match,load_json,call)
 special={}
 if source in ("TWSE","TPEx"):
  # Live real daily-close 3-way sample, not complete file verification.
  try:
   from scripts.v097_live_threeway_close_witness import run as compare_close
   compare_close(source)
   special={"status":"DAILY_CLOSE_THREE_WAY_WITNESS_EXECUTED",
     "report":"v097_INDEPENDENT_CLOSE_WITNESS_"+source+"_"+os.getenv("GITHUB_RUN_ID","manual")+".json",
     "all_rows_verified":False}
  except Exception as exc:
   special={"status":"RETRY_THREE_WAY_WITNESS_"+type(exc).__name__,
     "all_rows_verified":False}
 elif source=="TDCC":
  # Portal control query uses explicit selected date + identity to avoid
  # mistaking a generic landing page for historical numerical evidence.
  try:
   from scripts.v097_tdcc_official_same_day_compare import run as compare_tdcc
   compare_tdcc()
   special={"status":"TDCC_SAME_DATE_CONTROL_QUERIES_EXECUTED",
     "report":"v097_TDCC_SAME_DATE_COMPARE_"+os.getenv("GITHUB_RUN_ID","manual")+".json",
     "all_rows_verified":False}
  except Exception as exc:
   special={"status":"RETRY_TDCC_LIVE_COMPARE_"+type(exc).__name__,
     "all_rows_verified":False}
 report={"schema":"v097_seven_live_independent_publisher_bridge_v1","source":source,
  "run":os.getenv("GITHUB_RUN_ID","manual"),
  "created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
  "publisher_document":doc,"original_sample":original,"source_specific":special,
  "official_numeric_rows_compared_in_this_bridge":0,
  "official_numeric_source_not_inferred_from_document":True,
  "all_rows_verified":False,"silver_ready_promoted":False,
  "silver_gold_executed":False,
  "official_documentation_references":OFFICIAL_VERSIONS[source]["reference"]}
 out="v097_INDEPENDENT_PUBLISHER_BRIDGE_"+source+"_"+report["run"]+".json"
 if os.getenv("GITHUB_RUN_ID"):put_once(api,quality,out,report)
 print("INDEPENDENT_SOURCE_BRIDGE="+json.dumps({"source":source,
    "document":doc["status"],"bronze":original["status"],
    "special":special.get("status","DOCUMENT_ONLY"),
    "silver_promoted":0,"report":out},ensure_ascii=False),flush=True)
def selftest():
 assert set(PAGES)==set(SOURCE_PUBLISHERS)==set(SOURCES)
 for src,url in PAGES.items():
  assert allow(src,url) and not allow(src,"http://example.com/steal")
  assert not allow(src,"https://example.org/data")
 assert not allow("TWSE","https://www.twse.com.tw.evil.example/abc")
 print("SEVEN_LIVE_INDEPENDENT_PUBLISHER_BRIDGE_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
