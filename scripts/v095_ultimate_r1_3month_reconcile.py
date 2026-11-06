"""Three-month 14-lane evidence reconciliation, 2026-09..11.

Read-only for market data. Each lane produces independent immutable receipt.
A missing month/category does not become a fabricated zero or a certified PASS.
Only the Sept manifest is a known enumerated Bronze file set.
"""
import csv,datetime as dt,hashlib,io,json,os,pathlib,re,time,collections
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
MONTHS=("2026-09","2026-10","2026-11")
SOURCES={
 "BRONZE_TWSE":("TWSE","1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE"),
 "BRONZE_TPEX":("TPEx","15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG"),
 "BRONZE_MOPS":("MOPS","1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI"),
 "BRONZE_TDCC":("TDCC","1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-"),
 "BRONZE_TAIFEX":("TAIFEX","1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz"),
 "BRONZE_NDC":("NDC","1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-")
}
GROUPS={
 "SILVER_PRICE":("SILVER","1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5",("PRICE","OHLCV")),
 "SILVER_FUNDAMENTAL":("SILVER","1ick4kRSlmz1ukibDq3TOD7QQxiBHtzWb",("REVENUE","INSTITUTIONAL","FINANCIAL","FLOW")),
 "SILVER_TDCC":("SILVER","1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U",("TDCC","OWNERSHIP")),
 "SILVER_MACRO":("SILVER","1_KDD5xM9IeyBLSfDRppnrjAYQTEnGPRz",("MACRO","TAIFEX","NDC","DERIVATIVE")),
 "GOLD_TECHNICAL":("GOLD","1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3",("PRICE","TECHNICAL","OHLCV")),
 "GOLD_CHIP":("GOLD","1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3",("CHIP","MARGIN","CREDIT","FLOW","OWNERSHIP")),
 "GOLD_FINANCIAL":("GOLD","1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3",("REVENUE","FINANCIAL","VALUATION")),
 "GOLD_CROSS_ASSET":("GOLD","1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3",("CROSS","TAIFEX","NDC","MACRO","DERIVATIVE"))
}
SEP_FILE="governance/v095/202609_BRONZE_MIGRATION_RESUME_20261105.json"
CONTRACT_FILE="governance/v095/DATASET_CONTRACTS.csv"
SEPT_OBJECTS={
 "SILVER_PRICE":[("TSE_PRICE","14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"),("OTC_PRICE","1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk")],
 "SILVER_FUNDAMENTAL":[("MOPS_REVENUE","1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"),("TSE_FLOW","1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx")],
 "SILVER_TDCC":[("TDCC_WEEKLY","1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r")],
 "GOLD_TECHNICAL":[("TSE_PRICE","1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI"),("OTC_PRICE","1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6")],
 "GOLD_CHIP":[("TSE_INST","18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7"),("OTC_MARGIN","11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5")],
 "GOLD_FINANCIAL":[("MOPS_REVENUE","1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI")]
}
REPORT_PARENT="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
OUT=pathlib.Path("ultimate_r1_3month");OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def compact(x):return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
def drive():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def call(fn):
 last=None
 for i in range(3):
  try:return fn().execute()
  except Exception as e:
   last=e
   if i<2:time.sleep(2+i*2)
 raise last
def ls(s,parent):
 out=[];page=None
 while True:
  data=call(lambda:s.files().list(q="'"+parent+"' in parents and trashed=false",
   fields="nextPageToken,files(id,name,size,mimeType,md5Checksum)",pageSize=1000,pageToken=page))
  out+=data.get("files",[]);page=data.get("nextPageToken")
  if not page:return out
def as_month(name):
 # Do not interpret mere revision/created-on dates as dataset date.
 m=re.search(r"2026[-_]?((?:09)|(?:10)|(?:11))(?!\d)",name)
 if m:return "2026-"+m.group(1)
 return None
def check_parquet(s,name,fid,month):
 raw=call(lambda:s.files().get_media(fileId=fid))
 table=pq.read_table(io.BytesIO(raw))
 keys=[k for k in ("stock_id","trade_date","snapshot_date","revenue_month") if k in table.column_names]
 dates=[]
 for key in ("trade_date","snapshot_date","revenue_month"):
  if key in table.column_names:
   arr=table[key].to_pylist()
   unique=sorted({str(v)[:7] for v in arr if v is not None})
   dates=unique[:5];break
 # September revenue reported month may become available October; not automatically a PIT fail.
 wrong=[d for d in dates if d!=month]
 result={"name":name,"drive_id":fid,"sha256":sha(raw),"byte_count":len(raw),
  "rows":table.num_rows,"keys":keys,"sample_months":dates,
  "unexpected_month_sample":wrong,"parquet_read_pass":True,
  "semantic_validated":False,"pit_certified":False}
 if "input_silver_sha256" in table.column_names:
  result["declared_input_silver_sha256"]=sorted({str(x) for x in table["input_silver_sha256"].to_pylist() if x})[:6]
 return result
