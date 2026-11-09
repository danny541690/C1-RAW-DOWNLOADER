#!/usr/bin/env python3
"""v0.96 P0: encode SOURCE MANIFEST metadata to ZSTD Parquet; never market values."""
import hashlib,io,json,pathlib
import pyarrow as pa,pyarrow.parquet as pq
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_2026_annual_consolidated import service
OUT=pathlib.Path("v096_run")
def sha(raw):return hashlib.sha256(raw).hexdigest()
def main():
 manifest=json.loads((OUT/"manifest.json").read_text())
 rows=manifest["rows"]
 # Explicit field order prevents accidental raw data/vintage promotion.
 allowed=("legacy_version","source","month_folder","original_drive_file_id",
  "original_folder_id","original_name","original_mime_type","size_bytes",
  "drive_md5","source_format","source_sha256","sha_status",
  "source_native_schema_verified","raw_v096_storage","source_publication_time",
  "historical_pit_verified","market_data_rewritten","original_file_deleted")
 table=pa.Table.from_pylist([{k:r.get(k) for k in allowed} for r in rows],
  schema=pa.schema([(k,pa.int64() if k=="size_bytes"
    else pa.bool_() if k in ("source_native_schema_verified","historical_pit_verified",
     "market_data_rewritten","original_file_deleted")
    else pa.string()) for k in allowed]))
 buffer=io.BytesIO();pq.write_table(table,buffer,compression="zstd")
 blob=buffer.getvalue()
 verification=pq.read_table(io.BytesIO(blob))
 if verification.num_rows!=len(rows) or verification.num_columns!=len(allowed):
  raise ValueError("V096_METADATA_PARQUET_READBACK_BAD")
 OUT.mkdir(exist_ok=True)
 (OUT/"source_manifest.parquet").write_bytes(blob)
 state=json.loads((OUT/"execution.json").read_text())
 control=state["control_id"];d=service()
 name="V096_P0_INDEX_METADATA_"+sha(blob)[:24]+".parquet"
 result=d.files().list(q="'"+control+"' in parents and name='"+name+"' and trashed=false",
   fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=100).execute()
 if result.get("incompleteSearch") or result.get("nextPageToken"):
  raise RuntimeError("V096_METADATA_INDEX_NAME_LIST_UNVERIFIED")
 found=result.get("files",[])
 if len(found)>1:raise ValueError("V096_DUPLICATE_MANIFEST_OBJECT")
 if found: fid=found[0]["id"];action="REUSED"
 else:
  fid=d.files().create(body={"name":name,"parents":[control]},
       media_body=MediaIoBaseUpload(io.BytesIO(blob),
          mimetype="application/octet-stream",resumable=False),
       fields="id").execute()["id"]
  action="CREATED"
 remote=d.files().get_media(fileId=fid).execute()
 if sha(remote)!=sha(blob):raise ValueError("V096_PARQUET_SHA_READBACK")
 report={"status":"PASS_SOURCE_METADATA_PARQUET_ONLY",
   "rows":len(rows),"sha256":sha(blob),"drive_id":fid,"action":action,
   "readback":"PASS","raw_stock_data_converted":False,"PIT":False}
 (OUT/"parquet_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
