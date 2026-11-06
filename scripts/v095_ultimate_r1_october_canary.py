"""Bounded v0.93->v0.95 October ingestion canary: real bytes, immutable candidate copy.
Does not label any pilot data certified Bronze without a dataset contract and SHA/readback.
No official scraping, no historical promotion, no full-month processing.
"""
import io,os,json,time,hashlib,zipfile,pathlib,datetime,csv,re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
OUT=pathlib.Path("ultimate_r1");OUT.mkdir(exist_ok=True)
MONTH="2026-10"; CANDIDATE_PARENT="1McG_uf3UwVYv0nEZv9R1cpQM4iFJfjBw"
V093={"TWSE":"1su4RfhCvRt9rsSHBPOnsxfswU7vvGTUf","TPEX":"1TbWCxikRMqrua7zL_fCBilzEshYNqcvu","MOPS":"13_1lZ_7W2KAUJ3wdHW-cq9dg93WV2sMr","TAIFEX":"1Mu0jdIfzTMokDzOBJ-rjtV0QztBHjmDf"}
MAX_BYTES=250000;MAX_COPIES=3
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def ls(s,parent):
 o=[];page=None
 while True:
  x=s.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name,size,mimeType,md5Checksum,createdTime)",pageSize=1000,pageToken=page).execute()
  o+=x.get("files",[]);page=x.get("nextPageToken")
  if not page:return o
def sha(b):return hashlib.sha256(b).hexdigest()
def valid(f,b):
 n=f["name"].lower()
 if len(b)!=int(f.get("size") or -1):return "SIZE_MISMATCH",None
 if not b:return "EMPTY",None
 if n.endswith(".zip"):
  try:
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    members=z.namelist()
    if not members or not any(not x.endswith("/") for x in members):return "ZIP_EMPTY",None
    if z.testzip() is not None:return "ZIP_BAD_CRC",None
    inside=[x for x in members if "202610" in x or "2026-10" in x]
    if not inside:return "ZIP_CONTENT_DATE_NOT_VERIFIED",{"members":len(members)}
    return "ZIP_CRC_MONTH_MEMBER_PASS",{"members":len(members),"month_member_examples":inside[:3]}
  except (zipfile.BadZipFile,OSError):return "INVALID_ZIP",None
 if n.endswith(".csv"):
  if b"\x00" in b:return "BINARY_CSV",None
  try:
   txt=b.decode("utf-8-sig")
  except UnicodeError:
   try:txt=b.decode("cp950")
   except UnicodeError:return "UNREADABLE_ENCODING",None
  row=next(csv.reader(io.StringIO(txt)),[])
  if len(row)<3:return "CSV_TOO_FEW_FIELDS",None
  if "202610" not in n and "2026-10" not in n:return "CSV_FILENAME_DATE_UNVERIFIED",None
  return "CSV_PARSE_AND_MONTH_FILENAME_PASS",{"header":row[:12],"lines":txt.count("\n")+1}
 return "UNSUPPORTED_FORMAT",None
def main():
 s=api();run=os.environ.get("GITHUB_RUN_ID","local");summary={"schema":"JARVIS_V095_202610_STAGING_CANDIDATE_V1","run":run,"status":"BOUNDED_REAL_COPY_ONLY","source_priority":"V093_FIRST","month":MONTH,"candidates":[],"rejected":[],"copies":0,"bytes_copied":0,"max_copies":MAX_COPIES}
 for source,parent in V093.items():
  files=ls(s,parent)
  inspected=0
  # Prefer October-specific small files: never read massive TDCC, no multiple concurrent writers.
  opts=sorted([f for f in files if int(f.get("size") or 0)<=MAX_BYTES and int(f.get("size") or 0)>100 and f["name"].lower().endswith((".csv",".zip"))],key=lambda f:(0 if "2026-10" in f["name"] else 1,int(f.get("size") or 0)))
  for f in opts[:8]:
   if inspected>=4:break
   inspected+=1
   b=s.files().get_media(fileId=f["id"]).execute()
   quality,detail=valid(f,b)
   if not quality.endswith("_PASS"):
    summary["rejected"].append({"source":source,"name":f["name"],"reason":quality})
    continue
   digest=sha(b);key="V095_CANDIDATE_V093_"+source+"_202610_"+digest[:16]+"_"+f["name"][:90]
   matches=[x for x in ls(s,CANDIDATE_PARENT) if x["name"]==key]
   if len(matches)>1:raise RuntimeError("DUPLICATE_AMBIGUOUS_CANDIDATE")
   if matches:
    back=s.files().get_media(fileId=matches[0]["id"]).execute()
    if sha(back)!=digest:raise RuntimeError("CANDIDATE_HASH_MISMATCH")
    action="REUSED";dest=matches[0]["id"]
   elif summary["copies"]<MAX_COPIES:
    dest=s.files().create(body={"name":key,"parents":[CANDIDATE_PARENT],"description":"JARVIS v095 canary; source v093 Drive file "+f["id"]+"; SHA256 "+digest+"; not promoted to Bronze"},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream"),fields="id").execute()["id"]
    back=s.files().get_media(fileId=dest).execute()
    if sha(back)!=digest:raise RuntimeError("NEW_CANDIDATE_SHA_READBACK_MISMATCH")
    action="COPIED_TO_STAGING_SHA_VERIFIED";summary["copies"]+=1;summary["bytes_copied"]+=len(b)
   else:break
   summary["candidates"].append({"source":source,"v093_id":f["id"],"v095_staging_id":dest,"name":f["name"],"sha256":digest,"bytes":len(b),"format_quality":quality,"details":detail,"action":action,"bronze_promoted":False,"silver_gold_changed":False})
   break
 (OUT/"v093_to_v095_october_canary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps({"run":run,"candidate_count":len(summary["candidates"]),"real_copies":summary["copies"],"bytes_copied":summary["bytes_copied"],"rejected":len(summary["rejected"]),"bronze_published":0},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