def bronze(s,lane,record):
 source,folder=SOURCES[lane]
 children=ls(s,folder)
 named={z["name"]:z for z in children if z["mimeType"]=="application/vnd.google-apps.folder"}
 legacy=json.loads(pathlib.Path(SEP_FILE).read_text())
 sep=next(z for z in legacy["source_month_folders"] if z["source"]==source)
 contracts=list(csv.DictReader(pathlib.Path(CONTRACT_FILE).open(encoding="utf-8",newline="")))
 record["declared_dataset_contract_count"]=sum(x["source_class_id"].upper()==source.upper() for x in contracts)
 record["september_archive_legacy_manifest_count"]=len(sep["files"])
 for m in MONTHS:
  info={"status":"BLOCKED_UNTIL_SOURCE_UNIVERSE_VERIFIED"}
  f=named.get(m)
  if f:
   z=ls(s,f["id"]);items=[x for x in z if x["mimeType"]!="application/vnd.google-apps.folder"]
   info.update(folder_id=f["id"],observed_files=len(items),
     filenames_sample=[x["name"] for x in items[:8]],actual_folder_observed=True)
   if not items:info["reason"]="EMPTY_MONTH_FOLDER"
  else:
   info.update(actual_folder_observed=False,observed_files=0,reason="MISSING_MONTH_FOLDER")
  if m=="2026-09":
   # Historical migration files can live in a different exact target folder.
   mobj=ls(s,sep["drive_folder_id"])
   index={x["id"] for x in mobj}
   info["legacy_09_present_ids"]=sum(x["id"] in index for x in sep["files"])
   info["legacy_09_expected_ids"]=len(sep["files"])
  record["months"][m]=info
def downstream(s,lane,record):
 stage,parent,words=GROUPS[lane]
 root=ls(s,parent)
 # Only one level below root: no broad recursive crawl under arbitrary subdirectories.
 folder_months=[]
 for x in root:
  if x["mimeType"]=="application/vnd.google-apps.folder":
   mk=as_month(x["name"])
   if mk in MONTHS:folder_months.append((mk,x))
 inventories={m:[] for m in MONTHS}
 for month,folder in folder_months:
  for o in ls(s,folder["id"]):
   if o.get("mimeType")=="application/vnd.google-apps.folder":continue
   inventories[month].append(o)
 for month in MONTHS:
  all_files=inventories[month]
  matches=[x for x in all_files if any(w in x["name"].upper() for w in words)]
  record["months"][month]={"status":"CANDIDATE_SUBSET_ONLY_NOT_FULL_QA",
   "month_parent_count":sum(m==month for m,_ in folder_months),
   "observed_objects_at_month_depth":len(all_files),
   "matching_name_candidates":len(matches),
   "matching_names_sample":[x["name"] for x in matches[:10]],
   "source_field_contract_certified":False,"pit_certified":False}
 if lane in SEPT_OBJECTS:
  checked=[]
  for name,fid in SEPT_OBJECTS[lane]:
   try:checked.append(check_parquet(s,name,fid,"2026-09"))
   except Exception as exc:checked.append({"name":name,"file_id":fid,"error":type(exc).__name__+":"+str(exc)[:160]})
  record["months"]["2026-09"]["verified_known_candidate_parquets"]=checked
  record["months"]["2026-09"]["bytes_and_parquet_pass_count"]=sum(x.get("parquet_read_pass",False) for x in checked)
 # Month 10/11 observations must be cross checked with actual entries; do not fake a total count.
 for m in ("2026-10","2026-11"):
  samples=[x for x in inventories[m] if x["name"].lower().endswith(".parquet") and any(w in x["name"].upper() for w in words)]
  checked=[]
  for f in samples[:2]:
   try:checked.append(check_parquet(s,f["name"],f["id"],m))
   except Exception as exc:checked.append({"name":f["name"],"error":type(exc).__name__+":"+str(exc)[:160]})
  record["months"][m]["sample_parquet_evidence"]=checked
  record["months"][m]["parquet_byte_read_count"]=len(checked)
def main():
 lane=os.environ.get("JARVIS_LANE","")
 if lane not in set(SOURCES)|set(GROUPS):raise ValueError("UNKNOWN_LANE")
 run=os.environ.get("GITHUB_RUN_ID","local")
 record={"schema":"JARVIS_V095_202609_11_14LANE_RECONCILE_V1","run_id":run,
  "lane":lane,"scope":MONTHS,"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
  "months":{},"stage":("BRONZE" if lane in SOURCES else GROUPS[lane][0]),
  "release_status":"BLOCKED_PENDING_FULL_SOURCE_DATASET_PIT_GOLD_FORMULAS",
  "no_destructive_writes":True,"shared_checkpoint_updated":False}
 s=drive()
 try:
  if lane in SOURCES:bronze(s,lane,record)
  else:downstream(s,lane,record)
  record["inspection"]="COMPLETE_WITH_GAPS_TO_CLASSIFY"
 except Exception as e:
  record["inspection"]="ERROR"
  record["error"]=type(e).__name__+":"+str(e)[:240]
 payload=compact(record)
 (OUT/(lane+".json")).write_bytes(payload)
 name="JARVIS_V095_202609_11_RECONCILE_"+run+"_"+lane+".json"
 f=call(lambda:s.files().create(body={"name":name,"parents":[REPORT_PARENT]},
  media_body=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/json"),fields="id"))
 if sha(call(lambda:s.files().get_media(fileId=f["id"])))!=sha(payload):raise RuntimeError("RECEIPT_SHA_READBACK_FAILED")
 print(json.dumps({"run_id":run,"lane":lane,"inspection":record["inspection"],
  "observed_months":{m:record["months"].get(m,{}).get("observed_files",record["months"].get(m,{}).get("observed_objects_at_month_depth",0)) for m in MONTHS},
  "receipt_drive_id":f["id"],"release_status":record["release_status"]},ensure_ascii=False),flush=True)
 if record["inspection"]=="ERROR":raise RuntimeError("LANE_RECONCILE_INSPECTION_FAILED")
if __name__=="__main__":main()
