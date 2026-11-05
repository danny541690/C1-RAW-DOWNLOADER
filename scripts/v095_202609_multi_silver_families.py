"""JARVIS v0.95 2026-09 additional TWSE/TPEx Bronze->isolated Silver partitions.
Four lanes with disjoint source dataset families, preserving positional duplicate columns.
Not a release, not numeric semantic or PIT certification.
"""
import argparse,collections,datetime as dt,hashlib,io,json,os,pathlib,re,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
MAIN={"TWSE":"16G68HaFVX1Ddmu23xWeexhNDn0DWryet","TPEx":"1xz7SdR0itvatFQ_IaAdpsAw9fN6i-0iu"}
LANES={
"twse-chip":("TWSE",["institutional","foreign_holdings","valuation"]),
"twse-financing":("TWSE",["margin","lending","capital_reduction","ex_dividend"]),
"tpex-chip":("TPEx",["institutional","foreign_holdings","valuation","indices"]),
"tpex-financing":("TPEx",["margin","lending","marketcap","capital_reduction","ex_dividend","par_value_change"])
}
FOLDER={"TWSE":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5","TPEx":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5"}
RECOVERY_INST="1Tmh0sEZZCWFvdeTQ7eAOMuLX8WEY7ehR"
MONTH="2026-09_CANDIDATE_98_GATE"
DAYS={(dt.date(2026,9,1)+dt.timedelta(days=i)).isoformat() for i in range(30)
      if (dt.date(2026,9,1)+dt.timedelta(days=i)).weekday()<5 and i+1 not in (25,28)}
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
  client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def download(s,id):return s.files().get_media(fileId=id).execute()
def saved(s,parent,name,data):
 r=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",
  fields="files(id,name)",pageSize=50).execute()["files"]
 if len(r)>1:raise ValueError("DUPLICATE_OUTPUT_NAME")
 if r:
  if sha(download(s,r[0]["id"]))!=sha(data):raise ValueError("OUTPUT_CONFLICT_NEED_NEW_GENERATION")
  return r[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},
   media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(download(s,id))!=sha(data):raise ValueError("OUTPUT_SHA_READBACK_MISMATCH")
 return id
