#!/usr/bin/env python3
"""2026 source/QA/transform evidence rollup directly from immutable Drive run receipts.
Reads only records persisted by each lane; does not mutate market data or run repair.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
OUT=pathlib.Path("v095_2026_cross_lane_ledger")
PREFIX="JARVIS_V095_2026_RUN_RECEIPT_"
def sha(b):return hashlib.sha256(b).hexdigest()
def list_pages(d,q):
 out=[];page=None
 while True:
  x=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,createdTime,size)",
    pageSize=500,pageToken=page).execute()
  if x.get("incompleteSearch"):raise ValueError("DRIVE_SEARCH_INCOMPLETE")
  out.extend(x.get("files",[]))
  if len(out)>6000:raise ValueError("RECEIPT_LIST_OVER_BUDGET")
  page=x.get("nextPageToken")
  if not page:return out
def event(source,lane,run,kind,reason,period=None,attempts=None,state=None):
 return {"source":source,"lane":lane,"run_id":run,"type":kind,"reason":str(reason)[:220],
  "period":period,"attempts":attempts,"status":state or "REQUIRES_QA",
  "next_action":"TARGETED_REVALIDATE_OR_ADAPTER_CHANGE;NO_GLOBAL_REDOWNLOAD"}
def collect(obj,source,lane,run):
 issues=[]
 for item in obj.get("failed",[]) if isinstance(obj.get("failed"),list) else []:
  if isinstance(item,dict):issues.append(event(source,lane,run,"FAILED",item.get("message"),item.get("date") or item.get("month"),item.get("quarantined_after_cycles"),item.get("state")))
 for item in obj.get("blocked",[]) if isinstance(obj.get("blocked"),list) else []:
  if isinstance(item,dict):issues.append(event(source,lane,run,"BLOCKED",item.get("reason") or item.get("state"),item.get("month"),item.get("attempts"),item.get("state")))
 if obj.get("retry_queue_length"):
  issues.append(event(source,lane,run,"RETRY_QUEUE",obj["retry_queue_length"],state="RETRY_PENDING"))
 for reason in obj.get("blocking_causes",[]) if isinstance(obj.get("blocking_causes"),list) else []:
  issues.append(event(source,lane,run,"ANNUAL_GATE",reason,state="BLOCKS_CERTIFICATION"))
 if obj.get("verified_2026_full_year_complete") is False:
  issues.append(event(source,lane,run,"YEAR_NOT_CERTIFIED","Independent annual QA incomplete",state="NOT_CERTIFIED"))
 return issues
def publish(d,b):
 h=sha(b);name="JARVIS_V095_2026_CROSS_LANE_LEDGER_"+h[:24]+".json"
 rows=list_pages(d,"'"+OPS+"' in parents and name = '"+name+"' and trashed = false")
 if len(rows)>1:raise ValueError("MULTIPLE_SAME_SHA")
 if rows:fid=rows[0]["id"];action="REUSED"
 else:
  fid=d.files().create(body={"name":name,"parents":[OPS]},
   media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json",resumable=False),
   fields="id").execute()["id"]
  action="CREATED"
 if sha(d.files().get_media(fileId=fid).execute())!=h:raise ValueError("LEDGER_SHA_READBACK")
 return {"name":name,"drive_id":fid,"sha256":h,"action":action,"sha_readback":"PASS"}
def main():
 OUT.mkdir(exist_ok=True)
 d=drive()
 files=list_pages(d,"'"+OPS+"' in parents and name contains '"+PREFIX+"' and trashed = false")
 files=sorted((f for f in files if f["name"].startswith(PREFIX)),key=lambda f:f.get("createdTime",""),reverse=True)
 seen=collections.Counter();runs=[];issues=[];read_errors=[]
 for item in files:
  # Recent 3 receipts per lane/source, safe bounded readback and no full history scan.
  parts=item["name"].split("_")
  if len(runs)>=45:break
  try:
   raw=d.files().get_media(fileId=item["id"]).execute()
   h=sha(raw)
   if not item["name"].endswith("_"+h[:20]+".json"):raise ValueError("RECEIPT_FILENAME_SHA_MISMATCH")
   data=json.loads(raw)
   if data.get("schema")!="JARVIS_V095_2026_DURABLE_LANE_RECEIPT_R1":raise ValueError("RECEIPT_SCHEMA_MISMATCH")
   key=(data["lane"],data["source"])
   if seen[key]>=3:continue
   seen[key]+=1
   stats={"run_id":data["run_id"],"lane":data["lane"],"source":data["source"],
     "receipt_sha256":h,"receipt_drive_id":item["id"],"source_result_count":data.get("result_count")}
   if data.get("result_absent"):
    issues.append(event(data["source"],data["lane"],data["run_id"],"MISSING_WORKFLOW_RESULT",
      "No JSON result generated in source job",state="INVESTIGATE_RUN"))
   for p,val in data.get("source_results",{}).items():
    obj=val.get("data")
    if isinstance(obj,dict):issues.extend(collect(obj,data["source"],data["lane"],data["run_id"]))
   runs.append(stats)
  except Exception as exc:
   read_errors.append({"drive_file_id":item["id"],"error":type(exc).__name__+":"+str(exc)[:140]})
 report={"schema":"JARVIS_V095_2026_CROSS_LANE_LEDGER_R2","as_of":dt.datetime.now(dt.timezone.utc).isoformat(),
   "scope":"2026_only","read_only":True,"runs":runs,"issues":issues,"receipt_read_errors":read_errors,
   "missing_indicator_registry_not_yet_certified":True,"QA_repair_executed":False,
   "FinMind_gapfill_executed":False,"year_certified":False,
   "status":"PARTIAL_RECENT_RECEIPT_RECONCILIATION_NOT_FULL_HISTORY"}
 b=(json.dumps(report,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
 (OUT/"ledger.json").write_bytes(b)
 result=publish(d,b)
 (OUT/"drive_receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({"run_id":os.getenv("GITHUB_RUN_ID"),"receipts":len(runs),"issues":len(issues),
  "errors":len(read_errors),"Drive":result,"formal_completion":False},ensure_ascii=False))
if __name__=="__main__":main()
