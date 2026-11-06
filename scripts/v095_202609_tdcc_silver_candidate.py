"""Convert original September 2026 TDCC weekly Bronze partition JSONL to isolated Silver Parquet.
Derived weekly JSONL from original HTML; preserve source record and native archive SHA.
"""
import os,io,zipfile,json,re,decimal,hashlib,pathlib,collections,time,socket,ssl,http.client
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
SRC="1sRULF-1_1UTf5x2E6mWoDVx0BgdP2GS8"
DEST="1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U"
MONTH="2026-09_CANDIDATE_98_GATE"
WEEKS={"2026-09-04","2026-09-11","2026-09-18","2026-09-24"}
def sha(x):return hashlib.sha256(x).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def execute_retry(factory, label, attempts=4):
 for i in range(attempts):
  try:return factory().execute()
  except (BrokenPipeError,ConnectionError,TimeoutError,OSError,http.client.HTTPException,ssl.SSLError) as e:
   if i==attempts-1:raise
   delay=min(30,2**i*3)
   print(json.dumps({"label":label,"attempt":i+1,"error":type(e).__name__,"backoff_seconds":delay}),flush=True)
   time.sleep(delay)
def raw(s,id):return execute_retry(lambda:s.files().get_media(fileId=id),"TDCC_RAW_MEDIA")
def save(s,folder,name,b):
 a=execute_retry(lambda:s.files().list(q=f"'{folder}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=50),"TDCC_FIND_OUTPUT")["files"]
 if len(a)>1:raise ValueError("AMBIGUOUS_EXISTING_FILE")
 if a:
  if sha(raw(s,a[0]["id"]))!=sha(b):raise ValueError("CONFLICT_DIFFERENT_GENERATION")
  return a[0]["id"]
 x=s.files().create(body={"name":name,"parents":[folder]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(raw(s,x))!=sha(b):raise ValueError("DRIVE_READBACK_SHA_FAIL")
 return x
def main():
 s=svc();z=zipfile.ZipFile(io.BytesIO(raw(s,SRC)))
 if z.testzip() is not None:raise ValueError("TDCC_ARCHIVE_CRC")
 manifest=json.loads(z.read("complement_manifest_R1.json"))
 assert len(manifest["files"])==4
 out=[];keyset=set();counts=collections.Counter()
 for x in manifest["files"]:
  name=x["file"].split("/")[-1];b=z.read(name)
  if sha(b)!=x["sha256"]:raise ValueError("TDCC_PARTITION_SHA")
  match=re.search(r"distribution_(2026-09-\d\d)_",name)
  if not match or match.group(1) not in WEEKS:raise ValueError("TDCC_WEEK_DATE")
  day=match.group(1)
  for idx,line in enumerate(b.splitlines()):
   q=json.loads(line);record=q["source_record"]
   ymd=str(record["資料日期"])
   if ymd!=day.replace("-",""):raise ValueError("TDCC_CONTENT_DATE")
   code=str(record["證券代號"]).strip();tier=str(record["持股分級"]).strip()
   key=(day,code,tier)
   if key in keyset:raise ValueError("TDCC_DUPLICATE_STOCK_TIER")
   keyset.add(key)
   people=int(str(record["人數"]).replace(",",""))
   shares=int(str(record["股數"]).replace(",",""))
   ratio=decimal.Decimal(str(record["占集保庫存數比例%"]).replace(",",""))
   if people<0 or shares<0:raise ValueError("NEGATIVE_HOLDINGS")
   counts[day]+=1
   out.append(dict(snapshot_date=day,stock_id=code,holding_tier=tier,people_count=people,
    shares=shares,share_percent=str(ratio),source="TDCC",
    source_archive_id=SRC,source_member=name,source_sha256=sha(b),original_row_index=idx,
    native_record_json=json.dumps(record,ensure_ascii=False),
    published_at=None,pit_verified=False,normalization_version="TDCC_WEEKLY_202609_CANDIDATE_R1"))
 if set(counts)!=WEEKS or len(out)!=276097:raise ValueError("TDCC_PARTITION_ROW_TOTAL_MISMATCH:"+str(dict(counts)))
 a=execute_retry(lambda:s.files().list(q=f"'{DEST}' in parents and name = '{MONTH}' and trashed = false",pageSize=50,fields="files(id)"),"TDCC_FIND_MONTH")["files"]
 if len(a)>1:raise ValueError("DUPLICATE_MONTH_FOLDER")
 folder=a[0]["id"] if a else s.files().create(body={"name":MONTH,"parents":[DEST],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
 data=io.BytesIO();pq.write_table(pa.Table.from_pylist(out),data,compression="zstd")
 b=data.getvalue();assert pq.read_metadata(io.BytesIO(b)).num_rows==len(out)
 parquet_id=save(s,folder,"JARVIS_v095_202609_TDCC_OWNERSHIP_CANDIDATE_R1.parquet",b)
 report=dict(schema="JARVIS_v095_202609_TDCC_SILVER_CANDIDATE",rows=len(out),
  week_counts=dict(counts),native_weekly_manifest_sha_verified=True,
  native_10949_html_corpus_handoff_verified_separately=True,
  parquet_drive_id=parquet_id,parquet_sha256=sha(b),silver_status="CANDIDATE_NOT_RELEASED",
  source="TDCC",pit_verified=False,gold_allowed=False,
  unresolved=["source publication/availability timestamp","cross-check all derived weekly rows to native 10949 HTML sources","source security master including emerging-save-only"])
 qa_id=save(s,folder,"JARVIS_v095_202609_TDCC_OWNERSHIP_QA_R1.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
 report["qa_drive_id"]=qa_id
 pathlib.Path("v095_silver_tdcc_202609").mkdir(exist_ok=True)
 pathlib.Path("v095_silver_tdcc_202609/result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
