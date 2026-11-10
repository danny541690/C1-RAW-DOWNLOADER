#!/usr/bin/env python3
"""Quarantine legacy non-market control sidecars copied into v0.97 Bronze.
Never delete originals, never overwrite payloads; allow only verified Drive IDs.
Single writer after six QA lanes finish. Preserve prior receipts, mark CK superseded.
"""
import os,re,hashlib
from scripts.v097_bronze_first_pipeline import service,call,common,makefolder,folder,match,load_json,upsert,save,now
from scripts.v097_bronze_first_batch_v3 import ck_name
RUN=os.getenv("GITHUB_RUN_ID","manual")
ENDINGS=(".receipt.json",".manifest.json",".checkpoint.json")
def quarantine(api):
 m,c,q,bronze=common(api)
 root=folder(api,folder(api,"root","ChatGPT資料存取"),"JARVIS_C1_v097_LIFECYCLE")
 lake=folder(api,root,"02_DATA_LAKE")
 quarantine_root=makefolder(api,lake,"00_BRONZE_QUARANTINE_CONTROLS")
 stats={"found":0,"moved":0,"already_quarantined":0,"errors":[],"last_run":RUN}
 for lane in range(6):
  cf=match(api,c,ck_name("COPY",lane))
  if not cf:continue
  cp=load_json(api,cf["id"]);done=cp.get("done",{})
  qf=match(api,c,ck_name("QA",lane))
  qp=load_json(api,qf["id"]) if qf else {"schema":"v097_bf_v3_qa_ck_1","lane":lane,"done":{}}
  copy_changed=False;qa_changed=False
  for fid,detail in done.items():
   path=str(detail.get("dest_path") or "")
   if not path.lower().endswith(ENDINGS):continue
   stats["found"]+=1
   did=detail.get("dest_id")
   if not did:
    stats["errors"].append({"source_id":fid,"reason":"MISSING_DEST_ID"});continue
   try:
    meta=call(lambda:api.files().get(fileId=did,fields="id,name,parents,size,md5Checksum"))
    if not meta["name"].lower().endswith(ENDINGS):
     raise RuntimeError("DESTINATION_NAME_NOT_CONTROL")
    current=meta.get("parents") or []
    if len(current)!=1:raise RuntimeError("AMBIGUOUS_DESTINATION_PARENT")
    data=call(lambda:api.files().get_media(fileId=did))
    if hashlib.sha256(data).hexdigest()!=detail.get("sha"):
     raise RuntimeError("CONTROL_SHA_CHANGED_STOP")
    target=makefolder(api,quarantine_root,"LANE_%02d"%lane)
    if current[0]==target:
     stats["already_quarantined"]+=1
    else:
     # Ensure no accidental move from outside the intended Bronze origin subtree.
     source_root=match(api,bronze,path.split("/")[0])
     if not source_root:raise RuntimeError("SOURCE_NAMESPACE_NOT_IN_BRONZE")
     if detail.get("state") not in ("COPY_MATCHED_PENDING_INDEPENDENT_QA","COPY_QUARANTINED_NONMARKET"):
      raise RuntimeError("COPY_STATUS_NOT_ELIGIBLE_FOR_QUARANTINE")
     call(lambda:api.files().update(fileId=did,addParents=target,removeParents=current[0],
         fields="id,parents"))
     stats["moved"]+=1
    detail["state"]="COPY_QUARANTINED_NONMARKET"
    detail["exception"]="CONTROL_SIDECAR_NOT_MARKET_RAW"
    detail["quarantine_parent_id"]=target
    copy_changed=True
    qp["done"][fid]={"state":"BRONZE_REVOKED_NONMARKET",
                     "error":"CONTROL_SIDECAR_QUARANTINED","destination_id":did}
    qa_changed=True
   except Exception as e:
    stats["errors"].append({"source_id":fid,"reason":type(e).__name__+":"+str(e)[:140]})
  if copy_changed:
   cp["last_quarantine_run"]=RUN;cp["quarantine_at"]=now()
   upsert(api,c,ck_name("COPY",lane),cp)
  if qa_changed:
   qp["last_quarantine_run"]=RUN;qp["quarantine_at"]=now()
   upsert(api,c,ck_name("QA",lane),qp)
 if stats["errors"]:stats["status"]="QUARANTINE_PARTIAL_BLOCKED"
 else:stats["status"]="QUARANTINE_COMPLETE_FOR_CURRENT_CK_SNAPSHOT"
 save(api,q,"v097_BF_QUARANTINE_CONTROLS_%s.json"%RUN,stats)
 print("BF_QUARANTINE_REPORT",stats,flush=True)
 if stats["errors"]:raise RuntimeError("QUARANTINE_UNRESOLVED:"+str(len(stats["errors"])))
if __name__=="__main__":
 quarantine(service())
