"""Strict seven-source historical data content audit. Read-only; manifests are not market data."""
import argparse,datetime,json,io,zipfile,csv,time,pathlib
from scripts.annual_actual_firstpass import Drive,service
SRC=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
ROOT=pathlib.Path("v095_semantic_audit")
def has_data(raw,name):
 low=name.lower()
 if low.endswith((".manifest.json","manifest.json","receipt.json","checkpoint.json")):return False
 if len(raw)<200:return False
 stripped=raw.lstrip()
 if low.endswith(".csv"):
  rr=list(csv.reader(io.StringIO(raw[:6000].decode("utf-8-sig","replace"))))
  return len(rr)>=3 and max(map(len,rr[:3]))>=2
 if low.endswith(".json"):
  try:
   x=json.loads(raw.decode("utf-8-sig"))
   if isinstance(x,dict) and any(z in x for z in ("source_archive","coverage_certified","run_id","manifest_version")):return False
   if isinstance(x,dict) and isinstance(x.get("data"),list) and x["data"]:return True
   if isinstance(x,list) and len(x)>1:return True
  except Exception:return False
  return False
 if low.endswith((".html",".htm",".raw")):return b"<table" in raw.lower() or b"," in raw[:3000]
 if low.endswith(".xlsx"):return raw.startswith(b"PK\x03\x04")
 if low.endswith(".parquet"):return raw[:4]==b"PAR1"
 return False
def run(source):
 catalog=json.loads(pathlib.Path("config/v095_seven_source_drive_probe.json").read_text())
 x=next(r for r in catalog["items"] if r["source"]==source)
 out=ROOT/source;out.mkdir(parents=True,exist_ok=True)
 rec={"source":source,"historical_folder":x["folder_period"],"status":"BLOCKED","numeric_values_verified":False,
      "historical_pit_verified":False,"production_approved":False}
 try:
  d=Drive(service());data=d.call(lambda:d.api.files().get_media(fileId=x["file_id"]))
  if x["format"]=="zip":
   with zipfile.ZipFile(io.BytesIO(data)) as z:
    arr=z.infolist()
    rec["members"]=[{"name":i.filename[:100],"bytes":i.file_size} for i in arr[:25]]
    accepted=[]
    for i in arr:
     if i.is_dir() or i.file_size>3_000_000 or i.file_size<200:continue
     if has_data(z.read(i),i.filename):accepted.append(i.filename[:100])
    rec["plausible_market_data_members"]=accepted[:15]
    if not accepted:raise ValueError("ARCHIVE_MANIFEST_OR_RECEIPTS_ONLY_NO_VALID_DATASET")
  elif x["format"]=="json":
   if not has_data(data,"ndc.json"):raise ValueError("JSON_AUDIT_OR_COVERAGE_RECORD_NOT_NUMERIC_DATA")
  elif x["format"]=="html":
   if not has_data(data,"data.html"):raise ValueError("HTML_NOT_TABULAR")
  elif x["format"]=="csv":
   if not has_data(data,"data.csv"):raise ValueError("CSV_NOT_TABULAR")
  rec["status"]="PASS_PLAUSIBLE_CONTENT_NEEDS_PIT_AND_NUMERIC_RECHECK"
 except Exception as e:rec["error"]=type(e).__name__+":"+str(e)[:210]
 (out/"report.json").write_text(json.dumps(rec,ensure_ascii=False,indent=2))
 print("SEMANTIC_AUDIT",json.dumps(rec,ensure_ascii=False),flush=True)
 if not rec["status"].startswith("PASS"):raise SystemExit(1)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",choices=SRC,required=True)
 run(p.parse_args().source)
