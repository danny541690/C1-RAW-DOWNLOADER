"""ChatGPT query registry for enlarged October v0.95 native Silver/Gold candidate Parquet.
Reads real Drive dataset bodies and publishes compact immutable lookup metadata.
Schema/unit/PIT are NOT assumed certified.
"""
import os,io,json,hashlib,datetime as dt,collections,pathlib
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
TARGETS={
 "TWSE":{"silver":"17iEJqZQylntZSu3lwxjci5h0JMdFIusn","gold":"1g0VlVMGE8CnAIMLECKFG5-uDpuA3Tjmp"},
 "TPEX":{"silver":"1Q7efkutQ0gSsLfU0XwPcBb2wKhn3jKgi","gold":"1v_UpLdGZYuJzRdL6YP6vRFZ62peO-zke"}}
PARENT="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
OUT=pathlib.Path("ultimate_r1");OUT.mkdir(exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def main():
 d=api();result={"schema":"JARVIS_V095_LATEST_TO_202609_QUERY_REGISTRY_R1","asof":"2026-11-06",
 "verified_months":["2026-09","2026-10"],"unverified_months":["2026-11"],
 "scope":"OCTOBER_BOUNDED_ARCHIVES_PLUS_EXISTING_SEPTEMBER_ONLY_NOT_FULL_MONTH",
 "dataset_index":{},"no_historical_pit":True,"not_443_formula_certified":True,
 "data_unit_policy":"NATIVE_UNCLASSIFIED; use descriptive raw numeric only; no financial unit comparisons or investment signals"}
 for source,loc in TARGETS.items():
  silver=d.files().get_media(fileId=loc["silver"]).execute()
  gold=d.files().get_media(fileId=loc["gold"]).execute()
  tb=pq.read_table(io.BytesIO(silver));tg=pq.read_table(io.BytesIO(gold))
  if "trade_date" not in tb.schema.names or "numeric_native" not in tg.schema.names:raise ValueError("MISSING_SILVER_GOLD_CONTRACT")
  count=collections.Counter();categories=collections.Counter()
  # Column batch reading rather than copying whole dataset to Python.
  for date,cat in zip(tb.column("trade_date").to_pylist(),tb.column("category").to_pylist()):
   count[str(date)]+=1;categories[str(cat)]+=1
  sample=[]
  # Gold native rows: expose only numeric raw field and its exact original table label.
  for row in tg.slice(0,min(tg.num_rows,30)).to_pylist():
   if len(sample)>=5:break
   sample.append({k:str(row.get(k)) if row.get(k) is not None else None for k in ("trade_date","category","table_title","row_label","field_name","numeric_native","field_unit")})
  if tg.num_rows==0 or tb.num_rows==0:raise ValueError("EMPTY_DATASET")
  result["dataset_index"][source]={"silver_file_id":loc["silver"],"silver_sha256":sha(silver),
   "silver_rows":tb.num_rows,"gold_file_id":loc["gold"],"gold_sha256":sha(gold),
   "gold_numeric_rows":tg.num_rows,"date_rows":dict(sorted(count.items())),"categories":dict(categories),
   "sample_numeric_rows":sample,"quality":"CANDIDATE_DESCRIPTIVE_NATIVE_NO_PIT",
   "reverse_trace":"Gold.source_bronze_file_id and .source_bronze_sha256 -> Bronze; Gold.silver_file_id -> Silver"}
 payload=json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2).encode()
 name="JARVIS_V095_202609_TO_LATEST_QUERY_REGISTRY_"+sha(payload)[:20]+".json"
 files=d.files().list(q="'"+PARENT+"' in parents and name = '"+name+"' and trashed=false",fields="files(id,name)",pageSize=100).execute()["files"]
 if len(files)>1:raise ValueError("AMBIGUOUS_REGISTRY")
 if files:fid=files[0]["id"]
 else:fid=d.files().create(body={"name":name,"parents":[PARENT]},media_body=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/json"),fields="id").execute()["id"]
 if sha(d.files().get_media(fileId=fid).execute())!=sha(payload):raise ValueError("REGISTRY_READBACK_SHA_MISMATCH")
 (OUT/"enlarged_query_registry.json").write_bytes(payload)
 print(json.dumps({"registry_drive_id":fid,"sources":{k:{"silver":v["silver_rows"],"gold_numeric":v["gold_numeric_rows"],"dates":v["date_rows"]} for k,v in result["dataset_index"].items()},"pit":False},ensure_ascii=False))
if __name__=="__main__":main()
