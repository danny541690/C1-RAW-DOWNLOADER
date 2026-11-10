#!/usr/bin/env python3
"""Bronze-first V3 batched receipts: minimize Drive writes while preserving idempotence.
Reuses existing immutable v0.93 R2 audit; only pre-approved raw source ID+SHA can migrate.
Monthly path and TDCC identity checks come from base partition and this copy gate.
"""
import os,json,io,hashlib,re,time
from collections import Counter
from datetime import datetime,timezone
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_first_pipeline import (
 service,call,common,match,load_json,save,upsert,put_once,digest,
 raw_integrity,partition,AUDIT_LANES,COPY_LANES,MAX_BYTES,now,bootstrap,audit_lane,selftest
)
RUN=os.getenv("GITHUB_RUN_ID","manual")
CAP=max(1,min(300,int(os.getenv("BRONZE_COPY_BATCH","120"))))
VERSION="v097_BF_V3"
def ck_name(stage,lane):
 return "%s_%s_CK_%02d.json"%(VERSION,stage,lane)
def receipt_name(stage,lane,ids):
 sig=hashlib.sha256(("\n".join(ids)).encode()).hexdigest()[:20]
 return "%s_%s_L%02d_%s.json"%(VERSION,stage,lane,sig)
def _rescue_checkpoint_parent(api):
 return common(api)[1]
def work_for_lane(api,manifest,lane,done):
 rows=[]
 for i in range(lane,AUDIT_LANES,COPY_LANES):
  f=match(api,manifest,"v097_BF_AUDIT_LANE_%02d.json"%i)
  if not f:raise RuntimeError("AUDIT_INCOMPLETE_LANE:"+str(i))
  v=load_json(api,f["id"])
  rescue_ck=match(api,_rescue_checkpoint_parent(api),"v097_BF_RAW_RESCUE_V1_CK_%02d.json"%i)
  rescued=load_json(api,rescue_ck["id"])["done"] if rescue_ck else {}
  for row in v["items"]:
   fid=row["file_id"]
   if fid in done:continue
   if row["raw_status"]=="A_PASS_CANDIDATE_R2_BYTES":
    rows.append(row)
   elif row["raw_status"]=="RAW_UNKNOWN_NO_R2_RECEIPT" and rescued.get(fid,{}).get("state")=="RAW_RESCUED_BASIC_CANDIDATE":
    proof=rescued[fid]
    if not proof.get("sha256") or not proof.get("bytes"):continue
    newrow=dict(row)
    newrow.update(expected_sha256=proof["sha256"],size_bytes=proof["bytes"],
                  raw_status="A_PASS_CANDIDATE_RESCUE_BYTES",prior_status="RAW_RESCUED_BASIC_CANDIDATE")
    rows.append(newrow)
 return rows
def verify_identity(r):
 name=str(r.get("file_name") or "")
 # v0.93 inventory can contain correction/checkpoint sidecars; metadata is not market RAW.
 if name.lower().endswith((".receipt.json",".manifest.json",".checkpoint.json")):
  raise RuntimeError("CONTROL_SIDECAR_NOT_MARKET_RAW")
 path=str(r.get("path") or "")
 source=str(r.get("source") or "")
 year=str(r.get("year") or "")
 month=str(r.get("month") or "")
 if not (year and month and path.startswith(year+"/"+source+"/"+month+"/")):
  raise RuntimeError("SOURCE_PATH_PERIOD_NOT_GROUNDED")
 if source=="TDCC" and r.get("prior_status")=="TDCC_TABLE_NUMERIC_PENDING":
  name=r.get("file_name") or ""
  m=re.search(r"(?:distribution|tdcc)[_-](\d{8})[_-](\d{4,6})",name,re.I)
  if not m:raise RuntimeError("TDCC_SYMBOL_DATE_NOT_EVIDENCED")
  if m.group(1)[:6]!=month.replace("-","")[:6]:
   raise RuntimeError("TDCC_FILENAME_DATE_MISMATCH")
