"""Seven-source SHA+semantic provenance Drive migration candidate; fail-closed.
No production Bronze/Silver/Gold writes; one file per source, independent Matrix.
"""
import argparse,csv,datetime,hashlib,io,json,pathlib,time,zipfile
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.annual_actual_firstpass import Drive,service
DEST="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"
ALLOWED={"TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"}
sha=lambda b:hashlib.sha256(b).hexdigest()
def inspect(src,fmt,data):
 if fmt=="html":
  text=data.decode("utf-8","replace").lower()
  if "<table" not in text or len(data)<500:raise ValueError("NOT_SOURCE_HTML_TABLE")
  return {"bytes":len(data),"table_markup":True}
 if fmt=="csv":
  text=data[:100000].decode("utf-8-sig","replace")
  rows=list(csv.reader(io.StringIO(text)))
  if len(rows)<3 or max(map(len,rows[:3]))<2:raise ValueError("NOT_DATA_CSV")
  return {"bytes":len(data),"sample_rows":len(rows),"fields":max(map(len,rows[:3]))}
 if fmt=="json":
  obj=json.loads(data.decode("utf-8-sig"))
  if not isinstance(obj,(dict,list)) or len(obj)==0:raise ValueError("EMPTY_JSON")
  return {"bytes":len(data),"top_level":type(obj).__name__,"top_keys":list(obj)[:8] if isinstance(obj,dict) else []}
 if fmt=="zip":
  with zipfile.ZipFile(io.BytesIO(data)) as z:
   names=z.namelist()
   if not names or len(names)>2000:raise ValueError("ZIP_INDEX_INVALID")
   if z.testzip():raise ValueError("ZIP_CRC_MISMATCH")
   candidates=[i for i in z.infolist() if not i.is_dir() and i.file_size>=300 and i.filename.lower().endswith((".csv",".json",".html",".xlsx",".parquet"))]
   if not candidates:raise ValueError("ZIP_NO_SUBSTANTIVE_SOURCE_DATA")
   if any(i.file_size>8000000 or (i.compress_size and i.file_size/i.compress_size>200) for i in candidates):raise ValueError("ZIP_EXPANSION_LIMIT")
   return {"bytes":len(data),"zip_members":len(names),"data_members":len(candidates),"first_data_name":candidates[0].filename[:120]}
 raise ValueError("UNKNOWN_FORMAT")
def main(source):
 cfg=json.loads(pathlib.Path("config/v095_seven_source_drive_probe.json").read_text())
 items=[v for v in cfg["items"] if v["source"]==source]
 if len(items)!=1 or source not in ALLOWED:raise ValueError("INVALID_SOURCE_MANIFEST")
 it=items[0];out=pathlib.Path("v095_seven_drive_stress")/source;out.mkdir(parents=True,exist_ok=True)
 result={"source":source,"period_folder":it["folder_period"],"legacy_file_id":it["file_id"],
 "status":"BLOCKED","bronze_sha_pass":False,"silver_lossless_pass":False,
 "gold_pit_verified":False,"historical_period_verified":False,"official_source_semantics_verified":False,
 "production_write":False,"destination":"CANDIDATE_ONLY"}
 def save(): (out/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
 save();start=time.monotonic()
 try:
  d=Drive(service())
  f=d.api.files().get(fileId=DEST,fields="id,name,mimeType,trashed").execute()
  if f["name"]!="CANDIDATE" or f.get("trashed"):raise ValueError("DEST_SCOPE_FAILED")
  meta=d.api.files().get(fileId=it["file_id"],fields="id,name,mimeType,size,trashed").execute()
  if meta.get("trashed") or int(meta.get("size",0))>1500000:raise ValueError("SOURCE_META_OR_CAP")
  data=d.call(lambda:d.api.files().get_media(fileId=it["file_id"]))
  if len(data)<it["expected_min_bytes"]:raise ValueError("SOURCE_TOO_SMALL")
  expected=it.get("expected_sha256")
  if expected and sha(data)!=expected:raise ValueError("SOURCE_SHA_MISMATCH")
  result["raw_sha256"]=sha(data);result["raw_bytes"]=len(data)
  stats=inspect(source,it["format"],data)
  result.update(bronze_sha_pass=True,structural_check=stats)
  table=pa.table({"source":[source],"source_file_id":[it["file_id"]],"folder_period":[it["folder_period"]],
      "source_sha256":[sha(data)],"raw_payload":[data],"historical_pit_verified":[False],
      "semantic_normalization_approved":[False]})
  buffer=io.BytesIO();pq.write_table(table,buffer,compression="zstd")
  candidate=buffer.getvalue();back=pq.read_table(io.BytesIO(candidate)).to_pylist()
  if len(back)!=1 or back[0]["raw_payload"]!=data or back[0]["source_sha256"]!=sha(data):raise ValueError("LOSSLESS_PARQUET_MISMATCH")
  result.update(silver_lossless_pass=True,candidate_bytes=len(candidate),candidate_sha256=sha(candidate))
  name="v095_probe_"+source+"_"+it["folder_period"]+"_"+sha(data)[:16]+".candidate.parquet"
  found=d.find(DEST,name)
  d.put(DEST,name,candidate,"application/octet-stream",overwrite=False)
  if sha(d.read(DEST,name))!=sha(candidate):raise ValueError("DEST_READBACK_SHA")
  d.put(DEST,name,candidate,"application/octet-stream",overwrite=False)
  result.update(status="PASS_STRUCTURAL_CANDIDATE_NOT_SEMANTIC_APPROVAL",operation="SKIP_EXISTING" if found else "CREATED",idempotent_sha=True,name=name)
 except Exception as e:
  result["error"]=type(e).__name__+":"+str(e)[:180]
 result["elapsed_seconds"]=round(time.monotonic()-start,3);save()
 print("V095_SOURCE_STRESS",json.dumps(result,ensure_ascii=False),flush=True)
 if not result["status"].startswith("PASS"):raise SystemExit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",choices=sorted(ALLOWED),required=True)
 a=p.parse_args();main(a.source)
