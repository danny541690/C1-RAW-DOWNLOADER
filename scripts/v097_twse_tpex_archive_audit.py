#!/usr/bin/env python3
"""Bounded, checkpointed TWSE/TPEx historical ZIP member evidence classification.
Never promotes Silver Ready and never rewrites Bronze files.
"""
import os,re,json,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import source_api,adapter_version
VERSION="twse-tpex-archive-audit-v1"
LIMIT=max(1,min(600,int(os.getenv("AUDIT_BATCH","350"))))
SOURCES=("TWSE","TPEx")
SCHEMAS={"TWSE":"twse_mixed_index_and_stock_quotes","TPEx":"tpex_quotes_and_optional_sections"}
OFFICIAL={"TWSE":"https://openapi.twse.com.tw/","TPEx":"https://www.tpex.org.tw/openapi/"}
THIRD_PARTY="https://github.com/FinMind/FinMind-MCP/blob/master/knowledge/datasets.md"

def classify(source,row,ck,detail):
 if ck.get("adapter_version")!=adapter_version(source):return ("HOLD_STALE_ADAPTER",0,{})
 if not detail or detail.get("source_id")!=row["source_id"] or detail.get("destination_id")!=row["dest_id"]:
  return ("HOLD_RECEIPT_ID_MISMATCH",0,{})
 if (detail.get("source_sha256")!=row["sha"] or detail.get("dest_sha256")!=row["sha"]
     or detail.get("source_path")!=row["source_path"]):
  return ("HOLD_ORIGINAL_BYTE_OR_PATH_PROOF",0,{})
 if detail.get("status")!="ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":
  return ("HOLD_NOT_ZIP_MEMBER_MANIFEST",0,{})
 members=detail.get("members",[])
 if not isinstance(members,list) or not members:return ("HOLD_MISSING_MEMBER_MANIFEST",0,{})
 period=str(row["year"])+"-"+str(row["month"])
 states=Counter();candidate=0
 for m in members:
  name=m.get("member","")
  if not isinstance(name,str) or not name or name.startswith("/") or ".." in name.replace("\\","/").split("/"):
   states["HOLD_UNSAFE_MEMBER_PATH"]+=1;continue
  if not re.fullmatch(r"[0-9a-f]{64}",str(m.get("sha256",""))):
   states["HOLD_MEMBER_SHA_MISSING"]+=1;continue
  if m.get("status")!="CONTENT_PARSED_ORIGIN_PIT_HOLD":
   states["HOLD_MEMBER_"+str(m.get("status","UNKNOWN"))[:60]]+=1;continue
  dates=m.get("dates",[])
  if not dates or not all(isinstance(d,str) and re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}",d) and d[:7]==period for d in dates):
   states["HOLD_MEMBER_DATE_OR_PERIOD"]+=1;continue
  if m.get("dataset")!=SCHEMAS[source]:
   states["HOLD_MEMBER_DATASET_IDENTITY"]+=1;continue
  states["PARSER_SCHEMA_CANDIDATE_SOURCE_PROOF_PENDING"]+=1;candidate+=1
 return ("HOLD_OFFICIAL_ARCHIVE_PROVENANCE_NOT_VERIFIED",candidate,dict(states))

def run(source):
 if source not in SOURCES:raise RuntimeError("source TWSE or TPEx required")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 fi=match(api,quality,"v097_AP_INPUT_"+source+".json")
 fc=match(api,control,"v097_AP_CHECKPOINT_"+source+".json")
 if not fi or not fc:raise RuntimeError("SOURCE_CHECKPOINT_MISSING")
 original=load_json(api,fc["id"])["done"]
 rows=[r for r in load_json(api,fi["id"])["rows"]
       if original.get(r["source_id"],{}).get("status")=="ZIP_MEMBERS_AUDITED_ORIGIN_HOLD"]
 name="v097_ARCHIVE_MEMBER_EVIDENCE_CK_"+source+".json"
 old=match(api,control,name)
 ck=load_json(api,old["id"]) if old else {"schema":"v097_archive_member_evidence_1","source":source,"version":VERSION,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("AUDIT_VERSION_MISMATCH")
 ids={r["source_id"] for r in rows}
 if set(ck["done"])-ids:raise RuntimeError("AUDIT_ORPHAN_ID")
 batch=[r for r in rows if r["source_id"] not in ck["done"]][:LIMIT]
 receipts={};new={}
 for row in batch:
  sid=row["source_id"];original_ck=original[sid];rn=original_ck.get("receipt")
  if rn and rn not in receipts:
   rf=match(api,quality,rn)
   if not rf:raise RuntimeError("MISSING_IMMUTABLE_RECEIPT_"+rn)
   body=load_json(api,rf["id"])
   if body.get("source")!=source or body.get("adapter_version")!=adapter_version(source):
    raise RuntimeError("SOURCE_VERSION_RECEIPT_CONFLICT")
   records=body["rows"]
   if len(records)!=len({r["source_id"] for r in records}):
    raise RuntimeError("DUPLICATE_RECEIPT_RECORD")
   receipts[rn]={x["source_id"]:x for x in records}
  status,candidates,member_states=classify(source,row,original_ck,receipts.get(rn,{}).get(sid))
  new[sid]={"status":status,"schema_member_candidates":candidates,
            "member_states":member_states,"original_receipt":rn,
            "source_sha256":row["sha"],"source_path":row["source_path"],
            "official_schema_reference":OFFICIAL[source],"third_party_schema_reference":THIRD_PARTY,
            "silver_ready_promoted":False}
 ck["done"].update(new)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["last_success_at"]=datetime.now(timezone.utc).isoformat()
 if new:upsert(api,control,name,ck)
 total=len(rows);remaining=total-len(ck["done"])
 progress={"source":source,"total":total,"checked":len(ck["done"]),
           "batch":len(new),"remaining":remaining,"by_status":dict(Counter(r["status"] for r in new.values()))}
 print("ARCHIVE_MEMBER_AUDIT_PROGRESS="+json.dumps(progress,ensure_ascii=False),flush=True)
 if os.getenv("GITHUB_OUTPUT"):
  with open(os.environ["GITHUB_OUTPUT"],"a") as o:
   o.write("remaining="+str(remaining)+chr(10))
   o.write("progress="+("true" if new else "false")+chr(10))

def selftest():
 row={"source_id":"x","dest_id":"y","sha":"a"*64,"source_path":"2024/TWSE/2024-10/test.zip","year":"2024","month":"10"}
 ck={"adapter_version":adapter_version("TWSE")}
 m={"member":"x.json","sha256":"b"*64,"status":"CONTENT_PARSED_ORIGIN_PIT_HOLD","dates":["2024-10-25"],"dataset":SCHEMAS["TWSE"]}
 detail={"source_id":"x","destination_id":"y","source_sha256":"a"*64,"dest_sha256":"a"*64,"source_path":row["source_path"],"status":"ZIP_MEMBERS_AUDITED_ORIGIN_HOLD","members":[m]}
 assert classify("TWSE",row,ck,detail)[1]==1
 assert classify("TWSE",row,ck,{**detail,"dest_sha256":"c"*64})[0]=="HOLD_ORIGINAL_BYTE_OR_PATH_PROOF"
 assert classify("TWSE",row,ck,{**detail,"members":[{**m,"dates":["2023-10-25"]}]})[1]==0
 print("TWSE_TPEX_ARCHIVE_AUDIT_SELFTEST_PASS")

if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | TWSE | TPEx")
