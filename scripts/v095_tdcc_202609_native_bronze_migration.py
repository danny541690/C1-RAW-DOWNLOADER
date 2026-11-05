"""Bounded v0.93 -> v0.95 September TDCC native Bronze migration.
Immutable original bytes, source ID and SHA per member, Drive readback.
No FinMind, no other months, resumable by existing verified archive name.
"""
import argparse,hashlib,io,json,os,time,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SRC="1mOKduUYq2-LGonelM4fiIV-IY3HXVtm-"
DST="1_Pl4nN0HRXnIJSjJrt0iX2Lq7nkS1pcV"
def digest(b):return hashlib.sha256(b).hexdigest()
def api():
 names=("GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN")
 if any(not os.getenv(n) for n in names):raise RuntimeError("GOOGLE_DRIVE_OAUTH_SECRETS_UNAVAILABLE")
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",
               client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
               scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def listing(svc,parent):
 out=[];page=None
 while True:
  res=svc.files().list(q="'"+parent+"' in parents and trashed = false",
    pageSize=1000,pageToken=page,fields="nextPageToken,files(id,name,mimeType,size,md5Checksum)",orderBy="name").execute()
  out.extend(res.get("files",[]));page=res.get("nextPageToken")
  if not page:break
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--shard",type=int,required=True);p.add_argument("--shards",type=int,default=3)
 p.add_argument("--limit",type=int,default=60);p.add_argument("--max-batches",type=int,default=10);args=p.parse_args()
 assert 0<=args.shard<args.shards and args.limit==60 and 1<=args.max_batches<=12
 svc=api()
 for ident in (SRC,DST):
  f=svc.files().get(fileId=ident,fields="id,mimeType,name").execute()
  assert f["mimeType"]=="application/vnd.google-apps.folder"
 source=[x for x in listing(svc,SRC) if x.get("mimeType")!="application/vnd.google-apps.folder"]
 # Keep all raw items within the verified month folder, including receipts.
 shard=sorted((x for x in source if int(digest(x["id"].encode())[:8],16)%args.shards==args.shard),key=lambda x:x["id"])
 dest=listing(svc,DST)
 prefix="TDCC_202609_NATIVE_SHARD_"+str(args.shard)+"_"
 existing={x["name"]:x for x in dest if x["name"].startswith(prefix) and x["name"].endswith(".zip")}
 batches=[shard[i:i+args.limit] for i in range(0,len(shard),args.limit)]
 report={"source":"TDCC","period":"2026-09","shard":args.shard,"source_folder_total":len(source),
  "shard_items":len(shard),"expected_batches":len(batches),"existing_archives":len(existing),
  "downloaded_this_run":0,"saved_this_run":0,"errors":[],"status":"BLOCKED_NOT_COMPLETE"}
 completed_batches=0
 for idx,batch in enumerate(batches):
  if completed_batches>=args.max_batches:break
  name=prefix+f"{idx:05d}.zip"
  if name in existing:continue
  archive=io.BytesIO();manifest=[]
  with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
   for j,row in enumerate(batch):
    try:
     b=svc.files().get_media(fileId=row["id"]).execute()
     if len(b)!=int(row.get("size",len(b))):raise ValueError("NATIVE_FILE_SIZE_MISMATCH")
     key=f"original/{j:03d}_{row['id']}.raw"
     z.writestr(key,b)
     manifest.append({"source_drive_id":row["id"],"source_name":row["name"],"size":len(b),"sha256":digest(b),"archive_path":key})
     report["downloaded_this_run"]+=1
    except Exception as e:
     report["errors"].append({"source_file_id":row["id"],"error":type(e).__name__+":"+str(e)[:150]})
     break
   z.writestr("manifest.json",json.dumps({"period":"2026-09","source":"TDCC","immutable_originals":manifest,"source_folder":SRC},ensure_ascii=False))
  if len(manifest)!=len(batch):break
  data=archive.getvalue()
  result=svc.files().create(body={"name":name,"parents":[DST],"description":"v095 TDCC native originals with provenance and per-file SHA256"},
    media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/zip",resumable=True),
    fields="id,name,size").execute()
  read=svc.files().get_media(fileId=result["id"]).execute()
  if digest(read)!=digest(data):
   report["errors"].append({"archive":name,"error":"DRIVE_UPLOAD_SHA256_READBACK_MISMATCH"});break
  report["saved_this_run"]+=len(batch)
  completed_batches+=1
  report["last_verified_archive"]={"id":result["id"],"name":name,"sha256":digest(data),"members":len(batch)}
  # Continue only to the bounded batch budget; next run resumes by verified archive names.
 report["status"]="PARTIAL_MIGRATION" if report["saved_this_run"] else ("NO_ACTION_OR_BLOCKED")
 os.makedirs("tdcc_202609_migration",exist_ok=True)
 with open("tdcc_202609_migration/shard_"+str(args.shard)+".json","w") as out:json.dump(report,out,ensure_ascii=False,indent=2)
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report["errors"]:raise SystemExit(1)
if __name__=="__main__":main()
