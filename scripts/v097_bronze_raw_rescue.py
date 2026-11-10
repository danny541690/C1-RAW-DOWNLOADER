#!/usr/bin/env python3
"""Incremental v0.93 RAW *missing-R2-receipt* rescue; no Silver/Gold.
Do NOT relabel historical QUARANTINED as clean without original-source evidence.
One immutable lane receipt + one lane checkpoint per batch.
"""
import os,re,csv,io,json,hashlib
from collections import Counter
from scripts.v097_bronze_first_pipeline import service,call,common,match,load_json,put_once,upsert,raw_integrity,digest,now
from scripts.v097_bronze_first_batch_v3 import verify_identity,receipt_name
CAP=max(1,min(100,int(os.getenv("BF_RESCUE_BATCH","30"))))
RUN=os.getenv("GITHUB_RUN_ID","manual")
VERSION="v097_BF_RAW_RESCUE_V1"
def ck_name(lane):return "%s_CK_%02d.json"%(VERSION,lane)
def safe_native(data,name):
 lower=name.lower()
 integrity=raw_integrity(data,name)
 if integrity!="RAW_STRUCTURE_PASS":return integrity
 if lower.endswith((".receipt.json",".manifest.json",".checkpoint.json")):
  return "CONTROL_FILE_NEVER_MARKET_RAW"
 if lower.endswith((".zip",".xlsx",".json",".pdf")):return "RAW_BASIC_NATIVE_PASS"
 if lower.endswith((".csv",".txt",".tsv")):
  try:
   s=data.decode("utf-8-sig")
   if "\x00" in s:return "RAW_TEXT_BINARY_NUL"
   lines=s.splitlines()
   if not any(z.strip() for z in lines):return "RAW_EMPTY_TEXT"
   csv.reader(io.StringIO(s)).__next__()
  except Exception:return "RAW_TEXT_READER_FAILED"
  return "RAW_BASIC_NATIVE_PASS"
 if lower.endswith((".html",".htm")):
  try:s=data[:250000].decode("utf-8-sig",errors="replace").lower()
  except Exception:return "RAW_HTML_DECODE_FAILED"
  if any(x in s for x in ["access denied","403 forbidden","429 too many requests","502 bad gateway","service unavailable","error occurred"]):
   return "RAW_UPSTREAM_HTML_ERROR"
  if "<table" not in s and "<tbody" not in s:return "RAW_HTML_NOT_IDENTIFIED_DATA"
  return "RAW_BASIC_NATIVE_PASS"
 return "RAW_FORMAT_REQUIRES_SPECIAL_PARSER"
def rescue_one(api,r):
 result={"file_id":r["file_id"],"source":r.get("source"),"path":r.get("path"),
 "run":RUN,"time":now(),"verification_scope":"BASIC_NATIVE_ONLY_NOT_FINANCIAL_SEMANTICS"}
 try:
  verify_identity(r)
  fid=r["file_id"]
  meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,modifiedTime,mimeType"))
  if meta.get("name")!=r.get("file_name"):raise RuntimeError("ORIGINAL_NAME_CHANGED")
  size=int(meta.get("size") or 0)
  if size<1 or size>40*1024*1024:raise RuntimeError("SOURCE_SIZE_UNSUPPORTED")
  if r.get("size_bytes") and size!=int(r["size_bytes"]):raise RuntimeError("ORIGINAL_SIZE_CHANGED")
  data=call(lambda:api.files().get_media(fileId=fid))
  if len(data)!=size:raise RuntimeError("DOWNLOADED_BYTE_SIZE_MISMATCH")
  if meta.get("md5Checksum") and hashlib.md5(data).hexdigest()!=meta["md5Checksum"]:
   raise RuntimeError("ORIGINAL_MD5_MISMATCH")
  state=safe_native(data,meta["name"])
  if state!="RAW_BASIC_NATIVE_PASS":raise RuntimeError(state)
  result.update(state="RAW_RESCUED_BASIC_CANDIDATE",sha256=digest(data),bytes=len(data),
    source_md5=meta.get("md5Checksum"),source_modified=meta.get("modifiedTime"))
 except Exception as ex:
  result.update(state="RAW_RESCUE_BLOCKED",reason=type(ex).__name__+":"+str(ex)[:150])
 return result
def lane_run(api,lane):
 m,c,q,_=common(api)
 f=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%lane)
 if not f:raise RuntimeError("FROZEN_RAW_AUDIT_MISSING")
 snapshot=load_json(api,f["id"])
 ckf=match(api,c,ck_name(lane))
 ck=load_json(api,ckf["id"]) if ckf else {"schema":"v097_bf_raw_rescue_ck_1","lane":lane,"done":{}}
 if ck.get("lane")!=lane:raise RuntimeError("RESCUE_WRONG_CHECKPOINT_LANE")
 done=ck["done"]
 pending=[x for x in snapshot["items"] if x["raw_status"]=="RAW_UNKNOWN_NO_R2_RECEIPT" and x["file_id"] not in done]
 rows=pending[:CAP]
 if not rows:
  print("RAW_RESCUE_IDLE",lane,len(done));return
 ids=[r["file_id"] for r in rows]
 name=receipt_name("RAW_RESCUE",lane,ids)
 file=match(api,q,name)
 if file:
  saved=load_json(api,file["id"])["items"]
  if [x["file_id"] for x in saved]!=ids:raise RuntimeError("RESCUE_RECEIPT_ID_MISMATCH")
 else:
  saved=[rescue_one(api,row) for row in rows]
  put_once(api,q,name,{"schema":"v097_raw_rescue_receipt_1","run":RUN,"lane":lane,
       "at":now(),"items":saved})
 for row in saved:
  done[row["file_id"]]={"state":row["state"],"sha256":row.get("sha256"),
       "bytes":row.get("bytes"),"reason":row.get("reason"),"source_modified":row.get("source_modified"),
       "path":row["path"]}
 upsert(api,c,ck_name(lane),{"schema":"v097_bf_raw_rescue_ck_1","lane":lane,
   "last_run":RUN,"last_receipt":name,"at":now(),"done":done})
 print("RAW_RESCUE_DONE",lane,"processed",len(rows),"total",len(done),flush=True)
def tests():
 assert safe_native(b"","x.csv")!="RAW_BASIC_NATIVE_PASS"
 assert safe_native(b'{"a":1}',"x.json")=="RAW_BASIC_NATIVE_PASS"
 assert safe_native(b"<html>403 forbidden</html>","x.html")!="RAW_BASIC_NATIVE_PASS"
 assert safe_native(b"one,two\n1,2\n","x.csv")=="RAW_BASIC_NATIVE_PASS"
 assert safe_native(b"{}", "x.receipt.json")!="RAW_BASIC_NATIVE_PASS"
 print("RAW_RESCUE_SELFTEST_PASS")
if __name__=="__main__":
 tests()
 if os.getenv("BF_MODE")=="rescue":
  lane_run(service(),int(os.environ["BF_LANE"]))
