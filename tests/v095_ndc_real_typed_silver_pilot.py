"""Real NDC 2000-01 v093 native cells -> typed v095 candidate Silver, isolated.
Provenance + identity and unit preservation. No PIT approval and no Drive writes.
"""
import datetime,decimal,hashlib,io,json,pathlib,re
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.annual_actual_firstpass import Drive,service
ROOT=pathlib.Path("v095_ndc_typed_candidate");ROOT.mkdir(exist_ok=True)
SRC="1Ty74zKGSivXNHmA3WDG4VjeOKmWpA3n4"
digest=lambda x:hashlib.sha256(x).hexdigest()
report={"stage":"ISOLATED_TYPED_SILVER_CANDIDATE","source":"NDC","file_id":SRC,
 "status":"BLOCKED","production_bronze":False,"production_silver":False,
 "production_gold":False,"pit_verified":False,"historical_vintage_verified":False,
 "amount_unit_standardized":False}
try:
 d=Drive(service());raw=d.call(lambda:d.api.files().get_media(fileId=SRC))
 obj=json.loads(raw.decode("utf-8-sig"))
 if obj.get("source")!="NDC" or obj.get("month")!="2000-01" or not isinstance(obj.get("tables"),list):raise ValueError("NDC_MONTH_SOURCE_OR_SCHEMA")
 archive=obj.get("source_archive",{})
 if not archive.get("sha256") or not archive.get("file_id"):raise ValueError("NDC_ORIGIN_UNVERIFIED")
 xls=d.call(lambda:d.api.files().get_media(fileId=archive["file_id"]))
 if digest(xls)!=archive["sha256"]:raise ValueError("ORIGIN_XLSX_SHA_FAIL")
 base=datetime.datetime(1899,12,30).date()
 records=[];issues=[];keys=set();raw_cells=0
 for t in obj["tables"]:
  section=t.get("table")
  serial=t.get("source_date_cell")
  if serial is None:raise ValueError("EXCEL_SOURCE_DATE_MISSING")
  date=base+datetime.timedelta(days=int(serial))
  if date.strftime("%Y-%m")!=obj["month"]:raise ValueError("SOURCE_DATE_MONTH_MISMATCH")
  for cell in t.get("cells",[]):
   raw_cells+=1;field=cell.get("field");native=cell.get("native_value");status=cell.get("status")
   key=(date.isoformat(),section,field)
   if key in keys:raise ValueError("DUPLICATE_SERIES_IN_TABLE")
   keys.add(key)
   num=None;category=None
   if status=="VALUE_PRESENT":
    try:
     dval=decimal.Decimal(str(native))
     if dval.is_finite():num=str(dval)
    except (decimal.InvalidOperation,TypeError,ValueError):pass
    if num is None:category=str(native)
   elif status in ("BEFORE_SERIES_START","NOT_AVAILABLE","NOT_APPLICABLE"):
    issues.append({"field":field,"status":status})
   else:
    raise ValueError("UNKNOWN_SOURCE_CELL_STATUS:"+str(status))
   records.append({"source":"NDC","dataset_id":"NDC_ECONOMIC_CYCLE",
    "content_month":obj["month"],"source_date":date.isoformat(),"source_table":section,
    "field_native":field,"value_numeric_decimal":num,"value_categorical":category,
    "value_raw":str(native) if native is not None else None,"native_unit_policy":"AS_PUBLISHED_FIELD_SPECIFIC",
    "cell_status":status,"source_row_number":int(t["source_row"]),
    "legacy_raw_sha256":digest(raw),"source_archive_sha256":archive["sha256"],
    "captured_at_utc":archive.get("captured_utc"),"published_at_utc":None,
    "historical_vintage_verified":False,"pit_verified":False})
 if not records or len(records)!=raw_cells:raise ValueError("ROW_COUNT_MISMATCH")
 if sum(bool(x["value_numeric_decimal"]) for x in records)<20:raise ValueError("NUMERIC_CONTENT_TOO_SMALL")
 t=pa.Table.from_pylist(records)
 p=ROOT/"NDC_ECONOMIC_CYCLE_year=2000_month=01.candidate.parquet"
 pq.write_table(t,p,compression="zstd")
 back=pq.read_table(p).to_pylist()
 if back!=records:raise ValueError("TYPED_PARQUET_FULL_ROUNDTRIP_FAIL")
 report.update(status="PASS_TYPED_CANDIDATE_NOT_PIT",cells=len(records),numeric_rows=sum(x["value_numeric_decimal"] is not None for x in records),
  category_rows=sum(x["value_categorical"] is not None for x in records),
  no_value_rows=sum(x["cell_status"]!="VALUE_PRESENT" for x in records),
  unique_source_series=len(keys),source_month="2000-01",source_archive_sha256=archive["sha256"],
  candidate_parquet_sha256=digest(p.read_bytes()),bytes=p.stat().st_size,issues=issues)
except Exception as exc:report["error"]=type(exc).__name__+":"+str(exc)[:240]
(ROOT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print("NDC_TYPED_RESULT",json.dumps(report,ensure_ascii=False),flush=True)
if report["status"]!="PASS_TYPED_CANDIDATE_NOT_PIT":raise SystemExit(1)
