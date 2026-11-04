"""Bounded 1-file v0.93 -> v0.95 Drive candidate Parquet roundtrip. No production folders."""
import json,io,hashlib,datetime
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
from googleapiclient.http import MediaIoBaseUpload
from scripts.annual_actual_firstpass import Drive,service

SOURCE="1JGfdHn04dFqfn06DGAYInwV9pKskCPlu"
PILOT="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"
EXPECTED="bbc45508223183dcf903ec8e73072a5b25608cb20a6654e660a5864c69dce616"
NAME="pilot_TDCC_20251205_6556_immutable.candidate.parquet"
OUT=Path("v095_real_drive_transfer")
OUT.mkdir(exist_ok=True)
result={"stage":"CANDIDATE_ONLY","source":SOURCE,"destination_folder":PILOT,"production_bronze":False,"production_silver":False,"status":"BLOCKED"}
def sha(b):return hashlib.sha256(b).hexdigest()
try:
 d=Drive(service())
 meta=d.api.files().get(fileId=SOURCE,fields="id,name,size,mimeType,trashed").execute()
 folder=d.api.files().get(fileId=PILOT,fields="id,name,mimeType,trashed").execute()
 if folder.get("trashed") or folder.get("name")!="CANDIDATE" or meta.get("mimeType")!="text/html":raise ValueError("SCOPE_OR_SOURCE_MISMATCH")
 raw=d.call(lambda:d.api.files().get_media(fileId=SOURCE))
 if sha(raw)!=EXPECTED or len(raw)>2000000:raise ValueError("RAW_SHA_OR_SIZE")
 if b"<table" not in raw.lower():raise ValueError("NOT_TDCC_TABLE")
 table=pa.table({"source":["TDCC"],"security_id":["6556"],"date":["2025-12-05"],"legacy_file":[SOURCE],"source_sha256":[EXPECTED],"raw_html":[raw],"pit_verified":[False]})
 buf=io.BytesIO();pq.write_table(table,buf,compression="zstd");payload=buf.getvalue()
 rec=pq.read_table(io.BytesIO(payload)).to_pylist()
 if len(rec)!=1 or rec[0]["raw_html"]!=raw:raise ValueError("PARQUET_ROUNDTRIP")
 d.put(PILOT,NAME,payload,"application/octet-stream",overwrite=False)
 saved=d.read(PILOT,NAME)
 if sha(saved)!=sha(payload):raise ValueError("DRIVE_DEST_SHA")
 d.put(PILOT,NAME,payload,"application/octet-stream",overwrite=False)
 result.update(status="PASS",original_sha256=EXPECTED,parquet_sha256=sha(payload),bytes=len(raw),parquet_bytes=len(payload),idempotent=True)
except Exception as e:result["error"]=type(e).__name__+":"+str(e)[:250]
(OUT/"report.json").write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
if result["status"]!="PASS":raise SystemExit(1)
