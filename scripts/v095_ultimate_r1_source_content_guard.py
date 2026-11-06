"""JARVIS v0.95 source-content guard for v0.93 October folders.
Prevents misfiled offshore-fund data from being promoted as TDCC ownership.
Conservative finite audit; QA report to Drive with readback, no raw mutation.
"""
import os,json,re,io,hashlib,datetime,pathlib,collections
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SRC={"TDCC":"1Oz0JLNdt6WPRj2gmt9uZLcXzpQDtB6BU","MOPS":"13_1lZ_7W2KAUJ3wdHW-cq9dg93WV2sMr"}
DEST="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
OUT=pathlib.Path("ultimate_r1");OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def connect():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def ls(s,fid):
 rows=[];nextp=None
 while True:
  z=s.files().list(q="'"+fid+"' in parents and trashed=false",fields="nextPageToken,files(id,name,size,mimeType)",pageSize=1000,pageToken=nextp).execute()
  rows+=z.get("files",[]);nextp=z.get("nextPageToken")
  if not nextp:return rows
def classify(data):
 if isinstance(data,list):
  x=next((r for r in data if isinstance(r,dict)),{})
 elif isinstance(data,dict):
  x=data
 else:return "UNEXPECTED_STRUCTURE",[]
 keys={str(k).replace("\ufeff","").strip() for k in x}
 if any(k in keys for k in ("基金名稱","基金總代理","基金總代理名稱","境外基金機構","銷售機構","最新淨值小計(總額)")):
  return "MISFILED_FUND_DATA_NOT_TDCC_SHAREHOLDER",sorted(keys)[:16]
 stock=bool(keys & {"證券代號","股票代號","證券代碼","股票代碼","股票名稱"})
 holders=bool(keys & {"持股分級","持股人數","持股股數","股東人數","股數級距","集保戶數","持有股數"})
 return ("POSSIBLE_TDCC_REQUIRES_FULL_SCHEMA_QA" if stock and holders else "UNCLASSIFIED_NOT_TDCC_CERTIFIED"),sorted(keys)[:16]
def main():
 s=connect();r={"schema":"JARVIS_V095_V093_OCT_SOURCE_CONTENT_GUARD_V1","run_id":os.environ.get("GITHUB_RUN_ID"),"date":"2026-11-06","scope":"2026-10 v093 legacy source folders","report_only":True,"sources":{}}
 for source,folder in SRC.items():
  files=ls(s,folder)
  rows=[];candidates=sorted((x for x in files if int(x.get("size") or 0)>0 and int(x.get("size") or 0)<=1500000),key=lambda x:(int(x.get("size") or 0),x["name"]))
  for f in candidates[:10]:
   row={"name":f["name"],"id":f["id"],"bytes":int(f.get("size") or 0)}
   try:
    b=s.files().get_media(fileId=f["id"]).execute();row["sha256"]=sha(b)
    if f["name"].endswith(".json"):
     k,h=classify(json.loads(b.decode("utf-8-sig")));row.update(classification=k,keys_sample=h)
    elif f["name"].endswith(".zip"):
     import zipfile
     with zipfile.ZipFile(io.BytesIO(b)) as z:
      if z.testzip():raise ValueError("ZIP_BAD_CRC")
      row.update(classification="ZIP_VALID_STRUCTURE_NOT_DATASET_CERTIFIED",members=z.namelist()[:12])
    else:row.update(classification="FORMAT_NOT_YET_PARSABLE")
   except Exception as e:row.update(classification="QUARANTINE_PARSE_FAILURE",error=type(e).__name__+":"+str(e)[:150])
   rows.append(row)
  r["sources"][source]={"total_files":len(files),"sampled":len(rows),"classification_counts":dict(collections.Counter(x["classification"] for x in rows)),"samples":rows,"bronze_released":0}
 raw=json.dumps(r,ensure_ascii=False,indent=2).encode()
 name="JARVIS_V095_V093_OCT_SOURCE_CONTENT_GUARD_"+sha(raw)[:16]+".json"
 found=[x for x in ls(s,DEST) if x["name"]==name]
 if len(found)>1:raise ValueError("DUPLICATE_REPORT")
 if found:fid=found[0]["id"]
 else:fid=s.files().create(body={"name":name,"parents":[DEST]},media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json"),fields="id").execute()["id"]
 if sha(s.files().get_media(fileId=fid).execute())!=sha(raw):raise ValueError("SHA_READBACK")
 (OUT/"source_content_guard_202610.json").write_bytes(raw)
 print(json.dumps({"run_id":r["run_id"],"report_drive_id":fid,"classifications":{k:v["classification_counts"] for k,v in r["sources"].items()},"promotion_allowed":False},ensure_ascii=False))
if __name__=="__main__":main()
