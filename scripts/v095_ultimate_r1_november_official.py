"""2026-11 controlled official TWSE/TPEx OHLCV canary (Nov 4 and 5).
Reuse v0.93 verified URL constructor and native response validator.
Four requests maximum; immutable Bronze original, Silver market Parquet,
Gold descriptive daily OHLCV, all file-hash lineage; no historical PIT promise.
"""
import io,os,re,json,decimal,hashlib,datetime as dt,collections,pathlib,time,http.client,urllib.error
import pyarrow as pa,pyarrow.parquet as pq
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from scripts.v093_three_year_repair import Audit,request,validate
D=decimal.Decimal;OUT=pathlib.Path("ultimate_r1");OUT.mkdir(exist_ok=True)
DATES=("2026-11-04","2026-11-05")
SOURCE_FILTER=os.environ.get("V095_SOURCE_FILTER","TWSE,TPEx").split(",")
def bounded_official_request(url):
 last=None
 for attempt in range(3):
  try:return request(url)
  except (http.client.IncompleteRead,TimeoutError,ConnectionError,urllib.error.URLError,OSError) as err:
   last=err
   if attempt<2:time.sleep(2**attempt*3)
 raise RuntimeError("OFFICIAL_TRANSPORT_RETRIES_EXHAUSTED:"+type(last).__name__)

SOURCES={
 "TWSE":{"bronze":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE","silver":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5",
  "cat":"prices_indices","title":"每日收盤行情",
  "fields":{"id":"證券代號","name":"證券名稱","open":"開盤價","high":"最高價","low":"最低價","close":"收盤價","shares":"成交股數","amount":"成交金額"}},
 "TPEx":{"bronze":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG","silver":"1Ys8iWBOa4jjBOlLOZ8aEnn_LriPh_FZ5",
  "cat":"prices","title":"上櫃股票行情",
  "fields":{"id":"代號","name":"名稱","open":"開盤","high":"最高","low":"最低","close":"收盤","shares":"成交股數","amount":"成交金額(元)"}}}
GOLD="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
def sha(b):return hashlib.sha256(b).hexdigest()
def num(v):
 v=str(v).strip().replace(",","")
 if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)",v):return None
 try:return D(v)
 except decimal.InvalidOperation:return None
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"]);c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def ls(d,parent):
 a=[];page=None
 while True:
  z=d.files().list(q="'"+parent+"' in parents and trashed = false",fields="nextPageToken,files(id,name,mimeType)",pageSize=1000,pageToken=page).execute()
  a+=z.get("files",[]);page=z.get("nextPageToken")
  if not page:return a
