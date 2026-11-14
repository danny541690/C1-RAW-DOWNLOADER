#!/usr/bin/env python3
"""JARVIS v0.97: independent Bronze-only Silver-input readiness for V3 SHA-qualified files.
MUST NOT change source/destination raw, Bronze structures, or launch Silver/Gold.
Mode inventory scans six frozen copy/QA checkpoints; validates accounting and emits
an immutable candidate ledger. Mode lane performs incremental independent semantic
validation on destinations, backed by existing independently hashed QA evidence.
Mode aggregate consolidates all checkpoints into strict READY / HOLD decisions.
"""
import os,re,io,csv,json,hashlib,zipfile,datetime
from collections import Counter,defaultdict
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call
from scripts.v097_bronze_first_batch_v3 import ck_name
RUN=os.getenv("GITHUB_RUN_ID","manual")
CAP=max(1,min(2000,int(os.getenv("BRONZE_SEMANTIC_CAP","600"))))
SOURCE_SET={"TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind"}
EXPECTED_BASIC=74750
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def get_ck(api,c,stage,lane):
 f=match(api,c,ck_name(stage,lane))
 if not f:raise RuntimeError("MISSING_V3_%s_CK_L%02d"%(stage,lane))
 return load_json(api,f["id"])["done"]
def candidate_rows(api,c,lane):
 copies=get_ck(api,c,"COPY",lane);checks=get_ck(api,c,"QA",lane)
 out=[]
 for fid,x in copies.items():
  if x.get("state")!="COPY_MATCHED_PENDING_INDEPENDENT_QA":continue
  q=checks.get(fid,{})
  if q.get("state")!="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":continue
  path=str(x.get("source_path") or "")
  dest=str(x.get("dest_path") or "")
  parts=dest.split("/")
  if len(parts)!=5 or parts[0] not in SOURCE_SET:raise RuntimeError("INVALID_DESTINATION_PARTITION:"+fid)
  if not re.fullmatch(r"(?:19|20)\d{2}",parts[2]) or not re.fullmatch(r"0[1-9]|1[0-2]",parts[3]):
   raise RuntimeError("INVALID_PARTITION_DATE:"+fid)
  if not path.startswith(parts[2]+"/"+parts[0]+"/"+parts[2]+"-"+parts[3]+"/"):
   raise RuntimeError("SOURCE_DEST_PERIOD_CONFLICT:"+fid)
  if not re.fullmatch(r"[0-9a-f]{64}",x.get("sha") or ""):raise RuntimeError("NO_FROZEN_SHA:"+fid)
  if not x.get("dest_id"):raise RuntimeError("NO_V097_DESTINATION:"+fid)
  out.append({"source_id":fid,"dest_id":x["dest_id"],"sha":x["sha"],
    "source":parts[0],"year":parts[2],"month":parts[3],"source_path":path,
    "destination_path":dest,"size":x.get("size"),"lane":lane})
 return out
def inventory(api):
 _,c,q,_=common(api)
 counts=Counter();seen=set();perlane=[];rows=[]
 for lane in range(6):
  lst=candidate_rows(api,c,lane)
  if any(x["source_id"] in seen for x in lst):raise RuntimeError("CROSS_LANE_DUPLICATE")
  seen.update(x["source_id"] for x in lst)
  counts.update(x["source"] for x in lst)
  rows+=lst
  perlane.append({"lane":lane,"count":len(lst)})
 if len(seen)!=EXPECTED_BASIC:
  raise RuntimeError("EXPECTED_74750_BUT_VERIFIED_"+str(len(seen))+
    "_CHECK_FROZEN_V3_ACCOUNTING_FIRST")
 put_once(api,q,"v097_BRONZE_74750_BASELINE_ROWS_%s.json"%RUN,
   {"schema":"v097_bronze_74750_frozen_byte_candidates_1","run":RUN,"rows":rows,
    "source_qa_state":"BRONZE_BYTE_PROVENANCE_AND_PATH_PASS",
    "silver_ready":False})
 summary={"schema":"v097_bronze_74750_inventory_1","run":RUN,"date":now(),
  "byte_provenance_candidates":len(rows),"source_breakdown":dict(counts),
  "lanes":perlane,"not_a_semantic_release":True,"silver_ready":False}
 put_once(api,q,"v097_BRONZE_74750_BASELINE_SUMMARY_%s.json"%RUN,summary)
 print("BRONZE_74750_INVENTORY="+json.dumps(summary,ensure_ascii=False),flush=True)
 return summary
def parse_json(blob):
 data=json.loads(blob.decode("utf-8-sig"))
 if isinstance(data,list):
  if not data:return None,"EMPTY_JSON_ARRAY"
  if not isinstance(data[0],dict):return None,"JSON_ARRAY_NOT_RECORDS"
  return data,"JSON_RECORD_ARRAY"
 if isinstance(data,dict):
  if isinstance(data.get("tables"),list):
   tables=[t for t in data["tables"] if isinstance(t,dict) and
     isinstance(t.get("fields"),list) and isinstance(t.get("data"),list)]
   if not tables:return None,"JSON_TABLES_SCHEMA_UNRECOGNIZED"
   return data,"JSON_OFFICIAL_TABLES"
  if isinstance(data.get("data"),list) and isinstance(data.get("fields"),list):
   return data,"JSON_FIELD_DATA"
  if isinstance(data.get("rows"),list) and data.get("rows"):
   return data,"JSON_ROWS_UNVERIFIED_SCHEMA"
  return None,"UNKNOWN_JSON_DATASET"
 return None,"UNKNOWN_JSON_CONTAINER"
