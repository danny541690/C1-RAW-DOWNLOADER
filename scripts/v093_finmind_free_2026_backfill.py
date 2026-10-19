"""2026 FinMind Free multi-run raw backfill. One annual per stock/dataset request, split by native date into month ZIPs.
No Premium query, no date future, no new annual folder. Batch-snapshot checkpoints.
Monthly month.zip entries are original API response row slices + provenance metadata, NOT full API response bytes.
"""
import argparse,calendar,datetime,hashlib,io,json,os,re,time,urllib.parse,urllib.request,urllib.error,zipfile,collections
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
DATASETS=("TaiwanStockPrice","TaiwanStockInstitutionalInvestorsBuySell",
 "TaiwanStockMarginPurchaseShortSale","TaiwanStockMonthRevenue",
 "TaiwanStockFinancialStatements","TaiwanStockBalanceSheet",
 "TaiwanStockCashFlowsStatement","TaiwanStockPER","TaiwanStockShareholding")
BATCH=270
def quota_budget(state, now, has_token):
 # Keep a rolling hour across runners; reserve headroom for other small queries.
 cap=540 if has_token else 270
 ledger=state.get("request_ledger")
 if ledger is None:
  # Legacy batches had no ledger. Conservatively reserve a full window after
  # their last commit so migration cannot burst past the anonymous allowance.
  updated=state.get("updated_utc")
  ledger=[{"at":datetime.datetime.fromisoformat(updated).timestamp(),"count":cap}] if updated else []
 recent=[x for x in ledger if now-float(x["at"])<3600]
 return max(0,cap-sum(int(x["count"]) for x in recent)),recent,cap
def ls(d,p):
 out=[];tok=None
 while True:
  x=d.call(lambda:d.api.files().list(q="'"+p+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=tok))
  out+=x.get("files",[]);tok=x.get("nextPageToken")
  if not tok:return out
def existing(d,p,name):
 return next((x for x in ls(d,p) if x["name"]==name),None)
def get_json(d,parent,name):
 x=existing(d,parent,name)
 if not x:return None
 return json.loads(d.call(lambda:d.api.files().get_media(fileId=x["id"])).decode("utf-8-sig"))
def stocklist(d,ctrl):
 names=get_json(d,ctrl,"TaiwanStockInfo_2026_stock_universe_provisional.json")
 if not isinstance(names,list) or not names:raise ValueError("NO_PROVISIONAL_UNIVERSE")
 # Exclude non-standard IDs or tickers; do not silently label excluded as fully covered.
 return sorted({str(s) for s in names if re.fullmatch(r"[1-9][0-9]{3}",str(s))})
