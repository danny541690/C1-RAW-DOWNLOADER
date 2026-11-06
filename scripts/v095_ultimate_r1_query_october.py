"""Publish an indexed ChatGPT-readable October partial Gold preview + reverse lineage.
Inputs are actual Gold parquet artifacts written by v095_ultimate_r1_october_bsg.py.
No fabricated source coverage, no PIT certification.
"""
import os,io,json,hashlib,datetime as dt,pathlib
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
P=pathlib.Path("ultimate_r1");P.mkdir(exist_ok=True)
GOLD={"TWSE_VALUATION":"1DKXj9zyWNdRg99b9SPN5fPim6YzjcrS0","TPEX_INDICES":"1v9oeD9wG9COUGf252fArNtk7DdZsqlac","TAIFEX_PCR":"14wRa4CuGvMaGsQEr8Ig11hQ5EYXpKSJO"}
OPS="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
def sha(x):return hashlib.sha256(x).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def stringify(v):
 if isinstance(v,(dt.date,dt.datetime)):return v.isoformat()
 if isinstance(v,dict):return {k:stringify(x) for k,x in v.items()}
 if isinstance(v,list):return [stringify(x) for x in v]
 return v
def main():
 s=svc();datasets={};preview={}
 for lane,fid in GOLD.items():
  b=s.files().get_media(fileId=fid).execute();rows=pq.read_table(io.BytesIO(b)).to_pylist()
  if not rows:raise ValueError("EMPTY_GOLD_"+lane)
  if any(r.get("historical_pit_verified") is not False for r in rows):raise ValueError("UNSUPPORTED_PIT_CLAIM")
  refs={k:rows[0][k] for k in ("silver_file_id","silver_sha256","bronze_file_id","bronze_sha256")}
  datasets[lane]={"gold_file_id":fid,"gold_sha256":sha(b),"rows":len(rows),**refs,"period":"2026-10","status":"DESCRIPTIVE_ONLY_NO_HISTORICAL_PIT"}
  if lane=="TWSE_VALUATION":
   got=[r for r in rows if r["stock_id"]=="2330"]
   preview["2330_2026_10_19"]=stringify(got[0]) if len(got)==1 else {"status":"NOT_FOUND_OR_AMBIGUOUS","count":len(got)}
  elif lane=="TPEX_INDICES":
   got=[r for r in rows if r["index_name"]=="櫃買指數"]
   preview["otc_index_2026_10_19"]=stringify(got[0]) if len(got)==1 else {"status":"NOT_FOUND_OR_AMBIGUOUS","count":len(got)}
  elif lane=="TAIFEX_PCR":
   got=sorted(rows,key=lambda r:r["trade_date"])
   preview["taifex_latest_observed"]=stringify(got[-1])
 obj={"schema":"JARVIS_V095_CHATGPT_GOLD_LOOKUP_202610_R1","asof":"2026-11-06",
   "scope":"PARTIAL_THREE_SOURCE_DATASETS_NOT_FULL_MONTH","no_pit_certification":True,"no_full_443_claim":True,
   "dataset_index":datasets,"example_queries":preview}
 payload=json.dumps(obj,ensure_ascii=False,indent=2).encode()
 name="JARVIS_V095_202610_GOLD_QUERY_INDEX_"+sha(json.dumps(datasets,sort_keys=True).encode())[:16]+".json"
 x=s.files().list(q="'"+OPS+"' in parents and trashed = false and name = '"+name+"'",fields="files(id,name)",pageSize=30).execute()["files"]
 if len(x)>1:raise ValueError("DUPLICATE_QUERY_INDEX")
 if x:
  fid=x[0]["id"]
  if sha(s.files().get_media(fileId=fid).execute())!=sha(payload):raise ValueError("QUERY_INDEX_CONFLICT")
 else:
  fid=s.files().create(body={"name":name,"parents":[OPS]},media_body=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/json"),fields="id").execute()["id"]
 if sha(s.files().get_media(fileId=fid).execute())!=sha(payload):raise ValueError("QUERY_READBACK_MISMATCH")
 (P/"october_chatgpt_lookup.json").write_bytes(payload)
 print(json.dumps({"index_drive_id":fid,"datasets":{k:v["rows"] for k,v in datasets.items()},"examples":preview,"historical_pit":False},ensure_ascii=False,default=str))
if __name__=="__main__":main()
