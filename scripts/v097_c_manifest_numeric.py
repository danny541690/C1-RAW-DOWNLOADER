#!/usr/bin/env python3
"""JARVIS v0.97 C-layer incremental, source-scoped numerical & manifest evidence QA.
Inputs B forensic checkpoints and immutable Bronze ZIP bytes. NO Silver/Gold action.
No live external comparison or official-origin certification is claimed.
"""
import datetime,io,json,os,re,sys,zipfile
from collections import Counter
from decimal import Decimal,InvalidOperation
from scripts.v097_bronze_autopilot import source_api,digest,date_token
from scripts.v097_b_format_forensics import fingerprint,manifest_linkage
SOURCES=("TWSE","TPEx")
VERSION="c-source-manifest-number-date-v1"
SEMANTIC_VERSION="c-semantics-20261116-v3"
MAX_TRANSIENT_RETRY=3
BATCH=max(1,min(int(os.getenv("C_BATCH","60")),150))
NA={"","-","--","---","N/A","X","不適用","除權","除息","null"}
DOMAIN={"TWSE":("twse.com.tw","www.twse.com.tw","openapi.twse.com.tw"),"TPEx":("tpex.org.tw","www.tpex.org.tw")}
def columns(fields):
 return [re.sub(r"\s+","",str(f)).replace("（","(").replace("）",")") for f in fields]
def detect(fields):
 f=columns(fields);s=set(f)
 if {"代號","收盤","開盤","最高","最低"}.issubset(s) or {"證券代號","收盤價","開盤價","最高價","最低價"}.issubset(s):
  return "STOCK_DAILY_OHLCV"
 if "市值(佰萬元)" in s or ("市值" in s and ("發行股數" in s or "收盤價" in s)):return "MARKET_CAPITALIZATION"
 if ("融資" in "|".join(f) or "資餘額" in s or "資券相抵(張)" in s):return "MARGIN_FINANCING"
 if any("借券" in x for x in f) or ("前日餘額" in s and "當日還券" in s):return "LENDING"
 if "本益比" in s and ("殖利率(%)" in s or "股價淨值比" in s):return "VALUATION"
 if ("收盤指數" in s or "收市指數" in s) and "指數" in s:return "INDEX"
 if "僑外資及陸資持有股數(C)" in s or any("持股比率" in x for x in f):return "FOREIGN_HOLDING"
 if "成交金額(元)" in s and "成交股數" in s:return "MARKET_VOLUME"
 return "UNRESOLVED_SCHEMA"
def extract_tables(obj):
 if not isinstance(obj,dict):return []
 tables=obj.get("tables")
 if isinstance(tables,list):return [t for t in tables if isinstance(t,dict)]
 if isinstance(obj.get("fields"),list) and isinstance(obj.get("data"),list):
  return [obj]
 return []
def numeric(text):
 s=str(text).replace(",","").strip()
 if s in NA:return "MISSING"
 try:
  d=Decimal(s)
  return "OK" if d.is_finite() else "INVALID"
 except (InvalidOperation,ValueError):
  return "INVALID"
def inspect_member(raw):
 try: obj=json.loads(raw.decode("utf-8-sig"))
 except (UnicodeError,ValueError):return {"state":"NOT_JSON"}
 tbl=extract_tables(obj)
 if not tbl:return {"state":"NO_TABLES","keys":list(obj.keys())[:16] if isinstance(obj,dict) else []}
 datasets=Counter();numeric_checked=0;bad=0;shape=0;observed_dates=[];stock_codes=0;bad_samples=[]
 if isinstance(obj,dict):
  for name in ("date","Date","資料日期"):
   if name in obj:observed_dates.append(str(obj[name])[:20])
 for t in tbl:
  fields=t.get("fields",[]);data=t.get("data",[])
  if not isinstance(fields,list) or not isinstance(data,list):shape+=1;continue
  datasets[detect(fields)]+=1
  numeric_ix=[i for i,v in enumerate(fields) if any(q in str(v) for q in
    ("收盤","開盤","最高","最低","成交金額","成交股數","成交筆數","成交量","成交值","市值","發行股數","買進","賣出","餘額","本益比","股價淨值比"))]
  code_ix=[i for i,v in enumerate(fields) if str(v).strip() in ("代號","股票代號","證券代號")]
  for row in data:
   if not isinstance(row,list) or len(row)!=len(fields):shape+=1;continue
   for i in numeric_ix:
    numeric_checked+=1
    if numeric(row[i])=="INVALID":
     bad+=1
     if len(bad_samples)<8:
      bad_samples.append({"field":str(fields[i])[:80],"value_excerpt":str(row[i])[:28]})
   if code_ix and re.fullmatch(r"[0-9A-Z]{4,6}",str(row[code_ix[0]]).strip()):
    stock_codes+=1
 return {"state":"TABLES_EXAMINED","datasets":dict(datasets),"tables":len(tbl),
         "invalid_numeric_cells":bad,"numeric_cells_checked":numeric_checked,
         "row_width_conflicts":shape,"observed_dates":observed_dates[:5],"code_like_rows":stock_codes,
         "invalid_numeric_samples":bad_samples}