def fetch(ds,stock,end):
 params={"dataset":ds,"data_id":stock,"start_date":"2026-01-01","end_date":end}
 token=os.environ.get("FINMIND_TOKEN","").strip() or os.environ.get("FINMIND_API_TOKEN","").strip()
 # Anonymous Free requests remain supported at 300/hr; token raises quota to 600/hr.
 # Official quickstart uses token parameter; do not log token or URL
 if token:params["token"]=token
 req=urllib.request.Request("https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode(params),
  headers={"User-Agent":"JARVIS-0.93-FinMind-Free-2026-Batch/1.0","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=55) as f:b=f.read(18000001)
 if len(b)>18000000:raise ValueError("API_RESPONSE_LIMIT")
 x=json.loads(b.decode("utf-8-sig"))
 if x.get("status")!=200 or not isinstance(x.get("data"),list):
  raise ValueError("FINMIND_API_FAIL:"+str(x.get("status"))+":"+str(x.get("msg",""))[:90])
 return x["data"],hashlib.sha256(b).hexdigest(),len(b)
def month_of(r):
 for k in ("date","Date","trade_date","TradingDate"):
  t=r.get(k)
  if isinstance(t,str) and re.fullmatch(r"2026-[01][0-9]-[0-3][0-9]",t):return t[:7]
 return None
def makezip(items):
 out=io.BytesIO()
 with zipfile.ZipFile(out,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,blob in sorted(items):
   zi=zipfile.ZipInfo(n,date_time=(2026,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED
   z.writestr(zi,blob)
 return out.getvalue()
def main(max_requests):
 now=datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=8))).date()
 end=min(now,datetime.date(2026,12,31)).isoformat()
 d=Drive(service());root=d.folder(ROOT,"2026");fin=d.folder(root,"FinMind");ctrl=d.folder(fin,"_FREE_2026_CONTROL")
 symbols=stocklist(d,ctrl)
 tasks=[(ds,stock) for ds in DATASETS for stock in symbols]
 state=get_json(d,ctrl,"BACKFILL_2026_FREE_CURSOR_R1.json") or {"cursor":0,"runs_completed":0,"permanent_failures":[],"version":"FREE_BACKFILL_2026_R1"}
 # Repair the single initial cursor move caused by the old token-required preflight (zero successful API calls).
 if state.get("cursor")==1 and state.get("runs_completed")==1 and len(state.get("permanent_failures",[]))==1 and "FINMIND_TOKEN_REQUIRED_FOR_QUOTA" in state["permanent_failures"][0].get("error",""):
  state["cursor"]=0;state["permanent_failures"]=[];state["runs_completed"]=0
 token=os.environ.get("FINMIND_TOKEN","").strip() or os.environ.get("FINMIND_API_TOKEN","").strip()
 budget,ledger,hourly_cap=quota_budget(state,time.time(),bool(token))
 start=int(state["cursor"])
 limit=min(max(0,max_requests),BATCH,270 if token else 120,budget)
 stop=min(len(tasks),start+limit)
 if start>=len(tasks):
  print(json.dumps({"state":"BACKFILL_CURRENT_STOCK_DATASET_TASKS_COMPLETE","total_tasks":len(tasks),"cursor":start,"missing_retries":len(state["permanent_failures"]),"year_complete":False}),flush=True);return
 print(json.dumps({"state":"QUOTA_PREFLIGHT","token_present":bool(token),"hourly_budget":hourly_cap,"available_requests":budget,"batch_limit":limit,"cursor":start}),flush=True)
 if not limit:
  print(json.dumps({"state":"WAIT_FOR_ROLLING_QUOTA","cursor":start}),flush=True);return
 batch_id=f"B{start:06d}_{stop-1:06d}";monthly=collections.defaultdict(list)
 failures=[];zero=[];worked=[];data_rows=0;response_bytes=0
 for i in range(start,stop):
  ds,stock=tasks[i];info={"dataset":ds,"stock_id":stock,"task_index":i}
  try:
   rows,digest,nbytes=fetch(ds,stock,end)
   partitions=collections.defaultdict(list)
   for row in rows:
    if not isinstance(row,dict):raise ValueError("NON_OBJECT_ROW")
    if str(row.get("stock_id",""))!=stock:raise ValueError("STOCK_SCOPE_MISMATCH")
    mo=month_of(row)
    if mo is None:raise ValueError("DATE_NOT_EXPLICIT")
    if mo>"2026-12" or mo[:7]>end[:7]:raise ValueError("FUTURE_PERIOD")
    partitions[mo].append(row)
   if not rows:zero.append(info)
   for mo,subset in partitions.items():
    # Information is month-partitioned but keeps query/API digest provenance
    item={"dataset":ds,"stock_id":stock,"response_sha256":digest,"annual_query_dates":["2026-01-01",end],
      "query_source":"FinMind_Free_Token","rows":subset,"status":"RAW_MONTH_SLICE_NOT_PIT_VERIFIED"}
    member=f"{ds}/{stock}.json"
    monthly[mo].append((member,json.dumps(item,ensure_ascii=False,separators=(",",":")).encode("utf-8")))
   worked.append({**info,"records":len(rows),"sha256":digest,"response_bytes":nbytes,"months":sorted(partitions)})
   data_rows+=len(rows);response_bytes+=nbytes
  except Exception as e:
   err=type(e).__name__+":"+str(e)[:160]
   failures.append({**info,"error":err})
   print(json.dumps({"task":i,"dataset":ds,"stock_id":stock,"status":"DEFERRED","error":err},ensure_ascii=False),flush=True)
   if any(k in err.lower() for k in ("429","limit","quota","403","402","token")):
    stop=i+1
    break
  time.sleep(0.18)
 # Commit month archives first, and only then cursor. If crash, deterministic archive allows safe repeat.
 outputs=[]
 for mo,items in sorted(monthly.items()):
  mon=d.folder(fin,mo)
  zname="FinMind_FREE_2026_"+batch_id+"_"+mo+".zip"
  raw=makezip(items);sha=hashlib.sha256(raw).hexdigest()
  old=existing(d,mon,zname)
  if old:
   rb=d.call(lambda:d.api.files().get_media(fileId=old["id"]))
   if hashlib.sha256(rb).hexdigest()!=sha:raise ValueError("EXISTING_ARCHIVE_CONFLICT:"+mo)
  else:d.put(mon,zname,raw,"application/zip",overwrite=False)
  outputs.append({"month":mo,"file":zname,"sha256":sha,"bytes":len(raw),"member_count":len(items)})
 receipt={"batch_id":batch_id,"start_cursor":start,"next_cursor":stop,"total_stock_dataset_tasks":len(tasks),
 "end_date":end,"stock_universe":"TaiwanStockInfo filtered numeric 4-digit provisional","datasets":list(DATASETS),
 "successful_tasks":worked,"empty_tasks":zero,"failed_tasks":failures,"rows":data_rows,"api_response_bytes":response_bytes,
 "monthly_outputs":outputs,"validation":"STRUCTURAL_STOCK_DATE_ONLY","numeric_verified":False,"pit_verified":False,
 "full_45_free_datasets_complete":False,"saved_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 rname="BACKFILL_2026_FREE_"+batch_id+"_RECEIPT.json"
 d.put(ctrl,rname,json.dumps(receipt,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
 state["cursor"]=stop;state["runs_completed"]+=1
 state["permanent_failures"]+=failures
 state["last_batch"]=rname;state["updated_utc"]=receipt["saved_at_utc"]
 # Completion timestamps intentionally overestimate recent usage, keeping
 # back-to-back push/manual/scheduled runs within the same rolling allowance.
 state["request_ledger"]=ledger+[{"at":time.time(),"count":len(worked)+len(failures)}]
 d.put(ctrl,"BACKFILL_2026_FREE_CURSOR_R1.json",json.dumps(state,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
 print(json.dumps({"state":"BATCH_COMMITTED","batch_id":batch_id,"cursor":stop,"total_tasks":len(tasks),
 "percent":round(stop/max(len(tasks),1)*100,3),"successful":len(worked),"empty":len(zero),"deferred":len(failures),"rows":data_rows,
 "output_archives":len(outputs),"response_bytes":response_bytes,"control_receipt":rname,"remaining_tasks":len(tasks)-stop,
 "fully_downloaded":False},ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--max-requests",type=int,default=BATCH);a=p.parse_args();main(a.max_requests)

