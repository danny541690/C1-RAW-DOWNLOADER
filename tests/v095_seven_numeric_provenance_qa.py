"""JARVIS v0.95 content-aware seven-source acceptance.
Read-only. Distinguish evidence of parseable numeric cells, provenance, period and PIT.
No mass migration or production writes.
"""
import argparse,collections,csv,decimal,hashlib,html.parser,io,json,pathlib,re,zipfile
from scripts.annual_actual_firstpass import Drive,service
ROOT=pathlib.Path("v095_content_qa")
sources=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
def sha(b):return hashlib.sha256(b).hexdigest()
def numeric(s):
 try:
  x=decimal.Decimal(str(s).strip().replace(",",""))
  return x.is_finite()
 except (decimal.InvalidOperation,ValueError,TypeError):return False
class Tables(html.parser.HTMLParser):
 def __init__(self):super().__init__();self.in_table=0;self.in_cell=0;self.cells=[];self.table_count=0
 def handle_starttag(self,tag,attrs):
  if tag=="table":self.in_table+=1;self.table_count+=1
  if tag in ("td","th") and self.in_table:self.in_cell+=1
 def handle_endtag(self,tag):
  if tag in ("td","th"):self.in_cell=max(0,self.in_cell-1)
  if tag=="table":self.in_table=max(0,self.in_table-1)
 def handle_data(self,d):
  if self.in_cell and len(self.cells)<10000 and d.strip():self.cells.append(d.strip())
def inspect_bytes(raw,filename):
 low=filename.lower()
 result={"format":"unknown","numeric_sample_count":0,"row_evidence":False}
 if low.endswith((".html",".htm",".raw")) and b"<table" in raw[:300000].lower():
  x=Tables();x.feed(raw[:800000].decode("utf-8","replace"))
  n=sum(numeric(a) for a in x.cells)
  result.update(format="html_table",table_count=x.table_count,cell_samples=len(x.cells),numeric_sample_count=n,row_evidence=bool(x.table_count and x.cells))
 elif low.endswith((".csv",".raw")):
  rows=list(csv.reader(io.StringIO(raw[:150000].decode("utf-8-sig","replace"))))
  n=sum(numeric(x) for row in rows[:300] for x in row)
  result.update(format="csv_candidate",sample_rows=len(rows),numeric_sample_count=n,row_evidence=len(rows)>2)
 elif low.endswith((".json",".raw")):
  try:
   obj=json.loads(raw.decode("utf-8-sig"))
   d=obj.get("data",[]) if isinstance(obj,dict) else obj
   if isinstance(d,list) and d:
    vals=[v for entry in d[:200] for v in (entry.values() if isinstance(entry,dict) else entry if isinstance(entry,list) else [])]
    result.update(format="json_records",sample_rows=len(d),numeric_sample_count=sum(numeric(x) for x in vals),row_evidence=True)
  except (ValueError,UnicodeDecodeError):pass
 return result
def run(src):
 items=json.loads(pathlib.Path("config/v095_seven_source_drive_probe.json").read_text())["items"]
 it=next(v for v in items if v["source"]==src)
 path=ROOT/src;path.mkdir(parents=True,exist_ok=True)
 report={"source":src,"folder_period_claim":it["folder_period"],"status":"BLOCKED",
 "qa_numeric_samples":0,"source_content_confirmed":False,"source_archive_sha_verified":False,
 "historical_period_verified":False,"pit_verified":False,"financial_unit_verified":False,
 "production_bronze_approved":False,"production_silver_approved":False,"production_gold_approved":False}
 try:
  d=Drive(service());raw=d.call(lambda:d.api.files().get_media(fileId=it["file_id"]))
  report["file_sha256"]=sha(raw)
  if it.get("expected_sha256") and it["expected_sha256"]!=sha(raw):raise ValueError("PINNED_SOURCE_SHA_MISMATCH")
  if src=="NDC":
   obj=json.loads(raw.decode("utf-8-sig"))
   if obj.get("source")!="NDC" or not isinstance(obj.get("tables"),list):raise ValueError("NDC_SOURCE_ROWS_SCHEMA")
   cells=[c for t in obj["tables"] for c in t.get("cells",[]) if isinstance(c,dict)]
   values=[c for c in cells if c.get("status")=="VALUE_PRESENT" and numeric(c.get("native_value"))]
   if not values:raise ValueError("NDC_NO_NUMERIC_CELLS")
   archive=obj.get("source_archive",{})
   origin=archive.get("file_id")
   if not origin or len(archive.get("sha256",""))!=64:raise ValueError("NDC_ARCHIVE_PROVENANCE_MISSING")
   workbook=d.call(lambda:d.api.files().get_media(fileId=origin))
   if sha(workbook)!=archive["sha256"] or not workbook.startswith(b"PK\x03\x04"):raise ValueError("NDC_ARCHIVE_SHA_OR_XLSX_MAGIC")
   with zipfile.ZipFile(io.BytesIO(workbook)) as z:
    if z.testzip():raise ValueError("NDC_ARCHIVE_XLSX_BAD_CRC")
   report.update(qa_numeric_samples=len(values),source_content_confirmed=True,
     source_archive_sha_verified=True,excel_archive_bytes=len(workbook),
     source_row_date_cells=sum(bool(t.get("source_date_cell")) for t in obj["tables"]),
     native_fields_sample=[{"name":v.get("field"),"native_value":v.get("native_value")} for v in values[:5]])
  elif it["format"]=="zip":
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    if z.testzip():raise ValueError("SOURCE_ZIP_CRC")
    candidate=[i for i in z.infolist() if not i.is_dir() and i.filename.endswith(".raw") and i.file_size>=200]
    evidence=[]
    for info in candidate[:12]:
     if info.file_size>3000000:continue
     dbytes=z.read(info)
     e=inspect_bytes(dbytes,info.filename)
     evidence.append({"member":info.filename,"bytes":info.file_size,**e})
    numeric_count=sum(e["numeric_sample_count"] for e in evidence)
    report.update(qa_numeric_samples=numeric_count,raw_members_inspected=len(evidence),raw_member_evidence=evidence,
                  source_content_confirmed=bool(evidence))
    if not evidence:raise ValueError("ZIP_NO_ACTUAL_RAW_MEMBERS")
  else:
   ext=it["format"]
   e=inspect_bytes(raw,"sample."+ext)
   report.update(qa_numeric_samples=e["numeric_sample_count"],content_evidence=e,source_content_confirmed=e["row_evidence"])
   if not e["row_evidence"]:raise ValueError("SOURCE_NO_PARSEABLE_CONTENT")
  if report["qa_numeric_samples"]<=0:raise ValueError("NO_NUMERIC_SAMPLES_NEEDS_PARSER")
  report["status"]="PASS_NUMERIC_SAMPLE_NOT_PIT"
 except Exception as exc:report["error"]=type(exc).__name__+":"+str(exc)[:230]
 (path/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print("CONTENT_QA",json.dumps({k:v for k,v in report.items() if k not in ("raw_member_evidence","native_fields_sample")},ensure_ascii=False),flush=True)
 if not report["status"].startswith("PASS"):raise SystemExit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",required=True,choices=sources)
 run(p.parse_args().source)