def copy_one(api,bronze,r,lane):
 fid=r["file_id"];sha=r["expected_sha256"]
 out={"id":fid,"sha":sha,"source":r.get("source"),"path":r.get("path"),
      "source_name":r.get("file_name"),"run":RUN}
 try:
  verify_identity(r)
  meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,modifiedTime"))
  if meta.get("name")!=r.get("file_name"):raise RuntimeError("ORIGINAL_FILENAME_CHANGED")
  size=int(meta.get("size") or 0)
  if size<1 or size>MAX_BYTES:raise RuntimeError("SOURCE_EMPTY_OR_TOO_LARGE")
  b=call(lambda:api.files().get_media(fileId=fid))
  if len(b)!=size or (r.get("size_bytes") and len(b)!=int(r["size_bytes"])):
   raise RuntimeError("SOURCE_SIZE_CHANGED")
  if meta.get("md5Checksum") and hashlib.md5(b).hexdigest()!=meta["md5Checksum"]:
   raise RuntimeError("SOURCE_MD5_CHANGED")
  if digest(b)!=sha:raise RuntimeError("SOURCE_HASH_CHANGED")
  if raw_integrity(b,meta["name"])!="RAW_STRUCTURE_PASS":
   raise RuntimeError("RAW_STRUCTURE_DID_NOT_PASS")
  folder=partition(api,bronze,r,lane)
  name="%s__%s__%s"%(fid,sha[:16],os.path.basename(meta["name"]).replace("/","_"))
  d=match(api,folder,name)
  if not d:
   media=MediaInMemoryUpload(b,mimetype="application/octet-stream",resumable=False)
   d=call(lambda:api.files().create(body={"name":name,"parents":[folder],
     "description":"v0.93 native immutable; source id "+fid},media_body=media,fields="id,name"))
  content=call(lambda:api.files().get_media(fileId=d["id"]))
  if len(content)!=len(b) or digest(content)!=sha:
   raise RuntimeError("DESTINATION_SHA_OR_SIZE_MISMATCH")
  out.update(state="COPY_MATCHED_PENDING_INDEPENDENT_QA",destination_id=d["id"],
   destination_path="/".join([r["source"],"BF_LANE_%02d"%lane,str(r["year"]),str(r["month"]).split("-")[-1].zfill(2),name]),
   destination_sha=sha,destination_folder_id=folder,size=len(b))
 except Exception as e:
  out.update(state="COPY_EXCEPTION",error=type(e).__name__+":"+str(e)[:130])
 return out
def copy_lane(api,lane):
 m,c,q,bronze=common(api)
 name=ck_name("COPY",lane);f=match(api,c,name)
 ck=load_json(api,f["id"]) if f else {"schema":"v097_bf_v3_copy_ck_1","lane":lane,"done":{}}
 if ck.get("lane")!=lane:raise RuntimeError("WRONG_COPY_CHECKPOINT")
 done=ck["done"];todo=work_for_lane(api,m,lane,done)[:CAP]
 if not todo:
  print("BF_V3_COPY_IDLE",lane,len(done));return
 ids=[r["file_id"] for r in todo];receipt=receipt_name("COPY",lane,ids)
 prior=match(api,q,receipt)
 if prior:
  rows=load_json(api,prior["id"])["items"]
  if [r["id"] for r in rows]!=ids:raise RuntimeError("COPY_RECEIPT_CONFLICT")
 else:
  rows=[copy_one(api,bronze,r,lane) for r in todo]
  put_once(api,q,receipt,{"schema":"v097_bf_v3_copy_receipt_1","run":RUN,
    "lane":lane,"ids":ids,"utc":now(),"items":rows})
 for row in rows:
  done[row["id"]]={"state":row["state"],"sha":row.get("sha"),
       "dest_id":row.get("destination_id"),"dest_folder_id":row.get("destination_folder_id"),"dest_path":row.get("destination_path"),
       "source_path":row.get("path"),"size":row.get("size"),"error":row.get("error")}
 upsert(api,c,name,{"schema":"v097_bf_v3_copy_ck_1","lane":lane,
   "done":done,"last_run":RUN,"utc":now(),"last_receipt":receipt})
 print("BF_V3_COPY",lane,"batch",len(todo),"total_done",len(done),flush=True)
