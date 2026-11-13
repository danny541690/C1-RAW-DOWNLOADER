#!/usr/bin/env python3
"""Rebuild 800 missing TDCC A4 numeric receipt proofs from original bytes.
Use frozen 5035 mirror census and immutable V4 quarantine for exact source IDs.
For 2026 dates additionally independently compare level-17 TDCC mirror CSV;
for absent 2025 archive do not invent a pass. No ordinary-stock Bronze.
"""
import os,re,json,hashlib,requests,csv,io
from datetime import datetime,timezone
from collections import Counter,defaultdict
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call
from scripts.v097_tdcc_a3_a5_auto import FILE,html_identity,table_diagnostics
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("TDCC_800_LANE","0"))
CAP=max(1,min(70,int(os.getenv("TDCC_800_BATCH","25"))))
NAME="v097_TDCC_800_REVERIFY_V1"
INPUT="v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json"
def sha(b):return hashlib.sha256(b).hexdigest()
def lane_of(fid):return int(sha(fid.encode())[:8],16)%6
def now():return datetime.now(timezone.utc).isoformat()
def archive(date,cache):
 if date in cache:return cache[date]
 url="https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots/"+date[:4]+"/"+date[:4]+"-"+date[4:6]+"-"+date[6:]+".csv"
 try:
  r=requests.get(url,timeout=(8,40),headers={"User-Agent":"JARVIS-v097-Independent-Receipt-Verification"})
  if r.status_code==404:cache[date]=("NO_THIRDPARTY_DATE",{},None);return cache[date]
  r.raise_for_status()
  if len(r.content)>14_000_000:raise ValueError("THIRDPARTY_DATA_TOO_LARGE")
  table={}
  for x in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig"))):
   if x.get("資料日期")==date and x.get("持股分級")=="17":
    k=(date,str(x.get("證券代號") or "").strip().upper())
    if k in table:raise ValueError("THIRDPARTY_DUPLICATE_CODE")
    table[k]=(int(x["人數"]),int(x["股數"]))
  cache[date]=("ARCHIVE_AVAILABLE",table,sha(r.content))
 except Exception as e:cache[date]=("THIRDPARTY_ERROR:"+type(e).__name__,{},None)
 return cache[date]
def original_rows(api,q):
 f=match(api,q,INPUT)
 if not f:raise RuntimeError("RECONCILED_5035_CENSUS_MISSING")
 all=load_json(api,f["id"])
 if all.get("population")!=5035:raise RuntimeError("POPULATION_NOT_5035")
 selected=[r for r in all["records"] if r["result"]=="A4_NUMERIC_RECEIPT_NOT_FOUND"]
 if len(selected)!=800:raise RuntimeError("MISSING_COUNT_NOT_800")
 return [r for r in selected if lane_of(r["file_id"])==LANE]
def repair(api,item,stage,cache):
 fid=item["file_id"];r={"file_id":fid,"code":item["code"],"date":item["day"],
  "ordinary_stock_bronze_promoted":False}
 try:
  if stage.get("status")!="V097_V4_QUARANTINE_SHA_PASS":raise ValueError("QUARANTINE_SOURCE_NOT_VERIFIED")
  raw=call(lambda:api.files().get_media(fileId=fid))
  remote=call(lambda:api.files().get_media(fileId=stage["dest_id"]))
  src_sha=sha(raw)
  if not raw or src_sha!=stage.get("source_sha256") or sha(remote)!=src_sha:raise ValueError("THREE_WAY_SHA_BAD")
  code,dates,has_table=html_identity(raw)
  ob=table_diagnostics(raw)
  if code!=item["code"] or item["day"] not in dates or ob.get("status")!="HTML_DISTRIBUTION_TOTALS_MATCH":
   raise ValueError("ORIGINAL_IDENTITY_DATE_HOLDER_NUMERIC_NOT_CERTIFIED")
  status,totals,witness_sha=archive(item["day"],cache)
  r.update(source_sha256=src_sha,holders=ob["total_holders"],shares=ob["total_shares"],
   mirror_sha256=witness_sha,mirror_state=status)
  if status=="ARCHIVE_AVAILABLE":
   if totals.get((item["day"],item["code"]))==(r["holders"],r["shares"]):
    r["state"]="INTERNAL_AND_THIRDPARTY_TOTALS_EXACT_NONSTOCK"
   else:r["state"]="THIRDPARTY_TOTALS_MISSING_OR_DIFFERENT_HOLD"
  elif status=="NO_THIRDPARTY_DATE":
   r["state"]="ORIGINAL_INTERNAL_QA_PASS_EXTERNAL_DATE_NOT_AVAILABLE"
  else:r["state"]="ORIGINAL_INTERNAL_QA_PASS_EXTERNAL_FETCH_HOLD"
 except Exception as e:r.update(state="ORIGINAL_NUMERIC_REVERIFY_HOLD",error=type(e).__name__+":"+str(e)[:180])
 return r
