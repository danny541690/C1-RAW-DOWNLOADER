#!/usr/bin/env python3
"""JARVIS v0.97 B-layer TWSE/TPEx actual archive byte forensics.
Read-only original Bronze. Checkpointed; NEVER emits Silver Ready.
Classifies raw ZIP members by content signatures (not extensions), official
time-era, dataset fingerprints and source provenance gaps.
"""
import csv,datetime as dt,hashlib,io,json,os,re,sys,zipfile
from collections import Counter
from scripts.v097_bronze_autopilot import source_api,digest,adapter_version

VERSION="archive-forensics-b-1"
LIMIT=max(1,min(int(os.getenv("FORENSIC_BATCH","60")),150))
SOURCES=("TWSE","TPEx")
MAX_ZIP_BYTES=50*1024*1024
MAX_MEMBER_BYTES=20*1024*1024
MAX_UNPACKED=100*1024*1024
MAX_MEMBERS=400
SENSITIVE=("password","access_token","api_key","secret","refresh_token")
OFFICIAL={
 "TWSE":{"modern":"https://openapi.twse.com.tw/","archive":"https://www.twse.com.tw/zh/trading/historical/mi-index.html",
         "online_start":"2004-02-11"},
 "TPEx":{"modern":"https://www.tpex.org.tw/openapi/","archive":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html",
         "historical_2003_2006":"https://www.tpex.org.tw/en-us/mainboard/trading/info/pricing_hist96.html"}
}
PROVIDER="https://finmind.github.io/tutor/TaiwanMarket/Technical/"

def era(src,month):
 if src=="TWSE":
  return "PRE_CURRENT_DAILY_QUOTES_PAGE_SCOPE" if month<"2004-02" else ("2004_FEB_TRANSITION" if month=="2004-02" else "OFFICIAL_DAILY_QUOTE_PAGE_PERIOD")
 if month<"2003-08":return "PRE_TPEX_CURRENT_HISTORICAL_PAGE_SCOPE"
 if month<"2007-01":return "TPEX_2003_08_TO_2006_12_HISTORICAL"
 if month<"2007-05":return "TPEX_2007_01_TO_2007_04_TRANSITION"
 return "TPEX_POST_2007_04"

def safe_name(n):
 return isinstance(n,str) and bool(n) and not n.startswith("/") and not re.match(r"^[A-Za-z]:",n) and ".." not in n.replace(chr(92),"/").split("/")

def fingerprint(name,blob):
 # Max 8KB of decoded metadata; never include raw rows or tokens in reports.
 ext=name.rsplit(".",1)[-1].lower() if "." in name else "none"
 preview=blob[:8192]
 fmt="UNKNOWN";codec=None;keys=[];columns=[];dataset="UNCLASSIFIED"
 if preview.startswith(b"PK"+bytes([3,4])):fmt="NESTED_ZIP_OR_OFFICE"
 elif preview.startswith(b"%PDF"):fmt="PDF"
 elif preview.startswith(bytes([208,207,17,224])):fmt="LEGACY_XLS"
 elif preview.startswith(b"PAR1"):fmt="PARQUET"
 elif preview.startswith(bytes([31,139])):fmt="GZIP"
 else:
  for enc in ("utf-8-sig","cp950","big5"):
   try:
    sample=preview.decode(enc)
    codec=enc;break
   except UnicodeError:pass
  else:sample=None
  if sample is not None:
   s=sample.lstrip()
   if s.startswith(("{","[")):
    try:
     obj=json.loads(blob.decode(codec))
     fmt="JSON"
     if isinstance(obj,dict):
      keys=[str(k)[:65] for k in obj.keys() if not any(t in str(k).lower() for t in SENSITIVE)][:35]
      rows=obj.get("data",obj.get("rows",[]))
      if isinstance(rows,list) and rows and isinstance(rows[0],dict):
       columns=[str(k)[:65] for k in rows[0].keys()][:35]
      elif isinstance(obj.get("tables"),list):
       columns=[str(k)[:65] for t in obj["tables"][:8] if isinstance(t,dict) for k in t.get("fields",[])][:35]
     elif isinstance(obj,list) and obj and isinstance(obj[0],dict):
      columns=[str(k)[:65] for k in obj[0].keys()][:35]
    except (ValueError,UnicodeError):fmt="JSON_PARSE_FAILED"
   elif s.startswith(("<!DOCTYPE html","<html","<HTML","<table","<TABLE")):fmt="HTML"
   elif "," in sample or chr(9) in sample:
    try:
     lines=sample.splitlines()
     for line in lines[:5]:
      row=next(csv.reader([line]))
      if len(row)>=3:
       columns=[str(x)[:65] for x in row[:35]]
       fmt="CSV_OR_TSV";break
    except (csv.Error,ValueError):pass
   if fmt=="UNKNOWN" and sample[:20].isprintable():fmt="TEXT_OR_MANIFEST"
 matchset="|".join(keys+columns).lower()
 if any(t in matchset for t in ("trading_volume","trading_money","trading_turnover")):dataset="THIRD_PARTY_OHLCV_SCHEMA"
 elif any(t in matchset for t in ("收盤價","開盤價","成交股數","成交金額","最高價","最低價","收盤")):dataset="MARKET_QUOTES_CANDIDATE"
 elif any(t in matchset for t in ("買超","賣超","外資","投信","自營商")):dataset="INSTITUTIONAL_CANDIDATE"
 elif any(t in matchset for t in ("借券","融券","融資","資券")):dataset="MARGIN_LENDING_CANDIDATE"
 elif any(t in matchset for t in ("營收","股本","本益比","市值","pbr","per")):dataset="FUNDAMENTAL_CANDIDATE"
 elif any(t in matchset for t in ("sha256","source_url","status","error","checkpoint","source_path","source_id","manifest")):dataset="CONTROL_OR_RECEIPT_CANDIDATE"
 elif fmt=="JSON" and keys:dataset="JSON_UNMAPPED_SCHEMA"
 return {"name":name[:160],"extension":ext[:18],"signature":fmt,"encoding":codec,
         "dataset_fingerprint":dataset,"key_names":keys,"field_names":columns,
         "sha256":digest(blob),"bytes":len(blob)}

