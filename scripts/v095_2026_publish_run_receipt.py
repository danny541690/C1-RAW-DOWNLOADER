#!/usr/bin/env python3
"""2026 per-run durable Drive evidence. Does not certify market data."""
import datetime as dt,hashlib,io,json,os,pathlib,sys,time
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
PATHS=("v095_2026_price_incremental/result.json","v095_2026_source_archives/result.json",
"v095_2026_immediate_downstream/result.json","v095_2026_immediate_downstream/missing_indicators.json",
"annual_2026/report.json","v095_2026_equity_downstream/result.json",
"v095_2026_equity_downstream/lineage_receipt.json",
"v095_2025_equity_downstream/result.json","v095_2025_equity_downstream/lineage_receipt.json",
"v095_2025_four_source_inventory/result.json",
"v095_2025_source_archives/result.json","v095_2025_immediate_downstream/result.json",
"v095_2025_immediate_downstream/missing_indicators.json")
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
  data={}
  for p in PATHS:
    f=pathlib.Path(p)
    if not f.is_file():continue
    b=f.read_bytes()
    if len(b)>2_000_000:raise ValueError("RECEIPT_OVER_2MB:"+p)
    obj=json.loads(b)
    data[p]={"sha256":sha(b),"data":obj}
  year=int(os.getenv("V095_DATA_YEAR","2026"))
  if year not in (2025,2026):raise ValueError("RECEIPT_YEAR_OUT_OF_SCOPE")
  run_id=os.getenv("GITHUB_RUN_ID","LOCAL")
  lane=os.getenv("V095_RECEIPT_LANE","UNKNOWN").upper()
  source=os.getenv("V095_PRICE_SOURCE") or os.getenv("V095_BRONZE_SOURCE") or lane
  payload={"schema":"JARVIS_V095_2026_DURABLE_LANE_RECEIPT_R1",
    "run_id":run_id,"source":source,"lane":lane,
    "created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
    "source_results":data,"result_count":len(data),
    "result_absent":len(data)==0,"year_certified":False,"PIT_certified":False,
    "scope":str(year),"recovery":"REVIEW_MISSING_OR_FAILED_SOURCE_RESULTS"}
  raw=(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
  h=sha(raw);name=f"JARVIS_V095_{year}_RUN_RECEIPT_"+lane+"_"+source+"_"+run_id+"_"+h[:20]+".json"
  d=drive()
  q="'"+OPS+"' in parents and name = '"+name+"' and trashed = false"
  old=d.files().list(q=q,fields="files(id,name),nextPageToken",pageSize=100).execute()
  if old.get("nextPageToken") or len(old.get("files",[]))>1:raise RuntimeError("DUPLICATE_RUN_RECEIPTS")
  if old.get("files"):fid=old["files"][0]["id"];action="REUSED"
  else:
    fid=d.files().create(body={"name":name,"parents":[OPS],
     "description":"Immutable run evidence; candidate source and transforms, not annual release"},
     media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=False),
     fields="id").execute()["id"]
    action="CREATED"
  if sha(d.files().get_media(fileId=fid).execute())!=h:raise RuntimeError("RECEIPT_REMOTE_SHA_READBACK")
  pathlib.Path("v095_2026_run_receipt").mkdir(exist_ok=True)
  evidence={"run_id":run_id,"lane":lane,"source":source,"sha256":h,"drive_id":fid,
            "file_name":name,"action":action,"result_count":len(data),"readback":"PASS"}
  pathlib.Path("v095_2026_run_receipt/drive_receipt.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n")
  print(json.dumps(evidence,ensure_ascii=False))
if __name__=="__main__":sys.exit(main())
