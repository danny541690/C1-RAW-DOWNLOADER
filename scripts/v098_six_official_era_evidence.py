#!/usr/bin/env python3
"""JARVIS v0.98 official six-source read-only Bronze-era audit.
Run in FREE repo. Validate archive content sample against historical contract
and documented era. No claim of full dataset availability or official G2 PASS.
No private file IDs or raw file names printed in PUBLIC job logs.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,urllib.parse,urllib.request,urllib.error,zipfile,io,csv
OUT=pathlib.Path("v098_eight_source_audit");OUT.mkdir(exist_ok=True)
C1="1FzqFPBOKQH2mk324dZAtG7D5z_hGdwoa"
BRONZE="13DY2S3TuC4KYr8JKiptzUeXG9xZyIzam"
SOURCES=["TWSE","TPEx","MOPS","NDC","TDCC","TAIFEX"]
YEARS=list(range(2000,2027))
SAMPLE_YEARS={2000,2004,2008,2013,2018,2024,2026}
FOLDER="application/vnd.google-apps.folder"
def auth():
 body=urllib.parse.urlencode({"client_id":os.environ["GOOGLE_CLIENT_ID"],"client_secret":os.environ["GOOGLE_CLIENT_SECRET"],
 "refresh_token":os.environ["GOOGLE_REFRESH_TOKEN"],"grant_type":"refresh_token"}).encode()
 req=urllib.request.Request("https://oauth2.googleapis.com/token",data=body,headers={"Content-Type":"application/x-www-form-urlencoded"})
 with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)["access_token"]
def get_json(url,token):
 req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
def list_children(folder,token):
 rows=[];next_page=None;pages=0
 while True:
  params={"q":"'"+folder+"' in parents and trashed = false","pageSize":1000,
  "fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum,description,createdTime)"}
  if next_page:params["pageToken"]=next_page
  rows.extend(get_json("https://www.googleapis.com/drive/v3/files?"+urllib.parse.urlencode(params),token).get("files",[]))
  pages+=1
  if pages>100:raise RuntimeError("FOLDER_PAGE_CAP")
  page=get_json if False else None
  # only one request per page (nextPageToken obtained below by reusing a new request? handled below)
  break
 return rows
def list_children(folder,token):
 rows=[];next_page=None;pages=0
 while True:
  params={"q":"'"+folder+"' in parents and trashed = false","pageSize":1000,
  "fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum,createdTime)"}
  if next_page:params["pageToken"]=next_page
  resp=get_json("https://www.googleapis.com/drive/v3/files?"+urllib.parse.urlencode(params),token)
  rows.extend(resp.get("files",[]));next_page=resp.get("nextPageToken");pages+=1
  if not next_page:return rows
  if pages>=100:raise RuntimeError("FOLDER_PAGE_CAP")
def identify(items,name):
 x=[a for a in items if a.get("name")==name and a.get("mimeType")==FOLDER]
 if len(x)>1:raise RuntimeError("DUPLICATE_FOLDER")
 return x[0] if x else None
def classify(b,filename):
 raw_sha=hashlib.sha256(b).hexdigest()
 x={"raw_sha256":raw_sha,"byte_count":len(b),"format":"UNKNOWN","columns":[],"record_count_sample":0}
 if not b:return {**x,"state":"EMPTY_FILE"}
 name=filename.lower()
 if b.startswith(b"PK\x03\x04"):
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   members=[y for y in z.infolist() if not y.is_dir()]
   x.update(format="ZIP",zip_member_count=len(members),state="ZIP_STRUCTURE_OBSERVED",
      zip_member_name_extensions=sorted({pathlib.Path(y.filename).suffix.lower() for y in members}),
      zip_uncompressed_bytes=sum(y.file_size for y in members))
   if any(y.file_size>5000000 for y in members) or sum(y.file_size for y in members)>12000000:
    x["state"]="ZIP_RESOURCE_HOLD"
   return x
 if name.endswith((".xls",".xlsx")):
  x.update(format="EXCEL",state="BINARY_FORMAT_UNPARSED")
  return x
 for codec in ["utf-8-sig","big5","cp950"]:
  try:txt=b.decode(codec);x["encoding"]=codec;break
  except UnicodeDecodeError:continue
 else:return {**x,"state":"NON_TEXT_BINARY"}
 ss=txt.lstrip()
 if ss.startswith(("{","[")):
  try:
   obj=json.loads(ss);x["format"]="JSON"
   if isinstance(obj,list):data=obj
   elif isinstance(obj,dict):
    data=obj.get("data",obj.get("tables",obj.get("records",[])))
   else:data=[]
   if isinstance(data,list):
    x["record_count_sample"]=len(data)
    x["columns"]=sorted({str(k) for a in data[:30] if isinstance(a,dict) for k in a})
   x["state"]="JSON_SYNTAX_VALID"
   return x
  except ValueError:x["state"]="JSON_SYNTAX_FAIL";return x
 if name.endswith((".csv",".txt")) or "\n" in txt:
  sep="\t" if txt.splitlines()[0].count("\t")>txt.splitlines()[0].count(",") else ","
  x["format"]="TSV" if sep=="\t" else "CSV"
  try:
   rows=list(csv.reader(io.StringIO(txt[:1000000]),delimiter=sep))
   x["columns"]=rows[0][:80] if rows else []
   x["record_count_sample"]=max(0,len(rows)-1)
   x["state"]="DELIMITED_STRUCTURE_OBSERVED"
  except csv.Error:x["state"]="CSV_PARSE_ERROR"
  return x
 return {**x,"format":"HTML_OR_TEXT","state":"TEXT_OBSERVED"}
def main():
 report={"schema":"JARVIS_V098_SIX_OFFICIAL_BRONZE_ERA_PILOT_V1","date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
  "scope":"YEAR/SOURCE DIRECTORY AUDIT AND LIMITED CONTENT SAMPLE",
  "official_online_documents_compared_in_separate_registry":True,
  "official_native_rows_complete":False,"bronze_modified":False,"sources":SOURCES,"years":YEARS,"entries":[],"errors":[]}
 try:
  token=auth()
  rawroot=get_json("https://www.googleapis.com/drive/v3/files/"+BRONZE+"?fields=id,name,parents",token)
  if rawroot.get("name")!="20_BRONZE" or C1 not in rawroot.get("parents",[]):raise RuntimeError("DRIVE_FOLDER_IDENTITY")
  yrs=list_children(BRONZE,token)
  for year in YEARS:
   yr=identify(yrs,str(year))
   if not yr:
    for src in SOURCES:report["entries"].append({"source":src,"year":year,"state":"YEAR_FOLDER_MISSING_COVERAGE_UNKNOWN"})
    continue
   srcs=list_children(yr["id"],token)
   for source in SOURCES:
    sf=identify(srcs,source)
    rec={"source":source,"year":year,"state":"INIT","source_folder_exists":sf is not None,
      "child_count":0,"dir_count":0,"file_count_at_source_root":0,
      "has_any_file_sample":False,"sample":None,"dataset_earliest_verified":False}
    if not sf:rec["state"]="SOURCE_FOLDER_MISSING_COVERAGE_UNKNOWN";report["entries"].append(rec);continue
    try:
     children=list_children(sf["id"],token)
     rec["child_count"]=len(children)
     rec["dir_count"]=sum(x["mimeType"]==FOLDER for x in children)
     rec["file_count_at_source_root"]=len(children)-rec["dir_count"]
     rec["state"]="SOURCE_YEAR_STRUCTURE_OBSERVED"
     if year in SAMPLE_YEARS:
      files=[c for c in children if c["mimeType"]!=FOLDER]
      if not files:
       for ch in [v for v in children if v["mimeType"]==FOLDER][:3]:
        files=[z for z in list_children(ch["id"],token) if z["mimeType"]!=FOLDER]
        if files:break
      if files:
       f=sorted(files,key=lambda x:x.get("size",99999999))[0]
       rec["sample_file_size"]=int(f.get("size") or 0)
       if rec["sample_file_size"]<=1000000:
        url="https://www.googleapis.com/drive/v3/files/"+f["id"]+"?alt=media"
        req=urllib.request.Request(url,headers={"Authorization":"Bearer "+token})
        with urllib.request.urlopen(req,timeout=40) as resp:payload=resp.read(1000001)
        if len(payload)<=1000000:
         rec["sample"]=classify(payload,f["name"]);rec["has_any_file_sample"]=True
         rec["state"]="RAW_CONTENT_SAMPLE_OBSERVED"
        else:rec["state"]="RAW_SAMPLE_TOO_LARGE"
       else:rec["state"]="RAW_SAMPLE_TOO_LARGE"
      else:rec["state"]="NO_DIRECT_FILE_IN_THREE_SUBFOLDER_SAMPLES"
    except Exception as exc:
     rec["state"]="SCAN_ERROR";rec["error_type"]=type(exc).__name__
    report["entries"].append(rec)
    # No private ids in public report.
    print(json.dumps({"source":source,"year":year,"status":rec["state"],"child_count":rec["child_count"],
     "sample_format":(rec.get("sample") or {}).get("format")},ensure_ascii=False),flush=True)
 except Exception as exc:
  report["errors"].append({"type":type(exc).__name__})
 states=collections.Counter(x["state"] for x in report["entries"])
 report["summary"]={"year_source_rows":len(report["entries"]),"status_counts":dict(states),
  "sources_with_content_samples":sorted({x["source"] for x in report["entries"] if x.get("has_any_file_sample")}),
  "sampling_not_full_dataset_validation":True,"errors":report["errors"]}
 (OUT/"six_official_bronze_era_pilot.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print("OFFICIAL_SIX_FINAL "+json.dumps(report["summary"],ensure_ascii=False),flush=True)
 if report["errors"]:raise SystemExit(1)
if __name__=="__main__":main()
