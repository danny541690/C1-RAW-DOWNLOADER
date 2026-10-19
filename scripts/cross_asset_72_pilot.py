"""September 2026 cross-asset 72-candidate pilot. Actual fetches; no invented coverage."""
import csv,datetime,hashlib,io,json,os,time,urllib.parse,urllib.request
from scripts.annual_actual_firstpass import Drive,service
CONFIG="config/cross_asset_72_pilot_2026_09.json"
START="2026-09-01"; END="2026-09-30"
def url_for(x):
    if x["source"]=="FinMind":
        p={"dataset":x["dataset"],"start_date":START,"end_date":END}
        if x["data_id"]:p["data_id"]=x["data_id"]
        if os.environ.get("FINMIND_TOKEN"):p["token"]=os.environ["FINMIND_TOKEN"]
        return "https://api.finmindtrade.com/api/v4/data?"+urllib.parse.urlencode(p)
    if x["source"]=="FRED":
        return "https://fred.stlouisfed.org/graph/fredgraph.csv?"+urllib.parse.urlencode({"id":x["dataset"],"cosd":START,"coed":END})
    return None
def get(url):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 JARVIS-C1-v093 research-pilot","Accept":"application/json,text/csv,*/*"})
    with urllib.request.urlopen(req,timeout=35) as r:
        b=r.read(3000001)
    if len(b)>3000000:raise ValueError("RESPONSE_TOO_LARGE")
    return b
def check(x,b):
    if x["source"]=="FinMind":
        obj=json.loads(b.decode("utf-8-sig"))
        if obj.get("status")!=200:raise ValueError("FINMIND_STATUS_"+str(obj.get("status")))
        data=obj.get("data")
        if not isinstance(data,list) or not data:raise ValueError("NO_ROWS")
        rows=[v for v in data if START<=str(v.get("date",""))<=END]
        if not rows:raise ValueError("NO_ROWS_IN_PERIOD")
        return len(rows)
    if x["source"]=="FRED":
        s=b.decode("utf-8-sig"); rr=list(csv.DictReader(io.StringIO(s)))
        if not rr or len(rr[0])<2:raise ValueError("BAD_CSV")
        col=[k for k in rr[0] if k not in ("DATE","observation_date")]
        valid=[r for r in rr if START<=str(r.get("DATE",r.get("observation_date","")))<=END and any(r.get(k) not in ("",".",None) for k in col)]
        if not valid:raise ValueError("NO_NUMERIC_ROWS_IN_PERIOD")
        return len(valid)
    raise ValueError("UNMAPPED_SOURCE")
def putjson(d,folder,name,obj):
    d.put(folder,name,(json.dumps(obj,ensure_ascii=False,indent=2)+"\n").encode("utf-8"),"application/json",overwrite=True)
def main():
    with open(CONFIG,encoding="utf-8") as f:cfg=json.load(f)
    d=Drive(service()); month=cfg["drive_folder_id"]
    dirs={s:d.folder(month,s) for s in ["FinMind","FRED","TWSE","TPEx","MOPS","TAIFEX","OTHER_OFFICIAL","QA_REPORTS"]}
    checkpoints=d.folder(dirs["QA_REPORTS"],"_CHECKPOINTS")
    summary=[]
    for x in cfg["indicators"]:
        id=x["id"];src=x["source"];url=url_for(x)
        filename=id+(".json" if src=="FinMind" else ".csv")
        recordname=id+".json"
        old=d.read(checkpoints,recordname)
        state=json.loads(old) if old else {}
        used=int(state.get("attempts",0));attempts=used
        status="SOURCE_DISCOVERY_REQUIRED";err="";rows=0;sha=None;bytes_=0
        if url:
            raw=d.read(dirs[src],filename)
            if raw is not None:
                try:rows=check(x,raw);status="SAVED_BASIC_VALID";sha=hashlib.sha256(raw).hexdigest();bytes_=len(raw)
                except Exception as e:status="EXISTING_FILE_UNVERIFIED";err=str(e)[:160]
            elif state.get("status") in ("DEFERRED_MISSING","SOURCE_HOLD","NO_DATA_IN_MONTH","SOURCE_DISCOVERY_REQUIRED"):
                status=state["status"];err=state.get("error","")
            else:
                status="PENDING"
                for n in range(used+1,5):
                    attempts=n
                    putjson(d,checkpoints,recordname,{"status":"IN_PROGRESS","attempts":n,"id":id})
                    try:
                        raw=get(url);rows=check(x,raw)
                        d.put(dirs[src],filename,raw,"application/json" if src=="FinMind" else "text/csv")
                        sha=hashlib.sha256(raw).hexdigest();bytes_=len(raw);status="SAVED_BASIC_VALID";err=""
                        break
                    except Exception as e:
                        err=type(e).__name__+":"+str(e)[:160]
                        if "NO_ROWS" in err or "NO_NUMERIC_ROWS" in err:status="NO_DATA_IN_MONTH";break
                        if "FINMIND_STATUS_4" in err or "HTTP Error 403" in err or "HTTP Error 429" in err:status="SOURCE_HOLD";break
                        if n<4:time.sleep(min(2**(n-1),4))
                if status=="PENDING":status="DEFERRED_MISSING"
        item={"id":id,"group":x["group"],"source":src,"dataset":x["dataset"],"period":"2026-09","status":status,"rows":rows,"bytes":bytes_,"sha256":sha,"attempts":attempts,"error":err,"source_url":url.split("&token=")[0] if url else None,"validation":"BASIC_ONLY" if status=="SAVED_BASIC_VALID" else "NOT_VERIFIED","PIT_verified":False}
        putjson(d,checkpoints,recordname,item)
        summary.append(item)
        print(json.dumps({"id":id,"source":src,"status":status,"rows":rows},ensure_ascii=False),flush=True)
    counts={s:sum(x["status"]==s for x in summary) for s in sorted(set(x["status"] for x in summary))}
    report={"period":"2026-09","total":len(summary),"counts":counts,"rows":sum(x["rows"] for x in summary),"bytes":sum(x["bytes"] for x in summary),"completed_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"complete_72":counts.get("SAVED_BASIC_VALID",0)==72,"records":summary}
    putjson(d,dirs["QA_REPORTS"],"2026-09_CROSS_ASSET_72_STATUS.json",report)
    print(json.dumps({"total":len(summary),"counts":counts,"rows":report["rows"],"bytes":report["bytes"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