def manifest_linkage(z,details):
 """Verify internal archive manifest bytes without claiming official provenance."""
 lookup={x["name"]:x for x in details}
 summaries=[]
 for m in details:
  if m["name"].rsplit("/",1)[-1].lower()!="manifest.json":continue
  try:
   manifest=json.loads(z.read(m["name"]).decode("utf-8-sig"))
  except (UnicodeError,ValueError,KeyError):
   summaries.append({"status":"HOLD_MANIFEST_UNREADABLE"});continue
  if not isinstance(manifest,dict) or not isinstance(manifest.get("units"),list):
   summaries.append({"status":"HOLD_MANIFEST_UNSUPPORTED_SHAPE"});continue
  units=manifest["units"]
  if len(units)>15000:
   summaries.append({"status":"HOLD_MANIFEST_UNIT_COUNT_LIMIT","unit_count":len(units)});continue
  found=0;verified=0;conflict=0;missing=0;source_refs=0;unit_keys=set()
  for u in units:
   if not isinstance(u,dict):
    conflict+=1;continue
   unit_keys.update(str(k)[:50] for k in u.keys())
   member=next((u.get(k) for k in ("file","member","filename","raw_file","path") if isinstance(u.get(k),str)),None)
   sha=next((u.get(k) for k in ("sha256","hash","raw_sha256") if isinstance(u.get(k),str)),None)
   if any(k in u for k in ("source_url","url","official_url","endpoint")):source_refs+=1
   if member is None or member not in lookup:
    missing+=1;continue
   found+=1
   if isinstance(sha,str) and re.fullmatch("[0-9a-f]{64}",sha.lower()) and sha.lower()==lookup[member]["sha256"]:
    verified+=1
   else:conflict+=1
  summaries.append({"status":"MANIFEST_MEMBER_LINKAGE_AUDITED_NOT_OFFICIAL_SOURCE_PROOF",
    "units":len(units),"matched_members":found,"verified_sha256":verified,
    "missing_member_references":missing,"hash_or_shape_conflicts":conflict,
    "units_with_source_reference_field":source_refs,
    "unit_field_names":sorted(unit_keys)[:35],
    "declared_numeric_verified":manifest.get("numeric_verified") is True,
    "declared_pit_verified":manifest.get("pit_verified") is True})
 return summaries

def audit(source,row,blob):
 period=str(row["year"])+"-"+str(row["month"])
 result={"source_id":row["source_id"],"source_sha256":row["sha"],"original_path":row["source_path"],
         "era":era(source,period),"official_reference":OFFICIAL[source],
         "third_party_reference":PROVIDER,"silver_ready_promoted":False}
 if digest(blob)!=row["sha"]:
  return {**result,"status":"HOLD_SOURCE_DEST_SHA_MISMATCH"}
 if len(blob)>MAX_ZIP_BYTES or not zipfile.is_zipfile(io.BytesIO(blob)):
  return {**result,"status":"HOLD_BOUNDS_OR_NOT_ZIP"}
 try:
  details=[];unpacked=0
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   info=z.infolist()
   if len(info)>MAX_MEMBERS:return {**result,"status":"HOLD_ZIP_MEMBER_LIMIT"}
   for m in info:
    if m.is_dir():continue
    if not safe_name(m.filename):return {**result,"status":"HOLD_UNSAFE_ZIP_NAME"}
    if m.flag_bits & 1:return {**result,"status":"HOLD_ENCRYPTED_ZIP_MEMBER"}
    unpacked+=m.file_size
    if m.file_size>MAX_MEMBER_BYTES or unpacked>MAX_UNPACKED:
     return {**result,"status":"HOLD_ZIP_EXPANSION_LIMIT"}
    data=z.read(m)
    if len(data)!=m.file_size:return {**result,"status":"HOLD_ZIP_MEMBER_SIZE"}
    details.append(fingerprint(m.filename,data))
   linkage=manifest_linkage(z,details)
  kinds=Counter(t["signature"] for t in details)
  sets=Counter(t["dataset_fingerprint"] for t in details)
  return {**result,"status":"B_CONTENT_FINGERPRINTED_SOURCE_PROOF_PENDING",
    "member_count":len(details),"members":details,"manifest_linkage":linkage,
    "formats":dict(kinds),"dataset_fingerprints":dict(sets),
    "official_bytes_retrieved_independently":False}
 except (ValueError,zipfile.BadZipFile,RuntimeError,UnicodeError,MemoryError) as e:
  return {**result,"status":"HOLD_ZIP_CONTENT_ERROR","error_type":type(e).__name__}

