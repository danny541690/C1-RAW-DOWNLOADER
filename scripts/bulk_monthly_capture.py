"""2024 bulk TWSE/TPEx daily capture, month checkpoint and deferred retry.
The two bulk quote feeds alone do NOT represent all four-source full-market data.
"""
import argparse,calendar,csv,hashlib,io,json,os,time,urllib.parse,urllib.error,datetime
from scripts.annual_actual_firstpass import Drive,service
from scripts.bulk_drive_e2e import fetch
from scripts.bulk_market_canary import measure
def url_for(source,day):
    iso=day.isoformat()
    if source=="TWSE":
        return "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?"+urllib.parse.urlencode({"date":iso.replace("-",""),"type":"ALLBUT0999","response":"json"})
    return "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?"+urllib.parse.urlencode({"date":iso.replace("-",""),"response":"json"})
def run(year,month):
    d=Drive(service());root=d.folder(os.environ["GOOGLE_DRIVE_FOLDER_ID"],str(year))
    control=d.folder(root,"_CHECKPOINTS");reports=d.folder(root,"_REPORTS")
    result=[];first=datetime.date(year,month,1);days=calendar.monthrange(year,month)[1]
    for source in ("TWSE","TPEx"):
        folder=d.folder(d.folder(root,source),f"{year}-{month:02d}")
        for i in range(1,days+1):
            day=datetime.date(year,month,i)
            # Weekends cannot be trading days. Holidays must be independently checked.
            if day.weekday()>=5:continue
            key=f"BULK_{source}_{day.isoformat()}";name=f"{day.isoformat()}_BULK.json"
            cpname=key+".json";old=d.read(control,cpname)
            prior=json.loads(old) if old else {};used=int(prior.get("attempts_total",0))
            raw=d.read(folder,name)
            if raw is not None:
                try:
                    digest=hashlib.sha256(raw).hexdigest()
                    receipt=d.read(folder,name+".receipt.json")
                    if not receipt or json.loads(receipt).get("sha256")!=digest:raise ValueError("receipt missing or hash differs")
                    status="SAVED_BASIC_VALID";err=""
                except Exception as exc:
                    status="EXISTING_FILE_UNVERIFIED";err=type(exc).__name__
            elif prior.get("status") in ("DEFERRED_MISSING","SOURCE_HOLD","MARKET_CLOSED"):
                status=prior["status"];err=prior.get("error","")
            else:
                status="PENDING";err=""
            if status=="PENDING":
                if used>=4:status="DEFERRED_MISSING";err="MAX_FOUR_REQUESTS"
                else:
                    for n in range(used+1,5):
                        used=n
                        d.put(control,cpname,json.dumps({"status":"IN_PROGRESS","attempts_total":n}).encode(),"application/json",overwrite=True)
                        try:
                            raw=fetch(url_for(source,day))
                            obj=json.loads(raw)
                            if source=="TWSE" and obj.get("stat")!="OK":
                                status="MARKET_CLOSED" if "沒有符合條件" in str(obj.get("stat")) else "DEFERRED_MISSING"
                                err=str(obj.get("stat"))[:100];break
                            # Real market day requires a sufficiently large securities table.
                            if source=="TWSE":
                                stats=measure(source,raw)
                            else:
                                # The TPEx response may have non-security tables; retain as basic-only.
                                stats=measure(source,raw)
                            d.put(folder,name,raw,"application/json")
                            receipt={"source":source,"date":day.isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw),"rows_unverified":stats["rows"],"numeric_verified":False,"pit_verified":False}
                            d.put(folder,name+".receipt.json",json.dumps(receipt,ensure_ascii=False).encode(),"application/json",overwrite=True)
                            status="SAVED_BASIC_VALID";err="";break
                        except Exception as exc:
                            err=type(exc).__name__+":"+str(exc)[:90]
                            if n<4:time.sleep(min(2**(n-1),4))
                    if status=="PENDING":status="DEFERRED_MISSING"
            entry={"key":key,"source":source,"date":day.isoformat(),"status":status,"attempts_total":used,"error":err}
            d.put(control,cpname,json.dumps(entry,ensure_ascii=False).encode(),"application/json",overwrite=True)
            result.append(entry)
            print(json.dumps(entry,ensure_ascii=False),flush=True)
    saved=sum(u["status"]=="SAVED_BASIC_VALID" for u in result)
    missing=[u for u in result if u["status"] not in ("SAVED_BASIC_VALID","MARKET_CLOSED")]
    report={"year":year,"month":month,"scope":"TWSE_TPEX_BULK_QUOTES_ONLY","expected_weekday_source_units":len(result),"saved_basic_valid":saved,"missing":len(missing),"market_coverage_complete":False,"numeric_verified":False,"pit_verified":False}
    stem=f"{year}-{month:02d}_BULK_"
    d.put(reports,stem+"MONTHLY_PROGRESS.json",json.dumps(report,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
    d.put(reports,stem+"REPAIR_QUEUE.json",json.dumps(missing,ensure_ascii=False,indent=2).encode(),"application/json",overwrite=True)
    print(json.dumps({"result":"MONTH_COMPLETED","report":report},ensure_ascii=False),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,default=2024);p.add_argument("--month",type=int,required=True)
    a=p.parse_args();run(a.year,a.month)
