#!/usr/bin/env python3
"""Live independent THREE-WAY value witness, currently enabled for TPEx & TWSE daily close.
Actual Bronze bytes -> dated official public historical quote -> FinMind unadjusted price.
Samples only; reports cannot certify all rows or automatically release Silver.
Rate-limited, bounded and independently hashed on download.
"""
import hashlib,json,os,re,sys,time,zipfile,io
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from urllib.parse import urlencode
import requests
from scripts.v097_bronze_autopilot import source_api,digest,SOURCES
from scripts.v097_seven_native_v2_probe import detected_name

MAX_ATTEMPTS=2
MAX_SAMPLES=min(12,max(1,int(os.getenv("WITNESS_SAMPLES","4"))))
MAX_ROW_ATTEMPTS=3
UA="JARVIS-0.97-EvidenceVerifier/1.0"
def num(x):
 try:
  d=Decimal(str(x).replace(",","").strip())
  return d if d.is_finite() else None
 except (InvalidOperation,ValueError):return None
def day(x):
 x=str(x).strip()
 m=re.fullmatch(r"(\d{2,4})[/.-](\d{1,2})[/.-](\d{1,2})",x)
 if not m:return None
 y=int(m[1]);y+=1911 if y<1911 else 0
 if y<2000:return None
 return f"{y:04d}-{int(m[2]):02d}-{int(m[3]):02d}"
def original_quotes(raw, fallback_date=None):
 try:o=json.loads(raw.decode("utf-8-sig"))
 except (ValueError,UnicodeError):return []
 if not isinstance(o,dict):return []
 date=day(o.get("date","")) or day(o.get("Date","")) or fallback_date
 quotes=[]
 for t in o.get("tables",[]) if isinstance(o.get("tables"),list) else [o]:
  if not isinstance(t,dict):continue
  fields=[str(x).strip().replace(" ","") for x in t.get("fields",[])]
  tdate=day(t.get("date","")) or date
  rows=t.get("data",[])
  code=next((i for i,s in enumerate(fields) if s in ("代號","證券代號","股票代號","股票代碼","有價證券代號")),None)
  close=next((i for i,s in enumerate(fields) if s in ("收盤價","收盤","收市價")),None)
  if code is None or close is None:continue
  for row in rows[:10000]:
   if not isinstance(row,list) or max(code,close)>=len(row):continue
   stock=str(row[code]).strip()
   value=num(row[close])
   if re.fullmatch(r"[0-9]{4}",stock) and value is not None and value>0 and tdate:
    quotes.append({"date":tdate,"stock":stock,"close":str(value)})
 return quotes
def archive_quotes(blob):
 if len(blob)>50*1024*1024 or not zipfile.is_zipfile(io.BytesIO(blob)):return []
 quotes=[]
 with zipfile.ZipFile(io.BytesIO(blob)) as z:
  infos=z.infolist()
  if len(infos)>400:return []
  manifest={}
  for member in infos:
   if member.filename.rsplit("/",1)[-1].lower()=="manifest.json" and member.file_size<3*1024*1024:
    try:manifest=json.loads(z.read(member))
    except (UnicodeError,ValueError):pass
  dated={}
  if isinstance(manifest,dict):
   for u in manifest.get("units",[])[:1000]:
    if isinstance(u,dict) and isinstance(u.get("file"),str):
     dated[u["file"]]=day(u.get("date","")) or day(u.get("period",""))
  total=0
  for m in infos:
   if m.is_dir() or m.file_size>15*1024*1024:continue
   total+=m.file_size
   if total>70*1024*1024:break
   if m.filename.rsplit("/",1)[-1].lower()=="manifest.json":continue
   if not m.filename.lower().endswith((".json",".raw")):continue
   quotes.extend(original_quotes(z.read(m),dated.get(m.filename)))
   if quotes:break
 return quotes

def diagnose_shape(blob):
 try:
  if zipfile.is_zipfile(io.BytesIO(blob)):
   with zipfile.ZipFile(io.BytesIO(blob)) as z:
    return {"kind":"ZIP","members":len(z.infolist()),
      "sample_names":[x.filename[-65:] for x in z.infolist()[:6]]}
  o=json.loads(blob.decode("utf-8-sig"))
  if isinstance(o,dict):
   return {"kind":"JSON","top_keys":[str(k)[:60] for k in list(o.keys())[:12]],
      "table_fields":[[str(q)[:45] for q in t.get("fields",[])[:12]]
        for t in o.get("tables",[])[:3] if isinstance(t,dict)]}
  return {"kind":type(o).__name__}
 except Exception as e:return {"kind":"NOT_DECODED","error":type(e).__name__}