def run(source):
 if source not in SOURCES:raise ValueError("source TWSE or TPEx required")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 ckf=match(api,control,"v097_AP_CHECKPOINT_"+source+".json")
 if not inp or not ckf:raise RuntimeError("MISSING_FROZEN_SOURCE")
 original=load_json(api,ckf["id"])["done"]
 rows=[x for x in load_json(api,inp["id"])["rows"] if
       original.get(x["source_id"],{}).get("status")=="ZIP_MEMBERS_AUDITED_ORIGIN_HOLD"]
 ckname="v097_B_FORMAT_FORENSICS_CK_"+source+".json"
 prior=match(api,control,ckname)
 ck=load_json(api,prior["id"]) if prior else {"schema":"v097_b_format_forensics_checkpoint_1","source":source,"version":VERSION,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("FORENSICS_VERSION_CONFLICT")
 known={r["source_id"] for r in rows}
 if set(ck["done"])-known:raise RuntimeError("ORPHAN_FORENSIC_SOURCE_ID")
 batch=[x for x in rows if x["source_id"] not in ck["done"]][:LIMIT]
 additions={}
 for row in batch:
  try:
   blob=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   additions[row["source_id"]]=audit(source,row,blob)
  except Exception as e:
   additions[row["source_id"]]={"source_id":row["source_id"],
     "status":"RECHECK_DRIVE_READ_"+type(e).__name__,"silver_ready_promoted":False}
 ck["done"].update(additions)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 if additions:upsert(api,control,ckname,ck)
 counts=Counter(z["status"] for z in additions.values())
 formats=Counter(k for z in additions.values() for k,n in z.get("formats",{}).items() for _ in range(n))
 datasets=Counter(k for z in additions.values() for k,n in z.get("dataset_fingerprints",{}).items() for _ in range(n))
 remaining=len(rows)-len(ck["done"])
 summary={"source":source,"processed":len(ck["done"]),"total":len(rows),
   "this_batch":len(additions),"remaining":remaining,"statuses":dict(counts),
   "formats":dict(formats),"datasets":dict(datasets),"silver_promoted":0}
 print("B_FORMAT_FORENSICS="+json.dumps(summary,ensure_ascii=False),flush=True)
 if os.getenv("GITHUB_OUTPUT"):
  with open(os.environ["GITHUB_OUTPUT"],"a") as f:
   f.write("remaining="+str(remaining)+chr(10))
   f.write("progress="+("true" if additions else "false")+chr(10))

def selftest():
 import zipfile
 sample=json.dumps({"date":"2024-10-25","data":[{"股票代號":"2330","收盤價":"1050","成交股數":"23400"}]}).encode()
 q=io.BytesIO()
 with zipfile.ZipFile(q,"w") as z:
  z.writestr("payload.bin",sample)
  z.writestr("run_status",b"status,source_id,count"+bytes([10])+b"OK,x,1")
 row={"source_id":"test","sha":digest(q.getvalue()),"source_path":"2024/TWSE/2024-10/a.zip","year":"2024","month":"10"}
 o=audit("TWSE",row,q.getvalue())
 assert o["status"]=="B_CONTENT_FINGERPRINTED_SOURCE_PROOF_PENDING"
 assert o["formats"].get("JSON")==1
 assert o["dataset_fingerprints"].get("MARKET_QUOTES_CANDIDATE")==1
 assert o["silver_ready_promoted"] is False
 assert audit("TWSE",row,b"other")["status"]=="HOLD_SOURCE_DEST_SHA_MISMATCH"
 assert era("TPEx","2004-01")=="TPEX_2003_08_TO_2006_12_HISTORICAL"
 print("B_FORMAT_FORENSICS_SELFTEST_PASS")

if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | TWSE | TPEx")