def evidence_date(data,kind):
 vals=[]
 if isinstance(data,dict):
  for key in ("date","Date","資料日期","查詢日期"):
   v=data.get(key)
   if isinstance(v,(str,int)):vals.append(str(v))
  for tab in data.get("tables",[])[:4]:
   if isinstance(tab,dict):
    d=tab.get("date")
    if isinstance(d,str):vals.append(d)
 elif isinstance(data,list):
  first=data[0] if data else {}
  if isinstance(first,dict):
   for key in ("date","Date","資料日期","交易日期"):
    v=first.get(key)
    if isinstance(v,(str,int)):vals.append(str(v))
 return vals
def normalize_date(raw):
 raw=raw.strip()
 m=re.fullmatch(r"((?:19|20)\d{2})[-/]?(0[1-9]|1[0-2])[-/]?([0-3]\d)",raw)
 if m:
  try:return datetime.date(int(m[1]),int(m[2]),int(m[3])).isoformat()
  except ValueError:return None
 m=re.fullmatch(r"(\d{3})/(\d{1,2})/(\d{1,2})",raw)
 if m:
  try:return datetime.date(int(m[1])+1911,int(m[2]),int(m[3])).isoformat()
  except ValueError:return None
 return None
def validate_file(r,blob):
 """Fail-closed policy. All outputs evidence only, no normalization or transformation."""
 source=r["source"];path=r["source_path"];month=r["year"]+"-"+r["month"]
 name=path.rsplit("/",1)[-1].lower()
 result={"source_id":r["source_id"],"source":source,
  "dest_id":r["dest_id"],"content_sha256":sha(blob),
  "bytes":len(blob),"month":month}
 if not blob:return dict(result,state="HOLD_EMPTY_BYTES")
 if len(blob)>50*1024*1024:return dict(result,state="HOLD_TOO_LARGE_FOR_SEMANTIC_GATE")
 try:
  if name.endswith(".json"):
   data,kind=parse_json(blob)
   result["recognized_shape"]=kind
   if data is None:return dict(result,state="HOLD_UNKNOWN_DATASET_SCHEMA")
   dates=evidence_date(data,kind)
   date_values=[normalize_date(v) for v in dates]
   valid=[d for d in date_values if d]
   result["dates_sample"]=dates[:5]
   if dates and not valid:return dict(result,state="HOLD_CONTENT_DATE_INVALID")
   if valid and any(d[:7]!=month for d in valid):
    return dict(result,state="HOLD_CONTENT_DATE_PATH_CONFLICT")
   if not valid:return dict(result,state="HOLD_NO_VERIFIABLE_CONTENT_DATE")
   if kind not in ("JSON_OFFICIAL_TABLES","JSON_FIELD_DATA","JSON_RECORD_ARRAY"):
    return dict(result,state="HOLD_DATASET_SCHEMA_NOT_CONFIRMED")
   # No proof of official publication timestamp from file body alone.
   return dict(result,state="BRONZE_CONTENT_DATE_SCHEMA_PASS_PIT_HOLD")
  if name.endswith(".csv"):
   sample=blob[:500000].decode("utf-8-sig",errors="strict")
   dialect=csv.Sniffer().sniff(sample[:4000],delimiters=",;\t")
   rd=csv.reader(io.StringIO(sample),dialect);header=next(rd,[])
   if len(header)<3:return dict(result,state="HOLD_CSV_HEADER")
   return dict(result,state="BRONZE_CSV_HEADER_PASS_DATASET_AND_PIT_HOLD",header=header[:30])
  if name.endswith((".html",".htm")):
   content=blob.decode("utf-8-sig",errors="replace")
   if "<table" not in content.lower():return dict(result,state="HOLD_HTML_NOT_TABULAR")
   if source=="TDCC" and ("股權分散" in content or "StockNo" in content):
    return dict(result,state="BRONZE_TDCC_HTML_TABLE_PASS_MARKET_AND_PIT_HOLD")
   return dict(result,state="HOLD_HTML_DATASET_ADAPTER_REQUIRED")
  if name.endswith(".zip"):
   with zipfile.ZipFile(io.BytesIO(blob)) as z:
    files=z.infolist()
    if not files or z.testzip() is not None:return dict(result,state="HOLD_ZIP_INTEGRITY")
    return dict(result,state="HOLD_ARCHIVE_MEMBER_DATASET_ORIGIN",archive_members=len(files))
  if name.endswith(".pdf"):return dict(result,state="HOLD_PDF_DATASET_ADAPTER_REQUIRED")
  return dict(result,state="HOLD_UNKNOWN_EXTENSION")
 except Exception as exc:
  return dict(result,state="HOLD_CONTENT_PARSE_FAILED",reason=type(exc).__name__+":"+str(exc)[:100])
