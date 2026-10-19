"""2024 RAW integrity checkpoint: never trust receipt date, filename or structural rows alone.
Read-only 2024 TWSE/TPEx audit; isolate date mismatch and duplicate contents. No RAW overwrite.
"""
import argparse, collections,datetime,hashlib,json,re,calendar
from scripts.v093_2024_calendar_raw_qa_r1 import ROOT,CLOSED,listing,sub,read_id
from scripts.annual_actual_firstpass import Drive,service
def actual_date(obj):
 for k in ("date","Date","trade_date","tradeDate"):
  val=str(obj.get(k,"")).strip()
  if re.fullmatch(r"20\d{6}",val):return f"{val[:4]}-{val[4:6]}-{val[6:]}"
  if re.fullmatch(r"20\d\d[-/]\d\d[-/]\d\d",val):return val.replace("/","-")
  if re.fullmatch(r"1\d\d[/]\d\d[/]\d\d",val):return str(int(val[:3])+1911)+val[3:].replace("/","-")
 return None
def main(month):
 d=Drive(service());yr=sub(d,ROOT,"2024");reports=sub(d,yr,"_REPORTS")
 findings=[];byhash=collections.defaultdict(list)
 for source in ("TWSE","TPEx"):
  sf=sub(d,sub(d,yr,source),f"2024-{month:02d}")
  files={x["name"]:x for x in listing(d,sf) if x["mimeType"]!="application/vnd.google-apps.folder"}
  for day in range(1,calendar.monthrange(2024,month)[1]+1):
   dt=datetime.date(2024,month,day)
   if dt.weekday()>4 or dt.isoformat() in CLOSED:continue
   name=dt.isoformat()+"_BULK.json";entry={"source":source,"requested_date":dt.isoformat(),"filename":name,"status":"MISSING","numeric_verified":False,"pit_verified":False}
   if name in files:
    try:
     b=read_id(d,files[name]["id"]);digest=hashlib.sha256(b).hexdigest()
     entry["sha256"]=digest;entry["bytes"]=len(b)
     obj=json.loads(b.decode("utf-8-sig"))
     observed=actual_date(obj);entry["response_date"]=observed
     byhash[(source,digest)].append(entry)
     if observed is None:entry["status"]="DATE_UNPROVEN"
     elif observed!=entry["requested_date"]:entry["status"]="DATE_MISMATCH"
     else:entry["status"]="RESPONSE_DATE_MATCHED"
     rec=files.get(name+".receipt.json")
     if rec:
      rr=json.loads(read_id(d,rec["id"]).decode("utf-8-sig"))
      if rr.get("sha256")!=digest:entry["status"]="RECEIPT_HASH_MISMATCH"
     else:entry["status"]="RECEIPT_MISSING"
    except Exception as e:entry["status"]="READ_OR_PARSE_FAILED";entry["error"]=str(e)[:160]
   findings.append(entry)
 for group,items in byhash.items():
  dates={x["requested_date"] for x in items}
  if len(dates)>1:
   for e in items:e["status"]="DUPLICATE_IDENTICAL_DIFFERENT_DATES";e["duplicate_days"]=sorted(dates)
 stats=dict(collections.Counter(x["status"] for x in findings))
 report={"version":"C1-v0.93-2024-INTEGRITY-R2","month":f"2024-{month:02d}","generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"counts":stats,"findings":findings,"numeric_verified":False,"pit_verified":False,"policy":"NO_EXISTING_RAW_OVERWRITE; FAILED_DATE_NOT_A_VALID_HISTORICAL_SNAPSHOT","eligible_to_release":False}
 d.put(reports,f"2024-{month:02d}_INTEGRITY_R2.json",(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"month":month,"counts":stats,"invalid_examples":[{"source":x["source"],"requested":x["requested_date"],"response":x.get("response_date"),"reason":x["status"]} for x in findings if x["status"] not in ("RESPONSE_DATE_MATCHED",)][:7]},ensure_ascii=False),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--month",type=int,required=True);a=p.parse_args();main(a.month)
