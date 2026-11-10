#!/usr/bin/env python3
"""Bronze-first v1.1: fail-closed v0.93 evidence audit -> immutable copy -> independent QA.
No Silver, Gold, PIT, normalization, user XQ access, or FinMind purchase attempted.
12 audit lanes, 6 copy+QA lanes. GitHub workflow runs have single-writer concurrency.
"""
import os,re,json,io,hashlib,zipfile,time,random
from datetime import datetime,timezone
from collections import Counter
from googleapiclient.http import MediaInMemoryUpload
from scripts.v097_bronze_content_qa import service,call,folder,children,load_json,save
from scripts.v097_bronze_diagnosis import save_or_update
from scripts.v097_round2_verify import dirs,one

RUN=os.environ.get("GITHUB_RUN_ID","manual")
ROOT="JARVIS_C1_v097_LIFECYCLE"
SOURCES={"TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"}
AUDIT_LANES=12
COPY_LANES=6
MAX_COPY=int(os.getenv("BRONZE_COPY_BATCH","24"))
MAX_BYTES=40*1024*1024
GOOD={"ZIP_CRC_PASS_CONTENT_PENDING","ZIP_MIXED_ARCHIVE_CONTENT_PENDING",
      "JSON_ROWS_PARSED_PIT_PENDING","JSON_SCHEMA_CONTENT_PENDING",
      "CSV_SCHEMA_CONTENT_PENDING","CSV_SCHEMA_PENDING",
      "PDF_CONTENT_PENDING","HTML_TABLE_CONTENT_PENDING",
      "TDCC_TABLE_NUMERIC_PENDING"}
