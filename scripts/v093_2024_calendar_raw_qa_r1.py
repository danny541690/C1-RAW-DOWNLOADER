"""JARVIS C1 v0.93 2024 calendar-aware RAW audit and targeted repair.
No old files are overwritten. No FinMind broad crawl. Persist auditable findings monthly.
"""
import argparse,calendar,collections,csv,datetime,hashlib,io,json,os,time,urllib.request
from scripts.annual_actual_firstpass import Drive,service
from scripts.bulk_monthly_capture import url_for
from scripts.bulk_market_canary import measure
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
CLOSED=set("""2024-01-01 2024-02-06 2024-02-07 2024-02-08 2024-02-09 2024-02-12 2024-02-13 2024-02-14 2024-02-28 2024-04-04 2024-04-05 2024-05-01 2024-06-10 2024-07-24 2024-07-25 2024-09-17 2024-10-02 2024-10-03 2024-10-10 2024-10-31""".split())
EXPECTED={"TWSE":lambda d:f"{d}_BULK.json","TPEx":lambda d:f"{d}_BULK.json"}
def listing(d,parent):
 out=[];page=None
 while True:
  p=d.call(lambda:d.api.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageToken=page,pageSize=1000))
  out+=p.get("files",[]);page=p.get("nextPageToken")
  if not page:break
 return out
def sub(d,parent,name):
 rows=[x for x in listing(d,parent) if x["name"]==name and x["mimeType"]=="application/vnd.google-apps.folder"]
 if len(rows)!=1:raise RuntimeError("FOLDER_RESOLUTION "+name+" count="+str(len(rows)))
 return rows[0]["id"]
def read_id(d,fid):
 return d.call(lambda:d.api.files().get_media(fileId=fid))
def fetch_actual(source,date):
 u=url_for(source,datetime.date.fromisoformat(date))
 with urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0 JARVIS-C1-0.93-QA"}),timeout=35) as response:
  raw=response.read(15000001)
 if len(raw)>15000000:raise ValueError("response too large")
 evidence=measure(source,raw)
 return raw,{"rows":evidence["rows"],"url":u}
def audit_month(month,repair=False):
 d=Drive(service());year=sub(d,ROOT,"2024")
 reportdir=sub(d,year,"_REPORTS");out=[]
 for source in ("TWSE","TPEx"):
  folder=sub(d,sub(d,year,source),f"2024-{month:02d}")
  existing={x["name"]:x for x in listing(d,folder) if x["mimeType"]!="application/vnd.google-apps.folder"}
  for day in range(1,calendar.monthrange(2024,month)[1]+1):
   dayobj=datetime.date(2024,month,day);date=dayobj.isoformat()
   if dayobj.weekday()>4:continue
   filename=EXPECTED[source](date)
   present=existing.get(filename)
   entry={"date":date,"source":source,"raw_file":filename,"status":"PENDING","rows":None,"bytes":None,"numeric_verified":False,"pit_verified":False}
   if date in CLOSED:
    entry["status"]="MARKET_CLOSED"
    if present:entry["warning"]="NONTRADING_DAY_RAW_PRESENT_NOT_ACCEPTED_AS_MARKET_SNAPSHOT"
    out.append(entry);continue
   if present:
    try:
     raw=read_id(d,present["id"]);entry["bytes"]=len(raw);entry["sha256"]=hashlib.sha256(raw).hexdigest()
     receipt=existing.get(filename+".receipt.json")
     if receipt is None:raise ValueError("RECEIPT_MISSING")
     rc=json.loads(read_id(d,receipt["id"]).decode("utf-8-sig"))
     if rc.get("sha256")!=entry["sha256"]:raise ValueError("SHA256_MISMATCH")
     snapshot=measure(source,raw)
     entry["rows"]=snapshot["rows"];entry["status"]="SAVED_STRUCTURAL_VALID"
    except Exception as e:
     entry["status"]="EXISTING_UNVERIFIED";entry["error"]=type(e).__name__+":"+str(e)[:160]
    out.append(entry);continue
   entry["status"]="ACTUAL_TRADING_DAY_MISSING"
   if repair:
    errors=[]
    for attempt in range(1,3):
     try:
      raw,stats=fetch_actual(source,date)
      # Preserve original paths; put will refuse unequal contents of any previously created file.
      d.put(folder,filename,raw,"application/json",overwrite=False)
      rc={"source":source,"date":date,"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"rows_unverified":stats["rows"],"numeric_verified":False,"pit_verified":False,"repair_run":"C1_2024_QA_R1"}
      d.put(folder,filename+".receipt.json",json.dumps(rc,ensure_ascii=False).encode(),"application/json",overwrite=False)
      entry["status"]="REPAIRED_STRUCTURAL_VALID";entry["rows"]=stats["rows"];entry["bytes"]=len(raw);entry["sha256"]=rc["sha256"];entry["attempts"]=attempt
      break
     except Exception as exc:
      errors.append(type(exc).__name__+":"+str(exc)[:130])
      if attempt==1:time.sleep(2)
    if entry["status"]!="REPAIRED_STRUCTURAL_VALID":entry["error"]=" | ".join(errors)
   out.append(entry)
   print(json.dumps({"source":source,"date":date,"status":entry["status"]},ensure_ascii=False),flush=True)
 # Important: MOPS and FinMind presence is not market-wide or dataset completeness.
 extra={}
 for src in ("MOPS","FinMind"):
  fol=sub(d,sub(d,year,src),f"2024-{month:02d}")
  extras=listing(d,fol)
  extra[src]={"files":[{"name":x["name"],"size":x.get("size")} for x in extras if x["mimeType"]!="application/vnd.google-apps.folder"],"validation":"FILE_PRESENCE_ONLY"}
 counts=dict(collections.Counter(x["status"] for x in out))
 report={"version":"C1-v0.93-2024-MONTH-RAW-QA-R1","month":f"2024-{month:02d}","generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"official_calendar_status":"KNOWN_CLOSED_DATES_FROM_REVIEW_REQUIRE_INDEPENDENT_OFFICIAL_CALENDAR_SIGNOFF","scope":"TWSE_TPEX_BULK_QUOTES_WITH_RECEIPT_SHA_AND_STRUCTURAL_STOCK_ROW_CHECK","repair_requested":repair,"counts":counts,"entries":out,"other_sources":extra,"quality":{"market_coverage_complete":False,"numeric_verified":False,"pit_verified":False,"full_dataset_coverage":False},"caution":"Market-close status and structural row count do not certify full-market stock IDs or economic value correctness."}
 fname=f"2024-{month:02d}_QA_R1_CALENDAR_AND_RAW.json"
 d.put(reportdir,fname,(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 csvbuf=io.StringIO();w=csv.DictWriter(csvbuf,fieldnames=["date","source","status","rows","bytes","error","warning"]);w.writeheader()
 for e in out:w.writerow({k:e.get(k,"") for k in w.fieldnames})
 d.put(reportdir,f"2024-{month:02d}_QA_R1_MISSING_AND_WARNINGS.csv",csvbuf.getvalue().encode(),"text/csv",overwrite=True)
 print(json.dumps({"month":month,"counts":counts,"report":fname,"drive":"2024/_REPORTS"},ensure_ascii=False),flush=True)
 if counts.get("EXISTING_UNVERIFIED",0):print("QUALITY_GATE_BLOCKED: existing input verification failures",flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--month",type=int,required=True);p.add_argument("--repair",action="store_true")
 a=p.parse_args();audit_month(a.month,a.repair)
