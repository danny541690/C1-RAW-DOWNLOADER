"""Independent FinMind Free single-stock daily OHLC check against 2026-09 official Bronze.
Two diagnostic stocks only; this never certifies the full market or overrides raw files.
"""
import argparse,datetime,hashlib,io,json,os,pathlib,urllib.parse,urllib.request,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
MAIN={"2330":("TWSE","16G68HaFVX1Ddmu23xWeexhNDn0DWryet","prices_indices","每日收盤行情",
"證券代號",["開盤價","最高價","最低價","收盤價"]),
"6488":("TPEx","1xz7SdR0itvatFQ_IaAdpsAw9fN6i-0iu","prices","上櫃股票行情",
"代號",["開盤","最高","最低","收盤"])}
EXTRA=["12lSt3OY0WclDoCc6TAk3peruEW2-K9_r","1kXahDil5I6Mda5SN0XE-LG0bN8LZBm0y"]
def hashbytes(b):return hashlib.sha256(b).hexdigest()
def drive():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
  client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def raw(s,id):return s.files().get_media(fileId=id).execute()
def parse(obj,code,caption,codecolumn,columns):
 tables=[x for x in obj.get("tables",[]) if caption in str(x.get("title",""))]
 if len(tables)!=1:raise ValueError("OFFICIAL_REQUIRED_TABLE_NOT_FOUND")
 t=tables[0];index={x:i for i,x in enumerate(t["fields"])}
 for row in t["data"]:
  if str(row[index[codecolumn]]).strip()==code:
   return [float(str(row[index[k]]).replace(",","")) for k in columns]
 return None
def official(s,code):
 src,fid,kind,caption,codecolumn,columns=MAIN[code]
 b=raw(s,fid);z=zipfile.ZipFile(io.BytesIO(b));manifest=json.loads(z.read("manifest.json"))
 found={}
 for u in manifest["units"]:
  if not u["name"].startswith(kind+"_202609") or not u.get("date") or not u.get("file"):continue
  key=u["file"].split("/")[-1]
  payload=z.read(key)
  if hashbytes(payload)!=u.get("sha256"):raise ValueError("OFFICIAL_RAW_SHA_MISMATCH")
  obj=json.loads(payload.decode("utf-8-sig"))
  prices=parse(obj,code,caption,codecolumn,columns)
  if prices is not None:found[u["date"]]=prices
 if code=="6488":
  for fid in EXTRA:
   z=zipfile.ZipFile(io.BytesIO(raw(s,fid)))
   for name in z.namelist():
    if not name.endswith(".raw") or "prices_2026-09-" not in name:continue
    day=name.split("prices_")[-1].removesuffix(".raw")
    prices=parse(json.loads(z.read(name)),code,caption,codecolumn,columns)
    if prices is not None:found[day]=prices
 return found
def finmind(code):
 u="https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode(
 {"dataset":"TaiwanStockPrice","data_id":code,"start_date":"2026-09-01","end_date":"2026-09-30"})
 req=urllib.request.Request(u,headers={"Accept":"application/json","User-Agent":"JARVIS-v095-data-provenance-check"})
 with urllib.request.urlopen(req,timeout=45) as response:
  b=response.read(4_000_001)
  if len(b)>4_000_000:raise ValueError("FINMIND_RESPONSE_TOO_LARGE")
 obj=json.loads(b.decode("utf-8-sig"))
 if obj.get("status")!=200 or not isinstance(obj.get("data"),list):raise ValueError("FINMIND_FREE_STATUS_OR_SCHEMA")
 values={}
 for e in obj["data"]:
  if e.get("stock_id")==code and str(e.get("date","")).startswith("2026-09"):
   values[str(e["date"])[:10]]=[float(e[x]) for x in ("open","max","min","close")]
 return values,hashbytes(b)
def main():
 a=argparse.ArgumentParser();a.add_argument("--code",choices=MAIN.keys(),required=True);code=a.parse_args().code
 out=pathlib.Path("v095_202609_ohlc_crosscheck");out.mkdir(exist_ok=True)
 report={"schema":"JARVIS_202609_OFFICIAL_FINMIND_OHLC_SAMPLE","symbol":code,"period":"2026-09",
  "source":MAIN[code][0],"finmind_free_dataset":"TaiwanStockPrice","scope":"one_stock_20_days_only",
  "raw_official_overwrite":False,"market_universe_validated":False,"status":"FAILED"}
 try:
  first=official(drive(),code);other,sha=finmind(code)
  common=sorted(set(first)&set(other));different=[]
  for date in common:
   x,y=first[date],other[date]
   if any(abs(a-b)>0.011 for a,b in zip(x,y)):different.append({"date":date,"official":x,"finmind":y})
  report.update(official_dates=len(first),finmind_dates=len(other),matched_dates=len(common),
    missing_finmind_dates=sorted(set(first)-set(other)),missing_official_dates=sorted(set(other)-set(first)),
    price_difference_count=len(different),price_difference_examples=different[:12],finmind_source_sha256=sha)
  report["status"]="OHLC_SAMPLE_MATCH" if len(common)==20 and not different else "SOURCE_DIFFERENCES_REQUIRE_REVIEW"
 except Exception as e:
  report["error"]=type(e).__name__+":"+str(e)[:200]
 (out/(code+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report["status"]=="FAILED":raise SystemExit(1)
if __name__=="__main__":main()
