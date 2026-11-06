"""ULTIMATE R1: fourteen production-candidate workers with independent durable receipts.

Each lane checks actual immutable file bytes/schema and derives a bounded task queue.
Work sharing is read-only evidence assistance until a source-locked, signed contract
authorizes mutable downstream work. Never publish unapproved features.
"""
import collections, datetime as dt, hashlib, io, json, os, pathlib, sys, time
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

LANES={
 "BRONZE_TWSE":("BRONZE","TWSE"),
 "BRONZE_TPEX":("BRONZE","TPEx"),
 "BRONZE_MOPS":("BRONZE","MOPS"),
 "BRONZE_TDCC":("BRONZE","TDCC"),
 "BRONZE_TAIFEX":("BRONZE","TAIFEX"),
 "BRONZE_NDC":("BRONZE","NDC"),
 "SILVER_PRICE":("SILVER","PRICE"),
 "SILVER_FUNDAMENTAL":("SILVER","FUNDAMENTAL"),
 "SILVER_TDCC":("SILVER","TDCC"),
 "SILVER_MACRO":("SILVER","MACRO"),
 "GOLD_TECHNICAL":("GOLD","TECHNICAL"),
 "GOLD_CHIP":("GOLD","CHIP"),
 "GOLD_FINANCIAL":("GOLD","FINANCIAL"),
 "GOLD_CROSS_ASSET":("GOLD","CROSS_ASSET"),
}
SOURCE_MANIFEST="governance/v095/202609_BRONZE_MIGRATION_RESUME_20261105.json"
SILVER={
 "PRICE":[("TSE_PRICE","14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"),("OTC_PRICE","1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk")],
 "FUNDAMENTAL":[("MOPS_REVENUE","1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"),("TSE_INSTITUTIONAL","1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx")],
 "TDCC":[("TDCC_OWNERSHIP","1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r")],
 "MACRO":[]}
GOLD={
 "TECHNICAL":[("TSE_PRICE","1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI","14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"),
              ("OTC_PRICE","1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6","1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk")],
 "CHIP":[("TSE_INSTITUTIONAL","18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7","1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx"),
         ("OTC_MARGIN","11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5",None)],
 "FINANCIAL":[("MOPS_REVENUE","1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI","1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5")],
 "CROSS_ASSET":[]}
ROOTS={"SILVER_MACRO":"1uBAAcr24R0da3q0WBeFu-yc5r1HB5YfL",
       "GOLD_CROSS_ASSET":"1FYIz-uylwZLM7HL-7MG2iH90BefMyXDw"}
CAT="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
OUT=pathlib.Path("ultimate_r1_lanes");OUT.mkdir(exist_ok=True)
REPORT_FOLDER="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"

