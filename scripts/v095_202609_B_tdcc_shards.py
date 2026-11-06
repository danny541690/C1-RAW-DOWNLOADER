"""Extend September TDCC inventory with real immutable shard SHA and ZIP CRC."""
import collections,datetime as dt,hashlib,io,json,os,pathlib,re,time,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
FOLDER="1_Pl4nN0HRXnIJSjJrt0iX2Lq7nkS1pcV"
REPORT_PARENT="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
OUT=pathlib.Path("v095_202609_B_tdcc");OUT.mkdir(exist_ok=True)
PAT=re.compile(r"^TDCC_202609_NATIVE_SHARD_([012])_(\d{5})\.zip$")
def digest(b):return hashlib.sha256(b).hexdigest()
def conn():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
 client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
 token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def api(fn):
 err=None
 for i in range(3):
  try:return fn().execute()
  except Exception as e:
   err=e
   if i<2:time.sleep(i+1)
 raise err
def main():
 s=conn();arr=[];tok=None
 while True:
  page=api(lambda:s.files().list(q="'"+FOLDER+"' in parents and trashed=false",
   pageSize=1000,pageToken=tok,fields="nextPageToken,files(id,name,size,mimeType)"))
  arr+=page.get("files",[]);tok=page.get("nextPageToken")
  if not tok:break
 by_group=collections.defaultdict(set);shards=[];names=set()
 for f in arr:
  m=PAT.fullmatch(f["name"])
  if m:
   if f["name"] in names:raise ValueError("DUPLICATE_TDCC_SHARD_NAME")
   names.add(f["name"]);by_group[m.group(1)].add(int(m.group(2)));shards.append(f)
 required={"0":set(range(61)),"1":set(range(61)),"2":set(range(62))}
 missing={k:sorted(required[k]-by_group[k]) for k in required}
 unexpected={k:sorted(by_group[k]-required[k]) for k in required}
 records=[]
 for f in sorted(shards,key=lambda z:z["name"]):
  x={"name":f["name"],"drive_id":f["id"],"state":"BLOCKED"}
  try:
   b=api(lambda:s.files().get_media(fileId=f["id"]))
   x.update(bytes=len(b),sha256=digest(b))
   if len(b)!=int(f.get("size",-1)):raise ValueError("BYTE_LENGTH_DIFFERENCE")
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    x["zip_members"]=len(z.namelist())
    bad=z.testzip()
    if bad is not None:raise ValueError("CRC_ERROR:"+bad)
   x["state"]="CANDIDATE_BYTES_AND_ZIP_CRC_PASS"
  except Exception as exc:x["error"]=type(exc).__name__+":"+str(exc)[:120]
  records.append(x)
 ok=sum(x["state"]=="CANDIDATE_BYTES_AND_ZIP_CRC_PASS" for x in records)
 result={"schema":"JARVIS_V095_202609_TDCC_SHARDS_B_V1",
   "run_id":os.environ.get("GITHUB_RUN_ID","local"),
   "timestamp_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "folder_items":len(arr),"shard_count":len(shards),"bytes_and_crc_pass":ok,
   "expected_shard_count":184,
   "missing_sequences":missing,"unexpected_sequences":unexpected,
   "full_184_container_verified":len(shards)==184 and ok==184 and not any(missing.values()) and not any(unexpected.values()),
   "source_to_shard_row_level_sha_certified":False,
   "source_universe_verified":False,"full_september_release":False,
   "shard_manifest":records}
 payload=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
 (OUT/"tdcc_manifest.json").write_bytes(payload)
 summary={k:v for k,v in result.items() if k!="shard_manifest"}
 (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
 created=api(lambda:s.files().create(body={"name":"JARVIS_V095_202609_TDCC_NATIVE_184_SHARDS_AUDIT_"+result["run_id"]+".json","parents":[REPORT_PARENT]},
  media_body=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/json"),fields="id"))
 if digest(api(lambda:s.files().get_media(fileId=created["id"])))!=digest(payload):
  raise RuntimeError("REPORT_DRIVE_SHA_READBACK_FAILED")
 summary["drive_manifest_id"]=created["id"]
 print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
