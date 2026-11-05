"""2026-09 Gold subset from existing Silver. Descriptive as-of 2026-11-06, never historic PIT."""
import os,io,json,hashlib,collections,argparse,datetime,pathlib
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SOURCES={"otc-price":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk","otc-margin":"1obHT1dEE9ZxvdbcgBHXgTn2Z2SWxSpmU","tse-flow":"1AYTAGxQKV2q3FaZgmp6YJ20e8CkVcELx"}
PARENT="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def fetch(s,id):return s.files().get_media(fileId=id).execute()
def save(s,parent,name,b):
 a=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=40).execute()["files"]
 if a:
  if len(a)>1 or sha(fetch(s,a[0]["id"]))!=sha(b):raise ValueError("IMMUTABLE_DESTINATION_CONFLICT")
  return a[0]["id"]
 id=s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(fetch(s,id))!=sha(b):raise ValueError("SHA_READBACK_FAIL")
 return id
def run(lane):
 s=service();source=fetch(s,SOURCES[lane]);tab=pq.read_table(io.BytesIO(source))
 good=[];exceptions=collections.Counter();seen=set()
 for r in tab.to_pylist():
  if lane=="otc-price":
   fields=["open","high","low","close"]
   if any(r[k] is None for k in fields):exceptions["non_numeric_price"]+=1;continue
   if not(r["low"]<=r["open"]<=r["high"] and r["low"]<=r["close"]<=r["high"]):raise ValueError("INVALID_OHLC")
   val={k:r[k] for k in fields+["volume_shares","turnover_億元"]}
  elif lane=="otc-margin":
   val={k:r.get(k) for k in ("margin_balance_lots","short_balance_lots","margin_buy_lots","margin_sell_lots")}
   if val["margin_balance_lots"] is None or val["short_balance_lots"] is None:exceptions["missing_margin"]+=1;continue
  else:
   val={k:r.get(k) for k in ("foreign_ex_dealer_net_shares","trust_net_shares","institutional_total_net_shares")}
   if val["foreign_ex_dealer_net_shares"] is None or val["trust_net_shares"] is None:exceptions["missing_flow"]+=1;continue
  day=r["trade_date"];code=r["stock_id"];market=r["market"];key=(str(day),market,code)
  if key in seen:raise ValueError("DUPLICATE_KEY")
  seen.add(key)
  good.append(dict(trade_date=day,stock_id=code,market=market,**val,
   native_sha256=r["source_sha256"] if lane=="otc-price" else r["source_native_sha256"],
   asof_available_date=datetime.date(2026,11,6),
   historical_pit_verified=False,security_type_verified=False,usage="DESCRIPTIVE_ONLY"))
 if not good:raise ValueError("NO_VALID_SUBSCOPE")
 destname="2026-09_GOLD_DESCRIPTIVE_"+lane
 a=s.files().list(q=f"'{PARENT}' in parents and name = '{destname}' and trashed = false",fields="files(id)",pageSize=40).execute()["files"]
 if len(a)>1:raise ValueError("DUPLICATE_FOLDER")
 dest=a[0]["id"] if a else s.files().create(body={"name":destname,"parents":[PARENT],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
 buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(good),buf,compression="zstd")
 data=buf.getvalue();assert pq.read_metadata(io.BytesIO(data)).num_rows==len(good)
 id=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_DESCRIPTIVE_R1.parquet",data)
 qa=dict(lane=lane,source_silver_id=SOURCES[lane],source_sha256=sha(source),rows_in=tab.num_rows,
  rows_out=len(good),exclusions=dict(exceptions),gold_file_id=id,gold_sha256=sha(data),
  historical_pit_verified=False,all_market_98_percent_correctness_certified=False,
  asof="2026-11-06",release="DESCRIPTIVE_SUBSCOPE_ONLY")
 b=json.dumps(qa,ensure_ascii=False,indent=2).encode()
 qa["qa_id"]=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_QA_R1.json",b)
 p=pathlib.Path("gold_subscope_evidence");p.mkdir(exist_ok=True)
 (p/(lane+".json")).write_bytes(b)
 print(json.dumps(qa,ensure_ascii=False),flush=True)
if __name__=="__main__":
 a=argparse.ArgumentParser();a.add_argument("--lane",choices=SOURCES,required=True);run(a.parse_args().lane)
