"""4 lane 2026-09 Silver candidate original parsing for TAIFEX and NDC.
3 derivative lanes + 1 NDC workbook. Never promote to approved Silver.
"""
import argparse,csv,hashlib,io,json,os,pathlib,re,datetime,collections,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from openpyxl import load_workbook
import pyarrow as pa,pyarrow.parquet as pq
TAIFEX="1fr-4WqvgHazBZV-YYreidxQ03TY5aO2o"
NDC="16hZu79uBk7OWyOnv7-4ga8QZnXl4ANWr"
TARGETS={"taifex-options":"1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8",
"taifex-futures":"1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8",
"taifex-history":"1TmZXrdW2sqOmgoMHgK7W2ifyTjz4UFH8",
"ndc-workbook":"1_KDD5xM9IeyBLSfDRppnrjAYQTEnGPRz"}
MONTH="2026-09_CANDIDATE_98_GATE"
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",
   client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
   scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def listfiles(s,parent):
 arr=[];token=None
 while True:
  res=s.files().list(q=f"'{parent}' in parents and trashed = false",pageToken=token,
   pageSize=1000,fields="nextPageToken,files(id,name,size,mimeType)",orderBy="name").execute()
  arr+=res.get("files",[]);token=res.get("nextPageToken")
  if not token:break
 return [x for x in arr if x["mimeType"]!="application/vnd.google-apps.folder"]
def folder(s,parent):
 files=s.files().list(q=f"'{parent}' in parents and name = '{MONTH}' and trashed = false",pageSize=50,fields="files(id,mimeType)").execute()["files"]
 if len(files)>1:raise ValueError("DUPLICATE_SILVER_MONTH_FOLDER")
 if files:return files[0]["id"]
 return s.files().create(body={"name":MONTH,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def save(s,parent,name,b):
 files=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",pageSize=50,fields="files(id)").execute()["files"]
 if len(files)>1:raise ValueError("MULTIPLE_CANDIDATES_SAME_NAME")
 if files:
  if sha(get(s,files[0]["id"]))!=sha(b):raise ValueError("DIFFERENT_OUTPUT_IMMUTABLE_NEW_GENERATION_REQUIRED")
  return files[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},
   media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),
   fields="id").execute()["id"]
 if sha(get(s,id))!=sha(b):raise ValueError("DRIVE_READBACK_SHA_MISMATCH")
 return id
def write(s,dest,family,records,raw_digest,source_ids):
 if not records:return {"status":"SOURCE_PRESENT_NO_ROWS","rows":0}
 buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(records),buf,compression="zstd")
 b=buf.getvalue()
 if pq.read_metadata(io.BytesIO(b)).num_rows!=len(records):raise ValueError("PARQUET_ROW_COUNT_MISMATCH")
 name=f"JARVIS_v095_SILVER_202609_{family}_NATIVE_CANDIDATE_R1.parquet"
 id=save(s,dest,name,b)
 return {"status":"PARQUET_CANDIDATE","rows":len(records),"parquet_id":id,
   "parquet_sha256":sha(b),"source_sha256":raw_digest,"original_drive_ids":source_ids}
def taifex(s,lane,dest):
 sources=listfiles(s,TAIFEX);families={};duplicates=[];seen_sha={}
 for f in sources:
  name=f["name"]
  if "_MARKET_options_" in name:group="taifex-options"
  elif "_MARKET_futures_" in name:group="taifex-futures"
  else:group="taifex-history"
  if group!=lane:continue
  b=get(s,f["id"]);h=sha(b)
  if h in seen_sha:
   duplicates.append({"alias":f["id"],"same_as":seen_sha[h],"sha":h});continue
  seen_sha[h]=f["id"]
  if not b:raise ValueError("EMPTY_TAIFEX_SOURCE")
  try:content=b.decode("utf-8-sig");encoding="utf-8-sig"
  except UnicodeDecodeError:content=b.decode("cp950");encoding="cp950"
  rows=list(csv.reader(io.StringIO(content)))
  # Preserve every non-empty native record, including multiple headers and variable-width sections.
  records=[{"source":"TAIFEX","dataset_label":name.split("_2026-09_")[0],
   "native_row_index":i,"native_record_json":json.dumps(row,ensure_ascii=False),
   "native_encoding":encoding,"native_field_contract":"UNAPPROVED_PRESERVED_RAW",
   "source_drive_id":f["id"],"source_sha256":h,
   "observation_month":"2026-09","published_at":None,"pit_verified":False}
   for i,row in enumerate(rows) if any(str(c).strip() for c in row)]
  key="TAIFEX_"+("OPTIONS" if group=="taifex-options" else "FUTURES" if group=="taifex-futures" else "HISTORY_"+h[:10])
  families[key]=write(s,dest,key,records,h,[f["id"]])
 return {"source":"TAIFEX","lane":lane,"source_files_examined":len(seen_sha)+len(duplicates),
   "distinct_source_contents":len(seen_sha),"duplicate_sha_aliases":duplicates,"datasets":families}
def ndc(s,dest):
 z=zipfile.ZipFile(io.BytesIO(get(s,NDC)))
 if z.testzip() is not None:raise ValueError("NDC_SOURCE_ZIP_CRC")
 name="NDC_11509_official_series.xlsx";b=z.read(name)
 wb=load_workbook(io.BytesIO(b),read_only=True,data_only=True)
 records=[];sheets={}
 for sh in wb:
  count=0
  for i,row in enumerate(sh.iter_rows(values_only=True),1):
   if not any(v is not None and str(v).strip() for v in row):continue
   cells=[v.isoformat() if isinstance(v,(datetime.date,datetime.datetime)) else str(v) if v is not None else None for v in row]
   records.append({"source":"NDC","dataset_label":"NDC_11509","sheet_name":sh.title,
    "row_index":i,"native_cells_json":json.dumps(cells,ensure_ascii=False),
    "source_zip_drive_id":NDC,"native_workbook_sha256":sha(b),
    "observation_month":"2026-09","published_at":None,"pit_verified":False})
   count+=1
  sheets[sh.title]=count
 return {"source":"NDC","lane":"ndc-workbook","sheets":sheets,"datasets":{
  "NDC_11509":write(s,dest,"NDC_11509",records,sha(b),[NDC])}}
def main():
 a=argparse.ArgumentParser();a.add_argument("--lane",choices=TARGETS,required=True);lane=a.parse_args().lane
 s=service();dest=folder(s,TARGETS[lane])
 report=ndc(s,dest) if lane=="ndc-workbook" else taifex(s,lane,dest)
 report.update(period="2026-09",silver_status="CANDIDATE_ONLY",
  release_approved=False,gold_allowed=False,
  warnings=["Native rows kept as JSON; formal field mappings not yet audited","PIT and source calendar pending",
            "Do not claim 98% data correctness from row serialization alone"])
 root=pathlib.Path("v095_202609_taifex_ndc_silver");root.mkdir(exist_ok=True)
 (root/(lane+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2))
 save(s,dest,"JARVIS_v095_202609_"+lane+"_SILVER_QA_R1.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
