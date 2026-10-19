"""Read-only 2024-2026 three-official-source vs FinMind raw content sampling.
Report source data shape, stock IDs when explicitly present, missing categories;
no automatic backfill and no full-market certifications.
"""
import collections,datetime,hashlib,io,json,re,zipfile
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
REPORT_PARENT="1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit"
SOURCES=("TWSE","TPEx","MOPS","FinMind")
MONTHS=((2024,1),(2025,1),(2026,1),(2026,9))
MAX_PER_SOURCE=2
def listing(d,p):
 out=[];token=None
 while True:
  r=d.call(lambda:d.api.files().list(q="'"+p+"' in parents and trashed = false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=token))
  out+=r.get("files",[]);token=r.get("nextPageToken")
  if not token:return out
def children(d,p):return {a["name"]:a for a in listing(d,p) if a["mimeType"]=="application/vnd.google-apps.folder"}
def shape(buf):
 s={"len":len(buf)}
 try:
  data=json.loads(buf.decode("utf-8-sig"))
  s["parse"]="JSON_OK";s["root"]=type(data).__name__
  if isinstance(data,dict):
   s["keys"]=list(data)[:35]
   for k in ("data","tables","aaData","dataset","status","stat"):
    if k in data:
     val=data[k];s[k+"_type"]=type(val).__name__
     if isinstance(val,list):
      s[k+"_length"]=len(val)
      if val:
       if isinstance(val[0],dict):s[k+"_first_keys"]=list(val[0])[:35]
       elif isinstance(val[0],list):s[k+"_first_width"]=len(val[0])
     elif isinstance(val,(str,int,float)):s[k+"_value"]=val
  elif isinstance(data,list):
   s["row_count"]=len(data)
   if data and isinstance(data[0],dict):s["first_keys"]=list(data[0])[:35]
 except Exception as e:s["parse"]="NOT_JSON";s["error"]=type(e).__name__
 return s
def main():
 d=Drive(service());years=children(d,ROOT);out=[]
 for y,m in MONTHS:
  for source in SOURCES:
   result={"year":y,"month":m,"source":source,"inspection_level":"SAMPLED_CONTENT_NOT_MARKET_COVERAGE"}
   try:
    dirs=children(d,years[str(y)]["id"])
    folder=children(d,dirs[source]["id"])[f"{y}-{m:02d}"]["id"]
    allfiles=sorted([x for x in listing(d,folder) if x["mimeType"]!="application/vnd.google-apps.folder"],key=lambda x:x["name"])
    result["file_count"]=len(allfiles);result["file_names"]=[x["name"] for x in allfiles[:15]]
    candidates=[x for x in allfiles if x["name"].lower().endswith((".zip",".json",".html"))]
    # prefer one ZIP, and a second content sample if available
    candidates=sorted(candidates,key=lambda x:(not x["name"].lower().endswith(".zip"),x["name"]))[:MAX_PER_SOURCE]
    inspected=[]
    for f in candidates:
     evidence={"name":f["name"],"size":int(f.get("size",0)),"files_inspected":0}
     if int(f.get("size",0))>20000000:
      evidence["status"]="SKIPPED_LARGE";inspected.append(evidence);continue
     raw=d.call(lambda:d.api.files().get_media(fileId=f["id"]))
     evidence["sha256"]=hashlib.sha256(raw).hexdigest()
     if f["name"].lower().endswith(".zip"):
      z=zipfile.ZipFile(io.BytesIO(raw))
      evidence["members"]=len(z.namelist());evidence["zip_crc_bad_member"]=z.testzip()
      names=[n for n in z.namelist() if n.lower().endswith(".json") and not n.startswith("__MACOSX")]
      evidence["member_names_sample"]=names[:8]
      for n in names[:2]:
       b=z.read(n)
       if len(b)>3000000:continue
       evidence.setdefault("member_shapes",[]).append({"member":n,**shape(b)})
       evidence["files_inspected"]+=1
     elif f["name"].lower().endswith(".json"):
      evidence["shape"]=shape(raw);evidence["files_inspected"]=1
     else:evidence["status"]="HTML_NOT_PARSED"
     inspected.append(evidence)
    result["samples"]=inspected;result["status"]="SAMPLED"
   except Exception as e:result["status"]="ERROR";result["error"]=type(e).__name__+":"+str(e)[:200]
   out.append(result)
   print(json.dumps({"year":y,"month":m,"source":source,"status":result["status"],"files":result.get("file_count")},ensure_ascii=False),flush=True)
 report={"version":"C1-v093-RAW-CONTENT-SAMPLE-001","date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"tested_periods":MONTHS,"samples":out,
  "recommended_policy":{"primary":{"TWSE":["listed daily price","listed institutionals","listed financing and securities lending","listed corporate actions"],"TPEx":["otc daily price","otc institutionals","otc financing and securities lending"],"MOPS":["monthly revenue","quarterly financial statements and announcement provenance"]},"FinMind":["only gaps after official source-by-date-by-stock-by-field QA","FinMind-only fields after definition verification","selective cross-source golden checks"],"do_not_fetch_all_sources_indiscriminately":True},
  "limits":["Sampling at most two files per source and first two JSON members; NOT yearwide coverage","Zip entries and API request success are not validated stock/date/field coverage","No PIT or numeric cross-check","No source re-fetch; existing raw untouched"]}
 folder=d.folder(REPORT_PARENT,"V093_OFFICIAL_FIRST_FINMIND_DELTA_TEST")
 d.put(folder,"2024_2026_sampled_content_audit.json",(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"folder_id":folder,"checked":len(out),"sampled":sum(x["status"]=="SAMPLED" for x in out),"errors":[{"year":x["year"],"month":x["month"],"source":x["source"],"error":x.get("error")} for x in out if x["status"]=="ERROR"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
