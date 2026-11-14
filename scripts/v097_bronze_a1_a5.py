#!/usr/bin/env python3
"""JARVIS v0.97 Bronze-only A1-A5 evidence reconciliation; never runs Silver/Gold.
No unsupported assertion that hash/path verification is semantic certification.
"""
import json,os
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import common,match,load_json,upsert,save
from scripts.v097_bronze_content_qa import service
RUN=os.environ.get("GITHUB_RUN_ID","manual")
PREFIX="v097_BRONZE_A1A5_V1"
EXPECTED=82273
def now():return datetime.now(timezone.utc).isoformat()
def opt(api,p,name):
 f=match(api,p,name)
 return load_json(api,f["id"]) if f else {}
def done(doc):return doc.get("done",{})
def examine(row,copy,qa,combined):
 fid=row["file_id"];c=copy.get(fid,{});q=qa.get(fid,{});e=combined.get(fid,{})
 cs=c.get("state","");qs=q.get("state","");es=e.get("state","");raw=row.get("raw_status","")
 basic=cs=="COPY_MATCHED_PENDING_INDEPENDENT_QA" and qs=="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"
 if es=="BRONZE_ORIGINAL_RAW_QA_PASS_RELEASE_PENDING":
  state,reason="HOLD_SEMANTIC_DATE","SOURCE_PUBLICATION_AND_DATASET_COVERAGE_UNCERTIFIED";basic=True
 elif basic:state,reason="HOLD_CONTENT_QA","ONLY_BYTES_SHA_PATH_VERIFIED"
 elif cs=="COPY_QUARANTINED_NONMARKET" or qs=="BRONZE_REVOKED_NONMARKET":
  state,reason="EXCLUDED","NON_MARKET_CONTROL_SIDECAR"
 elif cs=="COPY_EXCEPTION" or qs=="BRONZE_QA_EXCEPTION":
  state,reason="EXCEPTION",c.get("error") or q.get("error") or "COPY_OR_QA_FAILED"
 elif raw in ("A_PASS_CANDIDATE_R2_BYTES","A_PASS_CANDIDATE_RESCUE_BYTES"):
  state,reason="HOLD_MIGRATION","COPY_OR_INDEPENDENT_QA_NOT_PROVEN"
 elif "CONTROL" in raw or "NONMARKET" in raw:
  state,reason="REVIEW_EXCLUSION","CONTROL_IDENTITY_NOT_CONFIRMED"
 else:state,reason="EXCEPTION",raw or "UNKNOWN_LEGACY_STATUS"
 return {"id":fid,"source":row.get("source",""),"state":state,"reason":reason,
  "raw_status":raw,"copy_state":cs,"qa_state":qs,"combined_state":es,
  "basic_verified":basic,"silver_ready":False}
def lane(api,i):
 m,c,q,_=common(api)
 copy=done(opt(api,c,"v097_BF_V3_COPY_CK_%02d.json"%i))
 qa=done(opt(api,c,"v097_BF_V3_QA_CK_%02d.json"%i))
 combined=done(opt(api,c,"v097_LEGACY_COMBINED_BRONZE_RAW_V1_CK_%02d.json"%i))
 rows=[]
 for j in (i,i+6):
  manifest=opt(api,m,"v097_BF_AUDIT_LANE_%02d.json"%j)
  if "items" not in manifest:raise RuntimeError("MISSING_AUDIT_LANE_"+str(j))
  rows+=manifest["items"]
 if len({r["file_id"] for r in rows})!=len(rows):raise RuntimeError("DUPLICATE_ID_IN_LANE")
 results=[examine(r,copy,qa,combined) for r in rows]
 by_source={}
 for r in results:by_source.setdefault(r["source"],Counter())[r["state"]]+=1
 counts=dict(Counter(r["state"] for r in results))
 payload={"schema":"v097_bronze_a1a5_lane_v1","run":RUN,"at":now(),
  "lane":i,"total":len(rows),"counts":counts,
  "by_source":{k:dict(v) for k,v in by_source.items()},"rows":results,
  "notice":"No Bronze semantic/PIT market release certified; no Silver/Gold executed."}
 save(api,q,PREFIX+"_RUN_%s_L%02d.json"%(RUN,i),payload)
 upsert(api,c,PREFIX+"_LATEST_L%02d.json"%i,{k:v for k,v in payload.items() if k!="rows"})
 print("BRONZE_A1A5_LANE="+json.dumps({"lane":i,"total":len(rows),"counts":counts}),flush=True)
def aggregate(api):
 _,c,q,_=common(api)
 counts=Counter();by_source={};total=0;lane_runs={}
 for i in range(6):
  f=opt(api,c,PREFIX+"_LATEST_L%02d.json"%i)
  if not f:raise RuntimeError("MISSING_LANE_"+str(i))
  lane_runs[str(i)]=f.get("run")
  total+=f["total"];counts.update(f["counts"])
  for src,vals in f["by_source"].items():by_source.setdefault(src,Counter()).update(vals)
 if total!=EXPECTED:raise RuntimeError("EXPECTED_82273_GOT_"+str(total))
 report={"schema":"v097_bronze_a1a5_summary_v1","run":RUN,"at":now(),
  "inventory":total,"counts":dict(counts),"lane_runs":lane_runs,
  "by_source":{k:dict(v) for k,v in by_source.items()},
  "ready_for_silver":0,"bronze_all_ready":False,
  "a1":"FROZEN_INVENTORY_RECONCILED",
  "a2":"EXISTING_QA_RECEIPTS_CLASSIFIED_NOT_SEMANTICALLY_COMPLETE",
  "a3":"EXCEPTIONS_CLASSIFIED_REPAIR_NOT_PROVEN",
  "a4":"PUBLICATION_CALENDAR_AND_COVERAGE_NOT_CERTIFIED",
  "a5":"BLOCKED_UNTIL_A2_A3_A4_COMPLETED",
  "silver_conversion_executed":False,"gold_executed":False}
 save(api,q,PREFIX+"_SUMMARY_RUN_%s.json"%RUN,report)
 upsert(api,c,PREFIX+"_SUMMARY_LATEST.json",report)
 print("BRONZE_A1A5_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
def selftest():
 r={"file_id":"a","source":"TPEx","raw_status":"A_PASS_CANDIDATE_R2_BYTES"}
 c={"a":{"state":"COPY_MATCHED_PENDING_INDEPENDENT_QA"}}
 q={"a":{"state":"BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"}}
 assert examine(r,c,q,{})["state"]=="HOLD_CONTENT_QA"
 assert examine(r,c,q,{"a":{"state":"BRONZE_ORIGINAL_RAW_QA_PASS_RELEASE_PENDING"}})["state"]=="HOLD_SEMANTIC_DATE"
 print("BRONZE_A1A5_SELFTEST_PASS")
if __name__=="__main__":
 mode=os.getenv("A1A5_MODE","selftest")
 if mode=="selftest":selftest()
 else:
  api=service()
  if mode=="lane":lane(api,int(os.environ["A1A5_LANE"]))
  elif mode=="aggregate":aggregate(api)
  else:raise RuntimeError("UNKNOWN_MODE")