def audit(source,row,raw):
 result={"source_id":row["source_id"],"source_sha256":row["sha"],"audit_version":SEMANTIC_VERSION,
         "official_origin_retrieved":False,"third_party_values_compared":False,
         "silver_ready_promoted":False}
 if digest(raw)!=row["sha"]:return {**result,"status":"HOLD_SHA_MISMATCH"}
 if not zipfile.is_zipfile(io.BytesIO(raw)):return {**result,"status":"HOLD_NOT_ZIP"}
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names=[x.filename for x in z.infolist() if not x.is_dir()]
  if len(names)>400 or len(set(names))!=len(names):
   return {**result,"status":"HOLD_ARCHIVE_MEMBER_DUPLICATE_OR_LIMIT"}
  detail=[];member_details=[]
  for n in names:
   if n.endswith("/") or n.startswith("/") or ".." in n.replace(chr(92),"/").split("/"):
    return {**result,"status":"HOLD_UNSAFE_MEMBER"}
   if z.getinfo(n).file_size>20*1024*1024:return {**result,"status":"HOLD_LARGE_MEMBER"}
   blob=z.read(n)
   f=fingerprint(n,blob)
   member_details.append(f)
   if n.rsplit("/",1)[-1].lower()!="manifest.json":
    detail.append({"member":n[:160],"sha256":digest(blob),**inspect_member(blob)})
  proof=manifest_linkage(z,member_details)
  sources=[]
  for name in names:
   if name.rsplit("/",1)[-1].lower()!="manifest.json":continue
   try: manifest=json.loads(z.read(name).decode("utf-8-sig"))
   except (ValueError,UnicodeError):continue
   if not isinstance(manifest,dict):continue
   for unit in manifest.get("units",[])[:15000]:
    if not isinstance(unit,dict):continue
    url=next((unit.get(k) for k in ("source_url","official_url","url","endpoint") if isinstance(unit.get(k),str)),None)
    if url:
     from urllib.parse import urlparse
     host=(urlparse(url).hostname or "").lower()
     sources.append({"official_host_candidate":host in DOMAIN[source],
        "url_present":True,"publisher_host":host[:80]})
  category=Counter(k for d in detail for k,n in d.get("datasets",{}).items() for _ in range(n))
  numeric_count=sum(x.get("numeric_cells_checked",0) for x in detail)
  invalid_count=sum(x.get("invalid_numeric_cells",0) for x in detail)
  width_count=sum(x.get("row_width_conflicts",0) for x in detail)
  linkage_bad=sum(x.get("hash_or_shape_conflicts",0)+x.get("missing_member_references",0) for x in proof)
  if not proof: status="HOLD_NO_MANIFEST_PROOF"
  elif linkage_bad:status="HOLD_MANIFEST_LINKAGE_CONFLICT"
  elif invalid_count or width_count:status="HOLD_NUMERIC_OR_WIDTH_CONFLICT"
  elif not category or set(category)=={"UNRESOLVED_SCHEMA"}:status="HOLD_DATASET_IDENTITY_UNRESOLVED"
  else:status="C_NUMERIC_AND_MANIFEST_PARSED_OFFICIAL_RECHECK_PENDING"
  return {**result,"status":status,"table_datasets":dict(category),
   "manifest_linkage":proof,"numeric_cells_checked":numeric_count,
   "invalid_numeric_cells":invalid_count,"row_width_conflicts":width_count,
   "source_url_hosts_seen":dict(Counter(x["publisher_host"] for x in sources)),
   "official_host_claims_in_manifest":sum(x["official_host_candidate"] for x in sources),
   "members":detail[:60],"publication_time_verified":False}
