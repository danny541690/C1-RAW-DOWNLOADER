"""Bounded 1-file v0.93 -> v0.95 Drive candidate Parquet roundtrip. No production folders."""
import json,io,hashlib,datetime
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from googleapiclient.http import MediaIoBaseUpload
from scripts.annual_actual_firstpass import Drive,service

SAMPLES=[("2025-12-05","6556","1JGfdHn04dFqfn06DGAYInwV9pKskCPlu","bbc45508223183dcf903ec8e73072a5b25608cb20a6654e660a5864c69dce616"),("2026-09-18","3189","1DAu8iSlsEoXw2S8__ZdtDOBovT9Q9aqQ","27411644b3a400c423b545147f3997864c4d2f0fd80dfca10ba4bedaa0677ee9")]
PILOT="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"


OUT=Path("v095_real_drive_transfer")
OUT.mkdir(exist_ok=True)
result={"stage":"CANDIDATE_ONLY","destination_folder":PILOT,"production_bronze":False,"production_silver":False,"status":"BLOCKED","files":[]}
def sha(b):return hashlib.sha256(b).hexdigest()
try:
 d=Drive(service())
 folder=d.api.files().get(fileId=PILOT,fields="id,name,mimeType,trashed").execute()
 if folder.get("trashed") or folder.get("name")!="CANDIDATE":raise ValueError("DEST_SCOPE_MISMATCH")
 for date,security,source,expected in SAMPLES:
  row={"security_id":security,"date":date,"source":source,"status":"BLOCKED"}
  result["files"].append(row)
  meta=d.api.files().get(fileId=source,fields="id,name,size,mimeType,trashed").execute()
  if meta.get("trashed") or meta.get("mimeType")!="text/html" or int(meta.get("size",0))>2000000:raise ValueError("SOURCE_SCOPE_MISMATCH_"+security)
  raw=d.call(lambda:d.api.files().get_media(fileId=source))
  if sha(raw)!=expected:raise ValueError("RAW_SHA_"+security)
  if b"<table" not in raw.lower():raise ValueError("NOT_TDCC_TABLE_"+security)
  table=pa.table({"source":["TDCC"],"security_id":[security],"date":[date],"legacy_file":[source],"source_sha256":[expected],"raw_html":[raw],"pit_verified":[False]})
  buf=io.BytesIO();pq.write_table(table,buf,compression="zstd");payload=buf.getvalue()
  rec=pq.read_table(io.BytesIO(payload)).to_pylist()
  if len(rec)!=1 or rec[0]["raw_html"]!=raw:raise ValueError("PARQUET_ROUNDTRIP_"+security)
  name="pilot_TDCC_"+date.replace("-","")+"_"+security+"_immutable.candidate.parquet"
  d.put(PILOT,name,payload,"application/octet-stream",overwrite=False)
  saved=d.read(PILOT,name)
  if sha(saved)!=sha(payload):raise ValueError("DRIVE_DEST_SHA_"+security)
  d.put(PILOT,name,payload,"application/octet-stream",overwrite=False)
  row.update(status="PASS",original_sha256=expected,parquet_sha256=sha(payload),bytes=len(raw),parquet_bytes=len(payload),idempotent=True)
 result["status"]="PASS"
except Exception as e:result["error"]=type(e).__name__+":"+str(e)[:250]
(OUT/"report.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
if result["status"]!="PASS":raise SystemExit(1)