# Not automatically safe: unknown HTML, spreadsheet without reader, quarantines, exceptions.
# R2 receipts contain actual hash, byte size and validation, not only metadata.
def now():return datetime.now(timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def match(api,parent,name):
 q="'%s' in parents and name = '%s' and trashed = false"%(parent,name.replace("'","\\'"))
 hits=[];token=None
 while True:
  a={"q":q,"fields":"nextPageToken,files(id,name,size,mimeType,md5Checksum,parents)","pageSize":1000}
  if token:a["pageToken"]=token
  d=call(lambda:api.files().list(**a))
  hits.extend(d.get("files",[]));token=d.get("nextPageToken")
  if not token:break
 if len(hits)>1:raise RuntimeError("DUPLICATE_DRIVE_NAME:"+name)
 return hits[0] if hits else None
def makefolder(api,parent,name):
 f=match(api,parent,name)
 if f:
  if f["mimeType"]!="application/vnd.google-apps.folder":raise RuntimeError("NOT_FOLDER:"+name)
  return f["id"]
 f=call(lambda:api.files().create(body={"name":name,"mimeType":"application/vnd.google-apps.folder","parents":[parent]},fields="id"))
 return f["id"]
def common(api):
 m,c,q=dirs(api)
 root=folder(api,folder(api,"root","ChatGPT資料存取"),ROOT)
 lake=folder(api,root,"02_DATA_LAKE")
 bronze=folder(api,lake,"01_BRONZE_ORIGINAL")
 return m,c,q,bronze
def put_once(api,parent,name,obj):
 found=match(api,parent,name)
 if found:
  old=load_json(api,found["id"])
  if old!=obj:raise RuntimeError("IMMUTABLE_MANIFEST_CONFLICT:"+name)
  return found["id"]
 return save(api,parent,name,obj)["id"]
def upsert(api,parent,name,obj):
 f=match(api,parent,name)
 if f:save_or_update(api,parent,name,obj,f["id"])
 else:save(api,parent,name,obj)
def classify(r,hit):
 if not hit:return "RAW_UNKNOWN_NO_R2_RECEIPT",""
 status=hit.get("status","")
 if hit.get("file_id")!=r["file_id"]:return "RAW_REJECT_ID_CONFLICT",status
 if hit.get("source")!=r.get("source"):return "RAW_REJECT_SOURCE_CONFLICT",status
 if hit.get("path")!=r.get("path"):return "RAW_REJECT_PATH_CONFLICT",status
 if not re.fullmatch("[0-9a-f]{64}",hit.get("sha256") or ""):return "RAW_UNKNOWN_HASH",status
 if not isinstance(hit.get("bytes"),int) or hit["bytes"]<1:return "RAW_UNKNOWN_BYTES",status
 if r.get("size_bytes") and hit["bytes"]!=int(r["size_bytes"]):return "RAW_REJECT_SIZE",status
 if not r.get("source") or r["source"] not in SOURCES:return "RAW_UNKNOWN_SOURCE",status
 if status in GOOD:
  if status=="TDCC_TABLE_NUMERIC_PENDING" and not r.get("file_name"):
   return "RAW_REVIEW_TDCC_IDENTITY",status
  return "A_PASS_CANDIDATE_R2_BYTES",status
 if status.startswith("QUARANTINED_"):return "RAW_REVIEW_QUARANTINED",status
 if status.startswith("EXCEPTION_"):return "RAW_BLOCKED_PARSER_OR_SIZE",status
 return "RAW_REVIEW_NOT_CERTIFIED",status
def audit_lane(api,lane):
 m,c,q,_=common(api)
 outname="v097_BF_AUDIT_LANE_%02d.json"%lane
 if match(api,m,outname):
  print("AUDIT_REUSED",lane,flush=True);return
 f=match(api,m,"v097_R2_MANIFEST_%02d.json"%lane)
 if not f:raise RuntimeError("NO_FROZEN_R2_LANE")
 original=load_json(api,f["id"])
 rows=original["files"]
 receipts={}
 conflicts=set()
 rx=re.compile(r"v097_R2_\d+_%02d_\d\d[.]json$"%lane)
 for file in children(api,q):
  if not rx.fullmatch(file["name"]):continue
  try:
   v=load_json(api,file["id"])
   if v.get("schema")!="r2_receipt_1" or v.get("lane")!=lane:raise ValueError("BAD_RECEIPT")
   for x in v.get("results",[]):
    fid=x.get("file_id")
    if fid not in receipts:receipts[fid]=x
    elif x.get("sha256")!=receipts[fid].get("sha256"):conflicts.add(fid)
  except Exception:
   # Fail closed; unreadable receipts do not authorize copies.
   raise RuntimeError("UNREADABLE_R2_RECEIPT:"+file["name"])
 items=[];count=Counter()
 for r in rows:
  fid=r["file_id"]
  outcome,status=classify(r,receipts.get(fid))
  if fid in conflicts:outcome="RAW_REJECT_SHA_CONFLICT"
  qrow={"file_id":fid,"source":r.get("source"),"year":r.get("year"),"month":r.get("month"),
        "path":r.get("path"),"file_name":r.get("file_name"),"size_bytes":r.get("size_bytes"),
        "md5":r.get("md5"),"expected_sha256":receipts.get(fid,{}).get("sha256"),
        "prior_status":status,"raw_status":outcome,"r2_evidence_only":True}
  items.append(qrow);count[outcome]+=1
 result={"schema":"v097_bronze_first_audit_1","lane":lane,"source_r2_manifest_id":f["id"],
         "items":items,"counts":dict(count),"n":len(items),"frozen_snapshot":"42591232910",
         "full_certified":False,"note":"Copy-time actual bytes, metadata and independent destination re-read required"}
 put_once(api,m,outname,result)
 print("BF_AUDIT",lane,len(items),dict(count),flush=True)
def partition(api,bronze,r,lane):
 # No transformations: separate source namespace and immutable content version filename.
 source=r.get("source")
 if not source or not re.fullmatch(r"[A-Za-z0-9_-]{2,32}",source):raise RuntimeError("BAD_SOURCE")
 y=str(r.get("year") or "UNCLASSIFIED")
 month=str(r.get("month") or "")
 if not re.fullmatch(r"(?:19|20)\d{2}|UNCLASSIFIED",y):raise RuntimeError("BAD_YEAR")
 if re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])",month):
  part_year,part_month=month.split("-")
  if part_year!=y:raise RuntimeError("YEAR_MONTH_MISMATCH")
  month=part_month
 elif re.fullmatch(r"0?[1-9]|1[0-2]",month):
  month=str(int(month)).zfill(2)
 else:
  raise RuntimeError("MONTH_NOT_VERIFIABLE:"+month)
 root=match(api,bronze,source)
 if not root:raise RuntimeError('SOURCE_ROOT_NOT_BOOTSTRAPPED:'+source)
 shard=match(api,root['id'],'BF_LANE_%02d'%lane)
 if not shard:raise RuntimeError('LANE_ROOT_NOT_BOOTSTRAPPED')
 return makefolder(api,makefolder(api,shard['id'],y),month.zfill(2))
