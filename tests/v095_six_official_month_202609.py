"""v0.95 six-official September 2026 monthly probe, distinct from certification.

Date window: 2026-09-01 through 2026-09-30. Never uses FinMind.
Only TWSE/TPEx listed daily queries offer date-scoped requests here.
The other four are endpoint-specific recent snapshots, NOT 7-day coverage.
This is a bounded actual-source canary, not full datasets, production Bronze,
Silver or Gold approval.
"""
import argparse,datetime,hashlib,json,os,pathlib,time,urllib.error,urllib.request
import pyarrow as pa
import pyarrow.parquet as pq

DAYS=[(datetime.date(2026,9,1)+datetime.timedelta(days=i)).isoformat() for i in range(30)]
ROOT=pathlib.Path("monthly_202609_official_canary")
# Confirmed fixed-window TWSE market exceptions; not a general-purpose calendar.
EXCHANGE_CLOSURES={
 "2026-09-25":("MID_AUTUMN_FESTIVAL","https://www.twse.com.tw/zh/trading/holiday.html"),
 "2026-09-28":("TEACHERS_DAY","https://www.tpex.org.tw/storage/eb_data/11509/11503027221.html")
}
for _day in DAYS:
  _dt=datetime.date.fromisoformat(_day)
  if _dt.weekday() >= 5:
    EXCHANGE_CLOSURES[_day]=("WEEKEND_SATURDAY" if _dt.weekday()==5 else "WEEKEND_SUNDAY",
                            "https://www.twse.com.tw/zh/trading/holiday.html")

ROUTES={
  "TWSE":("https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={compact}&response=json",True),
  "TPEx":("https://www.tpex.org.tw/www/zh-tw/margin/sbl?date={slash}&response=json",True),
  "MOPS":("https://openapi.twse.com.tw/v1/opendata/t187ap05_L",False),
  "TDCC":("https://openapi.tdcc.com.tw/v1/opendata/1-5",False),
  "TAIFEX":("https://openapi.taifex.com.tw/v1/PutCallRatio",False),
  "NDC":("https://ws.ndc.gov.tw/Download.ashx?u=LzAwMS9hZG1pbmlzdHJhdG9yLzEwL3JlbGZpbGUvNjIxNy80MDQ5NS85OTVhZTM4YS1mNzRkLTRjODAtODI2My0wYmI5ZTliZjMwNmIueGxzeA%3d%3d&n=MTE1MDjmlrDogZ7nqL%2fpmYTku7bmlbjliJcueGxzeA%3d%3d&icon=.xlsx",False)
}
MAX_BYTES={"TWSE":6*1024*1024,"TPEx":6*1024*1024,"MOPS":12*1024*1024,"TDCC":96*1024*1024,"TAIFEX":12*1024*1024,"NDC":8*1024*1024}
def sha(b):return hashlib.sha256(b).hexdigest()
def get(url,limit):
  req=urllib.request.Request(url,headers={"User-Agent":"JARVIS-v095-weekly-isolated-canary/1.0","Accept":"application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"})
  with urllib.request.urlopen(req,timeout=45) as r:
    data=r.read(limit+1)
    if len(data)>limit:raise ValueError("EXCEEDED_BOUNDED_BYTES")
    return data,int(r.status)
