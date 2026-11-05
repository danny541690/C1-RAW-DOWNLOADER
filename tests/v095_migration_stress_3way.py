"""Bounded three-way Google Drive v0.93 -> v0.95 migration load pilot.
Each shard owns disjoint SHA-pinned TDCC files. No production Bronze/Silver/Gold writes.
"""
import argparse,datetime,hashlib,io,json,pathlib,time
import pyarrow as pa,pyarrow.parquet as pq
from scripts.annual_actual_firstpass import Drive,service
DEST="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"
def sha(b):return hashlib.sha256(b).hexdigest()
def main(shard):
 p=pathlib.Path("v095_migration_stress")/f"shard_{shard}";p.mkdir(parents=True,exist_ok=True)
 manifest=json.loads(pathlib.Path("config/v095_tdcc_small_batch.json").read_text())
 rows=manifest["rows"]
 if len(rows)!=23 or manifest["status"]!="BASIC_VERIFIED_NOT_PIT_APPROVED":raise ValueError("UNEXPECTED_MANIFEST")
 selected=[x for i,x in enumerate(rows) if i%3==shard]
 report={"schema":"V095_PARALLEL_REAL_DRIVE_MIGRATION_STRESS_V1","shard":shard,"source":"TDCC",
 "stage":"CANDIDATE_ONLY","production_bronze":False,"production_silver":False,"production_gold":False,
 "source_files":len(selected),"passed":0,"failed":0,"created":0,"skipped":0,"source_bytes":0,
 "parquet_bytes":0,"elapsed_seconds":None,"per_file":[]}
 def save(): (p/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 save();start=time.monotonic()
 d=Drive(service());folder=d.api.files().get(fileId=DEST,fields="id,name,mimeType,trashed").execute()
 if folder.get("name")!="CANDIDATE" or folder.get("trashed") or folder.get("mimeType")!="application/vnd.google-apps.folder":raise ValueError("INVALID_CANDIDATE_SCOPE")
 for row in selected:
  t=time.monotonic();name="stress_v2_TDCC_"+row["date"].replace("-","")+"_"+row["security_id"]+"_"+row["sha256"][:12]+".candidate.parquet"
  record={"source_file":row["file_id"],"security":row["security_id"],"date":row["date"],"status":"BLOCKED"}
  report["per_file"].append(record)
  try:
   meta=d.api.files().get(fileId=row["file_id"],fields="id,size,mimeType,trashed").execute()
   if meta.get("mimeType")!="text/html" or meta.get("trashed") or int(meta.get("size",0))>2000000:raise ValueError("SOURCE_METADATA_FAILED")
   raw=d.call(lambda:d.api.files().get_media(fileId=row["file_id"]))
   if sha(raw)!=row["sha256"] or b"<table" not in raw.lower():raise ValueError("RAW_SHA_OR_TABLE_FAILED")
   tb=pa.table({"source":["TDCC"],"security_id":[row["security_id"]],"date":[row["date"]],
     "legacy_file":[row["file_id"]],"source_sha256":[row["sha256"]],"raw_html":[raw],"pit_verified":[False]})
   buf=io.BytesIO();pq.write_table(tb,buf,compression="zstd");payload=buf.getvalue()
   decoded=pq.read_table(io.BytesIO(payload)).to_pylist()
   if len(decoded)!=1 or decoded[0]["raw_html"]!=raw:raise ValueError("PARQUET_ROUNDTRIP")
   old=d.find(DEST,name)
   d.put(DEST,name,payload,"application/octet-stream",overwrite=False)
   readback=d.read(DEST,name)
   if sha(readback)!=sha(payload):raise ValueError("DRIVE_SHA_READBACK_FAILED")
   d.put(DEST,name,payload,"application/octet-stream",overwrite=False)
   report["created" if old is None else "skipped"]+=1
   report["source_bytes"]+=len(raw);report["parquet_bytes"]+=len(payload);report["passed"]+=1
   record.update(status="PASS",source_sha256=sha(raw),parquet_sha256=sha(payload),
    source_bytes=len(raw),parquet_bytes=len(payload),idempotent=True,remote_name=name)
  except Exception as ex:
   report["failed"]+=1;record["error"]=type(ex).__name__+":"+str(ex)[:230]
  record["elapsed_seconds"]=round(time.monotonic()-t,3)
  save()
  print("STRESS_FILE",shard,row["security_id"],record["status"],record["elapsed_seconds"],flush=True)
 report["elapsed_seconds"]=round(time.monotonic()-start,3)
 report["files_per_min"]=round(report["passed"]*60/max(.001,report["elapsed_seconds"]),2)
 report["status"]="PASS" if report["failed"]==0 and report["passed"]==len(selected) else "PARTIAL_FAILURE"
 save()
 print("STRESS_SHARD_SUMMARY",json.dumps({k:v for k,v in report.items() if k!="per_file"},ensure_ascii=False),flush=True)
 if report["status"]!="PASS":raise SystemExit(1)
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("--shard",type=int,choices=(0,1,2),required=True)
 args=parser.parse_args();main(args.shard)