def bootstrap(api):
 m,c,q,bronze=common(api)
 for source in sorted(SOURCES):
  root=makefolder(api,bronze,source)
  for lane in range(COPY_LANES):makefolder(api,root,"BF_LANE_%02d"%lane)
 print("BF_BOOTSTRAP_READY",len(SOURCES),COPY_LANES,flush=True)

def raw_integrity(b,name):
 if not b:return "RAW_EMPTY"
 if len(b)>MAX_BYTES:return "RAW_TOO_LARGE"
 if name.lower().endswith((".zip",".xlsx")) or b.startswith(b"PK\x03\x04"):
  try:
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    files=z.infolist()
    if not files:return "RAW_EMPTY_ARCHIVE"
    if any(x.filename.startswith("/") or ".." in x.filename.split("/") for x in files):return "RAW_UNSAFE_ZIP"
    if sum(x.file_size for x in files)>256*1024*1024:return "RAW_ZIP_TOO_LARGE"
    if z.testzip() is not None:return "RAW_ZIP_CRC_FAIL"
  except Exception:return "RAW_ZIP_FAIL"
 elif name.lower().endswith(".pdf") and not b.startswith(b"%PDF-"):return "RAW_PDF_INVALID"
 elif name.lower().endswith((".html",".htm")):
  html=b[:250000].decode("utf-8-sig",errors="replace").lower()
  if any(x in html for x in ("access denied","403 forbidden","429 too many requests","502 bad gateway","service unavailable","404 not found")):
   return "RAW_UPSTREAM_HTML_ERROR"
  if "<table" not in html and "<tbody" not in html:
   return "RAW_HTML_DATA_STRUCTURE_NOT_CONFIRMED"
 elif name.lower().endswith(".json"):
  try:json.loads(b.decode("utf-8-sig"))
  except Exception:return "RAW_JSON_INVALID"
 return "RAW_STRUCTURE_PASS"
def copy_lane(api,lane):
 m,c,q,bronze=common(api)
 ckname="v097_BF_COPY_V2_CK_%02d.json"%lane
 ckf=match(api,c,ckname)
 ck=load_json(api,ckf["id"]) if ckf else {"schema":"v097_bronze_copy_ck_2","done":{}}
 done=ck["done"];work=[]
 for k in range(lane,12,6):
  f=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%k)
  if not f:raise RuntimeError("AUDIT_LANE_INCOMPLETE:"+str(k))
  for r in load_json(api,f["id"])["items"]:
   if r["raw_status"]=="A_PASS_CANDIDATE_R2_BYTES" and r["file_id"] not in done:work.append(r)
 batch=work[:MAX_COPY]
 for r in batch:
  fid=r["file_id"]
  # Per-file outcome is always durable, even if source inaccessible; no endless retry.
  outcome={"source_id":fid,"source_sha256":r["expected_sha256"],"source_path":r["path"],
           "source":r["source"],"run_id":RUN,"checked_at":now(),"stage":"BRONZE_COPY"}
  try:
   meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,modifiedTime"))
   size=int(meta.get("size") or 0)
   if size<1 or size>MAX_BYTES:raise RuntimeError("SOURCE_EMPTY_OR_SIZE_LIMIT")
   b=call(lambda:api.files().get_media(fileId=fid))
   if len(b)!=size or (r.get("size_bytes") and len(b)!=int(r["size_bytes"])):
    raise RuntimeError("SOURCE_SIZE_CHANGED")
   if meta.get("md5Checksum") and hashlib.md5(b).hexdigest()!=meta["md5Checksum"]:
    raise RuntimeError("SOURCE_MD5_CHANGED")
   sha=digest(b)
   if sha!=r["expected_sha256"]:raise RuntimeError("SOURCE_SHA_CHANGED")
   # Mandatory native source and date identity validation at time of copy.
   if r.get("year") and r.get("month"):
    prefix=str(r["year"])+"/"+str(r["source"])+"/"+str(r["month"])+"/"
    if not str(r.get("path") or "").startswith(prefix):
     raise RuntimeError("SOURCE_PATH_SOURCE_PERIOD_MISMATCH")
   if r["source"]=="TDCC" and r.get("prior_status")=="TDCC_TABLE_NUMERIC_PENDING":
    n=r.get("file_name") or ""
    match_id=re.search(r"(?:distribution|tdcc)[_-](\d{8})[_-](\d{4,6})",n,re.I)
    if not match_id:raise RuntimeError("TDCC_DATE_STOCK_ID_NOT_EVIDENCED_IN_FILENAME")
    if match_id.group(1)[:6]!=str(r.get("month") or "").replace("-","")[:6]:
     raise RuntimeError("TDCC_FILENAME_PERIOD_MISMATCH")

   if raw_integrity(b,meta["name"])!="RAW_STRUCTURE_PASS":
    raise RuntimeError("SOURCE_RAW_STRUCTURE_FAILURE")
   targetfolder=partition(api,bronze,r,lane)
   # Preserve original bytes and basename in immutable, version-addressed target name.
   basename=os.path.basename(meta["name"]).replace("/","_")
   filename="%s__%s__%s"%(fid,sha[:16],basename)
   target=match(api,targetfolder,filename)
   if not target:
    media=MediaInMemoryUpload(b,mimetype="application/octet-stream",resumable=False)
    target=call(lambda:api.files().create(body={"name":filename,"parents":[targetfolder],
                 "description":"Immutable original from v0.93 fileID="+fid},media_body=media,fields="id,name,size,md5Checksum"))
   destination=call(lambda:api.files().get_media(fileId=target["id"]))
   if len(destination)!=len(b) or digest(destination)!=sha:
    raise RuntimeError("DESTINATION_HASH_MISMATCH")
   outcome.update(state="COPY_BYTES_MATCHED_QA_PENDING",destination_id=target["id"],
                  destination_name=filename,destination_folder=targetfolder,
                  destination_sha256=digest(destination),bytes=len(destination))
  except Exception as e:
   outcome.update(state="COPY_BLOCKED_REVIEW",error=type(e).__name__+":"+str(e)[:180])
  # Receipt first, then checkpoint. A retry cannot overwrite a changed receipt.
  receiptname="v097_BF_COPY_V2_%s.json"%fid
  put_once(api,q,receiptname,outcome)
  done[fid]=outcome["state"]
  upsert(api,c,ckname,{"schema":"v097_bronze_copy_ck_2","lane":lane,"done":done,"last_run":RUN,"utc":now()})
  print("BF_COPY",lane,fid,outcome["state"],flush=True)
 print("BF_COPY_BATCH",lane,len(batch),"pending",len(work)-len(batch),flush=True)
