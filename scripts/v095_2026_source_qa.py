#!/usr/bin/env python3
"""Source-scoped 2026 QA over immutable source / downstream receipts.
Never repairs or certifies 443 PIT; explicitly emits deduplicated actionable gaps.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
from googleapiclient.http import MediaIoBaseUpload
SOURCE=os.getenv("V095_QA_SOURCE","")
if SOURCE not in ("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC"):raise ValueError("INVALID_QA_SOURCE")
OUT=pathlib.Path("v095_2026_source_qa")
def sha(b):return hashlib.sha256(b).hexdigest()
def ls(d,q):
 rows=[];token=None
 while True:
  result=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,createdTime)",pageSize=500,pageToken=token).execute()
  if result.get("incompleteSearch"):raise RuntimeError("SOURCE_QA_INCOMPLETE_LIST")
  rows.extend(result.get("files",[]))
  if len(rows)>2500:raise RuntimeError("SOURCE_QA_LIST_BUDGET")
  token=result.get("nextPageToken")
  if not token:return rows
def type_of(reason):
 text=str(reason).lower()
 if any(x in text for x in ("429","timeout","connection","http_5","download")):return "1_DOWNLOAD_FAILURE"
 if any(x in text for x in ("zip","crc","empty","corrupt","uncompressed")):return "2_EMPTY_OR_CORRUPT"
 if any(x in text for x in ("month","date","time","published","pit","calendar")):return "3_DATE_OR_TIME"
 if any(x in text for x in ("member","field","schema","column","parser","adapter","manifest")):return "4_FIELD_OR_SCHEMA"
 return "5_CONTENT_ANOMALY"
def issue(source,kind,period,reason,attempts,status,run):
 return {"source":source,"dataset_id":None,"period":period,"classification":type_of(reason),
 "reason":str(reason)[:240],"status":status,"attempts":attempts,"run_ids":[run],
 "repair_decision":"QUARANTINE_PENDING_ADAPTER" if attempts==3 or "SCHEMA" in str(reason).upper() else "INVESTIGATE_EXACT_GAP",
 "zero_imputation":False,"automatic_download_repair_executed":False}
def main():
 OUT.mkdir(exist_ok=True)
 flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 d=drive();files=ls(d,"'"+OPS+"' in parents and name contains 'JARVIS_V095_2026_RUN_RECEIPT_' and trashed=false")
 candidates=sorted((f for f in files if f["name"].startswith("JARVIS_V095_2026_RUN_RECEIPT_")
    and ("_"+SOURCE+"_") in f["name"]),key=lambda x:x.get("createdTime",""),reverse=True)[:8]
 issues={};runs=[];errors=[]
 for f in candidates:
  try:
   raw=d.files().get_media(fileId=f["id"]).execute();h=sha(raw)
   if not f["name"].endswith("_"+h[:20]+".json"):raise ValueError("QA_RECEIPT_SHA_FILENAME")
   j=json.loads(raw)
   if j.get("source")!=SOURCE or j.get("schema")!="JARVIS_V095_2026_DURABLE_LANE_RECEIPT_R1":raise ValueError("QA_SOURCE_SCOPE")
   rid=j["run_id"];runs.append({"run_id":rid,"lane":j["lane"],"receipt_sha256":h,"drive_id":f["id"]})
   if j.get("result_absent"):
    x=issue(SOURCE,"MISSING","UNKNOWN","MISSING_RESULT_JSON",None,"MISSING_EVIDENCE",rid)
    issues[(x["period"],x["reason"])]=x
   for p,v in j.get("source_results",{}).items():
    obj=v.get("data")
    if not isinstance(obj,dict):continue
    for k in ("failed","blocked"):
     for val in obj.get(k,[]) if isinstance(obj.get(k),list) else []:
      if not isinstance(val,dict):continue
      period=val.get("date") or val.get("month") or "UNKNOWN"
      reason=val.get("reason") or val.get("message") or val.get("state") or "UNCLASSIFIED"
      x=issue(SOURCE,k,period,reason,val.get("attempts") or val.get("quarantined_after_cycles"),val.get("state"),rid)
      key=(period,str(reason))
      if key in issues:issues[key]["run_ids"].append(rid)
      else:issues[key]=x
    if obj.get("retry_queue_length"):
     x=issue(SOURCE,"RETRY_QUEUE","UNKNOWN","OPEN_RETRY_QUEUE",None,"RETRY_PENDING",rid)
     if ("UNKNOWN","OPEN_RETRY_QUEUE") in issues:issues[("UNKNOWN","OPEN_RETRY_QUEUE")]["run_ids"].append(rid)
     else:issues[("UNKNOWN","OPEN_RETRY_QUEUE")]=x
  except Exception as exc:errors.append({"id":f["id"],"type":type(exc).__name__,"message":str(exc)[:130]})
 report={"schema":"V095_2026_SOURCE_QA_R1","source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),
  "recent_receipts":runs,"deduplicated_issues":list(issues.values()),"receipt_errors":errors,
  "scope":"2026","full_history_coverage":False,"PIT_certified":False,
  "performed_repair":False,"year_certified":False}
 (OUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 data=(json.dumps(report,ensure_ascii=False,sort_keys=True)+"\n").encode();h=sha(data)
 name="JARVIS_V095_2026_SOURCE_QA_"+SOURCE+"_"+os.getenv("GITHUB_RUN_ID","LOCAL")+"_"+h[:20]+".json"
 target=d.files().create(body={"name":name,"parents":[OPS]},
  media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/json",resumable=False),
  fields="id").execute()["id"]
 if sha(d.files().get_media(fileId=target).execute())!=h:raise RuntimeError("QA_DRIVE_READBACK_SHA")
 print(json.dumps({"source":SOURCE,"run_id":report["run_id"],"receipts":len(runs),
   "distinct_issues":len(issues),"read_errors":len(errors),"drive_id":target,"sha256":h,
   "full_year_certified":False},ensure_ascii=False))
 if errors:raise SystemExit(2)
if __name__=="__main__":main()
