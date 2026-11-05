import datetime as dt,hashlib,json,pathlib,urllib.parse,urllib.request
month="2026-09"
days=sorted((dt.date(2026,9,1)+dt.timedelta(days=d)).isoformat() for d in range(30) if (dt.date(2026,9,1)+dt.timedelta(days=d)).weekday()<5 and d+1 not in (25,28))
assert len(days)==20
url="https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode({"dataset":"TaiwanStockTradingDate"})
report={"schema":"JARVIS_202609_FINMIND_FREE_TRADING_CALENDAR_CHECK","period":month,
"official_twse_2026_holidays":["2026-09-25","2026-09-28"],"official_expected_trading_dates":days,
"finmind_requests":0,"finmind_used_as_official_replacement":False,"complete_seven_source_universe_approved":False,"status":"BLOCKED"}
try:
 req=urllib.request.Request(url,headers={"User-Agent":"JARVIS-v095-monthly-quality-audit","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=35) as response:
  data=response.read(8000001)
  if len(data)>8000000:raise ValueError("FREE_API_RESPONSE_TOO_LARGE")
 report["finmind_requests"]=1
 obj=json.loads(data.decode("utf-8-sig"))
 if obj.get("status")!=200 or not isinstance(obj.get("data"),list):raise ValueError("FINMIND_FREE_SCHEMA_OR_STATUS")
 present=sorted(set(str(z.get("date",""))[:10] for z in obj["data"] if str(z.get("date","")).startswith(month)))
 report.update(finmind_dates=present,missing=sorted(set(days)-set(present)),extra=sorted(set(present)-set(days)),source_sha256=hashlib.sha256(data).hexdigest())
 if present!=days:raise ValueError("FREE_SOURCE_CALENDAR_DIFFERS_FROM_TWSE_OFFICIAL")
 report["status"]="FINMIND_FREE_CALENDAR_20_OF_20_MATCH_ONLY"
except Exception as e:
 report["error"]=type(e).__name__+":"+str(e)[:180]
out=pathlib.Path("v095_202609_seven_source_crosscheck");out.mkdir(exist_ok=True)
(out/"finmind_calendar.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
if report["status"]=="BLOCKED":raise SystemExit(1)
