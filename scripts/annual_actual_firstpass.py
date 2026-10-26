"""2024 first-pass actual source capture. Partial coverage is explicitly NOT certified as full-market.
All successful raw source responses saved immediately to Drive; failures deferred.
"""
import csv, hashlib, io, json, os, time, urllib.request, urllib.parse, urllib.error, socket, random
import http.client
from datetime import date
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

YEAR=2024
SOURCES=("TWSE","TPEx","MOPS","FinMind")
SCOPES=["https://www.googleapis.com/auth/drive"]
def retryable_drive_error(exc):
    if not isinstance(exc,HttpError):return True
    status=getattr(exc.resp,'status',None)
    if status in (429,500,502,503,504):return True
    if status!=403:return False
    try:
        reasons={x.get('reason') for x in json.loads(exc.content).get('error',{}).get('errors',[])}
    except (ValueError,TypeError,AttributeError):return False
    return bool(reasons & {'userRateLimitExceeded','rateLimitExceeded'})
def service():
    c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=SCOPES)
    c.refresh(Request())
    return build("drive","v3",credentials=c,cache_discovery=False)
class Drive:
    @staticmethod
    def call(make_request):
        for n in range(4):
            try:
                return make_request().execute(num_retries=0)
            except (TimeoutError, socket.timeout, ConnectionError, OSError, HttpError, http.client.IncompleteRead) as exc:
                status=getattr(getattr(exc,"resp",None),"status",None)
                if not retryable_drive_error(exc):
                    raise
                if n==3:raise
                time.sleep(min(2**n,6)+random.random())
    def __init__(self,api):self.api=api
    def find(self,parent,name):
        q="name = '"+name.replace("\\","\\\\").replace("'","\\'")+"' and '"+parent+"' in parents and trashed = false"
        x=self.call(lambda:self.api.files().list(q=q,fields="nextPageToken,files(id,name,mimeType)",pageSize=100))
        if x.get("nextPageToken"):raise ValueError("ambiguous folder pagination")
        f=x.get("files",[])
        if len(f)>1:raise ValueError("duplicate remote names")
        return f[0] if f else None
    def folder(self,parent,name):
        f=self.find(parent,name)
        if f:
            if f["mimeType"]!="application/vnd.google-apps.folder":raise ValueError("name collides with file")
            return f["id"]
        return self.call(lambda:self.api.files().create(body={"name":name,"parents":[parent],
          "mimeType":"application/vnd.google-apps.folder"},fields="id"))["id"]
    def read(self,parent,name):
        f=self.find(parent,name)
        return self.call(lambda:self.api.files().get_media(fileId=f["id"])) if f else None
    def put(self,parent,name,raw,mime="application/octet-stream",overwrite=False):
        old=self.find(parent,name)
        direct=getattr(self,'direct_readback',False)
        saved_id=old['id'] if old else None
        if old and not overwrite:
            existing=self.call(lambda:self.api.files().get_media(fileId=old['id'])) if direct else self.read(parent,name)
            if hashlib.sha256(existing).digest()!=hashlib.sha256(raw).digest():
                raise ValueError("existing remote file SHA mismatch")
            return
        media=MediaIoBaseUpload(io.BytesIO(raw),mimetype=mime,resumable=False)
        for n in range(4):
            try:
                media=MediaIoBaseUpload(io.BytesIO(raw),mimetype=mime,resumable=False)
                if old:
                    self.api.files().update(fileId=old["id"],media_body=media).execute(num_retries=0)
                else:
                    created=self.api.files().create(body={"name":name,"parents":[parent]},media_body=media,fields="id").execute(num_retries=0)
                    saved_id=created['id']
                break
            except (TimeoutError, socket.timeout, ConnectionError, OSError, HttpError, http.client.IncompleteRead) as exc:
                status=getattr(getattr(exc,"resp",None),"status",None)
                if not retryable_drive_error(exc):raise
                # A create may have reached Drive even when its response timed out.
                found=self.find(parent,name)
                if found:
                    saved=self.read(parent,name)
                    if saved is not None and hashlib.sha256(saved).digest()==hashlib.sha256(raw).digest():break
                    if not overwrite:raise ValueError("immutable remote create conflict")
                    if not old:old=found
                if n==3:raise
                time.sleep(min(2**n,6)+random.random())
        readback=(self.call(lambda:self.api.files().get_media(fileId=saved_id))
                  if direct and saved_id else self.read(parent,name))
        if hashlib.sha256(readback).digest()!=hashlib.sha256(raw).digest():
            raise ValueError("Google Drive readback hash differs")
