"""Seven-source actual bounded Bronze, lossless Parquet candidate Silver, metadata-only Gold QA."""
import io,json,hashlib,pathlib,datetime,urllib.request
import pyarrow as pa,pyarrow.parquet as pq,openpyxl
from tests.v095_r19_live_three_layer_candidates import NDC
ROOT=pathlib.Path("v095_seven_layer_candidate");ROOT.mkdir(exist_ok=True)
SOURCES=[
("TWSE","https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20261022&response=json","json",4000000),
("TPEx","https://www.tpex.org.tw/www/zh-tw/margin/sbl?date=2026%2F10%2F22&response=json","json",4000000),
("MOPS","https://openapi.twse.com.tw/v1/opendata/t187ap05_L","json",8000000),
("NDC",NDC,"xlsx",4000000),
("TAIFEX","https://openapi.taifex.com.tw/v1/PutCallRatio","json",6000000),
("TDCC","https://openapi.tdcc.com.tw/v1/opendata/1-5","json",20000000),
("FinMind","https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id=1101&start_date=2026-10-22&end_date=2026-10-22","json",4000000)]
sha=lambda b:hashlib.sha256(b).hexdigest()
def fetch(url,limit):
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-v095-seven-source-bounded-QA","Accept":"application/json,*/*"})
 with urllib.request.urlopen(req,timeout=35) as r:
  b=r.read(limit+1)
  if len(b)>limit:raise ValueError("TRUNCATED_BRONZE_CAP")
  return b
def validate(src,kind,raw):
 if kind=="xlsx":
  if not raw.startswith(b"PK\x03\x04"):raise ValueError("BAD_XLSX")
  wb=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
  n=len(wb.sheetnames);wb.close()
  if not n:raise ValueError("EMPTY_XLSX")
  return None
 p=json.loads(raw.decode("utf-8-sig"))
 if src in ("TWSE","TPEx"):
  if not isinstance(p,dict) or not isinstance(p.get("tables"),list):raise ValueError("TABLE_SCHEMA")
  n=sum(len(t.get("data",[])) for t in p["tables"] if isinstance(t,dict) and isinstance(t.get("data"),list))
 elif src=="FinMind":
  if not isinstance(p,dict) or p.get("status")!=200 or not isinstance(p.get("data"),list):raise ValueError("FINMIND_SCHEMA")
  n=len(p["data"])
 else:
  if not isinstance(p,list) or not p or not isinstance(p[0],dict):raise ValueError("LIST_SCHEMA")
  if src=="MOPS" and not ("公司代號" in p[0] and "資料年月" in p[0]):raise ValueError("MOPS_SCHEMA")
  if src=="TDCC" and not any(x in " ".join(p[0]) for x in ("證券代號","股票代號","持股","集保戶","股權")):raise ValueError("TDCC_SCHEMA")
  n=len(p)
 if not n:raise ValueError("EMPTY_SOURCE")
 return n
report={"schema":"V095_SEVEN_THREE_LAYER_QA_V1","historical_v093_migration":False,"production_writes":False,"gold_investment_approved":False,"rows":[]}
for src,url,kind,limit in SOURCES:
 row={"source":src,"bronze":"BLOCKED","silver":"BLOCKED","gold":"BLOCKED","historical_PIT":False}
 report["rows"].append(row);folder=ROOT/src;folder.mkdir(exist_ok=True)
 try:
  raw=fetch(url,limit);n=validate(src,kind,raw)
  b=folder/("bronze."+kind);b.write_bytes(raw)
  if sha(b.read_bytes())!=sha(raw):raise ValueError("BRONZE_SHA")
  row.update(bronze="PASS_BOUNDED",source_sha256=sha(raw),bytes=len(raw),record_count=n)
  table=pa.table({"source":[src],"raw_sha256":[sha(raw)],"raw_payload":[raw],"pit_verified":[False]})
  silver=folder/"silver_lossless_candidate.parquet";pq.write_table(table,silver,compression="zstd")
  back=pq.read_table(silver).to_pylist()
  if len(back)!=1 or back[0]["raw_payload"]!=raw:raise ValueError("SILVER_ROUNDTRIP")
  row.update(silver="PASS_LOSSLESS_NOT_NUMERIC_STANDARDIZED",parquet_sha256=sha(silver.read_bytes()))
  g={"metric":"source_record_count_QA_ONLY","value":n,"source":src,"source_sha256":sha(raw),"PIT":False,"release":False}
  file=folder/"gold_qa_only.json";file.write_text(json.dumps(g))
  if json.loads(file.read_text())!=g:raise ValueError("GOLD_READBACK")
  row["gold"]="PASS_QA_METADATA_NOT_STOCK_INDICATORS"
 except Exception as e:row["error"]=type(e).__name__+":"+str(e)[:220]
 print("THREE_LAYER",src,row["bronze"],row["silver"],row["gold"],row.get("error",""),flush=True)
 (ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
report.update(bronze_pass=sum(x["bronze"].startswith("PASS") for x in report["rows"]),
 silver_pass=sum(x["silver"].startswith("PASS") for x in report["rows"]),
 gold_qa_pass=sum(x["gold"].startswith("PASS") for x in report["rows"]))
report["status"]="PASS_7_SOURCE_QA_ONLY" if report["bronze_pass"]==report["silver_pass"]==report["gold_qa_pass"]==7 else "PARTIAL_BLOCKED"
(ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print("THREE_LAYER_SUMMARY",json.dumps({k:v for k,v in report.items() if k!="rows"}),flush=True)
if report["status"]!="PASS_7_SOURCE_QA_ONLY":raise SystemExit(1)