def request_json(url,params):
 for t in range(MAX_ATTEMPTS):
  try:
   response=requests.get(url,params=params,headers={"User-Agent":UA,"Accept":"application/json"},timeout=25)
   response.raise_for_status()
   if len(response.content)>5*1024*1024:raise ValueError("REMOTE_SIZE_LIMIT")
   return response.json(),{"url":response.url,"response_sha256":hashlib.sha256(response.content).hexdigest(),
      "retrieved_at":datetime.now(timezone.utc).isoformat(),"http_status":response.status_code}
  except (requests.RequestException,ValueError) as e:
   if t==MAX_ATTEMPTS-1:raise RuntimeError("REMOTE_"+type(e).__name__) from e
   time.sleep(1+t)
def official_close(source,stock,when):
 y,m,_=when.split("-")
 if source=="TWSE":
  o,p=request_json("https://www.twse.com.tw/exchangeReport/STOCK_DAY",
        {"response":"json","date":y+m+"01","stockNo":stock})
  if o.get("stat")!="OK":raise RuntimeError("OFFICIAL_RESPONSE_NOT_OK")
  rows=o.get("data",[])
 elif source=="TPEx":
  # Current official history endpoint (Gregorian month), not today's
  # OpenAPI snapshot. Legacy st43 often serves HTML rather than JSON.
  o,p=request_json("https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock",
        {"code":stock,"date":y+"/"+m+"/01","id":"","response":"json"})
  tables=o.get("tables",[])
  if not isinstance(tables,list) or not tables:raise RuntimeError("TPEX_HISTORY_TABLE_MISSING")
  rows=tables[0].get("data",[])
  if not isinstance(rows,list):raise RuntimeError("TPEX_HISTORY_DATA_MISSING")
 else:raise ValueError("ONLY_TWSE_TPEX")
 for row in rows:
  if isinstance(row,list) and len(row)>=7 and day(row[0])==when:
   value=num(row[6])
   if value is not None:return value,p
 raise RuntimeError("NO_OFFICIAL_MATCHING_TRADING_ROW")
def finmind_close(stock,when):
 token=os.getenv("FINMIND_TOKEN","")
 args={"dataset":"TaiwanStockPrice","data_id":stock,"start_date":when,"end_date":when}
 if token:args["token"]=token
 o,p=request_json("https://api.finmindtrade.com/api/v4/data",args)
 rows=o.get("data",[])
 if not isinstance(rows,list):raise RuntimeError("FINMIND_RESPONSE_NOT_ROWS")
 for row in rows:
  if isinstance(row,dict) and str(row.get("date"))==when and str(row.get("stock_id"))==stock:
   n=num(row.get("close"))
   if n is not None:return n,p
 raise RuntimeError("NO_FINMIND_MATCHING_STOCK_ROW")