def run(api):
 m,c,q,_=common(api);rows=original_rows(api,q)
 key=NAME+"_CK_%02d.json"%LANE
 f=match(api,c,key)
 ck=load_json(api,f["id"]) if f else {"schema":"tdcc_800_qa_ck_1","lane":LANE,"done":{}}
 if ck.get("schema")!="tdcc_800_qa_ck_1" or ck.get("lane")!=LANE:raise RuntimeError("CHECKPOINT_SCHEMA")
 allowed={r["file_id"] for r in rows}
 if not set(ck["done"]).issubset(allowed):raise RuntimeError("CHECKPOINT_ORPHAN")
 todo=[r for r in rows if r["file_id"] not in ck["done"]][:CAP]
 stage={}
 for x in range(6):
  f=match(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%x)
  if not f:raise RuntimeError("V4_STAGE_MISSING")
  stage.update(load_json(api,f["id"])["done"])
 cache={}
 receipt=NAME+"_"+RUN+"_L%02d_O%04d.json"%(LANE,len(ck["done"]))
 f=match(api,q,receipt)
 if f:items=load_json(api,f["id"])["items"]
 else:
  items=[repair(api,r,stage.get(r["file_id"],{}),cache) for r in todo]
  put_once(api,q,receipt,{"schema":"v097_tdcc_800_qa_receipt_1","run":RUN,
   "lane":LANE,"items":items,"market_bronze_promoted":0})
 for x in items:ck["done"][x["file_id"]]={"state":x["state"],"sha":x.get("source_sha256"),
   "holders":x.get("holders"),"shares":x.get("shares"),"error":x.get("error")}
 upsert(api,c,key,dict(ck,updated_at=now(),last_receipt=receipt))
 counter=Counter(x["state"] for x in ck["done"].values())
 print("TDCC_800_LANE="+json.dumps({"lane":LANE,"eligible":len(rows),"verified":len(ck["done"]),
  "remaining":len(rows)-len(ck["done"]),"by_state":dict(counter)},ensure_ascii=False),flush=True)
def summary(api):
 m,c,q,_=common(api);counts=Counter();n=0;total=0
 for lane in range(6):
  global LANE
  LANE=lane
  r=original_rows(api,q);total+=len(r)
  f=match(api,c,NAME+"_CK_%02d.json"%lane)
  done=load_json(api,f["id"])["done"] if f else {}
  n+=len(done);counts.update(x["state"] for x in done.values())
 if total!=800:raise RuntimeError("800_LANE_COUNTS_FAIL")
 report={"schema":"v097_tdcc_800_reverify_summary_1","run":RUN,
  "population":800,"checked":n,"remaining":800-n,"states":dict(counts),
  "ordinary_stock_bronze":0}
 put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
 print("TDCC_800_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 mode=os.getenv("TDCC_800_MODE","selftest")
 if mode=="selftest":
  assert lane_of("ABC") in range(6)
  print("TDCC_800_SELFTEST_PASS")
 else:
  api=service()
  if mode=="lane":run(api)
  elif mode=="summary":summary(api)
  else:raise SystemExit("BAD_MODE")
