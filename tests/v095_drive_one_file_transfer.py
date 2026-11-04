"""Bounded legacy TDCC SHA-pinned candidate migration. No Bronze, Silver or Gold writes."""
import json,io,hashlib
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.annual_actual_firstpass import Drive,service
PILOT="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"
OUT=Path("v095_real_drive_transfer")
OUT.mkdir(exist_ok=True)
def sha(x):return hashlib.sha256(x).hexdigest()
def save(r):(OUT/"report.json").write_text(json.dumps(r,indent=2,ensure_ascii=False))
catalog=json.loads(Path("config/v095_tdcc_small_batch.json").read_text())
items=catalog["rows"]
if len(items)>24 or len(items)!=len({x["file_id"] for x in items}):raise ValueError("BATCH_LIMIT_OR_DUPLICATE")
result={"stage":"CANDIDATE_ONLY","destination_folder":PILOT,"production_bronze":False,"production_silver":False,"status":"BLOCKED","files":[]}
save(result)
d=Drive(service())
folder=d.api.files().get(fileId=PILOT,fields="id,name,mimeType,trashed").execute()
if folder.get("trashed") or folder.get("name")!="CANDIDATE":raise ValueError("DEST_SCOPE_MISMATCH")
for x in items:
 row={"security_id":x["security_id"],"date":x["date"],"source":x["file_id"],"status":"BLOCKED"}
 result["files"].append(row)
 try:
  security=x["security_id"];date=x["date"];source=x["file_id"];expected=x["sha256"]
  if x["source"]!="TDCC" or len(expected)!=64:raise ValueError("MANIFEST_INVALID")
  meta=d.api.files().get(fileId=source,fields="id,name,size,mimeType,trashed").execute()
  if meta.get("trashed") or meta.get("mimeType")!="text/html" or int(meta.get("size",0))>2000000:raise ValueError("SOURCE_SCOPE_OR_SIZE")
  raw=d.call(lambda:d.api.files().get_media(fileId=source))
  if sha(raw)!=expected or b"<table" not in raw.lower():raise ValueError("RAW_SHA_OR_TABLE")
  table=pa.table({"source":["TDCC"],"security_id":[security],"date":[date],"legacy_file":[source],"source_sha256":[expected],"raw_html":[raw],"pit_verified":[False]})
  buffer=io.BytesIO();pq.write_table(table,buffer,compression="zstd");payload=buffer.getvalue()
  back=pq.read_table(io.BytesIO(payload)).to_pylist()
  if len(back)!=1 or back[0]["raw_html"]!=raw:raise ValueError("PARQUET_ROUNDTRIP")
  name="pilot_TDCC_"+date.replace("-","")+"_"+security+"_immutable.candidate.parquet"
  d.put(PILOT,name,payload,"application/octet-stream",overwrite=False)
  readback=d.read(PILOT,name)
  if sha(readback)!=sha(payload):raise ValueError("DRIVE_SHA_READBACK")
  d.put(PILOT,name,payload,"application/octet-stream",overwrite=False)
  row.update(status="PASS",original_sha256=expected,parquet_sha256=sha(payload),bytes=len(raw),parquet_bytes=len(payload),idempotent=True)
 except Exception as e:row["error"]=type(e).__name__+":"+str(e)[:200]
 save(result)
 print("CANDIDATE",security,date,row["status"],flush=True)
result["pass_count"]=sum(x["status"]=="PASS" for x in result["files"])
result["fail_count"]=len(items)-result["pass_count"]
result["status"]="PASS" if result["fail_count"]==0 else "PARTIAL_FAILURE"
save(result)
print(json.dumps({k:v for k,v in result.items() if k!="files"}),flush=True)
if result["fail_count"]:raise SystemExit(1)