def sha(b):return hashlib.sha256(b).hexdigest()
def encode(x):return (json.dumps(x,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode()
def connect():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def call(fn):
 last=None
 for k in range(3):
  try:return fn().execute()
  except Exception as e:
   last=e
   if k<2:time.sleep((k+1)*2)
 raise last
def listing(s,folder):
 rows=[];token=None
 while True:
  x=call(lambda:s.files().list(q="'"+folder+"' in parents and trashed=false",
    fields="nextPageToken,files(id,name,size,mimeType)",pageSize=1000,pageToken=token))
  rows.extend(x.get("files",[]));token=x.get("nextPageToken")
  if not token:return rows
def read(s,fid):return call(lambda:s.files().get_media(fileId=fid))
def inspect_parquet(s,name,fid):
 b=read(s,fid)
 if not b:raise ValueError("ZERO_BYTE_PARQUET")
 table=pq.read_table(io.BytesIO(b))
 keys=[k for k in ("trade_date","snapshot_date","revenue_month","stock_id") if k in table.column_names]
 # Structural and cross-partition evidence only. No unsupported PIT approval.
 return {"name":name,"file_id":fid,"sha256":sha(b),"bytes":len(b),
         "rows":table.num_rows,"columns":table.column_names,"key_columns":keys,
         "status":"CANDIDATE_SCHEMA_READ_PASS","pit_certified":False,
         "table":table}
def bronze(s,source,record):
 manifest=json.loads(pathlib.Path(SOURCE_MANIFEST).read_text())
 entry=next(x for x in manifest["source_month_folders"] if x["source"]==source)
 folder=listing(s,entry["drive_folder_id"])
 byid={f["id"]:f for f in folder}
 record["inventory_items"]=len(folder)
 record["manifest_items"]=len(entry["files"])
 tasklist=[]
 for idx,f in enumerate(entry["files"]):
  actual=byid.get(f["id"])
  if not actual or actual["name"]!=f["name"]:
   tasklist.append({"file_id":f["id"],"status":"MISSING_OR_STALE_ID"})
   continue
  # Bounded actual byte work. No repeated full re-download of huge archives.
  if idx==0:
   b=read(s,f["id"])
   tasklist.append({"file_id":f["id"],"name":f["name"],"sha256":sha(b),
    "byte_length_matches":len(b)==int(f["bytes"]),"status":"BYTE_RECHECK_PASS"
    if len(b)==int(f["bytes"]) else "BYTE_MISMATCH"})
  else:tasklist.append({"file_id":f["id"],"status":"OBSERVED_ID_AND_NAME_ONLY"})
 record["tasks"]=tasklist
 record["file_bytes_checked"]=sum(x["status"]=="BYTE_RECHECK_PASS" for x in tasklist)
 record["known_source_scope_only"]=True
 if source=="TDCC":
  record["other_source_files_not_in_legacy_manifest"]=max(0,len(folder)-len(entry["files"]))
 return any(t["status"]=="BYTE_MISMATCH" for t in tasklist)

def process(s,lane,record):
 stage,key=LANES[lane]
 if stage=="BRONZE":return bronze(s,key,record)
 if stage=="SILVER":
  tasks=[]
  for name,fid in SILVER[key]:
   x=inspect_parquet(s,name,fid);x.pop("table");tasks.append(x)
  if not tasks:
   items=listing(s,ROOTS[lane])
   record["stage_root_candidates"]=len(items)
   record["status"]="WAITING_TYPED_SOURCE_CONTRACT"
  record["tasks"]=tasks
  return False
 if stage=="GOLD":
  cat=json.loads(read(s,CAT))
  ids=cat["indicators"]
  if len(ids)!=443 or len({x["id"] for x in ids})!=443:raise ValueError("CATALOG_443_MISMATCH")
  record["catalog_id_count"]=443
  tasks=[]
  for name,fid,sid in GOLD[key]:
   x=inspect_parquet(s,name,fid)
   t=x.pop("table");declared=sorted({str(z) for z in t["input_silver_sha256"].to_pylist() if z}) if "input_silver_sha256" in t.column_names else []
   x["whole_silver_sha_declared"]=declared
   if sid:
    actual=sha(read(s,sid))
    x["current_silver_sha256"]=actual
    x["whole_silver_sha_matches"]=declared==[actual]
   else:x["whole_silver_sha_matches"]=False
   x["status"]="DESCRIPTIVE_CANDIDATE_NOT_PIT_CERTIFIED"
   tasks.append(x)
  if not tasks:
   record["stage_root_candidates"]=len(listing(s,ROOTS[lane]))
   record["status"]="WAITING_FEATURE_INPUT_CONTRACT"
  record["tasks"]=tasks
  record["all_443_formula_pit_certified"]=False
  return False
 raise ValueError("UNKNOWN_STAGE")

def main():
 lane=os.environ.get("JARVIS_LANE","")
 if lane not in LANES:raise ValueError("UNKNOWN_LANE")
 run=os.environ.get("GITHUB_RUN_ID","local")
 stage,key=LANES[lane]
 record={"schema":"JARVIS_V095_14LANE_INCREMENTAL_V1","run_id":run,
   "lane":lane,"stage":stage,"key":key,
   "observed_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
   "scope":"2026-09","writable_data_mutation":False,
   "historical_pit_certified":False,"official_release":False,
   "status":"CANDIDATE_EVIDENCE","tasks":[]}
 s=connect()
 try:
  failed=process(s,lane,record)
  if failed:record["status"]="BLOCKED_BYTE_MISMATCH"
 except Exception as e:
  record["status"]="BLOCKED_INSPECTION_ERROR"
  record["error"]=type(e).__name__+":"+str(e)[:220]
 # Same-tier assistance: inspect another stage peer only for evidence when
 # own lane lacks concrete data; no shared writes, duplicated transformations,
 # arbitrary takeover, or pretending read-only help is an actual repair.
 if not record["tasks"] and record["status"]!="BLOCKED_INSPECTION_ERROR":
  peers=[l for l,(st,_) in LANES.items() if st==stage and l!=lane]
  peer=peers[0]
  record["assist_target"]=peer
  record["assist_mode"]="EVIDENCE_READ_ONLY_SOURCE_RECHECK"
  try:
   other={"tasks":[]}
   process(s,peer,other)
   record["assisted_tasks"]=len(other.get("tasks",[]))
  except Exception as e:record["assist_error"]=type(e).__name__+":"+str(e)[:160]
 report=encode(record)
 (OUT/(lane+".json")).write_bytes(report)
 # Each run+lane receipt is immutable by unique name. Verify readback.
 name="JARVIS_V095_14LANE_"+run+"_"+lane+".json"
 created=call(lambda:s.files().create(body={"name":name,"parents":[REPORT_FOLDER]},
   media_body=MediaIoBaseUpload(io.BytesIO(report),mimetype="application/json"),fields="id"))
 remote=read(s,created["id"])
 if sha(remote)!=sha(report):raise ValueError("LANE_REPORT_READBACK_SHA_MISMATCH")
 print(json.dumps({"run_id":run,"lane":lane,"status":record["status"],
  "tasks":len(record["tasks"]),"assist_target":record.get("assist_target"),
  "report_drive_id":created["id"],"report_readback_verified":True,
  "data_release":"BLOCKED_UNTIL_PIT_AND_CONTRACT_APPROVED"},ensure_ascii=False),flush=True)
 if record["status"].startswith("BLOCKED_"):sys.exit(2)
if __name__=="__main__":main()
