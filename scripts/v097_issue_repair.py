#!/usr/bin/env python3
"""JARVIS v0.97 R3: issue-ledger driven repair and validation; v0.93 strictly read-only.
R2 receipts are the input, never the entire original inventory. No silent certification.
"""
import csv,hashlib,io,json,os,re,time,random,zipfile
from collections import Counter
from datetime import datetime,timezone
from html.parser import HTMLParser
from googleapiclient.errors import HttpError
from scripts.v097_bronze_content_qa import service,call,children,folder,load_json,save
from scripts.v097_bronze_diagnosis import save_or_update
from scripts.v097_bronze_remediation import load_registry,provider_reacquire
from scripts.v097_round2_verify import dirs,one,decode
RUN=os.environ.get("GITHUB_RUN_ID","manual")
LANES=12
RX=re.compile(r"^v097_R2_(\d+)_(\d\d)_(\d\d)[.]json$")
PRIORITY={
 "QUARANTINED_JSON_ERROR":0,"QUARANTINED_ZIP_ERROR":0,"QUARANTINED_MD5_MISMATCH":0,
 "QUARANTINED_SIZE_MISMATCH":0,"QUARANTINED_EMPTY":0,"EXCEPTION_READ_FAILURE":0,
 "QUARANTINED_TEXT_PARSE":0,"QUARANTINED_HTML_DECODING":0,
 "QUARANTINED_PDF_INVALID":0,"QUARANTINED_EMPTY_JSON":0,"QUARANTINED_EMPTY_ZIP":0,
 "QUARANTINED_UNSAFE_ZIP":0,"EXCEPTION_BOUNDED_SIZE":1,
 "EXCEPTION_NEEDS_STREAMED_ZIP_PARSER":1,"EXCEPTION_SPREADSHEET_PARSER_PENDING":1,
 "EXCEPTION_UNKNOWN_FORMAT":1,
 "TDCC_TABLE_NUMERIC_PENDING":2,
 "ZIP_MIXED_ARCHIVE_CONTENT_PENDING":3,"ZIP_CRC_PASS_CONTENT_PENDING":3,
 "JSON_SCHEMA_CONTENT_PENDING":4,"CSV_SCHEMA_CONTENT_PENDING":4,
 "HTML_TABLE_CONTENT_PENDING":4,"HTML_SCHEMA_PENDING":4,
 "CSV_SCHEMA_PENDING":4,"JSON_ROWS_PARSED_PIT_PENDING":5,
 "PDF_CONTENT_PENDING":5,
}
MAX_BATCH=min(60,max(1,int(os.getenv("R3_BATCH","24"))))
MAX_CYCLES=min(25,max(1,int(os.getenv("R3_CYCLES","8"))))
def now():return datetime.now(timezone.utc).isoformat()
def qdirs(api):
 m,ck,quality=dirs(api)
 return m,ck,quality,folder(api,folder(api,folder(api,"root","ChatGPT資料存取"),"JARVIS_C1_v097_LIFECYCLE"),"03_DATA_QUALITY") #unused
def ledger_folders(api):
 m,c,q=dirs(api)
 return m,c,q
def save_check(api,p,name,data,existing):
 for n in range(8):
  try:
   save_or_update(api,p,name,data,existing)
   return
  except HttpError as e:
   if e.resp.status not in (403,429,500,502,503,504):raise
   try:
    f=one(api,p,name)
    if f and load_json(api,f["id"]).get("done")==data.get("done"):return
   except Exception:pass
   if n==7:raise
   time.sleep(min(80,3*(2**n))+random.random())