def qa_one(api,fid,detail,lane):
 out={"id":fid,"sha":detail["sha"],"run":RUN,"lane":lane,"at":now()}
 try:
  if detail.get("state")!="COPY_MATCHED_PENDING_INDEPENDENT_QA":
   raise RuntimeError("NOT_COPIED")
  meta=call(lambda:api.files().get(fileId=detail["dest_id"],fields="id,name,parents,size"))
  parts=str(detail["dest_path"]).split("/")
  if len(parts)!=5 or meta.get("name")!=parts[-1]:
   raise RuntimeError("DESTINATION_FILENAME_OR_PATH_METADATA_MISMATCH")
  parents=meta.get("parents") or []
  if len(parents)!=1:raise RuntimeError("DESTINATION_AMBIGUOUS_PARENT")
  expected_parent=detail.get("dest_folder_id")
  if expected_parent and parents[0]!=expected_parent:
   raise RuntimeError("DESTINATION_ACTUAL_FOLDER_ID_MISMATCH")
  if not expected_parent:
   # Legacy checkpoint without destination-folder ID: prove real hierarchy.
   parent=parents[0]; chain=[]
   for _ in range(4):
    folder_meta=call(lambda:api.files().get(fileId=parent,fields="name,parents"))
    chain.append(folder_meta["name"])
    ancestry=folder_meta.get("parents") or []
    if not ancestry:break
    parent=ancestry[0]
   if len(chain)!=4 or chain!=[parts[3],parts[2],parts[1],parts[0]]:
    raise RuntimeError("DESTINATION_ACTUAL_PARENT_CHAIN_MISMATCH")
  src=call(lambda:api.files().get_media(fileId=fid))
  dest=call(lambda:api.files().get_media(fileId=detail["dest_id"]))
  if digest(src)!=detail["sha"] or digest(dest)!=detail["sha"] or len(src)!=len(dest):
   raise RuntimeError("INDEPENDENT_SOURCE_DEST_SHA_MISMATCH")
  if raw_integrity(dest,detail["dest_path"])!="RAW_STRUCTURE_PASS":
   raise RuntimeError("DESTINATION_BASIC_FORMAT_FAILED")
  # Immutable destination path must reflect original *actual* yyyy-mm, not month 00.
  if not re.search(r"/(?:19|20)\d{2}/(?:0[1-9]|1[0-2])/",detail["dest_path"]):
   raise RuntimeError("DESTINATION_YEAR_MONTH_PARTITION_INVALID")
  out.update(state="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS",dest_id=detail["dest_id"],
    bytes=len(dest),dest_path=detail["dest_path"])
 except Exception as e:
  out.update(state="BRONZE_QA_EXCEPTION",error=type(e).__name__+":"+str(e)[:130])
 return out
def qa_lane(api,lane):
 m,c,q,_=common(api)
 copyf=match(api,c,ck_name("COPY",lane))
 if not copyf:print("BF_V3_QA_NO_COPIES",lane);return
 copied=load_json(api,copyf["id"])["done"]
 name=ck_name("QA",lane);f=match(api,c,name)
 ck=load_json(api,f["id"]) if f else {"schema":"v097_bf_v3_qa_ck_1","lane":lane,"done":{}}
 done=ck["done"]
 todo=[fid for fid,detail in copied.items() if detail.get("state")=="COPY_MATCHED_PENDING_INDEPENDENT_QA" and fid not in done][:CAP]
 if not todo:
  print("BF_V3_QA_IDLE",lane,len(done));return
 receipt=receipt_name("QA",lane,todo);prior=match(api,q,receipt)
 if prior:
  rows=load_json(api,prior["id"])["items"]
  if [r["id"] for r in rows]!=todo:raise RuntimeError("QA_RECEIPT_CONFLICT")
 else:
  rows=[qa_one(api,fid,copied[fid],lane) for fid in todo]
  put_once(api,q,receipt,{"schema":"v097_bf_v3_qa_receipt_1","run":RUN,"lane":lane,
    "utc":now(),"items":rows})
 for row in rows:done[row["id"]]={"state":row["state"],"error":row.get("error")}
 upsert(api,c,name,{"schema":"v097_bf_v3_qa_ck_1","lane":lane,"done":done,
  "last_run":RUN,"utc":now(),"last_receipt":receipt})
 print("BF_V3_QA",lane,"batch",len(todo),"total_done",len(done),flush=True)
