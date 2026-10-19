"""v0.93 STANDARD R1: strict, resumable ZIP-to-Parquet pilot (2025-01 and 2026-09).
Immutable RAW. All data MUST be date/provenance checked; unrecognized data quarantined.
No full-population, numeric-economic, PIT or 443 feature PASS is implied.
"""
import argparse,collections,datetime,hashlib,io,json,re,zipfile
import pyarrow as pa,pyarrow.parquet as pq
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
C1="1Tnxlu3BVvzUV-yM2Fe0HbwPHvQaHdePC"
SOURCES=("TWSE","TPEx","MOPS","FinMind")
LIMIT_ARCHIVE=250_000_000
LIMIT_MEMBER=30_000_000
MAX_ZIP_UNCOMPRESSED=700_000_000
def ls(d,p):
 out=[];page=None
 while True:
  x=d.call(lambda:d.api.files().list(q="'"+p+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=page))
  out+=x.get("files",[]);page=x.get("nextPageToken")
  if not page:return out
def folder(d,p,name,create=False):
 found=[x for x in ls(d,p) if x["name"]==name and x["mimeType"]=="application/vnd.google-apps.folder"]
 if len(found)>1:raise ValueError("DUPLICATE_FOLDER "+name)
 if found:return found[0]["id"]
 if create:return d.folder(p,name)
 raise FileNotFoundError(name)
def normdate(x):
 s=str(x).strip()
 if re.fullmatch(r"20\d{6}",s):return s[:4]+"-"+s[4:6]+"-"+s[6:]
 if re.fullmatch(r"20\d\d[-/]\d\d[-/]\d\d",s):return s.replace("/","-")
 return None
def numeric(x):
 if x is None:return None
 if isinstance(x,(int,float)) and not isinstance(x,bool):return float(x)
 if isinstance(x,str):
  x=x.strip().replace(",","")
  if x in ("","--","-","N/A","X","---"):return None
  if re.fullmatch(r"[-+]?\d+(?:\.\d+)?",x):return float(x)
 return None
def parse(source,name,b,period):
 if not name.lower().endswith((".json",".raw",".jsonl")):raise ValueError("UNSUPPORTED_NATIVE_FORMAT")
 try:
  if name.lower().endswith(".jsonl"):
   lines=[json.loads(x) for x in b.decode("utf-8-sig").splitlines() if x.strip()]
   obj=lines
  else:obj=json.loads(b.decode("utf-8-sig"))
 except Exception as e:raise ValueError("NATIVE_JSON_PARSE:"+str(e)[:100])
 out=[];records=[]
 def harvest(rows,fields=None,table=None):
  if not isinstance(rows,list) or not rows:return
  for v in rows:
   if fields is not None and isinstance(v,list) and len(v)==len(fields):v=dict(zip(fields,v))
   if not isinstance(v,dict):continue
   sym=next((str(v[k]).strip() for k in ("stock_id","SecuritiesCompanyCode","Code","StockCode","證券代號","股票代號","公司代號","stockNo") if v.get(k)),None)
   dt=next((normdate(v[k]) for k in ("date","Date","trade_date","日期","資料日期","年月日") if v.get(k) and normdate(v[k])),None)
   # An archive member date alone is not enough to establish historical content for OTC.
   if not sym or not re.fullmatch(r"[0-9A-Za-z]{4,8}",sym):continue
   if dt is None:continue
   if dt[:7]!=period:continue
   vals={k:numeric(v.get(k)) for k in v if numeric(v.get(k)) is not None and k not in ("stock_id","Code","StockCode","stockNo","證券代號","公司代號","股票代號")}
   if not vals:continue
   records.append((dt,sym,table or "native",v,vals))
 if isinstance(obj,list):harvest(obj)
 if isinstance(obj,dict):
  if isinstance(obj.get("data"),list):harvest(obj["data"],obj.get("fields") if isinstance(obj.get("fields"),list) else None)
  if isinstance(obj.get("tables"),list):
   for j,t in enumerate(obj["tables"]):
    if isinstance(t,dict):harvest(t.get("data"),t.get("fields"),"table_"+str(j))
  if isinstance(obj.get("aaData"),list):harvest(obj["aaData"],obj.get("fields") if isinstance(obj.get("fields"),list) else None)
 if not records:raise ValueError("NO_VERIFIED_STOCK_DATE_NUMERIC_ROWS")
 # Record field names verbatim; no invented semantic mapping. Only safe staging columns.
 for dt,sym,t,v,vals in records:
  for k,num in vals.items():
   out.append({"trade_date":dt,"stock_id":sym,"market_source":source,"native_dataset":name[:150],"native_table":t,"native_field":str(k)[:100],"raw_value":str(v[k])[:100],"numeric_unscaled":num,"qa_status":"STAGED_UNMAPPED","pit_verified":False})
 return out
