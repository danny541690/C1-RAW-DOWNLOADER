#!/usr/bin/env python3
"""Admit only 2026 TDCC 800 restored originals with external same-date,
same-code, same-holder and same-share proof into isolated SPECIAL RAW.
Never mix Y securities into ordinary listed/OTC stock Bronze.
"""
import os,json
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,makefolder
from scripts.v097_tdcc_special_raw_3way_admit import archive_root,sha_lane,one
RUN=os.getenv("GITHUB_RUN_ID","manual")
LANE=int(os.getenv("TDCC_RECOVER_LANE","0"));BATCH=int(os.getenv("TDCC_RECOVER_BATCH","25"))
NAME="v097_TDCC_800_EXTERNAL_MATCH_SPECIAL_RAW"
def selection(api,c,q,lane):
 f=match(api,q,"v097_TDCC_5035_THIRDPARTY_ALL_43428270828.json")
 if not f:raise RuntimeError("FROZEN_CENSUS_MISSING")
 origin={r["file_id"]:r for r in load_json(api,f["id"])["records"] if r["result"]=="A4_NUMERIC_RECEIPT_NOT_FOUND"}
 proven={}
 for src_lane in range(6):
  f=match(api,c,"v097_TDCC_800_REVERIFY_V1_CK_%02d.json"%src_lane)
  if not f:continue
  for fid,entry in load_json(api,f["id"])["done"].items():
   if entry.get("state")!="INTERNAL_AND_THIRDPARTY_TOTALS_EXACT_NONSTOCK":continue
   if fid not in origin:raise RuntimeError("RECOVERY_OUTSIDE_800")
   if origin[fid]["day"]<"20260101":raise RuntimeError("UNEXPECTED_2025_THIRD_PARTY_PROOF")
   record=dict(origin[fid],source_sha256=entry["sha"],
      holders=entry["holders"],shares=entry["shares"])
   if fid in proven:raise RuntimeError("DUPLICATE_RECOVERY_ID")
   proven[fid]=record
 return [proven[fid] for fid in sorted(proven) if sha_lane(fid)==lane]
def root(api,bronze):
 p=archive_root(api,bronze)
 return makefolder(api,p,"02_RECOVERED_800_EXTERNAL_MATCH")
def bootstrap(api):
 _,_,_,b=common(api);folder=root(api,b)
 for i in range(6):makefolder(api,folder,"SPECIAL_LANE_%02d"%i)
 print("RECOVER_800_SPECIAL_BOOTSTRAPPED",flush=True)
def execute(api,lane):
 m,c,q,b=common(api)
 elig=selection(api,c,q,lane)
 folder=root(api,b);dest=match(api,folder,"SPECIAL_LANE_%02d"%lane)
 if not dest:raise RuntimeError("BOOTSTRAP_NOT_DONE")
 key=NAME+"_CK_%02d.json"%lane
 f=match(api,c,key)
 ck=load_json(api,f["id"]) if f else {"schema":"v097_800_special_ck_1","lane":lane,"done":{}}
 if ck.get("schema")!="v097_800_special_ck_1" or ck.get("lane")!=lane:raise RuntimeError("INVALID_CHECKPOINT")
 if not set(ck["done"]).issubset({r["file_id"] for r in elig}):raise RuntimeError("ORPHAN_CHECKPOINT")
 todo=[r for r in elig if r["file_id"] not in ck["done"]][:BATCH]
 stage={}
 for old_lane in range(6):
  f=match(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%old_lane)
  if not f:raise RuntimeError("STAGED_CK_MISSING")
  stage.update(load_json(api,f["id"])["done"])
 receipt=NAME+"_"+RUN+"_L%02d_O%04d.json"%(lane,len(ck["done"]))
 prev=match(api,q,receipt)
 if prev:results=load_json(api,prev["id"])["items"]
 else:
  results=[one(api,r,dest["id"],stage.get(r["file_id"],{})) for r in todo]
  put_once(api,q,receipt,{"schema":"v097_tdcc_800_special_receipt_1","run":RUN,"lane":lane,
    "items":results,"ordinary_stock_bronze_promoted":0})
 for r in results:ck["done"][r["file_id"]]={"state":r["state"],
    "dest_id":r.get("dest_id"),"error":r.get("error")}
 upsert(api,c,key,dict(ck,last_receipt=receipt,updated_at=datetime.now(timezone.utc).isoformat()))
 counts=Counter(x["state"] for x in ck["done"].values())
 print("TDCC_RECOVERED_SPECIAL="+json.dumps({"lane":lane,"eligible":len(elig),
   "checked":len(ck["done"]),"remaining":len(elig)-len(ck["done"]),
   "states":dict(counts)},ensure_ascii=False),flush=True)
def summary(api):
 m,c,q,b=common(api);n=0;eligible=0;state=Counter()
 for lane in range(6):
  eligible+=len(selection(api,c,q,lane))
  f=match(api,c,NAME+"_CK_%02d.json"%lane)
  done=load_json(api,f["id"])["done"] if f else {}
  n+=len(done);state.update(x["state"] for x in done.values())
 report={"schema":"v097_800_special_admission_summary_1","run":RUN,
  "eligible":eligible,"checked":n,"remaining":eligible-n,
  "states":dict(state),"special_raw_admitted":state["NONSTOCK_RAW_SHA_AND_3WAY_HOLDINGS_QA_PASS"],
  "ordinary_stock_bronze":0}
 put_once(api,q,NAME+"_SUMMARY_"+RUN+".json",report)
 print("TDCC_RECOVERED_SPECIAL_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":
 mode=os.getenv("TDCC_RECOVER_MODE","selftest")
 if mode=="selftest":
  assert sha_lane("ABC") in range(6)
  print("TDCC_RECOVERY_SELFTEST_OK",flush=True)
 else:
  api=service()
  if mode=="bootstrap":bootstrap(api)
  elif mode=="lane":execute(api,LANE)
  elif mode=="summary":summary(api)
  else:raise SystemExit("UNKNOWN_MODE")