def aggregate(api,persist=True):
 m,c,q,_=common(api);audit=Counter();copies=Counter();qa=Counter()
 for lane in range(AUDIT_LANES):
  f=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%lane)
  if not f:raise RuntimeError("AUDIT_LANE_MISSING")
  audit.update(load_json(api,f["id"])["counts"])
 if sum(audit.values())!=82273:raise RuntimeError("FROZEN_INVENTORY_MISMATCH")
 for lane in range(COPY_LANES):
  for step,counter in (("COPY",copies),("QA",qa)):
   f=match(api,c,ck_name(step,lane))
   if f:
    d=load_json(api,f["id"])
    if d.get("lane")!=lane:raise RuntimeError("CHECKPOINT_LANE_MISMATCH")
    counter.update(x["state"] for x in d["done"].values())
 rescued=Counter()
 rescue_pending=0
 for lane in range(12):
  f=match(api,c,"v097_BF_RAW_RESCUE_V1_CK_%02d.json"%lane)
  if f:
   ck=load_json(api,f["id"])
   if ck.get("lane")!=lane:raise RuntimeError("RAW_RESCUE_CHECKPOINT_LANE_MISMATCH")
   rescued.update(x["state"] for x in ck["done"].values())
 rescue_pending=max(0,audit.get("RAW_UNKNOWN_NO_R2_RECEIPT",0)-sum(rescued.values()))
 eligible=audit.get("A_PASS_CANDIDATE_R2_BYTES",0)+rescued.get("RAW_RESCUED_BASIC_CANDIDATE",0)
 handled=sum(copies.values())
 pending=max(0,eligible-handled)
 qa_valid=qa.get("BRONZE_BYTE_PROVENANCE_AND_PATH_PASS",0)+qa.get("BRONZE_QA_EXCEPTION",0)
 qa_pending=max(0,copies.get("COPY_MATCHED_PENDING_INDEPENDENT_QA",0)-qa_valid)
 if qa_valid>copies.get("COPY_MATCHED_PENDING_INDEPENDENT_QA",0):
  raise RuntimeError("BRONZE_VALID_QA_COUNT_EXCEEDS_UNQUARANTINED_COPIES")
 if qa.get("BRONZE_REVOKED_NONMARKET",0)>copies.get("COPY_QUARANTINED_NONMARKET",0):
  raise RuntimeError("REVOKED_QA_EXCEEDS_QUARANTINED_COPIES")
 report={"schema":"v097_bronze_first_v3_dashboard_1","run":RUN,"utc":now(),
  "inventory":82273,"r3_queue_processed":73146,"audit":dict(audit),"raw_candidate_count":eligible,"raw_rescue":dict(rescued),"raw_rescue_pending":rescue_pending,
  "copy":dict(copies),"qa":dict(qa),"copy_pending":pending,"qa_pending":qa_pending,
  "sidecar_quarantine_count":copies.get("COPY_QUARANTINED_NONMARKET",0),
  "bronze_final_certified":False,"legacy_control_sidecars_need_isolation":True,"full_historical_coverage_certified":False,
  "xq":"WAIT_FOR_USER_IMPORT","finmind_699":"WAIT_FOR_SUBSCRIPTION_AND_DATASET_ENTITLEMENTS",
  "silver_gold":"NOT_STARTED","note":"Native byte SHA/path check only; excludes unresolved raw and source-calendar gaps. v1/v2 copies remain historical superseded evidence."}
 if persist:save(api,q,"v097_BF_V3_SUMMARY_%s.json"%RUN,report)
 if os.getenv("GITHUB_OUTPUT"):
  with open(os.environ["GITHUB_OUTPUT"],"a") as g:g.write("pending=%d\n"%(pending+qa_pending+rescue_pending))
 print("BF_V3_SUMMARY",json.dumps(report),flush=True)
def tests():
 from scripts.v097_bronze_first_pipeline import raw_integrity
 assert raw_integrity(b"%PDF-1234","x.pdf")=="RAW_STRUCTURE_PASS"
 assert raw_integrity(b"","test.csv")=="RAW_EMPTY"
 assert receipt_name("COPY",2,["a","b"])==receipt_name("COPY",2,["a","b"])
 assert verify_identity({"source":"TWSE","year":"2024","month":"2024-05",
  "path":"2024/TWSE/2024-05/foo.csv"}) is None
 try:verify_identity({"source":"TWSE","year":"2024","month":"2024-05","path":"2024/TPEx/2024-05/foo.csv"})
 except RuntimeError:pass
 else:raise AssertionError("Mismatched source not blocked")
 print("BF_V3_SELFTEST_PASS")
if __name__=="__main__":
 mode=os.getenv("BF_MODE","selftest")
 if mode=="selftest":selftest();tests()
 else:
  api=service()
  if mode=="audit":audit_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="bootstrap":bootstrap(api)
  elif mode=="copy":copy_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="qa":qa_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="aggregate":aggregate(api)
  elif mode=="status":aggregate(api,persist=False)
  else:raise RuntimeError("BAD_MODE")