def prepare(api):
 m,c,q=ledger_folders(api)
 mark=one(api,m,"v097_R3_ISSUE_FROZEN.json")
 if mark:
  v=load_json(api,mark["id"])
  if v["schema"]!="r3_frozen_1":raise RuntimeError("Bad frozen R3 manifest")
  for i in range(LANES):
   if not one(api,m,"v097_R3_QUEUE_%02d.json"%i):raise RuntimeError("Incomplete frozen R3 queue")
  print("R3_FROZEN_EXISTING",v["total"],flush=True);return
 files=[x for x in children(api,q) if RX.fullmatch(x["name"])]
 if not files:raise RuntimeError("R2 receipts not found: cannot infer errors")
 files.sort(key=lambda f:(int(RX.fullmatch(f["name"]).group(1)),int(RX.fullmatch(f["name"]).group(3))))
 shard={i:{} for i in range(LANES)}
 for count,f in enumerate(files):
  mat=RX.fullmatch(f["name"]);idx=int(mat.group(2))
  if idx>=LANES:raise RuntimeError("Unexpected lane in R2 receipt")
  v=load_json(api,f["id"])
  if v.get("schema")!="r2_receipt_1" or v.get("lane")!=idx:raise RuntimeError("Invalid R2 receipt")
  for r in v["results"]:
   fid=r.get("file_id");status=r.get("status")
   if not fid or not status:raise RuntimeError("Missing R2 issue fields")
   if status not in PRIORITY:raise RuntimeError("Unknown R2 status "+status)
   prior=shard[idx].get(fid)
   entry={"file_id":fid,"source":r.get("source"),"path":r.get("path",""),"year":r.get("year"),
          "prior_status":status,"prior_sha256":r.get("sha256"),"prior_run":mat.group(1)}
   if prior and prior["prior_status"]!=status:raise RuntimeError("Conflicting immutable R2 evidence")
   shard[idx][fid]=entry
  if count%100==0:print("R3_RECEIPTS",count+1,len(files),flush=True)
 total=0;cnt=Counter()
 for i in range(LANES):
  rows=list(shard[i].values());rows.sort(key=lambda r:(PRIORITY[r["prior_status"]],r["file_id"]))
  total+=len(rows);cnt.update(x["prior_status"] for x in rows)
  blob={"schema":"r3_issue_queue_1","lane":i,"created":now(),"source":"R2_IMMUTABLE_RECEIPTS","items":rows}
  name="v097_R3_QUEUE_%02d.json"%i
  f=one(api,m,name)
  if f:
   original=load_json(api,f["id"])
   if [(x["file_id"],x["prior_status"]) for x in original["items"]]!=[(x["file_id"],x["prior_status"]) for x in rows]:
    raise RuntimeError("Partial queue conflict")
  else:save(api,m,name,blob)
  print("R3_QUEUE",i,len(rows),flush=True)
 save(api,m,"v097_R3_ISSUE_FROZEN.json",{"schema":"r3_frozen_1","created":now(),
     "total":total,"classes":dict(cnt),"counts":{str(i):len(shard[i]) for i in range(LANES)},
     "source_receipts":len(files),"certified":0})
 print("R3_ISSUES_FROZEN",total,flush=True)
class TableParser(HTMLParser):
 def __init__(self):
  super().__init__();self.row=[];self.rows=[];self.cell=False;self.text=""
 def handle_starttag(self,t,attrs):
  if t=="tr":self.row=[]
  if t in ("td","th"):self.cell=True;self.text=""
 def handle_data(self,t):
  if self.cell:self.text+=t
 def handle_endtag(self,t):
  if t in ("td","th"):
   self.cell=False;self.row.append(self.text.strip())
  if t=="tr" and self.row:self.rows.append(self.row)
