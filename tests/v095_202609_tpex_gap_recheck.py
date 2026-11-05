"""Bounded actual official TPEx September gap re-fetch (no FinMind, no Drive writes).

Only retry known missing primary JSON routes identified in legacy 2026-09 manifest.
Never certify full source or substitute current snapshot for a requested date.
"""
import argparse,datetime,hashlib,json,pathlib,time,urllib.parse,urllib.request,urllib.error,http.client
DATES={"prices":["2026-09-04","2026-09-08","2026-09-10","2026-09-22","2026-09-29"],
       "institutional":["2026-09-07","2026-09-08","2026-09-29","2026-09-30"]}
BASE={"prices":"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes",
      "institutional":"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"}
def fetch(category,day):
  params={"date":day.replace("-","/"),"response":"json"}
  if category=="institutional":params.update(type="Daily",sect="AL")
  url=BASE[category]+"?"+urllib.parse.urlencode(params)
  req=urllib.request.Request(url,headers={"Accept":"application/json","Accept-Encoding":"identity","User-Agent":"Mozilla/5.0 JARVIS-v095-official-gap-pilot"})
  with urllib.request.urlopen(req,timeout=50) as response:
    payload=response.read(12*1024*1024+1)
    if len(payload)>12*1024*1024:raise ValueError("OFFICIAL_RESPONSE_TOO_LARGE")
    final=response.geturl()
    if urllib.parse.urlsplit(final).hostname!="www.tpex.org.tw":raise ValueError("OFFICIAL_REDIRECT_HOST")
  obj=json.loads(payload.decode("utf-8-sig"))
  if not isinstance(obj,dict) or not isinstance(obj.get("tables"),list):raise ValueError("UNEXPECTED_TPEX_TABLE_SCHEMA")
  if not any(isinstance(t,dict) and t.get("data") for t in obj["tables"]):raise ValueError("OFFICIAL_EMPTY_NOT_AUTOMATIC_MISSING")
  returned_date=str(obj.get("date") or obj.get("responseDate") or "").replace("/","").replace("-","")
  if returned_date and returned_date!=day.replace("-",""):raise ValueError("CONTENT_DATE_MISMATCH:"+returned_date)
  return payload,url,sum(len(t.get("data",[])) for t in obj["tables"] if isinstance(t,dict))
def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--category",choices=sorted(DATES),required=True)
  ap.add_argument("--only-dates",default="",help="Comma-separated existing failed dates only")
  args=ap.parse_args()
  requested=args.only_dates.split(",") if args.only_dates else DATES[args.category]
  if len(set(requested))!=len(requested) or any(x not in DATES[args.category] for x in requested):raise ValueError("RETRY_SCOPE_NOT_IN_ORIGINAL_MISSING_MANIFEST")
  root=pathlib.Path("v095_202609_tpex_gap_recheck")/args.category;root.mkdir(parents=True,exist_ok=True)
  results=[]
  for day in requested:
    row={"category":args.category,"date":day,"status":"BLOCKED","release_approved":False}
    for attempt in range(1,5):
      row["attempts"]=attempt
      try:
        payload,url,records=fetch(args.category,day)
        f=root/(args.category+"_"+day+".raw")
        f.write_bytes(payload)
        if hashlib.sha256(f.read_bytes()).digest()!=hashlib.sha256(payload).digest():raise ValueError("COLD_LOCAL_READBACK_MISMATCH")
        row.update(status="CANDIDATE_OFFICIAL_RECOVERED",sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),rows=records,source_url=url,validated_local_hash=True)
        row.pop("error",None)  # a prior transient transport error is history, not final failure
        break
      except Exception as e:
        row["error"]=type(e).__name__+":"+str(e)[:180]
        row.setdefault("attempt_errors",[]).append({"attempt":attempt,"error":row["error"]})
        if attempt<4:time.sleep(3*attempt)
    results.append(row)
    print("TPEx_OFFICIAL_GAP_RECHECK",day,row["status"],row.get("error",""),flush=True)
    time.sleep(3)
  report={"schema":"JARVIS_V095_202609_TPEX_OFFICIAL_GAP_RECHECK",
          "period":"2026-09","category":args.category,"finmind_used":False,
          "drive_written":False,"production_approved":False,
          "results":results,"retrieved_count":sum(x["status"]=="CANDIDATE_OFFICIAL_RECOVERED" for x in results)}
  (root/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
  if report["retrieved_count"]!=len(requested):raise SystemExit(1)
if __name__=="__main__":main()