def run(year,month):
 d=Drive(service());period=f"{year}-{month:02d}";root=folder(d,ROOT,str(year));standard=folder(d,C1,"02_STANDARD",True)
 yearout=folder(d,standard,str(year),True);monthout=folder(d,yearout,period,True);dataset=folder(d,monthout,"RAW_NUMERIC_STAGING",True)
 report_root=folder(d,C1,"05_CONTROL",True);report_root=folder(d,report_root,"STANDARD_QA",True)
 report={"period":period,"created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"version":"C1-v093-02_STANDARD-R1","state":"INSPECTING","archives":[],"quality":{"numeric_semantics_verified":False,"pit_verified":False,"market_coverage_complete":False,"approved_golden_copy":False},"rows_staged":0,"source_members_unparsed":0,"archive_failures":0}
 for source in SOURCES:
  srcfolder=folder(d,folder(d,root,source),period)
  archives=sorted([f for f in ls(d,srcfolder) if f["name"].lower().endswith(".zip")],key=lambda x:x["name"])
  for f in archives:
   rec={"source":source,"name":f["name"],"bytes":int(f.get("size",0)),"members":[],"status":"PENDING"}
   report["archives"].append(rec)
   try:
    if rec["bytes"]>LIMIT_ARCHIVE:raise ValueError("ZIP_EXCEEDS_LIMIT")
    raw=d.call(lambda:d.api.files().get_media(fileId=f["id"]))
    rec["sha256"]=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
     if z.testzip():raise ValueError("ZIP_CRC_ERROR")
     if sum(x.file_size for x in z.infolist())>MAX_ZIP_UNCOMPRESSED:raise ValueError("ZIP_EXPANSION_LIMIT")
     chunks=[]
     for member in z.infolist():
      if member.is_dir():continue
      ent={"member":member.filename,"bytes":member.file_size,"status":"UNPROCESSED"}
      rec["members"].append(ent)
      if member.file_size>LIMIT_MEMBER:
       ent["status"]="OVERSIZE_QUARANTINE";report["source_members_unparsed"]+=1;continue
      if not member.filename.lower().endswith((".json",".raw",".jsonl")):
       ent["status"]="NON_NUMERIC_OR_UNSUPPORTED";continue
      if any(x in member.filename.lower() for x in ("manifest","receipt","checkpoint","status","metadata")):
       ent["status"]="MANIFEST_OR_METADATA";continue
      try:
       parsed=parse(source,member.filename,z.read(member),period)
       ent["rows"]=len(parsed);ent["status"]="NUMERIC_STAGED_UNMAPPED";chunks.extend(parsed)
      except Exception as e:
       ent["status"]="QUARANTINED_UNMAPPED";ent["reason"]=str(e)[:140];report["source_members_unparsed"]+=1
     if chunks:
      table=pa.Table.from_pylist(chunks)
      buf=io.BytesIO();pq.write_table(table,buf,compression="zstd")
      outname=source+"_"+hashlib.sha256(raw).hexdigest()[:16]+"_unmapped.parquet"
      d.put(dataset,outname,buf.getvalue(),"application/octet-stream")
      rec["parquet"]=outname;rec["staged_rows"]=len(chunks);report["rows_staged"]+=len(chunks)
    rec["status"]="INSPECTED_NO_APPROVED_FIELDS"
   except Exception as e:
    rec["status"]="ARCHIVE_ERROR";rec["error"]=type(e).__name__+":"+str(e)[:180];report["archive_failures"]+=1
   print(json.dumps({"period":period,"source":source,"archive":f["name"],"status":rec["status"],"staged_rows":rec.get("staged_rows",0),"unparsed":sum(m["status"]=="QUARANTINED_UNMAPPED" for m in rec["members"])},ensure_ascii=False),flush=True)
 report["state"]="STAGING_ONLY_NOT_PRODUCTION";report["source_archive_counts"]=dict(collections.Counter(x["source"] for x in report["archives"]))
 d.put(report_root,period+"_STANDARD_R1_AUDIT.json",(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"period":period,"report":"05_CONTROL/STANDARD_QA/"+period+"_STANDARD_R1_AUDIT.json","rows_staged":report["rows_staged"],"archive_failures":report["archive_failures"],"unmapped":report["source_members_unparsed"],"golden_copy":False},ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--year",type=int,choices=(2025,2026),required=True);p.add_argument("--month",type=int,choices=range(1,13),required=True)
 a=p.parse_args();run(a.year,a.month)