def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--sources",required=True)
  args=ap.parse_args()
  sources=args.sources.split(",")
  if len(set(sources))!=len(sources) or not set(sources)<=set(ROUTES):raise ValueError("SOURCE_SCOPE")
  results=[]
  for source in sources:
    route,daily=ROUTES[source]
    out=ROOT/source;out.mkdir(parents=True,exist_ok=True)
    for day in DAYS if daily else ["SNAPSHOT_NO_HISTORICAL_DATE"]:
      url=route.format(compact=day.replace("-",""),slash=day.replace("-","%2F")) if daily else route
      item={"source":source,"requested_date":day,"sample_dataset_only":True,
        "all_week_datasets_verified":False,"bronze_readback":False,
        "silver_readback":False,"gold_qa_only":False,"pit_verified":False,
        "production_release_approved":False,"status":"BLOCKED"}
      if daily and day in EXCHANGE_CLOSURES:
        reason,evidence=EXCHANGE_CLOSURES[day]
        item.update(status="SKIPPED_VERIFIED_MARKET_CLOSED",market_closed_reason=reason,
                    calendar_evidence_url=evidence,attempts=0,expected_trading_rows=False)
        results.append(item)
        print("OFFICIAL_WEEK_CANARY",source,day,item["status"],reason,flush=True)
        continue
      raw=None
      for attempt in range(1,3):
        item["attempts"]=attempt
        try:
          raw,status=get(url,MAX_BYTES[source]);item["http"]=status
          break
        except Exception as exc:
          item["error"]=type(exc).__name__+":"+str(exc)[:180]
          if attempt==1:time.sleep(3)
      if raw is not None:
        try:
          if source=="NDC":
            if not raw.startswith(bytes([80,75,3,4])):raise ValueError("NDC_NOT_XLSX")
            import io,zipfile
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
              if z.testzip() is not None:raise ValueError("BAD_XLSX_CRC")
            rows=[{"source":source,"request_scope":day,"native_sha256":sha(raw),"native_bytes":len(raw),"record_index":0,"record_json":"{\"format\":\"xlsx\",\"extraction\":\"not_yet_typed\"}"}]
          else:
            obj=json.loads(raw.decode("utf-8-sig"))
            if source in ("TWSE","TPEx") and isinstance(obj,dict):
              tables=obj.get("tables",[])
              records=[x for t in tables if isinstance(t,dict) for x in t.get("data",[]) if isinstance(x,(list,dict))]
            elif isinstance(obj,list):
              records=obj
            elif isinstance(obj,dict) and isinstance(obj.get("data"),list):
              records=obj["data"]
            else:raise ValueError("UNEXPECTED_DATA_STRUCTURE")
            if not records:raise ValueError("EMPTY_NOT_PROOF_OF_MISSING")
            rows=[{"source":source,"request_scope":day,"native_sha256":sha(raw),"native_bytes":len(raw),"record_index":i,"record_json":json.dumps(x,ensure_ascii=False,sort_keys=True)} for i,x in enumerate(records)]
          tag=day.replace("-","") if daily else "snapshot"
          bronze=out/(tag+".bronze")
          bronze.write_bytes(raw)
          if bronze.read_bytes()!=raw:raise ValueError("BRONZE_MISMATCH")
          item["bronze_readback"]=True
          silver=out/(tag+".parquet")
          pq.write_table(pa.Table.from_pylist(rows),silver,compression="zstd")
          back=pq.read_table(silver).to_pylist()
          if back!=rows:raise ValueError("SILVER_READBACK_MISMATCH")
          item["silver_readback"]=True
          metrics={"metric":"structural_row_count_QA_ONLY","value":len(rows),"source":source,
             "scope":day,"original_sha256":sha(raw),"silver_sha256":sha(silver.read_bytes()),
             "investment_signal":False,"historical_pit_approved":False}
          gold=out/(tag+".gold_QA_ONLY.json")
          gold.write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
          if json.loads(gold.read_text())!=metrics:raise ValueError("QA_GOLD_READBACK_MISMATCH")
          item.update({"status":"PASS_STRUCTURAL_CANDIDATE_ONLY","native_bytes":len(raw),
            "silver_rows":len(rows),"sha256":sha(raw),"gold_qa_only":True})
        except Exception as exc:
          item["error"]=type(exc).__name__+":"+str(exc)[:180]
      results.append(item)
      print("OFFICIAL_WEEK_CANARY",source,day,item["status"],item.get("error",""),flush=True)
      time.sleep(2)
  report={"schema":"JARVIS_V095_SIX_OFFICIAL_MONTH_202609_CANARY",
    "window":"2026-09-01/2026-09-30","requested_sources":sources,
    "FinMind_requested":False,"production_drive_writes":False,"release_approved":False,
    "formal_complete_month_certified":False,"results":results,
    "pass_candidates":sum(x["status"].startswith("PASS") for x in results),
    "expected_tse_otc_trading_days":20,
    "full_dataset_inventory_built":False,
    "monthly_historical_coverage_verified":False,
    "drive_write_verified":False,
    "gold_investment_approved":False,
    "verified_market_closed_skips":sum(x["status"]=="SKIPPED_VERIFIED_MARKET_CLOSED" for x in results),
    "date_scope_policy":"exchange closures apply only to equity daily endpoints; source snapshots have independent calendars",
    "contract_gaps":{source:(["only_one_daily_dataset","all_other_dataset_routes_unverified","official_historical_universe_unverified"] if source in ("TWSE","TPEx") else ["current_snapshot_not_2026_09_historical_month","all_other_dataset_routes_unverified","PIT_unverified"]) for source in sources}}
  (ROOT/("report_"+ "_".join(sources)+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2))
  # Deliberately fail on attempted-but-blocked routes, not on absence of
  # full-week certification (which remains a separate formal gate).
  if any(x["status"] not in ("PASS_STRUCTURAL_CANDIDATE_ONLY","SKIPPED_VERIFIED_MARKET_CLOSED") for x in results):
    raise SystemExit(1)
if __name__=="__main__":main()