def fetch(url, limit=8000000):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-C1-0.93/annual-raw","Accept":"*/*"})
    with urllib.request.urlopen(req,timeout=35) as r:
        data=r.read(limit+1)
        if len(data)>limit:raise ValueError("response exceeds size cap")
        return data
def candidates(month,source):
    last=(date(2024+(month==12),month%12+1,1)-date.resolution).day
    if source=="TWSE":
        # Monthly 2330 history only: NOT whole market.
        yield "STOCK_DAY_2330",f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=2024{month:02d}02&stockNo=2330&response=json","json"
    if source=="TPEx":
        # Official OTC snapshot for first calendar day; can be holiday.
        for day in range(1, min(last,7)+1):
            d=f"2024/{month:02d}/{day:02d}"
            yield "OTC_DAILY_QUOTES_"+str(day).zfill(2),"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?"+urllib.parse.urlencode({"response":"json","date":d}),"json"
    if source=="MOPS":
        for market in ("sii","otc"):
            yield "MONTHLY_REVENUE_"+market,f"https://mopsov.twse.com.tw/nas/t21/{market}/t21sc03_113_{month}_0.html","html"
    if source=="FinMind":
        yield "TaiwanStockPrice_2330","https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode({
            "dataset":"TaiwanStockPrice","data_id":"2330","start_date":f"2024-{month:02d}-01",
            "end_date":f"2024-{month:02d}-{last:02d}"}),"json"
def valid(source,raw,kind):
    if kind=="html":
        if len(raw)<800 or b"<table" not in raw.lower():raise ValueError("HTML missing table")
    else:
        x=json.loads(raw.decode("utf-8-sig"))
        if source=="TWSE" and (x.get("stat")!="OK" or not x.get("data")):raise ValueError("TWSE no history")
        if source=="FinMind" and (x.get("status")!=200 or not x.get("data")):raise ValueError("FinMind missing rows")
        if source=="TPEx" and not (x.get("aaData") or x.get("data") or x.get("tables")):raise ValueError("TPEx no data")
def put_json(d,p,name,obj):
    d.put(p,name,(json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
def run():
    d=Drive(service());root=os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    year_root=d.folder(root,str(YEAR))
    checkpoint_dir=d.folder(year_root,"_CHECKPOINTS")
    report_dir=d.folder(year_root,"_REPORTS")
    for month in range(1,13):
        report={"year":YEAR,"month":month,"coverage":"PARTIAL_SOURCE_SAMPLES_NOT_FULL_MARKET",
                "numeric_verified":False,"pit_verified":False,"units":[]}
        for source in SOURCES:
            target=d.folder(d.folder(year_root,source),f"{YEAR}-{month:02d}")
            for label,url,kind in candidates(month,source):
                key=f"{source}_{YEAR}_{month:02d}_{label}"
                saved_name=label+"."+kind
                status="PENDING";reason="";attempts=0
                previous_raw=d.read(checkpoint_dir,key+".json")
                previous=json.loads(previous_raw) if previous_raw else {}
                used=int(previous.get("total_attempts",0))
                if previous.get("status") in ("DEFERRED_MISSING","SOURCE_HOLD","EXISTING_FILE_UNVERIFIED"):
                    status=previous["status"];reason=previous.get("error","")
                # Checking the remote raw file provides durable continuation even if checkpoint upload failed.
                existing=d.read(target,saved_name)
                if existing is not None:
                    try:valid(source,existing,kind);status="SAVED_BASIC_VALID";reason="previously persisted"
                    except Exception as e:status="EXISTING_FILE_UNVERIFIED";reason=type(e).__name__
                if status=="PENDING" and used>=4:
                    status="DEFERRED_MISSING";reason="TOTAL_RETRY_BUDGET_EXHAUSTED"
                if status=="PENDING":
                    for n in range(used+1,5):
                        attempts+=1
                        put_json(d,checkpoint_dir,key+".json",{"unit":key,"status":"IN_PROGRESS","total_attempts":n})
                        try:
                            raw=fetch(url);valid(source,raw,kind)
                            d.put(target,saved_name,raw,"application/json" if kind=="json" else "text/html")
                            status="SAVED_BASIC_VALID";reason=""
                            break
                        except Exception as e:
                            reason=type(e).__name__+":"+str(e)[:120]
                            if isinstance(e,(ValueError,json.JSONDecodeError)):break
                            if n<4:time.sleep(min(2**(n-1),4))
                    if status=="PENDING":status="DEFERRED_MISSING"
                unit={"unit":key,"key":key,"source":source,"status":status,"attempts":used+attempts,"attempts_this_run":attempts,
                      "total_attempts":used+attempts,
                      "last_error":reason,"error":reason,"source_url":url,"is_full_market":False,
                      "bytes":len(existing) if existing is not None and status=="SAVED_BASIC_VALID" else (len(raw) if status=="SAVED_BASIC_VALID" else 0)}
                report["units"].append(unit)
                put_json(d,checkpoint_dir,key+".json",unit)
                print(json.dumps({"month":month,"source":source,"unit":label,"status":status,"attempts":attempts}),flush=True)
        report["saved_basic_valid"]=sum(u["status"]=="SAVED_BASIC_VALID" for u in report["units"])
        report["missing"]=sum(u["status"]!="SAVED_BASIC_VALID" for u in report["units"])
        report["coverage_complete"]=False
        from scripts.monthly_reporting import build_month
        generated=build_month(YEAR,month,report["units"])
        for filename,body in generated.items():
            d.put(report_dir,f"{YEAR}-{month:02d}_"+filename,body.encode("utf-8"),"text/plain",overwrite=True)
        gaps=[u for u in report["units"] if u["status"]!="SAVED_BASIC_VALID"]
        put_json(d,report_dir,f"2024-{month:02d}_REPAIR_QUEUE.json",gaps)
        print(json.dumps({"month":month,"saved":report["saved_basic_valid"],"missing":report["missing"],
                           "coverage_complete":False}),flush=True)
    put_json(d,report_dir,"2024_ANNUAL_STATUS.json",{"year":YEAR,"months_processed":12,"mode":"PARTIAL_SAMPLE_ONLY","market_coverage_complete":False,"numeric_verified":False,"pit_verified":False})
    print("2024 FIRST-PASS SOURCE SAMPLES FINISHED; FULL-MARKET DATA NOT VERIFIED",flush=True)
if __name__=="__main__":
    raise SystemExit("LEGACY_WORKER_POLICY_NOT_INTEGRATED: annual_actual_firstpass.py; required=V093_FIVE_STAGE_DOWNLOAD_RULES_V1_20261021; no download started")