def run(source):
 if source not in SOURCES:raise RuntimeError("SOURCE_REQUIRED")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 b=match(api,control,"v097_B_FORMAT_FORENSICS_CK_"+source+".json")
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 if not b or not inp:raise RuntimeError("NO_B_LAYER_CHECKPOINT")
 eligible=load_json(api,b["id"])["done"]
 rows={r["source_id"]:r for r in load_json(api,inp["id"])["rows"]}
 name="v097_C_MANIFEST_NUMERIC_CK_"+source+".json"
 f=match(api,control,name)
 ck=load_json(api,f["id"]) if f else {"schema":"v097_c_manifest_numeric_checkpoint_1","version":VERSION,"source":source,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("C_VERSION_MISMATCH")
 if set(ck["done"])-set(eligible):raise RuntimeError("C_ORPHAN_KEYS")
 failures={"HOLD_NUMERIC_OR_WIDTH_CONFLICT","HOLD_DATASET_IDENTITY_UNRESOLVED","HOLD_MANIFEST_LINKAGE_CONFLICT","HOLD_NO_MANIFEST_PROOF"}
 recheck=[sid for sid,v in ck["done"].items() if sid in eligible and
    ((v.get("status") in failures and v.get("audit_version")!=SEMANTIC_VERSION)
     or (str(v.get("status","")).startswith("RECHECK_C_") and v.get("attempts",0)<MAX_TRANSIENT_RETRY))]
 new_ids=[sid for sid in eligible if sid not in ck["done"]]
 selected_recheck=recheck[:BATCH//3]
 pending=selected_recheck+new_ids[:BATCH-len(selected_recheck)]
 new={};rechecked=0
 for sid in pending:
  try:
   row=rows[sid]
   if eligible[sid].get("source_sha256")!=row["sha"]:
    new[sid]={"status":"HOLD_B_SHA_CONFLICT","silver_ready_promoted":False};continue
   raw=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   new[sid]=audit(source,row,raw)
   if sid in ck["done"]:rechecked+=1
  except Exception as e:
   new[sid]={"status":"RECHECK_C_"+type(e).__name__,
      "attempts":ck["done"].get(sid,{}).get("attempts",0)+1,"silver_ready_promoted":False}
 ck["done"].update(new)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 if new:
  # Google Drive update may time out after committing the write. Re-read
  # before retrying and never change the original immutable Bronze bytes.
  from scripts.v097_seven_native_v2_probe import checkpoint_commit
  checkpoint_commit(api,control,name,ck,upsert,match,load_json)
 remaining=len(eligible)-len(ck["done"])
 print("C_MANIFEST_NUMERIC="+json.dumps({"source":source,"batch":len(new),"checked":len(ck["done"]),
      "b_available":len(eligible),"remaining_ready_for_c":remaining,"rechecked_existing":rechecked,
      "statuses":dict(Counter(x["status"] for x in new.values())),"silver_promoted":0}),flush=True)
def selftest():
 assert detect(["代號","名稱","收盤","開盤","最高","最低","成交股數"])=="STOCK_DAILY_OHLCV"
 assert detect(["排名","股票代號","收盤價","市值(佰萬元)"])=="MARKET_CAPITALIZATION"
 assert numeric("1,000")=="OK" and numeric("oops")=="INVALID"
 assert "www.twse.com.tw" in DOMAIN["TWSE"]
 assert inspect_member(json.dumps({"tables":[{"fields":["成交統計","成交金額(元)"],"data":[["1.一般股票","123456"]]}]},ensure_ascii=False).encode())["invalid_numeric_cells"]==0
 assert columns([" 成 交 股 數 "])==["成交股數"]
 assert inspect_member(json.dumps({"date":"2024-01-02","tables":[{"fields":["代號","收盤"],"data":[["2330","150"]]}]},ensure_ascii=False).encode())["state"]=="TABLES_EXAMINED"
 print("C_MANIFEST_NUMERIC_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | TWSE | TPEx")
