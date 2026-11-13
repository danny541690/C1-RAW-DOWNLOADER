#!/usr/bin/env python3
"""Target just two 2025 TDCC official historic transient query failures.
Do not mark official absence as original corruption; retry with fresh sessions
and immutable source A4 date/code/holder/shares from frozen 5035 ledger.
"""
import os,json,time,requests
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert
from scripts.v097_tdcc_official_same_day_compare import query
RUN=os.getenv("GITHUB_RUN_ID","manual")
def main():
 api=service();_,c,q,_=common(api)
 f=match(api,q,"v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json")
 if not f:raise RuntimeError("CENSUS_NOT_FOUND")
 origin={r["file_id"]:r for r in load_json(api,f["id"])["records"]}
 misses={}
 for lane in range(6):
  f=match(api,c,"v097_TDCC_2025_OFFICIAL_HISTORY_PROOFS_CK_%02d.json"%lane)
  if not f:raise RuntimeError("CK_NOT_FOUND")
  for fid,r in load_json(api,f["id"])["done"].items():
   if r.get("state") in ("OFFICIAL_QUERY_ERROR","OFFICIAL_RESPONSE_NOT_READABLE"):
    if fid in misses:raise RuntimeError("DUPLICATE")
    misses[fid]=origin[fid]
 if len(misses)!=2:raise RuntimeError("EXPECTED_2_OFFICIAL_TRANSIENTS_FOUND_"+str(len(misses)))
 result=[]
 for fid,r in misses.items():
  record={"file_id":fid,"code":r["code"],"day":r["day"],"source_sha256":r["source_sha256"],
     "original_holders":r["holders"],"original_shares":r["shares"]}
  states=[]
  for attempt in range(3):
   try:
    x=query(requests.Session(),{"date":r["day"],"code":r["code"],
      "old_holders":r["holders"],"old_shares":r["shares"],"orig_sha":r["source_sha256"]})
    states.append(x["state"])
    if x["state"]=="EXACT_SAME_DATE_CONTENT_MATCH":
     record.update(state="EXACT_SAME_DATE_CONTENT_MATCH",official_response_sha256=x.get("response_sha256"))
     break
    if x["state"] in ("OFFICIAL_RESPONSE_CODE_DATE_NOT_PROVED","DATE_NOT_CURRENTLY_IN_OFFICIAL_QUERY_DROPDOWN"):
     break
   except Exception as e:states.append(type(e).__name__)
   if attempt<2:time.sleep(2*(attempt+1))
  record.setdefault("state","OFFICIAL_EXACT_MATCH_NOT_PROVED")
  record["attempt_states"]=states
  result.append(record)
 report={"schema":"v097_tdcc_two_official_retry_1","run":RUN,
  "at":datetime.now(timezone.utc).isoformat(),"count":len(result),
  "official_proved":sum(x["state"]=="EXACT_SAME_DATE_CONTENT_MATCH" for x in result),
  "items":result,"raw_market_bronze":0}
 put_once(api,q,"v097_TDCC_TWO_OFFICIAL_RETRY_"+RUN+".json",report)
 print("TDCC_TWO_OFFICIAL_RETRY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
