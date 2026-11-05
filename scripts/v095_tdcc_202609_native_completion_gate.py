"""Final exact-ID and native SHA gate for bounded v0.93 -> v0.95 TDCC Sep 2026.
Does not certify other datasets, does not touch v0.93 originals.
"""
import hashlib,io,json,os,re,sys,zipfile,requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SRC="1mOKduUYq2-LGonelM4fiIV-IY3HXVtm-"
DST="1_Pl4nN0HRXnIJSjJrt0iX2Lq7nkS1pcV"
MARKER="TDCC_202609_NATIVE_BRONZE_ORIGINAL_COPY_COMPLETE.json"
def sha(b):return hashlib.sha256(b).hexdigest()
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def listfiles(svc,parent):
 arr=[];token=None
 while True:
  d=svc.files().list(q="'"+parent+"' in parents and trashed=false",pageSize=1000,pageToken=token,
    fields="nextPageToken,files(id,name,mimeType,size)",orderBy="name").execute()
  arr+=d.get("files",[]);token=d.get("nextPageToken")
  if not token:return arr
def main():
 svc=api()
 src=[x for x in listfiles(svc,SRC) if x.get("mimeType")!="application/vnd.google-apps.folder"]
 dest=listfiles(svc,DST)
 expected={}
 for shard in range(3):
  group=sorted([x for x in src if int(sha(x["id"].encode())[:8],16)%3==shard],key=lambda x:x["id"])
  for start in range(0,len(group),60):
   name=f"TDCC_202609_NATIVE_SHARD_{shard}_{start//60:05d}.zip"
   expected[name]=group[start:start+60]
 actual={x["name"]:x for x in dest if re.fullmatch(r"TDCC_202609_NATIVE_SHARD_[012]_[0-9]{5}\.zip",x["name"])}
 summary={"schema":"JARVIS_V095_202609_TDCC_NATIVE_COPY_GATE","source_native_file_count":len(src),
  "expected_zip_bundles":len(expected),"observed_zip_bundles":len(actual),
  "missing_zip_names":sorted(set(expected)-set(actual))[:12],
  "bronze_six_source_complete":False}
 if len(actual)!=len(expected) or set(actual)!=set(expected):
  summary["status"]="MIGRATION_IN_PROGRESS";print(json.dumps(summary));return
 validated=set()
 for name,expected_batch in sorted(expected.items()):
  content=svc.files().get_media(fileId=actual[name]["id"]).execute()
  z=zipfile.ZipFile(io.BytesIO(content))
  if z.testzip() is not None:raise ValueError("FINAL_NATIVE_ZIP_CRC_FAIL:"+name)
  manifest=json.loads(z.read("manifest.json"))["immutable_originals"]
  if [x["source_drive_id"] for x in manifest]!=[x["id"] for x in expected_batch]:raise ValueError("FINAL_NATIVE_SOURCE_ID_SEQUENCE_CHANGED:"+name)
  for row in manifest:
   payload=z.read(row["archive_path"])
   if sha(payload)!=row["sha256"] or len(payload)!=row["size"]:raise ValueError("FINAL_NATIVE_BYTE_MISMATCH:"+name)
   if row["source_drive_id"] in validated:raise ValueError("FINAL_NATIVE_DUPLICATE_ID")
   validated.add(row["source_drive_id"])
 if validated!={x["id"] for x in src}:raise ValueError("FINAL_NATIVE_UNIVERSE_NOT_EQUAL")
 summary.update(status="TDCC_NATIVE_COPY_COMPLETE_PASS",validated_native_ids=len(validated),all_files_source_id_and_sha_pass=True)
 b=(json.dumps(summary,ensure_ascii=False,indent=2)+"\n").encode()
 prior=[x for x in dest if x["name"]==MARKER]
 if prior:
  if svc.files().get_media(fileId=prior[0]["id"]).execute()!=b:raise ValueError("FINAL_MARKER_CONTENT_CONFLICT")
 else:
  obj=svc.files().create(body={"name":MARKER,"parents":[DST]},
    media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json"),fields="id").execute()
  if svc.files().get_media(fileId=obj["id"]).execute()!=b:raise ValueError("FINAL_MARKER_READBACK_MISMATCH")
 print(json.dumps(summary,ensure_ascii=False),flush=True)
 token=os.getenv("GITHUB_TOKEN")
 if token:
  url="https://api.github.com/repos/danny541690/C1-RAW-DOWNLOADER/actions/workflows/v095-tdcc-202609-native-bronze-migration.yml/disable"
  res=requests.put(url,headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"},timeout=25)
  print("SELF_DISABLE_AFTER_COMPLETE",res.status_code)
  if res.status_code!=204:raise ValueError("SELF_DISABLE_FAILED")
if __name__=="__main__":main()