def folder(d,p,name):
 x=[a for a in ls(d,p) if a["name"]==name]
 if len(x)>1:raise ValueError("DUPLICATE_FOLDER")
 if x:return x[0]["id"]
 return d.files().create(body={"name":name,"parents":[p],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def save(d,p,name,b):
 x=[a for a in ls(d,p) if a["name"]==name]
 if len(x)>1:raise ValueError("DUPLICATE_FILE")
 if x:
  fid=x[0]["id"]
  if sha(d.files().get_media(fileId=fid).execute())!=sha(b):raise ValueError("IMMUTABLE_DIFFERENT_CONTENT")
  return fid,"REUSED"
 fid=d.files().create(body={"name":name,"parents":[p]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(d.files().get_media(fileId=fid).execute())!=sha(b):raise ValueError("SHA_READBACK")
 return fid,"CREATED"
def parse(raw,source,day):
 config=SOURCES[source];obj=json.loads(raw);matches=[t for t in obj.get("tables",[]) if config["title"] in str(t.get("title",""))]
 if len(matches)!=1:raise ValueError("AMBIGUOUS_OFFICIAL_PRICE_TABLE")
 t=matches[0];columns={f:i for i,f in enumerate(t.get("fields") or [])}
 if not all(f in columns for f in config["fields"].values()):raise ValueError("OFFICIAL_SCHEMA_CHANGED")
 rows=[];seen=set();errors=0
 for pos,row in enumerate(t.get("data",[])):
  if len(row)!=len(columns):raise ValueError("ROW_WIDTH")
  k=config["fields"];code=str(row[columns[k["id"]]]).strip()
  if not re.fullmatch(r"\d{4}",code):continue
  if code in seen:raise ValueError("DUPLICATE_STOCK")
  seen.add(code);raw_values={a:row[columns[f]] for a,f in k.items()}
  p=[num(raw_values[x]) for x in ("open","high","low","close")]
  amount=num(raw_values["amount"]);vol=num(raw_values["shares"])
  if amount is not None and amount<0 or vol is not None and vol<0:raise ValueError("NEGATIVE_VOLUME")
  if all(x is not None for x in p) and not (p[2]<=p[0]<=p[1] and p[2]<=p[3]<=p[1]):raise ValueError("OHLC_LOGIC")
  if any(x is None for x in p):errors+=1
  rows.append({"trade_date":dt.date.fromisoformat(day),"stock_id":code,"market":"TSE" if source=="TWSE" else "OTC",
   "name":str(raw_values["name"]),"open":p[0],"high":p[1],"low":p[2],"close":p[3],
   "volume_shares":int(vol) if vol is not None and vol==vol.to_integral_value() else None,
   "turnover_億元":amount/D("100000000") if amount is not None else None,
   "native_row_index":pos,"native_ohlc_json":json.dumps({x:raw_values[x] for x in ("open","high","low","close")},ensure_ascii=False),
   "pit_verified":False,"published_at":None,"status":"NUMERIC_OHLC" if all(x is not None for x in p) else "NONNUMERIC_NEEDS_CLASSIFICATION"})
 if len(rows)<300:raise ValueError("SUSPICIOUSLY_FEW_MARKET_STOCKS")
 return rows,errors
def to_parquet(rows):
 b=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows),b,compression="zstd")
 out=b.getvalue()
 if pq.read_metadata(io.BytesIO(out)).num_rows!=len(rows):raise ValueError("PARQUET_COUNT")
 return out
def main():
 d=api();r={"schema":"V095_202611_LATEST_BSG_CANARY","run_id":os.getenv("GITHUB_RUN_ID"),
 "requested_days":list(DATES),"completed":{},"rejected":{},"pit_verified":False}
 for source,config in SOURCES.items():
  if source not in SOURCE_FILTER:continue
  jobs={j["period"]:j for j in Audit.jobs(object.__new__(Audit),"2026-11",set())
   if j["source"]==source and j["category"]==config["cat"] and j["period"] in DATES}
  for day in DATES:
   key=source+"_"+day
   try:
    if day not in jobs:raise ValueError("NO_FROZEN_OFFICIAL_ROUTE")
    job=jobs[day];url=job["url"];raw=bounded_official_request(url)
    facts=validate(raw,source,job["category"],day)
    rows,unparsed=parse(raw,source,day)
    if len(rows)<300:raise ValueError("TOO_FEW_ROWS")
    bm=folder(d,config["bronze"],"2026-11");digest=sha(raw)
    bronze_id,ba=save(d,bm,"V095_202611_"+source+"_"+day+"_"+digest[:20]+".json",raw)
    for row in rows:row.update(bronze_file_id=bronze_id,bronze_sha256=digest,source_url=url)
    sm=folder(d,config["silver"],"2026-11_CANDIDATE")
    silver=to_parquet(rows);sd=sha(silver)
    silver_id,sa=save(d,sm,"V095_202611_"+source+"_"+day+"_OHLCV_"+sd[:20]+".parquet",silver)
    gold=[]
    for row in rows:
     if row["close"] is None or row["close"]<=0:continue
     gold.append({"trade_date":row["trade_date"],"market":row["market"],"stock_id":row["stock_id"],
      "close":row["close"],"volume_shares":row["volume_shares"],"turnover_億元":row["turnover_億元"],
      "silver_file_id":silver_id,"silver_sha256":sd,"bronze_file_id":bronze_id,"bronze_sha256":digest,
      "historical_pit_verified":False,"usage":"DESCRIPTIVE_NO_BACKTEST"})
    gm=folder(d,GOLD,"2026-11_DESCRIPTIVE_ONLY")
    gb=to_parquet(gold)
    gid,ga=save(d,gm,"V095_202611_"+source+"_"+day+"_PRICE_GOLD_"+sha(gb)[:20]+".parquet",gb)
    r["completed"][key]={"bronze_id":bronze_id,"silver_id":silver_id,"gold_id":gid,
      "rows":len(rows),"gold_rows":len(gold),"native_numeric_exception_rows":unparsed,"source_date":day,
      "official_rows":facts.get("rows"),"sha256":digest,"actions":[ba,sa,ga]}
   except Exception as exc:r["rejected"][key]=type(exc).__name__+":"+str(exc)[:200]
 (OUT/"november_latest_bsg.json").write_text(json.dumps(r,ensure_ascii=False,indent=2))
 print(json.dumps({"run_id":r["run_id"],"completed":r["completed"],"rejected":r["rejected"],"pit":False},ensure_ascii=False))
if __name__=="__main__":main()
