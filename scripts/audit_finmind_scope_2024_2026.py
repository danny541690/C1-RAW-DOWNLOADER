"""C1 v0.93: read-only three-year RAW archive and FinMind scope audit.
Never claims stock-universe or PIT completeness from merely existing files.
"""
import collections,csv,datetime,hashlib,io,json,os,re,zipfile
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
REPORT_ROOT="1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit"
YEARS=(2024,2025,2026)
SOURCES=("TWSE","TPEx","MOPS","FinMind","TDCC","XQ")
def list_all(d,parent):
 out=[];page=None
 while True:
  request=d.api.files().list(q="'"+parent+"' in parents and trashed = false",pageSize=1000,fields="nextPageToken,files(id,name,mimeType,size)",pageToken=page)
  p=d.call(lambda:request);out+=p.get("files",[]);page=p.get("nextPageToken")
  if not page:break
 return out
def isdir(x):return x["mimeType"]=="application/vnd.google-apps.folder"
def inspect_zip(d,entry):
 result={"file":entry["name"],"size":int(entry.get("size",0)),"kind":"zip","members":[],"inspection":"SKIPPED_LARGE"}
 if int(entry.get("size",0))>30000000:return result
 try:
  content=d.call(lambda:d.api.files().get_media(fileId=entry["id"]))
  z=zipfile.ZipFile(io.BytesIO(content))
  names=z.namelist()
  result["member_count"]=len(names);result["member_names_sample"]=names[:50]
  result["crc_bad_member"]=z.testzip()
  result["inspection"]="ZIP_STRUCTURE_READ"
  if "FinMind" in entry["name"] and len(names)<=1200:
   # Filename only: do not infer the universe from source names alone.
   result["candidate_stock_ids_in_member_paths"]=sorted(set(re.findall(r"(?<![0-9])(?:[1-9][0-9]{3})(?![0-9])"," ".join(names))))[:80]
 except Exception as ex:result["inspection"]="ZIP_READ_FAILED";result["error"]=str(ex)[:180]
 return result
def main():
 d=Drive(service());root={x["name"]:x for x in list_all(d,ROOT) if isdir(x)}
 ledger=[];samples=[];issues=[]
 for year in YEARS:
  node=root.get(str(year))
  if not node:
   issues.append({"year":year,"error":"NO_YEAR_DIRECTORY"})
   continue
  subs={x["name"]:x for x in list_all(d,node["id"]) if isdir(x)}
  for source in SOURCES:
   sn=subs.get(source)
   if not sn:
    ledger.append({"year":year,"source":source,"month":None,"archives":0,"note":"SOURCE_FOLDER_MISSING"})
    continue
   months={x["name"]:x for x in list_all(d,sn["id"]) if isdir(x)}
   for mo in range(1,13):
    mn=f"{year}-{mo:02d}";mdir=months.get(mn)
    if not mdir:
     ledger.append({"year":year,"source":source,"month":mn,"archives":0,"note":"MONTH_FOLDER_MISSING"})
     continue
    entries=[x for x in list_all(d,mdir["id"]) if not isdir(x)]
    suffix=collections.Counter((x["name"].rsplit(".",1)[-1].lower() if "." in x["name"] else "none") for x in entries)
    ledger.append({"year":year,"source":source,"month":mn,"archives":len(entries),"file_types":dict(suffix),"bytes_in_drive":sum(int(x.get("size",0)) for x in entries),"note":"FILES_EXIST_NOT_COVERAGE_CERTIFICATION"})
    if source=="FinMind" and mo in (1,9,12):
     for x in entries[:4]:
      if x["name"].lower().endswith(".zip"):samples.append({"year":year,"source":source,"month":mn,**inspect_zip(d,x)})
 report={"version":"C1-v0.93-FINMIND-RAW-SCOPE-AUDIT-001","audit_time_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"years":YEARS,"sources":SOURCES,"ledger":ledger,"sampled_zip_inspections":samples,"issues":issues,"caveats":["File presence does not imply market-wide or dataset coverage","FinMind 2024 known workflow is price sample 2330 only","2025/2026 scope inferred from inspected archive filenames only, not whole-stock universe","PIT and numeric QA remain blocked","No data modified or downloaded from sources"],"verification":"METADATA_AND_SAMPLED_ZIP_ONLY"}
 folder=d.folder(REPORT_ROOT,"V093_FINMIND_COVERAGE_AUDIT_2024_2026")
 raw=(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode()
 d.put(folder,"three_year_raw_inventory.json",raw,"application/json",overwrite=True)
 buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=["year","source","month","archives","file_types","bytes_in_drive","note"]);w.writeheader()
 for x in ledger:w.writerow({k:json.dumps(x[k],ensure_ascii=False) if k=="file_types" and k in x else x.get(k,"") for k in w.fieldnames})
 d.put(folder,"three_year_source_month_ledger.csv",buf.getvalue().encode("utf-8-sig"),"text/csv",overwrite=True)
 byyear={}
 for y in YEARS:
  a=[x for x in ledger if x["year"]==y]
  byyear[str(y)]={"file_entries":sum(x["archives"] for x in a),"months_with_files":sum(x["archives"]>0 for x in a),"by_source":{s:sum(x["archives"] for x in a if x["source"]==s) for s in SOURCES}}
 print(json.dumps({"folder_id":folder,"summary":byyear,"sample_inspections":[{"year":x["year"],"month":x["month"],"name":x["file"],"inspection":x["inspection"],"member_count":x.get("member_count"),"member_sample":x.get("member_names_sample",[])[:8]} for x in samples],"issues":issues},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
