"""JARVIS Sep official TWSE aggregate credit balance: typed Silver and market Gold."""
import os,io,json,hashlib,collections,pathlib,datetime
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SRC="1R9WquaNOM1kFhVMaLWX_IOnePgsGAuCb"
SILVER="1uF0qhHMd41-_mF1czgYgNCBu6A5zjC5U";GOLD="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 s=build("drive","v3",credentials=c,cache_discovery=False)
 def read(id):return s.files().get_media(fileId=id).execute()
 def save(parent,name,b):
  q=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=40).execute()["files"]
  if q:
   if len(q)!=1 or sha(read(q[0]["id"]))!=sha(b):raise ValueError("OUTPUT_CONFLICT")
   return q[0]["id"]
  id=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
  if sha(read(id))!=sha(b):raise ValueError("READBACK_MISMATCH")
  return id
 data=read(SRC);source=pq.read_table(io.BytesIO(data));out=[];stats=collections.Counter();seen=set()
 names_req=["項目","買進","賣出","現金(券)償還","前日餘額","今日餘額"]
 for row in source.to_pylist():
  labels=json.loads(row["native_fields_json"])
  if labels!=names_req:continue
  raw=json.loads(row["native_row_json"])
  item=str(raw["0:項目"]).strip()
  if item not in ("融資(交易單位)","融券(交易單位)"):continue
  try:
   buy,sell,repay,prior,today=[int(str(raw[f"{i}:{labels[i]}"]).replace(",","")) for i in range(1,6)]
  except (ValueError,KeyError,TypeError):stats["bad_values"]+=1;continue
  if min(buy,sell,repay,prior,today)<0:stats["negative"]+=1;continue
  kind="margin_financing" if item.startswith("融資") else "securities_short"
  expected=prior+buy-sell-repay if kind=="margin_financing" else prior+sell-buy-repay
  if expected!=today:stats["balance_algebra_failure"]+=1;continue
  date=row["trade_date"];key=(date,kind)
  if key in seen:raise ValueError("DUPLICATE_DAY_KIND")
  seen.add(key)
  out.append({"trade_date":date,"market":"TSE","credit_kind":kind,"original_unit":"official_trading_unit",
    "buy_units":buy,"sell_units":sell,"repayment_units":repay,
    "prior_balance_units":prior,"current_balance_units":today,
    "net_balance_change_units":today-prior,"native_sha256":row["source_sha256"],
    "historical_pit_verified":False})
 if len({x["trade_date"] for x in out})!=20 or len(out)!=40 or stats:raise ValueError("TWSE_CREDIT_QA_FAIL "+str(stats))
 buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(out),buf,compression="zstd")
 silver_id=save(SILVER,"202609_TWSE_CREDIT_AGGREGATE_SILVER_V1.parquet",buf.getvalue())
 gold=[{"trade_date":r["trade_date"],"market":"TSE","credit_kind":r["credit_kind"],
   "balance_trading_units":r["current_balance_units"],"balance_change_trading_units":r["net_balance_change_units"],
   "silver_sha256":sha(buf.getvalue()),"historical_pit_verified":False} for r in out]
 g=io.BytesIO();pq.write_table(pa.Table.from_pylist(gold),g,compression="zstd")
 gold_id=save(GOLD,"202609_TWSE_CREDIT_BALANCE_GOLD_V1.parquet",g.getvalue())
 qa={"status":"SILVER_STANDARD_COLUMN_ALGEBRA_PASS_GOLD_COMPUTED","source_rows":source.num_rows,
     "verified_silver_rows":len(out),"trading_days":20,"silver_id":silver_id,"gold_id":gold_id,
     "source_sha256":sha(data),"silver_sha256":sha(buf.getvalue()),"gold_sha256":sha(g.getvalue()),
     "unit":"official trading unit; shares conversion not assumed",
     "historical_pit_verified":False,"source_universe_coverage_not_inferred":True}
 rep=json.dumps(qa,ensure_ascii=False,indent=2).encode()
 qa["qa_id"]=save(GOLD,"202609_TWSE_CREDIT_SILVER_GOLD_QA_V1.json",rep)
 pathlib.Path("credit_result").mkdir(exist_ok=True)
 pathlib.Path("credit_result/receipt.json").write_bytes(rep)
 print(json.dumps(qa,ensure_ascii=False))
if __name__=="__main__":main()
