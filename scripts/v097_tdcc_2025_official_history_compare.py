#!/usr/bin/env python3
"""JARVIS v0.97: exact official history cross-reference for 1858 2025 TDCC
Y-code records missing independent 2025 mirror archive. Portal only allows
dates within its live retention. Use immutable A4 per-original totals and SHA;
official same-day query must return EXACT holder/share totals. Never fabricate
matches for expired dates or admit to listed/OTC ordinary-stock Bronze.
"""
import os,json,time,hashlib,requests
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call
from scripts.v097_tdcc_special_raw_3way_admit import sha_lane
from scripts.v097_tdcc_official_same_day_compare import query,URL,read_inputs
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("TDCC_2025_OFFICIAL_LANE","0"))
CAP=max(1,min(30,int(os.getenv("TDCC_2025_OFFICIAL_BATCH","12"))))
NAME="v097_TDCC_2025_OFFICIAL_HISTORY_PROOFS"
def now():return datetime.now(timezone.utc).isoformat()
def candidates(api,q,lane):
 f=match(api,q,"v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json")
 if not f:raise RuntimeError("FROZEN_5035_CENSUS_MISSING")
 rows=load_json(api,f["id"])["records"]
 arr=[r for r in rows if r["result"]=="THIRDPARTY_DATE_NOT_AVAILABLE" and
        r["day"][:4]=="2025" and sha_lane(r["file_id"])==lane]
 return sorted(arr,key=lambda x:(x["day"],x["code"]))
def main(api,lane):
 m,c,q,_=common(api);rows=candidates(api,q,lane)
 key=NAME+"_CK_%02d.json"%lane
 f=match(api,c,key)
 ck=load_json(api,f["id"]) if f else {"schema":"v097_2025_tdcc_official_ck_1","lane":lane,"done":{}}
 if ck["schema"]!="v097_2025_tdcc_official_ck_1" or ck["lane"]!=lane:raise RuntimeError("BAD_CHECKPOINT")
 if not set(ck["done"]).issubset({r["file_id"] for r in rows}):raise RuntimeError("CHECKPOINT_ORPHAN")
 sess=requests.Session()
 available=set();form_state="ERROR"
 try:
  entry=sess.get(URL,timeout=(8,20),headers={"User-Agent":"Mozilla/5.0"})
  entry.raise_for_status()
  _,available,_=read_inputs(entry.content)
  form_state="OFFICIAL_LIVE_DATES_READ"
 except Exception as e:form_state="OFFICIAL_LIVE_DATE_ERROR:"+type(e).__name__
 todo=[x for x in rows if x["file_id"] not in ck["done"]][:CAP]
 receipt=NAME+"_"+RUN+"_L%02d_O%04d.json"%(lane,len(ck["done"]))
 f=match(api,q,receipt)
 if f:outcomes=load_json(api,f["id"])["rows"]
 else:
  outcomes=[]
  for x in todo:
   r={"file_id":x["file_id"],"day":x["day"],"code":x["code"],
     "source_sha256":x["source_sha256"],"original_holders":x["holders"],
     "original_shares":x["shares"],"market_bronze":False}
   if x["day"] not in available:
    r["state"]="DATE_NOT_AVAILABLE_IN_OFFICIAL_HISTORY_WINDOW"
   else:
    probe=query(sess,{"date":x["day"],"code":x["code"],
     "old_holders":x["holders"],"old_shares":x["shares"],"orig_sha":x["source_sha256"]})
    r["state"]=probe["state"]
    r["official_response_sha256"]=probe.get("response_sha256")
    r["delta_holders"]=probe.get("holder_difference")
    r["delta_shares"]=probe.get("share_difference")
    r["query_http"]=probe.get("http")
   outcomes.append(r)
   if r["state"]=="EXACT_SAME_DATE_CONTENT_MATCH":time.sleep(0.2)
  put_once(api,q,receipt,{"schema":"v097_tdcc_official_2025_receipt_1","run":RUN,
   "lane":lane,"form_state":form_state,"rows":outcomes,"ordinary_stock_bronze":0})
 for x in outcomes:
  ck["done"][x["file_id"]]={"state":x["state"],
    "official_response_sha256":x.get("official_response_sha256")}
 upsert(api,c,key,dict(ck,updated_at=now(),last_receipt=receipt))
 st=Counter(r["state"] for r in ck["done"].values())
 print("TDCC_2025_OFFICIAL_LANE="+json.dumps({"lane":lane,"total":len(rows),
  "checked":len(ck["done"]),"remaining":len(rows)-len(ck["done"]),
  "states":dict(st)},ensure_ascii=False),flush=True)
def summary(api):
 m,c,q,_=common(api);n=total=0;states=Counter()
 for lane in range(6):
  total+=len(candidates(api,q,lane))
  f=match(api,c,NAME+"_CK_%02d.json"%lane)
  done=load_json(api,f["id"])["done"] if f else {}
  n+=len(done);states.update(x["state"] for x in done.values())
 if total!=1858:raise RuntimeError("2025_TARGET_NOT_1858")
 report={"schema":"v097_tdcc_2025_official_summary_1","run":RUN,"population":total,
  "checked":n,"remaining":total-n,"states":dict(states),
  "exact_official_matches":states["EXACT_SAME_DATE_CONTENT_MATCH"],
  "market_bronze_promoted":0}
 put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
 print("TDCC_2025_OFFICIAL_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 mode=os.getenv("TDCC_2025_OFFICIAL_MODE","selftest")
 if mode=="selftest":
  assert sha_lane("abc") in range(6)
  print("TDCC_2025_OFFICIAL_SELFTEST_OK")
 else:
  api=service()
  if mode=="lane":main(api,LANE)
  elif mode=="summary":summary(api)
  else:raise SystemExit("BAD_MODE")