def run(source):
 if source not in ("TWSE","TPEx"):raise ValueError("ONLY_EQUITY_MARKETS")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inp=match(api,quality,"v097_AP_INPUT_"+source+".json")
 f=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+source+".json")
 if not inp or not f:raise RuntimeError("MISSING_FROZEN_INPUT_OR_CHECKPOINT")
 rows={r["source_id"]:r for r in load_json(api,inp["id"])["rows"]}
 done=load_json(api,f["id"])["done"]
 checkpoint_name=os.getenv("WITNESS_CK_PREFIX","v097_STANDALONE_PRICE_WITNESS_CK_")+source+".json"
 checkpoint_file=match(api,control,checkpoint_name)
 checkpoint=load_json(api,checkpoint_file["id"]) if checkpoint_file else {
  "schema":"v097_independent_price_witness_checkpoint_v1","source":source,"done":{}}
 if checkpoint.get("source")!=source:raise RuntimeError("PRICE_WITNESS_CHECKPOINT_SOURCE_CONFLICT")
 seen=checkpoint["done"]
 results=[];attempts=0
 for sid,v in done.items():
  if len(results)>=MAX_SAMPLES or attempts>=MAX_SAMPLES*24:break
  previous=seen.get(sid)
  if previous:
   state=str(previous.get("status",""))
   if not state.startswith("RECHECK_THREE_WAY_") or previous.get("attempts",0)>=MAX_ROW_ATTEMPTS:
    continue
  path=str(v.get("original_path",""))
  if not path.lower().endswith((".raw",".json",".zip")):continue
  if str(v.get("status","")).startswith(("HOLD_SOURCE","HOLD_ORIGINAL")):continue
  row=rows.get(sid)
  if not row:continue
  attempts+=1
  try:
   raw=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   if digest(raw)!=row["sha"]:raise RuntimeError("BRONZE_SOURCE_SHA_CHANGED")
   quotes=archive_quotes(raw) if zipfile.is_zipfile(io.BytesIO(raw)) else original_quotes(raw)
   if not quotes:
    results.append({"source_id":sid,"status":"HOLD_NO_SINGLE_DAY_EQUITY_QUOTES_IDENTIFIED",
      "source_shape":diagnose_shape(raw)})
    continue
   q=quotes[0]
   official,op=official_close(source,q["stock"],q["date"])
   third,tp=finmind_close(q["stock"],q["date"])
   original=num(q["close"])
   equal=original==official==third
   results.append({"source_id":sid,"status":"THREE_WAY_DAILY_CLOSE_MATCHED_SAMPLE" if equal else "HOLD_THREE_WAY_CLOSE_DIFFERENCE",
    "stock_id":q["stock"],"trade_date":q["date"],"original_close":str(original),
    "official_close":str(official),"finmind_unadjusted_close":str(third),
    "original_sha256":row["sha"],"official_fetch":op,"finmind_fetch":tp,
    "same_unit":"NTD_PER_SHARE","all_rows_verified":False,"silver_ready_promoted":False})
  except Exception as e:
   results.append({"source_id":sid,"status":"RECHECK_THREE_WAY_"+type(e).__name__,
      "error_category":str(e)[:90],"silver_ready_promoted":False})
  time.sleep(0.7)
 if results:
  for item in results:
   sid=item["source_id"]
   seen[sid]={"status":item["status"],
    "attempts":seen.get(sid,{}).get("attempts",0)+1,
    "last_run":os.getenv("GITHUB_RUN_ID","manual"),
    "stock_id":item.get("stock_id"),"trade_date":item.get("trade_date"),
    "official_response_sha256":item.get("official_fetch",{}).get("response_sha256"),
    "third_party_response_sha256":item.get("finmind_fetch",{}).get("response_sha256")}
  checkpoint["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
  if os.getenv("GITHUB_RUN_ID"):upsert(api,control,checkpoint_name,checkpoint)
 report={"schema":"v097_independent_three_way_close_witness_v1",
   "source":source,"run":os.getenv("GITHUB_RUN_ID","manual"),
   "records":results,"full_file_verified":False,
   "silver_gold_executed":False,"new_silver_ready":0}
 if os.getenv("GITHUB_RUN_ID"):
  put_once(api,quality,"v097_INDEPENDENT_CLOSE_WITNESS_"+source+"_"+report["run"]+".json",report)
 print("THREEWAY_LIVE_CLOSE_WITNESS="+json.dumps({"source":source,"sampled":len(results),
   "counts":dict(Counter(x["status"] for x in results)),"promoted":0},ensure_ascii=False))
def selftest():
 assert day("115/11/16")=="2026-11-16"
 assert day("2026-11-16")=="2026-11-16"
 assert day("115/08/19")=="2026-08-19"
 x=json.dumps({"date":"2026-11-16","tables":[{"fields":["證券代號","收盤價"],"data":[["2330","1,000"],["00956","9"]]}]},ensure_ascii=False).encode()
 assert original_quotes(x)==[{"date":"2026-11-16","stock":"2330","close":"1000"}]
 assert original_quotes(x, "2026-11-16")[0]["stock"]=="2330"
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:
  z.writestr("quote.raw",x)
  z.writestr("manifest.json",json.dumps({"units":[{"file":"quote.raw","date":"2026-11-16"}]}))
 assert archive_quotes(b.getvalue())[0]["close"]=="1000"
 assert MAX_ROW_ATTEMPTS==3
 assert num("--") is None and num("0.00")==0
 print("THREEWAY_INDEPENDENT_CLOSE_WITNESS_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | TWSE | TPEx")
