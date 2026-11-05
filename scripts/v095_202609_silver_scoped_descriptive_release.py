"""September 2026 Silver typed snapshot acceptance; no historical PIT/backtest admission.

Uses pre-existing Parquet bytes and SHA readback. Formal descriptive Gold access for
as-of >= audit date is distinct from PIT-certified historical simulation use.
"""
import os,io,json,hashlib,datetime,decimal,collections,pathlib,re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow.parquet as pq,pyarrow as pa
FOLDER="1uBAAcr24R0da3q0WBeFu-yc5r1HB5YfL"
ASOF="2026-11-06"
DATA={
"TWSE_price":{"id":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz","expected_days":20,"min_rows":21000,"value_fields":["open","high","low","close"],"eligible_scope":"TSE_QUOTED_SECURITIES"},
"TPEx_price":{"id":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk","expected_days":20,"min_rows":17000,"value_fields":["open","high","low","close"],"eligible_scope":"OTC_QUOTED_SECURITIES"},
"MOPS_revenue":{"id":"1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5","expected_days":None,"min_rows":1900,"value_fields":["revenue_億元"],"eligible_scope":"TSE_OTC_4_DIGIT_ISSUERS"}
}
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def write(s,parent,name,b):
 found=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=30).execute()["files"]
 if len(found)>1:raise ValueError("DUPLICATE_OUTPUT")
 if found:
  if sha(get(s,found[0]["id"]))!=sha(b):raise ValueError("IMMUTABLE_RELEASE_CONFLICT")
  return found[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json",resumable=True),fields="id").execute()["id"]
 if sha(get(s,id))!=sha(b):raise ValueError("RELEASE_MANIFEST_READBACK_SHA")
 return id
def main():
 s=service();report={"schema":"JARVIS_V095_202609_SILVER_SCOPED_ANALYSIS_RELEASE_V1",
 "period":"2026-09","release_asof":ASOF,"historical_PIT_certified":False,
 "gold_allowed_historical_backtest":False,"all_202609_silver_complete":False,
 "gold_analysis_allowed":"DESCRIPTIVE_ASOF_2026_11_06_ONLY_BY_DATASET",
 "threshold":0.98,"data":{}}
 for key,spec in DATA.items():
  blob=get(s,spec["id"]);t=pq.read_table(io.BytesIO(blob))
  if t.num_rows<spec["min_rows"]:raise ValueError("ROW_VOLUME_TOO_LOW:"+key)
  for col in spec["value_fields"]:
   if col not in t.schema.names or not pa.types.is_decimal(t.schema.field(col).type):
    raise ValueError("MISSING_TYPED_DECIMAL:"+key+":"+col)
  if key.endswith("_price"):
   if not pa.types.is_date32(t.schema.field("trade_date").type):raise ValueError("TRADE_DATE_NOT_TYPED")
   dates=t["trade_date"].to_pylist()
   if len(set(dates))!=spec["expected_days"]:raise ValueError("TRADING_DATES_NOT_20")
   # Exact four-column valid numeric cells; other official placeholders stay native.
   vals=[t[c].to_pylist() for c in spec["value_fields"]]
   valid=sum(all(v[i] is not None for v in vals) for i in range(t.num_rows))
   o,h,l,c=vals
   invalid_logic=sum(1 for i in range(t.num_rows) if all(v[i] is not None for v in vals)
      and not (l[i]<=o[i]<=h[i] and l[i]<=c[i]<=h[i]))
   if invalid_logic:raise ValueError("CROSS_COLUMN_OHLC_BROKEN")
  else:
   valid=t["revenue_億元"].null_count
   valid=t.num_rows-valid
  rate=valid/t.num_rows
  status="SCOPED_SILVER_98_DESCRIPTIVE_PASS" if rate>=0.98 else "SCOPED_PARTIAL_HELD"
  report["data"][key]={"source_file_id":spec["id"],"source_sha256":sha(blob),
   "rows":t.num_rows,"numerically_valid_rows":valid,"numeric_valid_rate":rate,
   "coverage_denom_kind":"OBSERVED_TYPED_RECORDS_ONLY_NOT_COMPLETE_OFFICIAL_DATASET_UNIVERSE",
   "status":status,"eligible_scope":spec["eligible_scope"],
   "gold_descriptive_current_snapshot":rate>=0.98,
   "gold_historical_backtest":False,
   "identity_warnings":["4-digit numeric identifier alone does not certify common stock vs ETF"] if "price" in key else [],
   "publication_rule":"Only use for analysis as of "+ASOF+" or later; historical PIT not proven",
   "quality_limit":"Numeric correctness/official full market coverage not independently verified; 98% numeric coverage not global data correctness"}
 data=json.dumps(report,ensure_ascii=False,indent=2).encode()
 folder=FOLDER
 report["release_manifest_drive_id"]=write(s,folder,"JARVIS_v095_202609_SCOPED_DESCRIPTIVE_GOLD_INPUT_RELEASE_20261106.json",data)
 pathlib.Path("v095_202609_silver_release").mkdir(exist_ok=True)
 pathlib.Path("v095_202609_silver_release/result.json").write_bytes(data)
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