def lane(api,ln):
 _,c,q,_=common(api)
 candidates=candidate_rows(api,c,ln)
 ckname="v097_BRONZE_74750_SEMANTIC_CK_L%02d.json"%ln
 cf=match(api,c,ckname)
 d=load_json(api,cf["id"]) if cf else {"schema":"v097_bronze_74750_semantic_ck_1","lane":ln,"done":{}}
 done=d["done"]
 todo=[r for r in candidates if r["source_id"] not in done][:CAP]
 if not todo:
  print("BRONZE_74750_LANE_IDLE="+str(ln)+" completed="+str(len(done)));return
 results=[]
 for r in todo:
  fid=r["source_id"]
  try:
   blob=call(lambda:api.files().get_media(fileId=r["dest_id"]))
   record=validate_file(r,blob)
   if record["content_sha256"]!=r["sha"]:
    record.update(state="HOLD_DEST_SHA_CHANGED")
  except Exception as exc:
   record={"source_id":fid,"dest_id":r["dest_id"],"source":r["source"],
      "state":"HOLD_DRIVE_READ_ERROR","reason":type(exc).__name__+":"+str(exc)[:160]}
  results.append(record)
 # Receipt first, then checkpoint; idempotent and crash recoverable.
 first_id=todo[0]["source_id"];last_id=todo[-1]["source_id"]
 sig=hashlib.sha256((first_id+":"+last_id).encode()).hexdigest()[:12]
 name="v097_BRONZE_74750_SEMANTIC_%s_L%02d_%s.json"%(RUN,ln,sig)
 put_once(api,q,name,{"schema":"v097_bronze_74750_semantic_receipt_1","run":RUN,
    "lane":ln,"items":results,"at":now()})
 for rec in results:
  done[rec["source_id"]]={"state":rec["state"],"sha":rec.get("content_sha256"),
                           "receipt":name}
 upsert(api,c,ckname,{"schema":"v097_bronze_74750_semantic_ck_1",
    "lane":ln,"done":done,"last_run":RUN,"at":now()})
 counts=Counter(x["state"] for x in results)
 print("BRONZE_74750_LANE="+json.dumps({"lane":ln,"batch":len(results),
  "checked_total":len(done),"eligible":len(candidates),
  "remaining":len(candidates)-len(done),"states":dict(counts)},ensure_ascii=False),flush=True)
def aggregate(api):
 _,c,q,_=common(api);counts=Counter();total=0;checked=0
 for ln in range(6):
  candidates=candidate_rows(api,c,ln);total+=len(candidates)
  cf=match(api,c,"v097_BRONZE_74750_SEMANTIC_CK_L%02d.json"%ln)
  done=load_json(api,cf["id"])["done"] if cf else {}
  allowed={x["source_id"] for x in candidates}
  if not set(done).issubset(allowed):raise RuntimeError("SEMANTIC_CHECKPOINT_ORPHAN")
  checked+=len(done);counts.update(x["state"] for x in done.values())
 if total!=EXPECTED_BASIC:raise RuntimeError("BASELINE_COHORT_NOT_74750:"+str(total))
 result={"schema":"v097_bronze_74750_semantic_release_gate_1","run":RUN,"at":now(),
   "baseline_byte_verified":total,"semantic_checked":checked,"semantic_remaining":total-checked,
   "states":dict(counts),"silver_ready_certified":0,
   "ready_rule":"requires dataset-specific numeric, source publication and PIT proof; these are not inferred from SHA",
   "decision":"HOLD_PENDING_SEMANTIC_AND_PUBLICATION_PROOF",
   "no_recheck_6358":True,"silver_gold_executed":False}
 put_once(api,q,"v097_BRONZE_74750_SEMANTIC_SUMMARY_%s.json"%RUN,result)
 print("BRONZE_74750_GATE="+json.dumps(result,ensure_ascii=False),flush=True)
def selftest():
 assert normalize_date("20240715")=="2024-07-15"
 assert normalize_date("113/07/15")=="2024-07-15"
 assert normalize_date("2024-02-31") is None
 r={"source_id":"1","dest_id":"2","source":"TPEx","source_path":"2024/TPEx/2024-09/a.json","year":"2024","month":"09"}
 b=b'{"date":"20261016","tables":[{"fields":["a"],"data":[["x"]]}]}'
 assert validate_file(r,b)["state"]=="HOLD_CONTENT_DATE_PATH_CONFLICT"
 print("BRONZE_74750_SELFTEST_PASS")
if __name__=="__main__":
 mode=os.getenv("BRONZE_74750_MODE","selftest")
 if mode=="selftest":selftest()
 else:
  api=service()
  if mode=="inventory":inventory(api)
  elif mode=="lane":lane(api,int(os.environ["BRONZE_LANE"]))
  elif mode=="aggregate":aggregate(api)
  else:raise SystemExit("UNKNOWN_BRONZE_74750_MODE")
