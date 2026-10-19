"""2026-09 raw-content coverage discovery, official-first FinMind delta strategy.
Reads all named source archives; samples up to 12 native JSON files per ZIP.
No network source API calls, no modifying raw data, no phantom completeness.
"""
import collections,datetime,hashlib,io,json,re,zipfile
from scripts.annual_actual_firstpass import Drive,service
YEAR_FOLDER="1kow1Aj-swUC30u3rSw6EwUeIMvjuT5QN"
REPORT_PARENT="1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit"
PERIOD="2026-09"
SOURCES=("TWSE","TPEx","MOPS","FinMind")
def listing(d,p):
 out=[];token=None
 while True:
  v=d.call(lambda:d.api.files().list(q="'"+p+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=token))
  out+=v.get("files",[]);token=v.get("nextPageToken")
  if not token:break
 return out
def find_folder(d,parent,name):
 v=[x for x in listing(d,parent) if x["name"]==name and x["mimeType"]=="application/vnd.google-apps.folder"]
 if len(v)!=1:raise ValueError("FOLDER_NOT_UNIQUE "+name)
 return v[0]["id"]
def shape(x):
 o={"type":type(x).__name__}
 if isinstance(x,dict):
  o["keys"]=list(x)[:25]
  for k in ("data","tables","units","files","receipts","native_files"):
   v=x.get(k)
   if isinstance(v,list):
    o[k+"_length"]=len(v)
    if v:
     o[k+"_first_keys"]=list(v[0])[:30] if isinstance(v[0],dict) else None
  for k in ("stat","status","date","month","content_month","numeric_verified","pit_verified"):
   if isinstance(x.get(k),(str,int,float,bool)):o[k]=x[k]
 elif isinstance(x,list):
  o["rows"]=len(x)
  if x and isinstance(x[0],dict):o["first_keys"]=list(x[0])[:40]
 return o
def data_profile(v):
 result={"structure":shape(v)}
 rows=v.get("data") if isinstance(v,dict) else v if isinstance(v,list) else None
 if isinstance(rows,list) and rows and isinstance(rows[0],dict):
  keys=list(rows[0]);result["row_keys"]=keys[:35]
  sym=next((k for k in ("stock_id","SecuritiesCompanyCode","Code","StockCode","證券代號","公司代號","股票代號","證券代碼") if k in keys),None)
  date=next((k for k in ("date","Date","日期","資料日期","年月日") if k in keys),None)
  result["identity_fields"]={"stock":sym,"date":date}
  if sym:
   a={str(r.get(sym,"")).strip() for r in rows if isinstance(r,dict) and r.get(sym) is not None}
   result["observed_stock_ids"]=len(a);result["stock_sample"]=sorted(a)[:8]
  if date:
   dates={str(r.get(date,"")) for r in rows if isinstance(r,dict) and r.get(date)}
   result["observed_dates"]=len(dates);result["date_sample"]=sorted(dates)[:6]
 elif isinstance(v,dict) and isinstance(v.get("tables"),list):
  result["tables"]=[]
  for t in v["tables"][:12]:
   if not isinstance(t,dict):continue
   fields=t.get("fields",[]);data=t.get("data",[])
   result["tables"].append({"title":str(t.get("title",""))[:90],"fields":fields[:20] if isinstance(fields,list) else str(fields)[:200],"rows":len(data) if isinstance(data,list) else None})
 return result
def main():
 d=Drive(service());result={"version":"C1-v093-SEP2026-DEEP-SOURCE-SCAN-001","created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"period":PERIOD,"sources":[],"restrictions":["Archive content inspection does not verify the full universe","Only sample twelve JSON native data members per archive; manifests are inspected","No FinMind API calls; no source downloads; existing raw never overwritten","Numeric and PIT QA still blocked"],"policy":"OFFICIAL_PRIMARY_FINMIND_GAP_ONLY"}
 for source in SOURCES:
  record={"source":source,"period":PERIOD,"archives":[],"status":"PENDING"}
  try:
   mo=find_folder(d,find_folder(d,YEAR_FOLDER,source),PERIOD)
   files=[f for f in listing(d,mo) if f["name"].lower().endswith(".zip")]
   for f in sorted(files,key=lambda x:x["name"]):
    ar={"name":f["name"],"id":f["id"],"size":int(f.get("size",0)),"status":"PENDING"}
    try:
     if ar["size"]>30000000:raise ValueError("EXCEEDS_ARCHIVE_SCAN_LIMIT")
     buf=d.call(lambda:d.api.files().get_media(fileId=f["id"]))
     ar["sha256"]=hashlib.sha256(buf).hexdigest()
     z=zipfile.ZipFile(io.BytesIO(buf));allnames=z.namelist()
     ar["zip_entries"]=len(allnames);ar["crc_bad_member"]=z.testzip()
     ar["all_member_names"]=allnames[:250]
     manifests=[n for n in allnames if n.split("/")[-1] in ("manifest.json","unit_manifest.json","complement_manifest_R1.json","financial_supplement_manifest.json","capture_receipts.json")]
     ar["manifests"]=[]
     for n in manifests[:6]:
      try:
       x=json.loads(z.read(n))
       s=shape(x)
       if isinstance(x,dict) and isinstance(x.get("units"),list):
        units=x["units"];by_dataset=collections.Counter(str(r.get("dataset",r.get("key",r.get("name","UNKNOWN")))) for r in units if isinstance(r,dict))
        s["unit_dataset_sample"]=by_dataset.most_common(24)
       ar["manifests"].append({"member":n,"summary":s})
      except Exception as e:ar["manifests"].append({"member":n,"error":str(e)[:140]})
     candidates=[n for n in allnames if n.lower().endswith(".json") and n not in manifests and not n.endswith(".receipt.json")]
     ar["native_samples"]=[]
     for n in candidates[:12]:
      try:
       b=z.read(n)
       if len(b)>12000000:raise ValueError("MEMBER_TOO_LARGE")
       v=json.loads(b.decode("utf-8-sig"));ar["native_samples"].append({"member":n,**data_profile(v)})
      except Exception as e:ar["native_samples"].append({"member":n,"error":str(e)[:130]})
     ar["native_json_total"]=len(candidates)
     ar["status"]="INSPECTED"
    except Exception as e:ar["status"]="ERROR";ar["error"]=type(e).__name__+":"+str(e)[:180]
    record["archives"].append(ar)
    print(json.dumps({"source":source,"archive":ar["name"],"state":ar["status"],"members":ar.get("zip_entries"),"samples":len(ar.get("native_samples",[]))},ensure_ascii=False),flush=True)
   record["status"]="ARCHIVES_INSPECTED" if files else "NO_ZIP_IN_PERIOD"
  except Exception as e:record["status"]="SOURCE_SCAN_ERROR";record["error"]=str(e)
  result["sources"].append(record)
 parent=d.folder(REPORT_PARENT,"V093_202609_OFFICIAL_FINMIND_SOURCE_DELTA")
 d.put(parent,"2026-09_native_member_inventory.json",(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"folder_id":parent,"archives_inspected":sum(a["status"]=="INSPECTED" for s in result["sources"] for a in s["archives"]),"sources":[{"source":s["source"],"status":s["status"],"archives":len(s["archives"])} for s in result["sources"]]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
