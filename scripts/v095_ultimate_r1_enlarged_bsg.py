"""v0.95 pilot enlarged October TWSE/TPEx real archive ingestion.
Bounded 8 source archives per market; verified zip CRC/native sha/date and
source-specific rows -> typed native numeric Silver + Gold descriptive search.
Immutable original copy, immutable Parquet, no PIT historical certification.
"""
import os,io,json,re,zipfile,hashlib,datetime as dt,pathlib,collections
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
OUT=pathlib.Path("ultimate_r1");OUT.mkdir(exist_ok=True)
CFG={
 "TWSE":{"old":"1su4RfhCvRt9rsSHBPOnsxfswU7vvGTUf","bronze":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE","silver":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5"},
 "TPEX":{"old":"1TbWCxikRMqrua7zL_fCBilzEshYNqcvu","bronze":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG","silver":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5"}}
GOLD="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
MAX_ARCHIVES=9;MAX_FILE_BYTES=1250000;MAX_ROWS=28000;MAX_GOLD_NUMERIC=100000
def sha(b):return hashlib.sha256(b).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def ls(d,parent):
 o=[];page=None
 while True:
  p=d.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name,size,mimeType)",pageSize=1000,pageToken=page).execute()
  o+=p.get("files",[]);page=p.get("nextPageToken")
  if not page:return o