def verify_lane(api,lane):
 m,c,q,bronze=common(api)
 ckname="v097_BF_QA_V2_CK_%02d.json"%lane
 ckf=match(api,c,ckname)
 ck=load_json(api,ckf["id"]) if ckf else {"schema":"v097_bronze_qa_ck_2","done":{}}
 done=ck["done"]
 copy_ck=match(api,c,"v097_BF_COPY_V2_CK_%02d.json"%lane)
 if not copy_ck:
  print("BF_VERIFY_NO_COPIES",lane,flush=True);return
 copied=load_json(api,copy_ck["id"])["done"]
 pending=[fid for fid,state in copied.items()
          if state=="COPY_BYTES_MATCHED_QA_PENDING" and fid not in done]
 for fid in pending[:MAX_COPY]:
  crf=match(api,q,"v097_BF_COPY_V2_%s.json"%fid)
  if not crf:raise RuntimeError("COPY_CHECKPOINT_WITHOUT_RECEIPT:"+fid)
  cr=load_json(api,crf["id"])
  expected=cr["source_sha256"]
  result={"source_id":fid,"dest_id":cr.get("destination_id"),"run_id":RUN,"at":now(),
          "source_expected_sha256":expected}
  try:
   if cr.get("state")!="COPY_BYTES_MATCHED_QA_PENDING":
    raise RuntimeError("COPY_RECEIPT_NOT_APPROVED")
   src=call(lambda:api.files().get_media(fileId=fid))
   dst=call(lambda:api.files().get_media(fileId=cr["destination_id"]))
   if digest(src)!=expected or digest(dst)!=expected or len(src)!=len(dst):
    raise RuntimeError("INDEPENDENT_SHA_OR_SIZE_MISMATCH")
   if raw_integrity(dst,cr["destination_name"])!="RAW_STRUCTURE_PASS":
    raise RuntimeError("DESTINATION_CONTENT_INVALID")
   result.update(state="BRONZE_BYTE_PROVENANCE_PASS",sha256=digest(dst),bytes=len(dst))
  except Exception as e:
   result.update(state="BRONZE_QA_BLOCKED",error=type(e).__name__+":"+str(e)[:180])
  put_once(api,q,"v097_BF_QA_V2_%s.json"%fid,result)
  done[fid]=result["state"]
  upsert(api,c,ckname,{"schema":"v097_bronze_qa_ck_2","lane":lane,"done":done,"last_run":RUN,"utc":now()})
  print("BF_VERIFY",lane,fid,result["state"],flush=True)
 print("BF_VERIFY_BATCH",lane,len(pending[:MAX_COPY]),"queue",len(pending),flush=True)

