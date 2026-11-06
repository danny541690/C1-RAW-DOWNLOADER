"""Read a September Gold indicator and trace its original Silver/Bronze source.
Runs in the SAME unified workflow's optional query mode, never invents missing values.
"""
import os,io,json,pathlib,hashlib,datetime
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
ROOT=pathlib.Path("v095_unified_202609");ROOT.mkdir(exist_ok=True)
SOURCES={
 "TSE":{"gold":"1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI","silver":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"},
 "OTC":{"gold":"1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6","silver":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk"},
 "REVENUE":{"gold":"1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI","silver":"1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"}
}
FIELD={
 "CLOSE":{"TSE":"close_price_NTD","OTC":"close"},
 "OPEN":{"OTC":"open"},"HIGH":{"OTC":"high"},"LOW":{"OTC":"low"},
 "MA5":{"TSE":"SMA_5"},"MA10":{"TSE":"SMA_10"},"MA20":{"TSE":"SMA_20"},
 "RETURN1D":{"TSE":"close_change_1d_pct"},
 "TURNOVER":{"TSE":"turnover_億元","OTC":"turnover_億元"},
 "VOLUME":{"TSE":"volume_shares","OTC":"volume_shares"},
 "REVENUE_M0":{"REVENUE":"revenue_億元"},
 "REVENUE_YOY_M0":{"REVENUE":"revenue_yoy_pct"},
 "REVENUE_MOM_M0":{"REVENUE":"revenue_mom_pct"}
}
def sha(x):return hashlib.sha256(x).hexdigest()
def scalar(x):
 if x is None:return None
 if isinstance(x,(datetime.date,datetime.datetime)):return x.isoformat()
 return str(x)
def main():
 stock=os.environ.get("JARVIS_STOCK","2330").strip()
 ind=os.environ.get("JARVIS_INDICATOR","MA5").strip()
 day=os.environ.get("JARVIS_DATE","2026-09-30").strip()
 market=os.environ.get("JARVIS_MARKET","TSE").strip().upper()
 if not (stock.isdigit() and len(stock)==4 and day.startswith("2026-09-") and len(day)==10):
  raise ValueError("INVALID_QUERY_MONTH_OR_STOCK")
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());s=build("drive","v3",credentials=c,cache_discovery=False)
 catalog=json.loads(s.files().get_media(fileId="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7").execute().decode("utf-8"))
 if ind not in {x["id"] for x in catalog["indicators"]}:
  raise ValueError("INDICATOR_NOT_IN_V095_443_CATALOG")
 dataset="REVENUE" if ind.startswith("REVENUE_") else market
 f=FIELD.get(ind,{}).get(dataset)
 report={"schema":"JARVIS_V095_SEPTEMBER_TRACE_QUERY_V1","query":{"stock_id":stock,"market":market,"date":day,"indicator_id":ind},
  "result":None,"source_chain":None,"historical_PIT_verified":False,"history_outside_september_not_a_failure":True}
 if dataset not in SOURCES or not f:
  report["status"]="UNMAPPED_FORMULA_OR_DATASET"
 else:
  ids=SOURCES[dataset];gb=s.files().get_media(fileId=ids["gold"]).execute()
  sb=s.files().get_media(fileId=ids["silver"]).execute()
  gold=pq.read_table(io.BytesIO(gb));silver=pq.read_table(io.BytesIO(sb))
  if f not in gold.column_names:
   report["status"]="NOT_COMPUTED_GOLD_COLUMN"
  else:
   gr=next((r for r in gold.to_pylist() if str(r.get("stock_id"))==stock
     and (str(r.get("trade_date"))==day if dataset!="REVENUE" else str(r.get("revenue_month"))=="2026-09")),None)
   sr=next((r for r in silver.to_pylist() if str(r.get("stock_id"))==stock
     and (str(r.get("trade_date"))==day if dataset!="REVENUE" else str(r.get("revenue_month"))=="2026-09")),None)
   if gr:
    value=gr[f]
    if ind=="VOLUME" and value is not None:value=value/1000
    report["result"]={"value":scalar(value),"unit":"張" if ind=="VOLUME" else None,
      "Gold_field":f,"quality":"PRESENT_DESCRIPTIVE" if value is not None else "NULL_OR_HISTORY_WARMUP"}
    report["source_chain"]={"gold_file_id":ids["gold"],"gold_sha256":sha(gb),
      "silver_file_id":ids["silver"],"silver_sha256":sha(sb),
      "bronze_source_sha256":sr.get("source_sha256",sr.get("source_native_sha256")) if sr else None,
      "bronze_zip_drive_id":sr.get("source_zip_id") if sr else None,
      "bronze_member":sr.get("source_member") if sr else None,
      "gold_input_sha_matches_silver":(gr.get("input_silver_sha256")==sha(sb)) if "input_silver_sha256" in gr else None}
    report["status"]="VALUE_FOUND_NOT_HISTORICAL_PIT_CERTIFIED"
   else:report["status"]="NO_GOLD_ROW_FOR_STOCK_DATE"
 out=ROOT/"query_trace.json";out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
