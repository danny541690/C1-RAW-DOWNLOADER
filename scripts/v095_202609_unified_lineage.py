"""JARVIS v0.95 September: 443-ID catalog, live Gold -> Silver -> Bronze lineage, PIT matrix.
Evidence-only; no invented formulas or publication times.
"""
import os,io,json,re,hashlib,pathlib,datetime,collections
import pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
ROOT=pathlib.Path("v095_unified_202609");ROOT.mkdir(exist_ok=True)
CAT="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
QA_PARENT="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
PARTS={
 "TSE_PRICE":{"gold":"1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI","silver":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz"},
 "OTC_PRICE":{"gold":"1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6","silver":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk"},
 "MOPS_REVENUE":{"gold":"1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI","silver":"1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"},
 "TSE_INSTITUTIONAL":{"gold":"18pghcU3lYeWP008NzbHQ1ZDeK85a3Hs7","silver":"1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx"},
 "OTC_CREDIT":{"gold":"11kpQ1ehaY3wkUGBUblqX_-rNPYz-XYA5","silver":"1obHT1dEE9ZxvdbcgBHXgTn2Z2SWxSpmU"}
}
# Only use IDs with unambiguous definitions; every formula still requires independent approval.
CROSSWALK={
 "CLOSE":("TSE_PRICE","close_price_NTD"),"MA5":("TSE_PRICE","SMA_5"),
 "MA10":("TSE_PRICE","SMA_10"),"MA20":("TSE_PRICE","SMA_20"),
 "RETURN1D":("TSE_PRICE","close_change_1d_pct"),
 "TURNOVER":("TSE_PRICE","turnover_億元"),
 "REVENUE_M0":("MOPS_REVENUE","revenue_億元"),
 "REVENUE_M1":("MOPS_REVENUE","revenue_prior_month_億元"),
 "REVENUE_YOY_M0":("MOPS_REVENUE","revenue_yoy_pct"),
 "REVENUE_MOM_M0":("MOPS_REVENUE","revenue_mom_pct")
}
def sha(x):return hashlib.sha256(x).hexdigest()
def conn():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def get(s,id):return s.files().get_media(fileId=id).execute()
def scalar(x):
 if x is None:return None
 if isinstance(x,(datetime.date,datetime.datetime)):return x.isoformat()
 return str(x)
def table_details(s,name,pair):
 sb=get(s,pair["silver"]);gb=get(s,pair["gold"])
 silver=pq.read_table(io.BytesIO(sb));gold=pq.read_table(io.BytesIO(gb))
 source_cols=[v for v in ("source_sha256","source_native_sha256","native_sha256","source_member","input_silver_sha256","source_zip_id") if v in gold.column_names or v in silver.column_names]
 silver_source_hashes=[]
 for k in ("source_sha256","source_native_sha256"):
  if k in silver.column_names:
   vals=silver[k].to_pylist()
   silver_source_hashes=sorted({str(x) for x in vals if x})[:25];break
 declared=[]
 for k in ("input_silver_sha256","source_sha256","source_native_sha256"):
  if k in gold.column_names:
   vals=gold[k].to_pylist();declared=sorted({str(x) for x in vals if x})[:25]
   if k=="input_silver_sha256":break
 input_sha_verified="input_silver_sha256" in gold.column_names and set(gold["input_silver_sha256"].to_pylist())=={sha(sb)}
 excluded={"trade_date","stock_id","market","name","source_native_sha256","native_sha256","source_sha256","input_silver_sha256","original_row_index","asof_available_date","historical_PIT_verified","historical_pit_verified","security_type_verified","usage","output_usage","source_member","source_zip_id","input_silver_file_id","snapshot_date"}
 metrics=[]
 for col in gold.column_names:
  if col in excluded:continue
  a=gold[col];metrics.append({"column":col,"type":str(a.type),"rows":len(a),"non_null":len(a)-a.null_count})
 sample=[]
 for row in gold.to_pylist()[:1]:
  sample=[{"name":k,"value":scalar(v)} for k,v in row.items()][:25]
 return {"source":name,"gold_drive_file_id":pair["gold"],"silver_drive_file_id":pair["silver"],
  "silver_sha256":sha(sb),"gold_sha256":sha(gb),"silver_rows":silver.num_rows,"gold_rows":gold.num_rows,
  "gold_input_silver_sha_verified":input_sha_verified,
  "gold_columns":gold.column_names,"silver_columns":silver.column_names,
  "gold_metrics":metrics,"trace_columns":source_cols,
  "source_hash_sample":silver_source_hashes,
  "sample_gold_row":sample,
  "pit_verified":False,"historical_backtest_allowed":False}
def history_status(r):
 key=r["id"];name=r.get("name","")
 if re.search(r"(?:60|120|240)(?:D|$|_)",key) or re.search(r"(?:TTM|24M|_4Q|_YOY)",key):
  return "REQUIRES_PRIOR_PERIOD_DATA"
 if "MAIN" in key or "BROKER" in key or "BRANCH" in key:
  return "POSSIBLE_XQ_SOURCE_NOT_VERIFIED"
 return "SEPTEMBER_ELIGIBILITY_NEEDS_FORMULA_REVIEW"
def main():
 s=conn();doc=json.loads(get(s,CAT).decode("utf-8"))
 ids=doc["indicators"]
 if len(ids)!=443 or len({r["id"] for r in ids})!=443:raise ValueError("CATALOG_ID_FAILURE")
 inventory={name:table_details(s,name,pair) for name,pair in PARTS.items()}
 mapping=[];count=collections.Counter()
 for item in ids:
  ref=CROSSWALK.get(item["id"]);rule=history_status(item)
  row={"id":item["id"],"name":item["name"],"group":item["group"],"history_scope":rule,
    "formula_status":"PENDING_APPROVAL","pit_status":"NOT_CERTIFIED","gold_column":None,
    "source_dataset":None,"silver_file_id":None,"bronze_source_hashes":[],"nonnull_rows":None}
  if ref and ref[1] in inventory[ref[0]]["gold_columns"]:
   x=inventory[ref[0]];field=next(v for v in x["gold_metrics"] if v["column"]==ref[1])
   row.update(gold_column=ref[1],source_dataset=ref[0],gold_file_id=x["gold_drive_file_id"],
     silver_file_id=x["silver_drive_file_id"],bronze_source_hashes=x["source_hash_sample"],nonnull_rows=field["non_null"])
   row["field_status"]="MATCHED_COLUMN_NOT_FORMULA_APPROVED"
  else:row["field_status"]="UNMAPPED_NOT_CONFIRMED_ABSENT"
  count[row["field_status"]]+=1;mapping.append(row)
 pit={"descriptive_snapshot_date":"2026-11-06","September_revenue_on_September_30":"NOT_AVAILABLE",
   "event_time_fields":["trade_date","snapshot_date","revenue_month"],
   "required_for_historical_backtest":["first_published_at","available_at","revision_effective_at","security_master_valid_from","corporate_action_asof"],
   "never_infer_publication_from_download_time":True,
   "full_historical_pit_certified":False}
 result={"schema":"JARVIS_V095_202609_GOLD_LINEAGE_PIT_V1","month":"2026-09",
   "catalog":443,"mapping_counts":dict(count),"partitions":inventory,"pit":pit,
   "missing_history_is_not_monthly_failure":True,
   "AI_query_interface_status":"INDEX_ONLY_NO_LIVE_GENERAL_QUERY_ENDPOINT",
   "formal_release":False}
 (ROOT/"indicator_443_crosswalk.json").write_text(json.dumps(mapping,ensure_ascii=False,indent=2))
 (ROOT/"lineage_index.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
 (ROOT/"pit_matrix.json").write_text(json.dumps(pit,ensure_ascii=False,indent=2))
 print(json.dumps({"catalog":443,"mapped":dict(count),"datasets":{k:v["gold_rows"] for k,v in inventory.items()},"pit":"UNVERIFIED"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
