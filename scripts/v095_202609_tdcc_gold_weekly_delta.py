"""Weekly TDCC descriptive Gold; no historical PIT certification."""
import os,io,json,hashlib,collections,datetime,pathlib
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SRC="1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r";PARENT="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
def h(b):return hashlib.sha256(b).hexdigest()
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());s=build("drive","v3",credentials=c,cache_discovery=False)
 def fetch(id):return s.files().get_media(fileId=id).execute()
 def save(folder,name,b):
  q=s.files().list(q=f"'{folder}' in parents and name = '{name}' and trashed = false",fields="files(id)").execute()["files"]
  if q:
   if len(q)!=1 or h(fetch(q[0]["id"]))!=h(b):raise ValueError("CONFLICT")
   return q[0]["id"]
  id=s.files().create(body={"name":name,"parents":[folder]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
  if h(fetch(id))!=h(b):raise ValueError("SHA_FAIL")
  return id
 b=fetch(SRC);t=pq.read_table(io.BytesIO(b));assert t.num_rows==276097
 groups=collections.defaultdict(list)
 for r in t.to_pylist():
  code=str(r["stock_id"])
  if code.isdigit() and len(code)==4:groups[code,str(r["holding_tier"])].append(r)
 out=[]
 for (stock,tier),rr in groups.items():
  rr.sort(key=lambda z:z["snapshot_date"]);old=None
  for x in rr:
   if old and old["snapshot_date"]==x["snapshot_date"]:raise ValueError("DUPLICATE_TIER_DATE")
   out.append(dict(snapshot_date=x["snapshot_date"],stock_id=stock,source_tier=tier,
    shares=x["shares"],holders=x["people_count"],
    wow_shares=None if old is None else x["shares"]-old["shares"],
    wow_holders=None if old is None else x["people_count"]-old["people_count"],
    source_native_sha256=x["source_sha256"],asof="2026-11-06",
    historical_pit_verified=False,stock_market_verified=False))
   old=x
 buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(out),buf,compression="zstd")
 name="202609_TDCC_DESCRIPTIVE_GOLD_20261106"
 q=s.files().list(q=f"'{PARENT}' in parents and name = '{name}' and trashed = false",fields="files(id)").execute()["files"]
 if len(q)>1:raise ValueError("DUPLICATE_FOLDER")
 folder=q[0]["id"] if q else s.files().create(body={"name":name,"parents":[PARENT],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
 id=save(folder,"TDCC_202609_GOLD_NATIVE_TIER_WOW_R1.parquet",buf.getvalue())
 report=dict(status="DESCRIPTIVE_ONLY",input_rows=t.num_rows,output_rows=len(out),
  input_sha256=h(b),gold_id=id,gold_sha256=h(buf.getvalue()),
  release_asof="2026-11-06",historical_pit_allowed=False,
  business_tier_semantics_verified=False,stock_market_verified=False)
 result=json.dumps(report,ensure_ascii=False,indent=2).encode()
 report["qa_id"]=save(folder,"TDCC_202609_GOLD_NATIVE_TIER_QA_R1.json",result)
 pathlib.Path("tdcc_gold_qa").mkdir(exist_ok=True)
 pathlib.Path("tdcc_gold_qa/result.json").write_bytes(result)
 print(json.dumps(report,ensure_ascii=False))
if __name__=="__main__":main()
