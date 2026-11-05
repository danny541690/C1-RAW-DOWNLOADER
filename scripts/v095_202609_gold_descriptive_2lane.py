"""JARVIS 2026-09 Gold as-of 2026-11-06 descriptive feature snapshot.
Release is real but restricted: NEVER historical PIT, no predictive label, no stock selection.
"""
import os,io,json,hashlib,datetime,pathlib,collections,decimal,argparse
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pyarrow as pa,pyarrow.parquet as pq
D=decimal.Decimal
SOURCE_IDS={"tse":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz","revenue":"1y623bgGtMtRgkJmUZfIzX0eVnpmINbc5"}
GOLD_PARENT={"tse":"1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3","revenue":"1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"}
RELEASE="2026-11-06"
def sha(b):return hashlib.sha256(b).hexdigest()
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
  client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def read(s,id):return s.files().get_media(fileId=id).execute()
def save(s,parent,name,data):
 exists=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",fields="files(id)",pageSize=100).execute()["files"]
 if len(exists)>1:raise ValueError("MULTIPLE_GOLD_OUTPUTS")
 if exists:
  if sha(read(s,exists[0]["id"]))!=sha(data):raise ValueError("IMMUTABLE_GOLD_SHA_CONFLICT")
  return exists[0]["id"]
 file=s.files().create(body={"name":name,"parents":[parent]},
  media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/octet-stream",resumable=True),fields="id").execute()["id"]
 if sha(read(s,file))!=sha(data):raise ValueError("GOLD_DRIVE_SHA_READBACK")
 return file
def folder(s,parent,name):
 files=s.files().list(q=f"'{parent}' in parents and name = '{name}' and trashed = false",pageSize=40,fields="files(id)").execute()["files"]
 if len(files)>1:raise ValueError("DUPLICATE_GOLD_FOLDER")
 if files:return files[0]["id"]
 return s.files().create(body={"name":name,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
def snapshot_tse(rows,input_sha):
 rows.sort(key=lambda r:(r["stock_id"],r["trade_date"]))
 daily=collections.defaultdict(dict)
 for r in rows:
  if r["trade_date"].isoformat()[:7]!="2026-09":raise ValueError("WRONG_PRICE_MONTH")
  key=(r["stock_id"],r["trade_date"])
  if r["trade_date"] in daily[r["stock_id"]]:raise ValueError("DUPLICATE_DAILY_KEY")
  daily[r["stock_id"]][r["trade_date"]]=r
 expected_calendar=[datetime.date(2026,9,1)+datetime.timedelta(days=i) for i in range(30) if (datetime.date(2026,9,1)+datetime.timedelta(days=i)).weekday()<5 and i+1 not in (25,28)]
 if len(expected_calendar)!=20:raise ValueError("BAD_OFFICIAL_CALENDAR")
 expected_idx={d:i for i,d in enumerate(expected_calendar)}
 out=[];limits=collections.Counter()
 for stock,dated in daily.items():
  dates=sorted(dated)
  series=[dated[d] for d in dates]
  for i,r in enumerate(series):
   c=r["close"];price_valid=all(r[k] is not None for k in ("open","high","low","close"))
   if not price_valid or c is None or c<=0:
    limits["missing_or_invalid_ohlc"]+=1;continue
   feat={
    "trade_date":r["trade_date"],"stock_id":stock,"market":"TSE","name":r.get("name"),
    "close_price_NTD":c,"volume_shares":r["volume_shares"],"turnover_億元":r["turnover_億元"],
    "input_silver_sha256":input_sha,
    "source_native_sha256":r["source_sha256"],
    "original_adjustment":"UNADJUSTED",
    "asof_available_date":datetime.date.fromisoformat(RELEASE),
    "historical_PIT_verified":False,
    "security_type_verified":False,
    "output_usage":"DESCRIPTIVE_ONLY_NO_BACKTEST"
   }
   # Daily changes from consecutive available market-wide day only, never bridge missing stock trading day.
   if i and expected_idx[dates[i]]-expected_idx[dates[i-1]]==1 and series[i-1]["close"] is not None and series[i-1]["close"]>0:
    feat["close_change_1d_pct"]=(c/series[i-1]["close"]-D(1))*D(100)
   else:feat["close_change_1d_pct"]=None
   # Strict windows: require each prior session in all 20 official trade dates, no missing price.
   for n in (5,10,20):
    if i+1>=n and expected_idx[dates[i]]-expected_idx[dates[i-n+1]]==n-1 and all(series[j]["close"] is not None for j in range(i-n+1,i+1)):
     closes=[series[j]["close"] for j in range(i-n+1,i+1)]
     feat[f"SMA_{n}"]=sum(closes,D(0))/D(n)
     feat[f"close_vs_SMA_{n}_pct"]=(c/feat[f"SMA_{n}"]-D(1))*D(100) if feat[f"SMA_{n}"]>0 else None
     vs=[series[j]["volume_shares"] for j in range(i-n+1,i+1)]
     feat[f"avg_volume_shares_{n}"]=sum(vs)/n if all(x is not None for x in vs) else None
     limits[f"good_SMA_{n}"]+=1
    else:
     feat[f"SMA_{n}"]=None;feat[f"close_vs_SMA_{n}_pct"]=None;feat[f"avg_volume_shares_{n}"]=None
   out.append(feat)
 # With only Sep source, 60/120/240 and indicators requiring 200ma are NEVER computed.
 return out,dict(limits)
def snapshot_revenue(rows,input_sha):
 out=[];issues=collections.Counter();seen=set()
 for r in rows:
  if r["revenue_month"]!="2026-09":raise ValueError("WRONG_REVENUE_MONTH")
  key=(r["market"],r["stock_id"])
  if key in seen:raise ValueError("DUPLICATE_REVENUE_KEY")
  seen.add(key)
  current=r.get("current_month");prior=r.get("previous_month");yearago=r.get("year_ago_month")
  if current is None:issues["missing_current"]+=1;continue
  out.append({
   "revenue_month":"2026-09","stock_id":r["stock_id"],"market":r["market"],"name":r["name"],
   "revenue_億元":r["revenue_億元"],
   "revenue_prior_month_億元":r.get("prior_month_億元"),
   "revenue_year_ago_month_億元":r.get("year_ago_month_億元"),
   "revenue_mom_pct":(current/prior-D(1))*D(100) if prior is not None and prior>0 else None,
   "revenue_yoy_pct":(current/yearago-D(1))*D(100) if yearago is not None and yearago>0 else None,
   "revenue_yoy_pct_reported":r.get("yoy_pct_reported"),
   "revenue_mom_pct_reported":r.get("mom_pct_reported"),
   "input_silver_sha256":input_sha,"source_native_sha256":r["native_sha256"],
   "asof_available_date":datetime.date.fromisoformat(RELEASE),
   "historical_PIT_verified":False,
   "security_type_verified":False,
   "output_usage":"DESCRIPTIVE_ONLY_NO_BACKTEST"
  })
 return out,dict(issues)
def main():
 a=argparse.ArgumentParser();a.add_argument("--lane",choices=SOURCE_IDS,required=True);lane=a.parse_args().lane
 s=svc();original=read(s,SOURCE_IDS[lane]);hashval=sha(original)
 t=pq.read_table(io.BytesIO(original));rows=t.to_pylist()
 if lane=="tse":
  assert t.num_rows==21860,"UNEXPECTED_TSE_SILVER_ROWS"
  valid=sum(all(r[k] is not None for k in ("open","high","low","close")) for r in rows)
 else:
  assert t.num_rows==1980,"UNEXPECTED_REVENUE_ROWS"
  valid=sum(r.get("revenue_億元") is not None for r in rows)
 rate=valid/t.num_rows
 if rate<0.98:raise ValueError("INPUT_NUMERIC_AVAILABILITY_BELOW_98")
 features,issues=(snapshot_tse(rows,hashval) if lane=="tse" else snapshot_revenue(rows,hashval))
 if not features:raise ValueError("NO_VALID_GOLD_ROWS")
 tbl=pa.Table.from_pylist(features)
 buf=io.BytesIO();pq.write_table(tbl,buf,compression="zstd")
 blob=buf.getvalue()
 if pq.read_metadata(io.BytesIO(blob)).num_rows!=len(features):raise ValueError("GOLD_ROW_READBACK")
 dest=folder(s,GOLD_PARENT[lane],"2026-09_DESCRIPTIVE_ONLY_ASOF_2026-11-06_"+lane)
 fid=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_DESCRIPTIVE_R1.parquet",blob)
 metrics={"schema":"JARVIS_v095_202609_SCOPED_GOLD_DESCRIPTIVE_R1",
  "lane":lane,"source_Silver_file_id":SOURCE_IDS[lane],"Silver_sha256":hashval,
  "observed_Silver_rows":t.num_rows,"input_valid_numeric_rows":valid,
  "numeric_valid_rate":rate,"feature_rows":len(features),"feature_sha256":sha(blob),
  "gold_parquet_drive_id":fid,"gold_folder_id":dest,
  "status":"DESCRIPTIVE_GOLD_DATASET_PUBLISHED",
  "historical_backtest_allowed":False,"pit_verified":False,
  "market_universe_certified":False,
  "all_September_Gold_complete":False,"as_of":RELEASE,
  "blocked_features":(["SMA_60","SMA_120","SMA_240","RS_60","RS_120","RS_240","rolling breakout_50","rolling breakout_120","cross market RS and stage transitions"] if lane=="tse" else
  ["24 month revenue peak","revenue acceleration over prior 4 months","TTM quarterly earnings or EPS"]),
  "business_limitations":["PIT unverified: not known as-of September trading dates","4-digit instrument code does not prove stock security master classification","numeric availability not equivalent to source-wide correctness"],
  "issues":issues}
 report=json.dumps(metrics,ensure_ascii=False,indent=2).encode()
 metrics["QA_report_file_id"]=save(s,dest,"JARVIS_v095_202609_GOLD_"+lane+"_QA_R1.json",report)
 root=pathlib.Path("v095_202609_gold_descriptive");root.mkdir(exist_ok=True)
 (root/(lane+".json")).write_bytes(report)
 print(json.dumps(metrics,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