def numeric(s):
 return float(s.replace(",","").replace("%","")) if re.fullmatch(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?",s.strip()) else None
def validate_tdcc(text):
 p=TableParser();p.feed(text)
 grades=[];percentages=[]
 for row in p.rows:
  joined="".join(row)
  if "持股" in joined and ("比例" in joined or "分級" in joined):continue
  cells=[numeric(x.strip()) for x in row]
  if len(cells)>=4 and any(x is not None for x in cells):
   grades.append(cells)
   percentages.extend(float(x.rstrip("%")) for x in row if re.fullmatch(r"\d+(?:\.\d+)?%",x.strip()))
 if not grades:return {"state":"TDCC_SCHEMA_UNRECOGNIZED","rows":len(p.rows)}
 # Without source-specific header mapping, cannot assert column sums or stock universe correctness.
 return {"state":"TDCC_NUMERIC_CELLS_PARSED_NEEDS_GRADE_TOTAL_VALIDATION",
         "rows":len(p.rows),"numeric_rows":len(grades),"percentage_cells":len(percentages)}
def validate_json(blob):
 fixes=[]
 for enc in ("utf-8-sig","cp950","big5"):
  try:
   obj=json.loads(blob.decode(enc))
   if enc!="utf-8-sig":fixes.append("TRANSCODE_"+enc)
   break
  except (UnicodeError,ValueError):obj=None
 if obj is None:
  if blob.lstrip().startswith((b"<html",b"<!DOCTYPE",b"<HTML")):
   return {"state":"UPSTREAM_HTML_ERROR_NOT_JSON"}
  return {"state":"JSON_PARSING_FAILURE_NO_SAFE_REPAIR"}
 if isinstance(obj,dict):
  if "data" in obj and not isinstance(obj["data"],(dict,list)):
   return {"state":"JSON_UNEXPECTED_DATA_TYPE","top_keys":list(obj)[:12]}
  items=obj.get("data")
  if isinstance(items,list) and not items and obj.get("status") not in (None,200):
   return {"state":"UPSTREAM_API_ERROR","api_status":obj.get("status")}
  if not isinstance(items,list):
   return {"state":"JSON_SCHEMA_MAPPING_REQUIRED","top_keys":list(obj)[:15]}
  n=len(items)
 elif isinstance(obj,list):n=len(obj)
 else:return {"state":"JSON_NOT_TABULAR"}
 return {"state":"JSON_PARSED_REQUIRES_SOURCE_SCHEMA_PIT","row_count":n,"fixes":fixes,"object":obj if fixes else None}
def validate_zip(blob):
 try:
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   info=z.infolist();total=sum(x.file_size for x in info)
   if not info:return {"state":"ZIP_EMPTY"}
   if total>256*1024*1024:return {"state":"ZIP_LARGE_REQUIRES_STREAMING","bytes":total}
   states=Counter();market=0
   for it in info:
    if it.is_dir():continue
    if it.filename.startswith("/") or ".." in it.filename.split("/"):
     return {"state":"ZIP_UNSAFE_PATH"}
    with z.open(it) as f:
     data=f.read(min(it.file_size,2*1024*1024)+1)
     while f.read(262144):pass
    is_control=bool(re.search(r"manifest|checkpoint|receipt|report|control",it.filename,re.I))
    if is_control:states["control"]+=1;continue
    market+=1;ext=it.filename.lower().rsplit(".",1)[-1]
    if ext=="json":
     states["json_parseable" if validate_json(data)["state"]=="JSON_PARSED_REQUIRES_SOURCE_SCHEMA_PIT" else "json_schema_or_error"]+=1
    elif ext in ("csv","txt","tsv","html","htm","xls","xlsx","pdf"):
     states[ext]+=1
    else:states["other"]+=1
   return {"state":"ZIP_MEMBERS_PARSED_SOURCE_SCHEMA_PENDING","market_members":market,
           "member_types":dict(states),"members":len(info)}
 except (zipfile.BadZipFile,RuntimeError,EOFError,ValueError) as e:
  return {"state":"ZIP_INTEGRITY_FAILURE","reason":type(e).__name__}
def verify_one(api,item,registry,lane):
 fid=item["file_id"];status=item["prior_status"];out={"file_id":fid,"source":item["source"],"prior_status":status,
  "r3_at":now(),"original_modified":False,"numeric_certified":False,"pit_certified":False,
  "repair_attempted":False,"outcome":"EXCEPTION_REQUIRES_REVIEW"}
 # Avoid redundant reading for R2-parse-successful files, where missing PIT must be resolved from publication metadata.
 if status in ("JSON_ROWS_PARSED_PIT_PENDING","PDF_CONTENT_PENDING"):
  out["outcome"]="PIT_OR_DOCUMENT_RULE_PENDING";return out
 try:
  meta=call(lambda:api.files().get(fileId=fid,fields="id,size,md5Checksum,name"))
  if int(meta.get("size") or 0)>40*1024*1024:
   out["outcome"]="LARGE_FILE_NEEDS_BOUNDED_STREAMING";return out
  blob=call(lambda:api.files().get_media(fileId=fid))
  if meta.get("md5Checksum") and hashlib.md5(blob).hexdigest()!=meta["md5Checksum"]:
   out["outcome"]="SOURCE_MD5_MISMATCH";return out
  sha=hashlib.sha256(blob).hexdigest();out["sha256"]=sha
  if item.get("prior_sha256") and item["prior_sha256"]!=sha:
   out["outcome"]="SOURCE_BYTES_CHANGED_SINCE_R2";return out
  name=meta.get("name") or item.get("path","");ext=name.lower().rsplit(".",1)[-1]
  if status.startswith("ZIP_") or "ZIP" in status or blob[:4]==b"PK\x03\x04":
   analysis=validate_zip(blob)
  elif item["source"]=="TDCC" and (ext in ("html","htm") or blob.lstrip().lower().startswith(b"<!doctype html")):
   text,encoding=decode(blob);analysis=validate_tdcc(text);analysis["encoding"]=encoding
  elif ext in ("json","raw") or status.startswith("JSON_") or status=="QUARANTINED_JSON_ERROR":
   analysis=validate_json(blob)
  elif ext in ("csv","tsv","txt"):
   text,encoding=decode(blob);reader=csv.reader(io.StringIO(text),delimiter="\t" if ext=="tsv" else ",")
   first=[];widths=Counter()
   for i,row in enumerate(reader):
    widths[len(row)]+=1
    if i<3:first.append(row[:18])
   analysis={"state":"CSV_ROWS_PARSED_SOURCE_SCHEMA_PENDING","rows":sum(widths.values()),
             "width_counts":dict(widths),"encoding":encoding,"head":first}
   if len(widths)>1:analysis["state"]="CSV_ROW_WIDTH_MISMATCH_REVIEW"
  else:analysis={"state":"FORMAT_NEEDS_DATASET_PARSER"}
  normalized=analysis.pop("object",None)
  out["analysis"]=analysis
  out["outcome"]=analysis["state"]
  if normalized is not None and analysis["state"]=="JSON_PARSED_REQUIRES_SOURCE_SCHEMA_PIT":
   # Data-safe transformation ONLY: a new independent recovery candidate. Source remains untouched.
   q=ledger_folders(api)[2]
   b=json.dumps(normalized,ensure_ascii=False,separators=(",",":")).encode("utf-8")
   saved=save(api,q,"v097_R3_CANDIDATE_%s_%d_%s.json"%(RUN,lane,sha[:16]),b)
   out.update(repair_attempted=True,recovered_candidate_id=saved["id"],
              candidate_sha256=hashlib.sha256(b).hexdigest(),
              outcome="REPAIRED_ENCODING_CANDIDATE_PENDING_SEMANTIC_PIT")
  # Only hard failures get exact source reacquisition, and only if a verified registry mapping exists.
  hard=status.startswith("QUARANTINED_") or status.startswith("EXCEPTION_")
  if hard and out["outcome"] not in ("REPAIRED_ENCODING_CANDIDATE_PENDING_SEMANTIC_PIT",):
   if (registry.get(fid) or {}).get("providers"):
    source_row={"file_id":fid,"source":item["source"],"path":item.get("path",""),
      "file_name":name,"year":item.get("year"),"month":None}
    rec=provider_reacquire(api,source_row,{"r3_issue":status},registry,RUN,lane)
    out["repair_attempted"]=True;out["source_reacquire"]=rec
    if rec.get("state")=="RECOVERED_TO_QUARANTINE":out["outcome"]="SOURCE_REACQUIRED_CANDIDATE_PENDING_SEMANTIC_PIT"
   else:out["repair_blocker"]="NO_VERIFIED_SOURCE_URL_OR_EQUIVALENT_DATASET"
  return out
 except Exception as e:
  out.update(outcome="EXCEPTION_ACCESS_OR_PARSER",reason=type(e).__name__,message=str(e)[:120])
  return out
def worker(api,lane):
 m,c,q=ledger_folders(api);ref=one(api,m,"v097_R3_QUEUE_%02d.json"%lane)
 if not ref:raise RuntimeError("No R3 queue")
 rows=load_json(api,ref["id"])["items"];ckname="v097_R3_CK_%02d.json"%lane
 fck=one(api,c,ckname)
 ck=load_json(api,fck["id"]) if fck else {"schema":"r3_ck_1","lane":lane,"done":[],"outcomes":{}}
 if ck["schema"]!="r3_ck_1" or ck["lane"]!=lane:raise RuntimeError("R3 bad checkpoint")
 done=set(ck["done"]);allowed={r["file_id"] for r in rows}
 if not done.issubset(allowed):raise RuntimeError("R3 checkpoint IDs outside queue")
 counts=Counter(ck["outcomes"])
 registry=load_registry(api)
 for cycle in range(MAX_CYCLES):
  todo=[r for r in rows if r["file_id"] not in done][:MAX_BATCH]
  if not todo:break
  recname="v097_R3_%s_%02d_%02d.json"%(RUN,lane,cycle)
  prior=one(api,q,recname)
  if prior:
   results=load_json(api,prior["id"])["results"]
   if [x["file_id"] for x in results]!=[x["file_id"] for x in todo]:raise RuntimeError("R3 receipt mismatch")
  else:
   results=[verify_one(api,r,registry,lane) for r in todo]
   save(api,q,recname,{"schema":"r3_result_1","run_id":RUN,"lane":lane,"results":results,"utc":now()})
  for r in results:
   if r["file_id"] not in done:
    done.add(r["file_id"]);counts[r["outcome"]]+=1
  ck={"schema":"r3_ck_1","lane":lane,"eligible":len(rows),"done":sorted(done),
      "remaining":len(rows)-len(done),"outcomes":dict(counts),"last_run":RUN,"updated":now()}
  save_check(api,c,ckname,ck,fck["id"] if fck else None)
  if not fck:fck=one(api,c,ckname)
  print("R3_PROGRESS",lane,len(done),len(rows),flush=True)
def aggregate(api):
 m,c,q=ledger_folders(api);f=one(api,m,"v097_R3_ISSUE_FROZEN.json")
 frozen=load_json(api,f["id"]);lanes=[];total=0;remaining=0;counter=Counter()
 for lane in range(LANES):
  name="v097_R3_CK_%02d.json"%lane;f=one(api,c,name)
  if not f:
   expected=frozen["counts"][str(lane)];lanes.append({"lane":lane,"done":0,"remaining":expected})
   remaining+=expected;continue
  d=load_json(api,f["id"])
  if d["eligible"]!=frozen["counts"][str(lane)] or len(d["done"])+d["remaining"]!=d["eligible"]:raise RuntimeError("R3 ledger conservation failed")
  total+=len(d["done"]);remaining+=d["remaining"];counter.update(d["outcomes"])
  lanes.append({"lane":lane,"done":len(d["done"]),"remaining":d["remaining"]})
 if total+remaining!=frozen["total"]:raise RuntimeError("R3 aggregate conservation failure")
 outcome={"schema":"r3_summary_1","run":RUN,"utc":now(),"issues_total":frozen["total"],
   "processed":total,"remaining":remaining,"outcomes":dict(counter),"lanes":lanes,
   "numeric_certified":0,"pit_certified":0,"bronze_certified":0,
   "note":"Issue-specific repair candidates and semantic review are not automatically certified."}
 save(api,q,"v097_R3_%s_SUMMARY.json"%RUN,outcome)
 if os.getenv("GITHUB_OUTPUT"):
  with open(os.environ["GITHUB_OUTPUT"],"a") as f:f.write("remaining=%d\n"%remaining)
 print("R3_SUMMARY",json.dumps({k:v for k,v in outcome.items() if k!="lanes"}),flush=True)
if __name__=="__main__":
 api=service();mode=os.getenv("R3_MODE")
 if mode=="prepare":prepare(api)
 elif mode=="worker":worker(api,int(os.environ["R3_LANE"]))
 elif mode=="aggregate":aggregate(api)
 else:raise RuntimeError("R3_MODE missing")
