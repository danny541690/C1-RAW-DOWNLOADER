#!/usr/bin/env python3
"""Live independent THREE-WAY value witness, currently enabled for TPEx & TWSE daily close.
Actual Bronze bytes -> dated official public historical quote -> FinMind unadjusted price.
Samples only; reports cannot certify all rows or automatically release Silver.
Rate-limited, bounded and independently hashed on download.
"""
import hashlib,json,os,re,sys,time
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from urllib.parse import urlencode
import requests
from scripts.v097_bronze_autopilot import source_api,digest,SOURCES
from scripts.v097_seven_native_v2_probe import detected_name

MAX_ATTEMPTS=2
MAX_SAMPLES=min(8,max(1,int(os.getenv("WITNESS_SAMPLES","2"))))
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
def original_quotes(raw):
 try:o=json.loads(raw.decode("utf-8-sig"))
 except (ValueError,UnicodeError):return []
 if not isinstance(o,dict):return []
 date=day(o.get("date",""))
 quotes=[]
 for t in o.get("tables",[]) if isinstance(o.get("tables"),list) else [o]:
  if not isinstance(t,dict):continue
  fields=[str(x).strip().replace(" ","") for x in t.get("fields",[])]
  rows=t.get("data",[])
  code=next((i for i,s in enumerate(fields) if s in ("代號","證券代號","股票代號")),None)
  close=next((i for i,s in enumerate(fields) if s in ("收盤價","收盤")),None)
  if code is None or close is None:continue
  for row in rows[:100]:
   if not isinstance(row,list) or max(code,close)>=len(row):continue
   stock=str(row[code]).strip()
   value=num(row[close])
   if re.fullmatch(r"[0-9]{4}",stock) and value is not None and value>0 and date:
    quotes.append({"date":date,"stock":stock,"close":str(value)})
 return quotes
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
  o,p=request_json("https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php",
        {"l":"zh-tw","d":str(int(y)-1911)+"/"+m,"stkno":stock})
  rows=o.get("aaData",[])
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
 results=[];attempts=0
 for sid,v in done.items():
  if len(results)>=MAX_SAMPLES or attempts>=MAX_SAMPLES*12:break
  path=str(v.get("original_path",""))
  if not path.lower().endswith((".raw",".json")):continue
  if not str(v.get("status","")).startswith("CONTENT_PARSED"):continue
  row=rows.get(sid)
  if not row:continue
  attempts+=1
  try:
   raw=call(lambda:api.files().get_media(fileId=row["dest_id"]))
   if digest(raw)!=row["sha"]:raise RuntimeError("BRONZE_SOURCE_SHA_CHANGED")
   quotes=original_quotes(raw)
   if not quotes:
    results.append({"source_id":sid,"status":"HOLD_NO_SINGLE_DAY_EQUITY_QUOTES_IDENTIFIED"})
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
 x=json.dumps({"date":"2026-11-16","tables":[{"fields":["證券代號","收盤價"],"data":[["2330","1,000"],["00956","9"]]}]},ensure_ascii=False).encode()
 assert original_quotes(x)==[{"date":"2026-11-16","stock":"2330","close":"1000"}]
 assert num("--") is None and num("0.00")==0
 print("THREEWAY_INDEPENDENT_CLOSE_WITNESS_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | TWSE | TPEx")
