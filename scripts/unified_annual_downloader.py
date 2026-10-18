"""JARVIS v0.93 unified four-source annual orchestrator.
MODE=plan validates structure offline; MODE=capture requires Drive credentials.
Bulk TWSE/TPEx quotes + MOPS monthly revenue + FinMind 2330 PRICE SAMPLE ONLY.
This adapter deliberately NEVER certifies full-market, all datasets, or PIT.
"""
import argparse,calendar,json,os,time,hashlib,datetime,urllib.parse,urllib.request
from scripts.annual_actual_firstpass import Drive,service,candidates,valid
from scripts.production_gates import raw_segments
from scripts.monthly_reporting import build_month
from scripts.bulk_monthly_capture import url_for
SOURCES=("TWSE","TPEx","MOPS","FinMind")
def plan(year,month):
    if not (2000<=year<=2100 and 1<=month<=12):raise ValueError("bad period")
    days=calendar.monthrange(year,month)[1]
    units=[]
    for source in ("TWSE","TPEx"):
        for day in range(1,days+1):
            d=datetime.date(year,month,day)
            if d.weekday()<5:units.append({"source":source,"key":f"{source}_BULK_{d.isoformat()}","date":d.isoformat(),"kind":"json","url":url_for(source,d)})
    for source in ("MOPS","FinMind"):
        # Existing 2024 source adapters: non-generalized years blocked, not faked.
        if year!=2024:continue
        for label,url,kind in candidates(month,source):
            units.append({"source":source,"key":f"{source}_{label}_{year}-{month:02d}","kind":kind,"url":url})
    # Source coverage manifest: missing datasets are explicitly blocked, never counted as captured.
    return units
def fetch(url):
    request=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS/0.93"})
    with urllib.request.urlopen(request,timeout=40) as response:
        return response.read(15000001)
def run(year,month,mode):
    units=plan(year,month)
    if mode=="plan":
        print(json.dumps({"year":year,"month":month,"sources":SOURCES,"unit_count":len(units),"full_market_verified":False}))
        return
    d=Drive(service());root=d.folder(os.environ["GOOGLE_DRIVE_FOLDER_ID"],str(year))
    cp=d.folder(root,"_CHECKPOINTS");report_folder=d.folder(root,"_REPORTS")
    entries=[]
    for unit in units:
        source=unit["source"];name=unit["key"]+"."+unit["kind"]
        target=d.folder(d.folder(root,source),f"{year}-{month:02d}")
        record_name=unit["key"]+".json";prior_raw=d.read(cp,record_name)
        prior=json.loads(prior_raw) if prior_raw else {}
        attempted=int(prior.get("attempts",0));status="PENDING";error="";raw=d.read(target,name)
        if raw is not None:
            try:
                if len(raw)>15000000:raise ValueError("oversize")
                if source in ("MOPS","FinMind"):valid(source,raw,unit["kind"])
                else:
                    payload=json.loads(raw)
                    if not(payload.get("tables") or payload.get("aaData") or payload.get("data")):raise ValueError("no market tables")
                status="SAVED_BASIC_VALID"
            except Exception as ex:status="EXISTING_FILE_UNVERIFIED";error=type(ex).__name__
        elif prior.get("status") in ("DEFERRED_MISSING","SOURCE_HOLD","MARKET_CLOSED"):
            status=prior["status"];error=prior.get("error","")
        if status=="PENDING":
            for n in range(attempted+1,5):
                attempted=n
                d.put(cp,record_name,json.dumps({"attempts":n,"status":"IN_PROGRESS"}).encode(),"application/json",overwrite=True)
                try:
                    raw=fetch(unit["url"])
                    if len(raw)>15000000:raise ValueError("oversize")
                    if source in ("MOPS","FinMind"):valid(source,raw,unit["kind"])
                    else:
                        payload=json.loads(raw)
                        if not(payload.get("tables") or payload.get("aaData") or payload.get("data")):raise ValueError("no market tables")
                    d.put(target,name,raw,"application/json" if unit["kind"]=="json" else "text/html")
                    status="SAVED_BASIC_VALID";error=""
                    break
                except Exception as ex:
                    error=type(ex).__name__+":"+str(ex)[:90]
                    if n<4:time.sleep(min(2**(n-1),4))
            if status=="PENDING":status="DEFERRED_MISSING"
        receipt={"key":unit["key"],"source":source,"status":status,"attempts":attempted,
                 "bytes":len(raw) if status=="SAVED_BASIC_VALID" else 0,"last_error":error,
                 "sha256":hashlib.sha256(raw).hexdigest() if status=="SAVED_BASIC_VALID" else None,
                 "validation_level":"BASIC_ONLY","is_full_market":False}
        d.put(cp,record_name,json.dumps(receipt,ensure_ascii=False).encode(),"application/json",overwrite=True)
        entries.append(receipt)
        print(json.dumps({"month":month,"key":unit["key"],"status":status},ensure_ascii=False),flush=True)
    docs=build_month(year,month,entries)
    for filename,text in docs.items():d.put(report_folder,f"{year}-{month:02d}_{filename}",text.encode("utf-8"),"text/plain",overwrite=True)
    print(json.dumps({"year":year,"month":month,"saved":sum(e["status"]=="SAVED_BASIC_VALID" for e in entries),"missing":sum(e["status"]!="SAVED_BASIC_VALID" for e in entries),"full_market_verified":False}),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,default=2024);p.add_argument("--month",type=int,required=True);p.add_argument("--mode",choices=("plan","capture"),default="plan")
    a=p.parse_args();run(a.year,a.month,a.mode)
