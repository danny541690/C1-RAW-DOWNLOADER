"""JARVIS v0.95 isolated 7-source Matrix stage worker.
Artifacts only; no Google Drive writes, no PIT / production Gold approval.
"""
import argparse,io,json,hashlib,pathlib,urllib.request,datetime,time,os
import pyarrow as pa,pyarrow.parquet as pq,openpyxl

ENDPOINTS={
"TWSE":("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20261022&response=json","json",4000000),
"TPEx":("https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=2026%2F10%2F22&response=json","json",4000000),
"MOPS":("https://openapi.twse.com.tw/v1/opendata/t187ap05_L","json",8000000),
"NDC":("https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx","xlsx",4000000),
"TAIFEX":("https://openapi.taifex.com.tw/v1/PutCallRatio","json",6000000),
"TDCC":("https://openapi.tdcc.com.tw/v1/opendata/1-5","json",20000000),
"FinMind":("https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=1101&start_date=2026-10-22&end_date=2026-10-22","json",4000000)
}
hashof=lambda b:hashlib.sha256(b).hexdigest()
def verify(source,kind,raw):
 if kind=="xlsx":
  if not raw.startswith(b"PK\\x03\\x04"):raise ValueError("INVALID_XLSX_MAGIC")
  w=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
  sheets=len(w.sheetnames);w.close()
  if not sheets:raise ValueError("EMPTY_WORKBOOK")
  return {"sheets":sheets,"records":None}
 p=json.loads(raw.decode("utf-8-sig"))
 if source in ("TWSE","TPEx"):
  if not isinstance(p,dict) or not isinstance(p.get("tables"),list):raise ValueError("TABLE_SCHEMA")
  n=sum(len(t.get("data",[])) for t in p["tables"] if isinstance(t,dict) and isinstance(t.get("data"),list))
 elif source=="FinMind":
  if not isinstance(p,dict) or p.get("status")!=200 or not isinstance(p.get("data"),list):raise ValueError("FINMIND_SCHEMA")
  n=len(p["data"])
 else:
  if not isinstance(p,list) or not p or not isinstance(p[0],dict):raise ValueError("LIST_SCHEMA")
  if source=="MOPS" and not ("公司代號" in p[0] and "資料年月" in p[0]):raise ValueError("MOPS_SCHEMA")
  if source=="TDCC" and not any(x in " ".join(p[0]) for x in ("證券代號","股票代號","持股","集保戶","股權")):raise ValueError("TDCC_SCHEMA")
  n=len(p)
 if not n:raise ValueError("NO_SOURCE_ROWS")
 return {"records":n}
def run(stage,source):
 root=pathlib.Path("matrix_stage")/source
 root.mkdir(parents=True,exist_ok=True)
 previous=json.loads((root/"manifest.json").read_text()) if (root/"manifest.json").exists() else {}
 record={"source":source,"stage":stage,"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
   "production_write":False,"historical_v093_migration":False,"historical_pit_approved":False,
   "gold_investment_approved":False,"status":"BLOCKED"}
 try:
  if stage=="bronze":
   url,kind,cap=ENDPOINTS[source]
   q=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-v095-Matrix-qa","Accept":"application/json,*/*"})
   t=time.monotonic()
   with urllib.request.urlopen(q,timeout=35) as conn:
    raw=conn.read(cap+1)
    if len(raw)>cap:raise ValueError("SOURCE_PAYLOAD_CAP_EXCEEDED")
   stats=verify(source,kind,raw)
   (root/"raw.bin").write_bytes(raw)
   if hashof((root/"raw.bin").read_bytes())!=hashof(raw):raise ValueError("RAW_DISK_READBACK")
   record.update(status="PASS_BOUNDED_BRONZE",sha256=hashof(raw),bytes=len(raw),mime=kind,
     fetch_seconds=round(time.monotonic()-t,3),**stats)
  elif stage=="silver":
   raw=(root/"raw.bin").read_bytes()
   if previous.get("stage")!="bronze" or not previous.get("status","").startswith("PASS") or hashof(raw)!=previous.get("sha256"):
    raise ValueError("BRONZE_DEPENDENCY_SHA_FAILED")
   content=pa.table({"source":[source],"raw_sha256":[hashof(raw)],"raw_payload":[raw],"pit_verified":[False]})
   out=root/"candidate.parquet";pq.write_table(content,out,compression="zstd")
   rows=pq.read_table(out).to_pylist()
   if len(rows)!=1 or rows[0]["raw_payload"]!=raw or rows[0]["raw_sha256"]!=hashof(raw):
    raise ValueError("PARQUET_ROUNDTRIP_FAILED")
   record.update(status="PASS_LOSSLESS_SILVER_NOT_NORMALIZED",source_sha256=hashof(raw),
     sha256=hashof(out.read_bytes()),bytes=out.stat().st_size,records=previous.get("records"),sheets=previous.get("sheets"))
  elif stage=="gold":
   file=root/"candidate.parquet";blob=file.read_bytes()
   if previous.get("stage")!="silver" or not previous.get("status","").startswith("PASS") or hashof(blob)!=previous.get("sha256"):
    raise ValueError("SILVER_DEPENDENCY_SHA_FAILED")
   rows=pq.read_table(file).to_pylist()
   if len(rows)!=1 or rows[0]["source"]!=source or rows[0]["pit_verified"] is not False:
    raise ValueError("SILVER_QA_FAILED")
   metric={"metric":"source_payload_integrity_QA_ONLY","value":True,"source":source,
      "silver_sha256":hashof(blob),"historical_pit":False,"production_signal":False}
   out=root/"gold_qa.json";out.write_text(json.dumps(metric))
   if json.loads(out.read_text())!=metric:raise ValueError("GOLD_QA_READBACK")
   record.update(status="PASS_GOLD_QUALITY_METADATA_ONLY",sha256=hashof(out.read_bytes()),
     silver_sha256=hashof(blob))
  else:raise ValueError("UNKNOWN_STAGE")
 except Exception as e:
  record["error"]=type(e).__name__+":"+str(e)[:220]
 (root/"manifest.json").write_text(json.dumps(record,ensure_ascii=False,indent=2))
 print("MATRIX",source,stage,record["status"],record.get("error",""),flush=True)
 if not record["status"].startswith("PASS"):raise SystemExit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",choices=list(ENDPOINTS),required=True)
 p.add_argument("--stage",choices=["bronze","silver","gold"],required=True)
 a=p.parse_args();run(a.stage,a.source)