def aggregate(api):
 m,c,q,_=common(api)
 audit=Counter(); eligible=0; copied=Counter();qa=Counter()
 for k in range(12):
  f=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%k)
  if not f:raise RuntimeError("AUDIT_NOT_COMPLETE")
  d=load_json(api,f["id"]);audit.update(d["counts"])
  eligible+=d["counts"].get("A_PASS_CANDIDATE_R2_BYTES",0)
 if sum(audit.values())!=82273:raise RuntimeError("FROZEN_INVENTORY_CONSERVATION_FAILED")
 for k in range(6):
  cf=match(api,c,"v097_BF_COPY_V2_CK_%02d.json"%k)
  vf=match(api,c,"v097_BF_QA_V2_CK_%02d.json"%k)
  if cf:copied.update(load_json(api,cf["id"])["done"].values())
  if vf:qa.update(load_json(api,vf["id"])["done"].values())
 handled=sum(copied.values())
 pending=max(0,eligible-handled)
 qa_pending=max(0,copied.get("COPY_BYTES_MATCHED_QA_PENDING",0)-sum(qa.values()))
 result={"schema":"v097_bronze_first_dashboard_v2","run_id":RUN,"at":now(),
         "inventory":82273,"r3_processed_issues":73146,"audit":dict(audit),"copy_eligible":eligible,
         "copy":dict(copied),"qa":dict(qa),"copy_pending":pending,"qa_pending":qa_pending,
         "state":"COPY_AND_QA_IN_PROGRESS" if pending or qa_pending else "BRONZE_BYTE_QA_ONLY_COMPLETED_WITH_EXCEPTIONS",
         "bronze_full_source_coverage_certified":False,"full_bronze_release_approved":False,"destination_partition_revision":"v2_YEAR_MM",
         "xq_status":"WAIT_FOR_USER_MANUAL_CSV","finmind_699_status":"WAIT_FOR_PAID_ACCESS_AND_DATASET_CONFIRMATION",
         "silver_gold":"STRICTLY_NOT_STARTED_BY_THIS_PIPELINE",
         "note":"Per-file SHA copy and QA only; all unresolved legacy/source coverage issues retained. Never declare full Bronze certified."}
 save(api,q,"v097_BF_SUMMARY_%s.json"%RUN,result)
 with open(os.environ.get("GITHUB_OUTPUT","/tmp/v097_bf_output"),"a") as f:
  f.write("pending=%d\n"%(pending+qa_pending))
 print("BF_SUMMARY",json.dumps(result,ensure_ascii=False),flush=True)
def selftest():
 assert classify({"file_id":"id","source":"TWSE","path":"a","size_bytes":4},
   {"file_id":"id","source":"TWSE","path":"a","sha256":"a"*64,"bytes":4,"status":"ZIP_CRC_PASS_CONTENT_PENDING"})[0]=="A_PASS_CANDIDATE_R2_BYTES"
 assert classify({"file_id":"id","source":"TWSE","path":"a","size_bytes":4},
   {"file_id":"id","source":"TWSE","path":"a","sha256":"a"*64,"bytes":4,"status":"JSON_ROWS_PARSED_PIT_PENDING"})[0]=="A_PASS_CANDIDATE_R2_BYTES"
 assert classify({"file_id":"id","source":"TWSE","path":"a","size_bytes":4},
   {"file_id":"id","source":"TWSE","path":"a","sha256":"a"*64,"bytes":4,"status":"QUARANTINED_EMPTY"})[0]!="A_PASS_CANDIDATE_R2_BYTES"
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:z.writestr("test.txt","hi")
 assert raw_integrity(b.getvalue(),"original.zip")=="RAW_STRUCTURE_PASS"
 assert raw_integrity(b"","zero.csv")=="RAW_EMPTY"
 print("BF_SELFTEST_PASS")
if __name__=="__main__":
 mode=os.getenv("BF_MODE","selftest")
 if mode=="selftest":selftest()
 else:
  api=service()
  if mode=="bootstrap":bootstrap(api)
  elif mode=="audit":audit_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="copy":copy_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="qa":verify_lane(api,int(os.environ["BF_LANE"]))
  elif mode=="aggregate":aggregate(api)
  else:raise RuntimeError("UNKNOWN_MODE")
