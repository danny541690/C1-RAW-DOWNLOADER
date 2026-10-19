"""C1 v0.93 2024 TPEx R3 historical correction/resume.
OLD RAW NEVER DELETED OR REPLACED. Corrected names only. Exact response-date, SHA and readback.
"""
import argparse,calendar,datetime,hashlib,json,random,time,urllib.parse,urllib.request,urllib.error,http.client,socket,collections
from scripts.v093_2024_calendar_raw_qa_r1 import ROOT,CLOSED,listing,sub,read_id
from scripts.v093_2024_integrity_r2 import actual_date
from scripts.annual_actual_firstpass import Drive,service
CORRECTED="_HISTORICAL_CORRECTED_R3.json"
def fetch(day):
 fmt=day.replace("-","/")
 url="https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?"+urllib.parse.urlencode({"response":"json","date":fmt})
 req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-C1-v093-historical-R3","Accept":"application/json"})
 with urllib.request.urlopen(req,timeout=45) as r:b=r.read(9000001)
 if len(b)>9000000:raise ValueError("RESPONSE_SIZE_LIMIT")
 x=json.loads(b.decode("utf-8-sig"))
 dated=actual_date(x)
 if dated!=day:raise ValueError(f"WRONG_RESPONSE_DATE expected={day} got={dated}")
 tables=x.get("tables") or []
 rows=sum(len(t.get("data") or []) for t in tables if isinstance(t,dict) and any(str(f).strip() in ("代號","股票代號","證券代號") for f in t.get("fields",[])))
 if rows<300:raise ValueError(f"NOT_FULL_SNAPSHOT_ROWS={rows}")
 return b,rows,url
def valid_existing(d,files,name,day):
 if name not in files or name+".receipt.json" not in files:return False
 b=read_id(d,files[name]["id"])
 r=json.loads(read_id(d,files[name+".receipt.json"]["id"]).decode("utf-8-sig"))
 x=json.loads(b.decode("utf-8-sig"))
 return actual_date(x)==day and r.get("sha256")==hashlib.sha256(b).hexdigest() and r.get("response_date")==day and r.get("rows",0)>=300
def run(month):
 d=Drive(service());year=sub(d,ROOT,"2024");monthfolder=sub(d,sub(d,year,"TPEx"),f"2024-{month:02d}");reports=sub(d,year,"_REPORTS")
 files={x["name"]:x for x in listing(d,monthfolder) if x["mimeType"]!="application/vnd.google-apps.folder"}
 out=[];stats=collections.Counter()
 for n in range(1,calendar.monthrange(2024,month)[1]+1):
  dt=datetime.date(2024,month,n);day=dt.isoformat()
  if dt.weekday()>4 or day in CLOSED:continue
  name=day+CORRECTED
  e={"date":day,"source":"TPEx","corrected_filename":name,"status":"PENDING","numeric_verified":False,"pit_verified":False}
  try:
   if valid_existing(d,files,name,day):
    e["status"]="EXISTING_R3_READBACK_VERIFIED"
   else:
    # Do not clobber partial or mismatching same-named corrected files.
    if name in files or name+".receipt.json" in files:
     e["status"]="CORRECTED_FILE_CONFLICT_MANUAL_REVIEW"
    else:
     errors=[]
     for attempt in range(1,4):
      try:
       raw,rows,url=fetch(day)
       digest=hashlib.sha256(raw).hexdigest()
       d.put(monthfolder,name,raw,"application/json",overwrite=False)
       receipt={"date":day,"source":"TPEx","format":"YYYY/MM/DD","response_date":day,"sha256":digest,
          "bytes":len(raw),"rows":rows,"numeric_verified":False,"pit_verified":False,"url":url,"run":"R3_CORRECT_HISTORICAL"}
       d.put(monthfolder,name+".receipt.json",json.dumps(receipt,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=False)
       # Independent remote readback; do not mark success without re-reading.
       now={x["name"]:x for x in listing(d,monthfolder) if x["mimeType"]!="application/vnd.google-apps.folder"}
       if not valid_existing(d,now,name,day):raise ValueError("R3_READBACK_VERIFICATION_FAILED")
       e.update({"status":"R3_DATE_AND_SHA_VERIFIED","sha256":digest,"rows":rows,"bytes":len(raw),"attempts":attempt})
       break
      except Exception as exc:
       errors.append(type(exc).__name__+":"+str(exc)[:150])
       if attempt<3:time.sleep(1.5*attempt+random.random())
     if e["status"]=="PENDING":e.update({"status":"RETRY_DEFERRED","errors":errors})
  except Exception as exc:e.update({"status":"ERROR","error":type(exc).__name__+":"+str(exc)[:160]})
  out.append(e);stats[e["status"]]+=1
  print(json.dumps({"date":day,"status":e["status"],"attempts":e.get("attempts")},ensure_ascii=False),flush=True)
 report={"version":"2024-TPEx-CORRECT-HISTORICAL-R3","month":f"2024-{month:02d}","generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "status":"COMPLETE_FOR_TPEX_CORRECTED_DATES_ONLY" if all(e["status"] in ("R3_DATE_AND_SHA_VERIFIED","EXISTING_R3_READBACK_VERIFIED") for e in out) else "PARTIAL_WITH_GAPS",
 "counts":dict(stats),"entries":out,"scope":"TPEx BULK historical response-date verified only, not 4-source dataset coverage","numeric_verified":False,"pit_verified":False}
 d.put(reports,f"2024-{month:02d}_TPEX_R3_HISTORICAL_REPAIR.json",(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"month":month,"counts":dict(stats),"status":report["status"]},ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--month",type=int,required=True);a=p.parse_args();run(a.month)
