#!/usr/bin/env python3
"""2026 recent workflow receipt rollup: read only GitHub artifacts; SHA-archive in Drive.
This audit does not itself repair, redownload, PIT-certify or modify market data.
"""
import collections,datetime as dt,hashlib,io,json,os,pathlib,urllib.request,zipfile
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
REPO="danny541690/C1-RAW-DOWNLOADER"
OUT=pathlib.Path("v095_2026_cross_lane_ledger")
NAMES={**{f"JARVIS v0.95 2026 {s} independent Bronze and downstream gate":("D",s) for s in ("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")},
       **{f"JARVIS v0.95 2026 {s} independent Silver Gold candidate worker":("S_G",s) for s in ("MOPS","TDCC","TAIFEX","NDC")},
       "JARVIS v0.95 2026 independent hourly QA and gap ledger":("Q","ALL")}
def http(path,token,binary=False):
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+path,
       headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
       "X-GitHub-Api-Version":"2022-11-28","User-Agent":"JARVIS-v095-2026-evidence"})
    with urllib.request.urlopen(req,timeout=35) as r:b=r.read()
    return b if binary else json.loads(b)
def dig(blob):return hashlib.sha256(blob).hexdigest()
def publish(d,b):
    h=dig(b);name="JARVIS_V095_2026_CROSS_LANE_LEDGER_"+h[:24]+".json"
    q="'"+OPS+"' in parents and name = '"+name+"' and trashed = false"
    existing=d.files().list(q=q,fields="files(id,name),nextPageToken",pageSize=100).execute()
    if existing.get("nextPageToken"):raise RuntimeError("LEDGER_NAME_QUERY_PAGINATED")
    files=existing.get("files",[])
    if len(files)>1:raise RuntimeError("DUPLICATE_LEDGER_NAME")
    if files:fid=files[0]["id"];action="REUSED"
    else:
        fid=d.files().create(body={"name":name,"parents":[OPS],
              "description":"2026 recent GitHub source/downstream QA receipts; not full-year certified"},
              media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json",resumable=False),
              fields="id").execute()["id"]
        action="CREATED"
    read=d.files().get_media(fileId=fid).execute()
    if dig(read)!=h:raise RuntimeError("LEDGER_REMOTE_SHA_MISMATCH")
    return {"name":name,"drive_id":fid,"sha256":h,"action":action,"sha_readback":"PASS"}
def events(obj,lane,source,run_id,path):
    records=[]
    def add(typ,reason,part=None,attempts=None,status=None):
        records.append({"lane":lane,"source":source,"run_id":str(run_id),"artifact":path,
            "dataset_id":None,"period":part,"type":typ,"reason":str(reason)[:220],
            "attempts":attempts,"state":status or "REQUIRES_QA_REVIEW",
            "next_action":"REVALIDATE_PARTITION_ONLY_IF_NEW_SOURCE_OR_ADAPTER"})
    for item in (obj.get("failed",[]) if isinstance(obj.get("failed"),list) else []):
        add(item.get("kind","DOWNLOAD_OR_TRANSFORM_FAILURE"),item.get("message","UNKNOWN"),
            item.get("date") or item.get("month"),item.get("quarantined_after_cycles") or item.get("attempts"),
            item.get("state"))
    for item in (obj.get("blocked",[]) if isinstance(obj.get("blocked"),list) else []):
        if isinstance(item,dict):add("SOURCE_OR_CONVERSION_BLOCK",item.get("reason") or item.get("state"),item.get("month"),
                                 item.get("attempts"),item.get("state"))
    for item in (obj.get("blocked_details",[]) if isinstance(obj.get("blocked_details"),list) else []):
        if isinstance(item,dict):add("DOWNSTREAM_BLOCK",item.get("reason"),item.get("month"),item.get("attempts"))
    if obj.get("retry_queue_length"):
        add("OPEN_RETRY_QUEUE","RECORDED_SOURCE_RETRY_ITEMS",None,None,"RETRY_QUEUE_OPEN")
    if obj.get("blocking_causes"):
        for err in obj["blocking_causes"][:30]:
            add("ANNUAL_QA_GATE",json.dumps(err,ensure_ascii=False) if not isinstance(err,str) else err,
                None,None,"BLOCKS_FORMAL_YEAR_RELEASE")
    if obj.get("verified_2026_full_year_complete") is False:
        add("YEAR_NOT_CERTIFIED","YEAR_COMPLETE_FALSE",None,None,"NOT_CERTIFIED")
    return records
def main():
    OUT.mkdir(exist_ok=True)
    token=os.environ["GH_TOKEN"]
    runs=http("/actions/runs?per_page=100",token).get("workflow_runs",[])
    # Latest completed run per active workflow name, plus last 2 for changes
    grouped=collections.defaultdict(list)
    for r in runs:
        if r.get("name") in NAMES and r.get("status")=="completed" and len(grouped[r["name"]])<2:
            grouped[r["name"]].append(r)
    records=[];events_all=[];fetch_errors=[]
    for name,items in grouped.items():
        lane,source=NAMES[name]
        for run in items:
            rid=run["id"]
            rec={"run_id":rid,"lane":lane,"source":source,"conclusion":run.get("conclusion"),
                 "created_at":run.get("created_at"),"artifacts":[]}
            try:
                arts=http(f"/actions/runs/{rid}/artifacts?per_page=30",token).get("artifacts",[])[:5]
                for art in arts:
                    if art.get("expired"):continue
                    raw=http(f"/actions/artifacts/{art['id']}/zip",token,True)
                    if len(raw)>30_000_000:raise ValueError("ARTIFACT_OVER_SIZE_LIMIT")
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        for member in z.infolist():
                            if member.file_size>3_000_000 or not member.filename.endswith((".json",)) or ".." in pathlib.PurePosixPath(member.filename).parts:continue
                            if not member.filename.endswith(("result.json","report.json","missing_indicators.json")):continue
                            obj=json.loads(z.read(member))
                            if isinstance(obj,dict):
                                ev=events(obj,lane,source,rid,member.filename)
                                events_all.extend(ev)
                                rec["artifacts"].append({"name":member.filename,"sha256":dig(z.read(member)),
                                  "issue_events":len(ev)})
            except Exception as ex:
                fetch_errors.append({"run_id":rid,"source":source,"type":type(ex).__name__,"message":str(ex)[:130]})
            records.append(rec)
    output={"schema":"JARVIS_V095_2026_CROSS_LANE_LEDGER_R1",
      "created_at":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":"2026","read_only":True,
      "source_run_receipts":records,"issues":events_all,"artifact_fetch_errors":fetch_errors,
      "repair_executed":False,"finmind_gapfill_executed":False,"full_year_certified":False,
      "notes":"Bounded latest 2 per workflow only; not exhaustive historical defect ledger or complete dataset denominator"}
    blob=(json.dumps(output,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    (OUT/"ledger.json").write_bytes(blob)
    result=publish(drive(),blob)
    (OUT/"drive_receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"run_id":os.environ.get("GITHUB_RUN_ID"),"receipt_runs":len(records),
         "issues":len(events_all),"artifact_errors":len(fetch_errors),"Drive":result,
         "year_certified":False},ensure_ascii=False))
if __name__=="__main__":main()
