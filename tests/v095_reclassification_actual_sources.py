"""v0.93 -> v0.95 dataset-classification preflight, real Drive bytes, read only.

Proves whether *classification* is possible; does not conflate lossless Parquet
packaging with typed/normalized Silver. No production Drive writes.
"""
import argparse,collections,csv,datetime,decimal,hashlib,io,json,pathlib,re,time,zipfile
from scripts.annual_actual_firstpass import Drive,service

SRC_LIST=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
TYPES={"TWSE":{"market":"TSE","scope":"LISTED_ONLY"},
       "TPEx":{"market":"OTC","scope":"OTC_ONLY"},
       "MOPS":{"market":"TSE_OTC","scope":"COMPANY_DISCLOSURE"},
       "NDC":{"market":"MACRO","scope":"MACRO_SERIES"},
       "TAIFEX":{"market":"DERIVATIVES","scope":"FUTURES_OPTIONS"},
       "TDCC":{"market":"TSE_OTC","scope":"CUSTODY_DATA"},
       "FinMind":{"market":"TSE_OTC_SUPPLEMENT","scope":"GAP_FILL_ONLY"}}
ROOT=pathlib.Path("v095_reclassification_audit")
def sha(x):return hashlib.sha256(x).hexdigest()
def ns(v):
 try:return decimal.Decimal(str(v).replace(",","")).is_finite()
 except (ValueError,TypeError,decimal.InvalidOperation):return False
def inspect_archive(raw,source):
 out={"source_native_archive":True,"datasets":[],"manifest_used":False,"payload_members":0}
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  if z.testzip():raise ValueError("ZIP_CRC_FAIL")
  names=[x for x in z.namelist() if not x.endswith("/")]
  out["members"]=len(names)
  manif=[n for n in names if n.endswith("manifest.json")]
  if manif:
   m=json.loads(z.read(manif[0]))
   out["manifest_used"]=True
   out["manifest_keys"]=sorted(m)[:20] if isinstance(m,dict) else []
   if isinstance(m,dict):
    out["manifest_source_match"]=str(m.get("source","")).upper()==source.upper() if m.get("source") else None
    out["manifest_period"]=str(m.get("month") or m.get("period") or m.get("year_month") or "")[:10] or None
    for k in ("datasets","data_sets","items"):
     a=m.get(k)
     if isinstance(a,list):
      out["dataset_manifest_count"]=len(a)
      out["dataset_titles"]=[str(x.get("dataset") or x.get("dataset_id") or x.get("name"))[:80] for x in a[:12] if isinstance(x,dict)]
  payload=[n for n in names if n.endswith(".raw")]
  out["payload_members"]=len(payload)
  out["raw_member_names"]=payload[:10]
  out["dataset_classification"]="BLOCKED_NO_PER_MEMBER_DATASET_CONTRACT"
  # A single source archive may contain many datasets: do not classify by ZIP filename.
 return out
def inspect_ndc(raw):
 obj=json.loads(raw.decode("utf-8-sig"))
 if not isinstance(obj,dict) or obj.get("source")!="NDC":raise ValueError("NDC_SOURCE_MISMATCH")
 tables=obj.get("tables",[])
 if not isinstance(tables,list) or not tables:raise ValueError("NDC_TABLES_ABSENT")
 fields=[]
 for t in tables:
  for c in t.get("cells",[]):
   if c.get("status")!="VALUE_PRESENT":continue
   fields.append({"dataset_id":"NDC_MACRO_CYCLE","series":c.get("field"),
                  "native_value":c.get("native_value"),"numeric":ns(c.get("native_value")),
                  "unit":"AS_PUBLISHED_NEEDS_PER_SERIES_CONTRACT",
                  "period_excel_serial":t.get("source_date_cell"),"period_claim":obj.get("month")})
 numeric=sum(x["numeric"] for x in fields)
 if not numeric:raise ValueError("NDC_NUMERIC_NOT_FOUND")
 xls=obj.get("source_archive",{})
 return {"dataset_classification":"PROVISIONAL_NDC_MACRO_CYCLE",
  "numeric_cells":numeric,"categorical_cells":len(fields)-numeric,
  "source_archive_sha256":xls.get("sha256"),"units":"NATIVE_UNCHANGED",
  "source_month":obj.get("month"),"excel_date_serials":list(set(x["period_excel_serial"] for x in fields)),
  "series_names":[x["series"] for x in fields[:8]],"series_count":len(fields),
  "pit_verified":False,"series_vintage_verified":False}
