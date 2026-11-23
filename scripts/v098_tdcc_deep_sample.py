#!/usr/bin/env python3
"""TDCC deep tree sample for 7 vintages; read-only in FREE repo.
Useful when earlier 3-subfolder pilot finds no file or >1MB.
Depth bounded, Google API metadata includes size/md5, range reads only for >2MB.
Never print file IDs/paths or raw table contents to public log.
"""
import collections,hashlib,json,os,pathlib,urllib.parse,urllib.request,urllib.error,datetime as dt,io,csv
BASE="https://www.googleapis.com/drive/v3/files"
BRONZE="13DY2S3TuC4KYr8JKiptzUeXG9xZyIzam"
YEARS=[2000,2004,2008,2013,2018,2024,2026]
FOLDER="application/vnd.google-apps.folder"
OUT=pathlib.Path("tdcc_depth_probe");OUT.mkdir(exist_ok=True)
def token():
 body=urllib.parse.urlencode({"client_id":os.environ["GOOGLE_CLIENT_ID"],"client_secret":os.environ["GOOGLE_CLIENT_SECRET"],
  "refresh_token":os.environ["GOOGLE_REFRESH_TOKEN"],"grant_type":"refresh_token"}).encode()
 with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token",data=body,headers={"Content-Type":"application/x-www-form-urlencoded"}),timeout=25) as r:return json.load(r)["access_token"]
def query(q,t):
 rows=[];next_token=None
 for i in range(20):
  p={"q":q,"fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum,parents)","pageSize":1000}
  if next_token:p["pageToken"]=next_token
  with urllib.request.urlopen(urllib.request.Request(BASE+"?"+urllib.parse.urlencode(p),headers={"Authorization":"Bearer "+t}),timeout=35) as r:d=json.load(r)
  rows.extend(d.get("files",[]));next_token=d.get("nextPageToken")
  if not next_token:return rows
 raise RuntimeError("TOO_MANY_PAGES")
def children(parent,t):
 # One page only: source may contain tens of thousands of files.
 # Never imply the sample page is the full inventory.
 params={"q":"'"+parent+"' in parents and trashed = false",
         "pageSize":1000,"fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum,parents)"}
 with urllib.request.urlopen(urllib.request.Request(BASE+"?"+urllib.parse.urlencode(params),
      headers={"Authorization":"Bearer "+t}),timeout=35) as r:data=json.load(r)
 return data.get("files",[])
def unique(parent,name,t):
 rows=[x for x in children(parent,t) if x.get("name")==name and x.get("mimeType")==FOLDER]
 if len(rows)>1:raise RuntimeError("DUPLICATE_FOLDER")
 return rows[0]["id"] if rows else None
def evidence(f,t):
 size=int(f.get("size") or 0)
 if size==0:return {"status":"EMPTY","bytes":0}
 hdr={"Authorization":"Bearer "+t}
 if size>1500000:hdr["Range"]="bytes=0-131071"
 req=urllib.request.Request(BASE+"/"+f["id"]+"?alt=media",headers=hdr)
 with urllib.request.urlopen(req,timeout=45) as r:b=r.read(1500001)
 if size<=1500000 and len(b)<size:return {"status":"PARTIAL_UNEXPECTED"}
 x={"file_bytes":size,"read_bytes":len(b),"complete":len(b)==size,"provider_md5_available":bool(f.get("md5Checksum"))}
 if x["complete"]:x["sample_sha256"]=hashlib.sha256(b).hexdigest()
 if b[:4]==b"PK\x03\x04":
  x["format"]="ZIP";x["state"]="ZIP_MAGIC_OBSERVED"
 elif b.startswith((b"{",b"[")):
  x["format"]="JSON";x["state"]="JSON_PREFIX_OBSERVED"
 else:
  for encoding in ["utf-8-sig","cp950","big5"]:
   try:
    s=b.decode(encoding,errors="strict");x["encoding"]=encoding;break
   except UnicodeDecodeError:continue
  else:
   s=b.decode("utf-8",errors="replace");x["encoding"]="unknown"
  if "<table" in s[:1000].lower() or s.lstrip().startswith("<"):
   x["format"]="HTML";x["state"]="HTML_PREFIX_OBSERVED"
  else:
   x["format"]="DELIMITED_OR_TEXT"
   delim="\t" if s.splitlines()[0].count("\t")>s.splitlines()[0].count(",") else ","
   try:x["header_sample"]=next(csv.reader(io.StringIO(s.splitlines()[0]),delimiter=delim))[:80]
   except Exception:x["header_sample"]=[]
   x["state"]="PARTIAL_HEADER_OBSERVED" if not x["complete"] else "TEXT_FILE_HEADER_OBSERVED"
 return x
def main():
 t=token()
 report=[]
 for year in YEARS:
  rr={"source":"TDCC","year":year,"status":"INIT","visited_folders":0,"sampled":0,
   "file_candidates":0,"format_samples":[]}
  try:
   yr=unique(BRONZE,str(year),t)
   src=unique(yr,"TDCC",t) if yr else None
   if not src:rr["status"]="YEAR_OR_SOURCE_FOLDER_NOT_FOUND"
   else:
    stack=[(src,0)];visited=set()
    while stack and rr["visited_folders"]<60 and rr["sampled"]<3:
     folder,depth=stack.pop(0)
     if folder in visited:continue
     visited.add(folder);rr["visited_folders"]+=1
     kids=children(folder,t)
     files=[k for k in kids if k.get("mimeType")!=FOLDER]
     rr["file_candidates"]+=len(files)
     for f in sorted(files,key=lambda x:int(x.get("size") or 0))[:3]:
      try:
       obs=evidence(f,t);rr["format_samples"].append(obs);rr["sampled"]+=1
      except Exception as exc:rr["format_samples"].append({"state":"READ_ERROR","error_type":type(exc).__name__})
      if rr["sampled"]>=3:break
     if depth<4:stack.extend((k["id"],depth+1) for k in kids if k.get("mimeType")==FOLDER)
    rr["status"]="SAMPLED" if rr["sampled"] else "NO_FILE_WITHIN_BOUNDED_TREE"
  except Exception as exc:
   rr["status"]="ERROR";rr["error_type"]=type(exc).__name__
  report.append(rr);print("TDCC_DEPTH "+json.dumps({k:v for k,v in rr.items() if k!="format_samples"},ensure_ascii=False),flush=True)
 payload={"schema":"JARVIS_TDCC_DEPTH_SAMPLES_R3B","run_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
  "maximum_depth":4,"max_folders_per_year":60,"max_files_per_year":3,"full_archive_scan":False,
  "reports":report}
 (OUT/"tdcc_deep_schema.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
 print("TDCC_DEPTH_FINAL "+json.dumps({"years":len(report),"sampled":sum(r["sampled"] for r in report),
  "with_samples":sum(r["sampled"]>0 for r in report)},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