def folder(d,parent,name):
 x=[f for f in ls(d,parent) if f["name"]==name]
 if len(x)>1:raise ValueError("DUPLICATE_FOLDER")
 if x:return x[0]["id"]
 return d.files().create(body={"name":name,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def save(d,parent,name,data):
 x=[f for f in ls(d,parent) if f["name"]==name]
 if len(x)>1:raise ValueError("AMBIGUOUS_DUPLICATE")
 if x:
  if sha(d.files().get_media(fileId=x[0]["id"]).execute())!=sha(data):raise ValueError("IMMUTABLE_CONFLICT")
  return x[0]["id"],"REUSED"
 fid=d.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(d.files().get_media(fileId=fid).execute())!=sha(data):raise ValueError("READBACK_SHA_MISMATCH")
 return fid,"CREATED"
def numeric(x):
 v=str(x).strip().replace(",","").replace("−","-")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",v):return None
 try:return float(v)
 except (ValueError,OverflowError):return None
def parse(blob,source):
 z=zipfile.ZipFile(io.BytesIO(blob))
 if z.testzip() is not None:raise ValueError("ZIP_CRC_BAD")
 if "manifest.json" not in z.namelist():raise ValueError("NO_MANIFEST")
 manifest=json.loads(z.read("manifest.json"))
 units=manifest.get("units") or []
 if not 1<=len(units)<=100:raise ValueError("INVALID_UNITS")
 out=[];gold=[];issues=[];meta=[]
 for u in units:
  if u.get("source","").upper().replace("EX","EX") not in (source,"TPEX" if source=="TPEX" else "TWSE"):
   issues.append("SOURCE_MISMATCH");continue
  if u.get("month")!="2026-10":continue
  name=u.get("file") or u.get("unit_id","")+".raw"
  if name not in z.namelist():
   name=name.split("/")[-1]
  if name not in z.namelist():issues.append("MEMBER_NOT_FOUND");continue
  b=z.read(name)
  if sha(b)!=u.get("sha256"):issues.append("SOURCE_MEMBER_HASH_MISMATCH");continue
  try:obj=json.loads(b)
  except (ValueError,UnicodeError):issues.append("NON_JSON_MEMBER");continue
  day=str(obj.get("date") or "").replace("-","")
  if not re.fullmatch(r"202610\d\d",day):issues.append("WRONG_OR_MISSING_DATE");continue
  date=dt.date(int(day[:4]),int(day[4:6]),int(day[6:]))
  tables=obj.get("tables",[])
  if not isinstance(tables,list):issues.append("INVALID_TABLES");continue
  parsed=0
  for index,t in enumerate(tables):
   fields=t.get("fields") or [];data=t.get("data") or []
   if not isinstance(fields,list) or not isinstance(data,list) or not fields:continue
   if len(data)>20000:issues.append("TOO_MANY_ROWS_TABLE");continue
   for rn,row in enumerate(data):
    if len(out)>=MAX_ROWS:issues.append("ROW_CAP_REACHED");break
    if not isinstance(row,list) or len(row)!=len(fields):issues.append("ROW_WIDTH_MISMATCH");continue
    vals=[numeric(x) for x in row]
    ident=str(row[0]).strip() if row else ""
    rec={"source":source,"trade_date":date,"category":str(u.get("category") or ""),"table_title":str(t.get("title") or ""),
     "table_index":index,"row_index":rn,"native_columns_json":json.dumps(fields,ensure_ascii=False),
     "native_values_json":json.dumps(row,ensure_ascii=False),"native_numeric_json":json.dumps(vals),
     "native_unit":"NATIVE_SOURCE_UNCONFIRMED","source_native_sha256":sha(b),"source_member":name,
     "published_at":None,"historical_pit_verified":False}
    out.append(rec);parsed+=1
    for fi,val in enumerate(vals):
     if val is None or len(gold)>=MAX_GOLD_NUMERIC:continue
     gold.append({"source":source,"trade_date":date,"category":str(u.get("category") or ""),
      "table_title":str(t.get("title") or ""),"row_label":ident,"field_name":str(fields[fi]),"numeric_native":val,
      "field_unit":"NATIVE_UNCLASSIFIED","source_member":name,"source_native_sha256":sha(b),
      "silver_input_provenance":"SILVER_SOURCE_ROW_INDEX","table_index":index,"row_index":rn,
      "field_index":fi,"historical_pit_verified":False,"usage":"DESCRIPTIVE_ONLY_NO_BACKTEST"})
  meta.append({"date":date.isoformat(),"category":u.get("category"),"member":name,"native_sha256":sha(b),"rows":parsed})
 if not out:raise ValueError("NO_VALID_NATIVE_ROWS_"+",".join(issues[:4]))
 return out,gold,meta,issues
def parquet(records):
 buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(records),buf,compression="zstd")
 b=buf.getvalue()
 if pq.read_metadata(io.BytesIO(b)).num_rows!=len(records):raise ValueError("BAD_PARQUET_ROWCOUNT")
 return b
def main():
 d=svc();report={"schema":"JARVIS_V095_202610_ENLARGED_BSG_V1","run_id":os.getenv("GITHUB_RUN_ID"),
   "scope":"2026-10 only; 2026-09 existing reused and 2026-11 not yet available","sources":{},"failures":{},"pit":False}
 for source,ids in CFG.items():
  try:
   files=ls(d,ids["old"]);files=sorted((x for x in files if x["name"].lower().endswith(".zip") and 500<int(x.get("size") or 0)<MAX_FILE_BYTES),key=lambda x:x["name"])
   files=files[:MAX_ARCHIVES];silver=[];gold=[];receipts=[];failed=[]
   bronze_month=folder(d,ids["bronze"],"2026-10")
   for f in files:
    try:
     blob=d.files().get_media(fileId=f["id"]).execute()
     rows,features,unitmeta,issues=parse(blob,source)
     digest=sha(blob)
     bfid,action=save(d,bronze_month,"V095_V093_202610_"+source+"_"+digest[:24]+".zip",blob)
     for row in rows:row["source_bronze_file_id"]=bfid;row["source_bronze_sha256"]=digest
     for row in features:row["source_bronze_file_id"]=bfid;row["source_bronze_sha256"]=digest
     silver+=rows;gold+=features
     receipts.append({"source_file":f["id"],"bronze_id":bfid,"sha256":digest,"action":action,"units":unitmeta,"issues":issues[:10],"silver_rows":len(rows),"gold_numeric_rows":len(features)})
    except Exception as e:failed.append({"file":f["id"],"error":type(e).__name__+":"+str(e)[:110]})
   if not silver:raise ValueError("NO_SOURCE_ARCHIVES_CONVERTIBLE")
   # Stable deterministic order independent of metadata listing.
   silver.sort(key=lambda x:(x["trade_date"],x["source_native_sha256"],x["table_index"],x["row_index"]))
   gold.sort(key=lambda x:(x["trade_date"],x["source_native_sha256"],x["table_index"],x["row_index"],x["field_index"]))
   b1=parquet(silver);bs=sha(b1)
   p=folder(d,ids["silver"],"2026-10_NATIVE_CANDIDATE")
   sid,sa=save(d,p,"V095_202610_"+source+"_NATIVE_SILVER_"+bs[:20]+".parquet",b1)
   for row in gold:row["silver_file_id"]=sid;row["silver_sha256"]=bs
   b2=parquet(gold);bg=sha(b2)
   gp=folder(d,GOLD,"2026-10_DESCRIPTIVE_ONLY")
   gid,ga=save(d,gp,"V095_202610_"+source+"_NATIVE_GOLD_"+bg[:20]+".parquet",b2)
   report["sources"][source]={"raw_archives":len(receipts),"bronze_new_or_reused":[r["action"] for r in receipts],
    "silver_rows":len(silver),"gold_numeric_rows":len(gold),"silver_id":sid,"silver_sha256":bs,"gold_id":gid,"gold_sha256":bg,
    "archive_receipts":receipts,"rejected_files":failed,
    "scope":"selected source 2026-10 files, not full month",
    "silver_status":"NATIVE_CANDIDATE_FIELD_REORDER_NO_UNIT_CERTIFICATION",
    "gold_status":"DESCRIPTIVE_NATIVE_NUMERIC_NOT_443_FORMULA_CERTIFIED"}
  except Exception as e:report["failures"][source]={"error":type(e).__name__+":"+str(e)[:200]}
 (OUT/"october_enlarged_bsg.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str))
 print(json.dumps({"run_id":report["run_id"],"sources":{k:{x:v[x] for x in ("raw_archives","silver_rows","gold_numeric_rows","silver_id","gold_id")} for k,v in report["sources"].items()},"failures":report["failures"],"pit":False},ensure_ascii=False))
if __name__=="__main__":main()