def native_rows(o,unit,source,raw_sha,raw_id):
 tables=[]
 if isinstance(o.get("fields"),list) and isinstance(o.get("data"),list):
  tables.append(("top",o.get("title",""),o["fields"],o["data"]))
 for i,t in enumerate(o.get("tables") or []):
  if isinstance(t,dict) and isinstance(t.get("fields"),list) and isinstance(t.get("data"),list):
   tables.append((str(i),t.get("title",""),t["fields"],t["data"]))
 result=[];width_errors=0
 for table_id,title,fields,items in tables:
  if not fields:continue
  for row_idx,row in enumerate(items):
   if not isinstance(row,(list,dict)):continue
   if isinstance(row,list) and len(row)!=len(fields):
    width_errors+=1;continue
   positional={str(i)+":"+str(k):v for i,(k,v) in enumerate(zip(fields,row))} if isinstance(row,list) else row
   code=""
   for k,v in positional.items():
    label=k.split(":",1)[-1]
    if label in ("證券代號","股票代號","代號","公司代號","公司代碼") and re.fullmatch(r"\d{4}",str(v).strip()):
     code=str(v).strip();break
   when=unit.get("date")
   if when and when not in DAYS:raise ValueError("OUTSIDE_EXPECTED_TRADE_CALENDAR")
   result.append({
    "source":source,"family":unit["name"].split("_2026")[0],"market":"TSE" if source=="TWSE" else "OTC",
    "trade_date":when,"period":"2026-09","security_id":code or None,
    "table_id":table_id,"table_title":str(title or ""), "row_index":row_idx,
    "native_fields_json":json.dumps(fields,ensure_ascii=False),
    "native_row_json":json.dumps(positional,ensure_ascii=False,sort_keys=True),
    "source_zip_id":raw_id,"source_member":unit["file"].split("/")[-1],
    "source_sha256":raw_sha,
    "native_unit":"SOURCE_UNMAPPED","published_at":None,"pit_verified":False,
    "status":"SILVER_CANDIDATE_NEEDS_FIELD_CONTRACT"
   })
 return result,width_errors
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--lane",choices=LANES,required=True)
 lane=parser.parse_args().lane;source,families=LANES[lane]
 s=service();zip_bytes=download(s,MAIN[source])
 z=zipfile.ZipFile(io.BytesIO(zip_bytes))
 if z.testzip() is not None:raise ValueError("MAIN_ZIP_CRC_ERROR")
 manifest=json.loads(z.read("manifest.json"))["units"]
 recovery={}
 if lane=="tpex-chip":
  rz=zipfile.ZipFile(io.BytesIO(download(s,RECOVERY_INST)))
  if rz.testzip() is not None:raise ValueError("RECOVERY_ZIP_CRC")
  for name in rz.namelist():
   match=re.search(r"institutional_(2026-09-\d\d)\.raw$",name)
   if match:recovery[match.group(1)]=(rz.read(name),RECOVERY_INST,name)
 parent=FOLDER[source]
 found=s.files().list(q=f"'{parent}' in parents and name = '{MONTH}' and trashed = false",pageSize=50,fields="files(id)").execute()["files"]
 if len(found)!=1:raise ValueError("SHARED_SILVER_MONTH_FOLDER_NOT_FOUND")
 dest=found[0]["id"]
 report={"lane":lane,"month":"2026-09","source":source,"families":{},"file_outputs":{},
    "status":"CANDIDATE_ONLY","release_approved":False,"gold_allowed":False}
 for family in families:
  matched=[u for u in manifest if u["name"].startswith(family+"_202609") or u["name"].startswith(family+"_2026-09")]
  if not matched:raise ValueError("FAMILY_NOT_IN_BRONZE_MANIFEST:"+family)
  rows=[];gaps=[];dates=set();shape_errors=0;source_units=0
  for u in matched:
   raw_bytes=None;origin=MAIN[source]
   if u.get("file"):
    mem=u["file"].split("/")[-1];raw_bytes=z.read(mem)
    if sha(raw_bytes)!=u["sha256"]:raise ValueError("BAD_ORIGINAL_SHA:"+u["name"])
   elif family=="institutional" and source=="TPEx" and u.get("date") in recovery:
    raw_bytes,origin,mem=recovery[u["date"]]
   else:
    gaps.append({"unit":u["name"],"reason":u.get("state","UNVERIFIED")});continue
   try:o=json.loads(raw_bytes.decode("utf-8-sig"))
   except (ValueError,UnicodeError):raise ValueError("SOURCE_JSON_UNREADABLE:"+u["name"])
   if not isinstance(o,dict):raise ValueError("UNEXPECTED_SOURCE_JSON")
   temp,errors=native_rows(o,{**u,"file":mem},source,sha(raw_bytes),origin)
   rows.extend(temp);shape_errors+=errors;source_units+=1
   if u.get("date"):dates.add(u["date"])
  if not rows:
   report["families"][family]={"status":"NO_PARSED_RECORDS","source_units":source_units,"gaps":gaps}
   continue
  frame=pa.Table.from_pylist(rows)
  buffer=io.BytesIO();pq.write_table(frame,buffer,compression="zstd")
  blob=buffer.getvalue()
  if pq.read_metadata(io.BytesIO(blob)).num_rows!=len(rows):raise ValueError("PARQUET_ROW_READBACK_MISMATCH")
  name=f"JARVIS_v095_SILVER_202609_{source}_{family}_NATIVE_CANDIDATE_R1.parquet"
  outputid=saved(s,dest,name,blob)
  report["families"][family]={"row_count":len(rows),"official_units":source_units,"days":len(dates),
     "missing_source_units":gaps,"row_width_rejections":shape_errors,
     "output_id":outputid,"sha256":sha(blob),"format":"NATIVE_ROW_JSON_PLUS_PROVENANCE"}
  report["file_outputs"][family]=outputid
 print(json.dumps(report,ensure_ascii=False),flush=True)
 path=pathlib.Path("v095_202609_multi_silver")
 path.mkdir(exist_ok=True)
 (path/(lane+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2))
 saved(s,dest,f"JARVIS_v095_SILVER_202609_{lane}_QA_R1.json",json.dumps(report,ensure_ascii=False,indent=2).encode())
if __name__=="__main__":main()