def inspect_csv(raw):
 # Only prove shape, not business meaning from filename.
 rows=list(csv.reader(io.StringIO(raw[:100000].decode("utf-8-sig","replace"))))
 if len(rows)<2:raise ValueError("CSV_ROWS_ABSENT")
 header=rows[0]
 return {"dataset_classification":"HOLD_CSV_UNTIL_NATIVE_HEADER_CONTRACT",
         "header_sample":header[:15],"sample_rows":len(rows),
         "numeric_cells_sample":sum(ns(v) for row in rows[1:70] for v in row)}
def inspect_html(raw,source):
 s=raw[:500000].decode("utf-8","replace").lower()
 if "<table" not in s:raise ValueError("HTML_TABLE_ABSENT")
 return {"dataset_classification":"HOLD_HTML_UNTIL_TABLE_LEVEL_CONTRACT",
        "tables_in_sample":s.count("<table"),"source":source}
def classify(source,raw,fmt):
 if fmt=="zip":return inspect_archive(raw,source)
 if fmt=="json" and source=="NDC":return inspect_ndc(raw)
 if fmt=="csv":return inspect_csv(raw)
 if fmt=="html":return inspect_html(raw,source)
 raise ValueError("UNKNOWN_SOURCE_NATIVE_FORMAT")
def run(shard):
 cfg=json.loads(pathlib.Path("config/v095_seven_source_drive_probe.json").read_text())
 files=[x for i,x in enumerate(cfg["items"]) if i%3==shard]
 d=Drive(service());results=[];started=time.monotonic()
 folder=ROOT/f"shard_{shard}";folder.mkdir(parents=True,exist_ok=True)
 for obj in files:
  source=obj["source"]
  entry={"source":source,"source_file_id":obj["file_id"],
   "claimed_period":obj["folder_period"],"source_namespace":TYPES[source],
   "status":"BLOCKED","bronze_source_immutable":True,
   "bronze_production_approved":False,"silver_production_approved":False,
   "gold_production_approved":False,"historical_pit_verified":False,
   "numeric_units_verified":False,"classification_promoted":False}
  try:
   raw=d.call(lambda:d.api.files().get_media(fileId=obj["file_id"]))
   entry.update(raw_sha256=sha(raw),raw_bytes=len(raw),
    target_candidate_path=f"10_INGEST_STAGING/CANDIDATE/{source}/{obj['folder_period']}/{sha(raw)[:16]}/")
   classified=classify(source,raw,obj["format"])
   entry["native_classification_evidence"]=classified
   entry["status"]="PASS_CLASSIFICATION_EVIDENCE_QUARANTINED"
   if classified["dataset_classification"].startswith("PROVISIONAL"):
    entry["next_step"]="VERIFY_DATASET_SPECIFIC_SCHEMA_UNITS_PUBLISHED_AT_BEFORE_TYPED_SILVER"
   else:
    entry["next_step"]="ADD_DATASET_LEVEL_CONTRACT_AND_SOURCE_PERIOD_PIT_BEFORE_TYPED_SILVER"
  except Exception as e:entry["error"]=type(e).__name__+":"+str(e)[:250]
  results.append(entry)
  (folder/"report.json").write_text(json.dumps({"schema":"V095_RECLASSIFICATION_PREFLIGHT_V1","shard":shard,
   "status":"CANDIDATE_ONLY","results":results},ensure_ascii=False,indent=2))
  print("RECLASSIFICATION",source,entry["status"],entry.get("error",""),flush=True)
 summary={"shard":shard,"source_count":len(files),"passed":sum(x["status"].startswith("PASS") for x in results),
          "blocked":sum(not x["status"].startswith("PASS") for x in results),
          "elapsed_sec":round(time.monotonic()-started,3)}
 print("RECLASSIFICATION_SHARD",json.dumps(summary),flush=True)
 if summary["blocked"]:raise SystemExit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--shard",type=int,choices=(0,1,2),required=True)
 run(p.parse_args().shard)
