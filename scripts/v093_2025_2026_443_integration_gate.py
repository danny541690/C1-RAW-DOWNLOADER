"""C1 v0.93 2025/2026 integration preflight: real Drive inventory + 443-ID audit.
Read-only source inspection. No fake indicator computation, numeric/PIT success claims.
"""
import collections,datetime,json,re
from scripts.annual_actual_firstpass import Drive,service
ROOT="1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn"
SPEC_ID="1aki0gf1ROiiFbJQM6j2yOoAaqjEaq0C1"
REPORT_PARENT="1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit"
SOURCES=("TWSE","TPEx","MOPS","FinMind","TDCC","XQ")
def listing(d,parent):
 out=[];page=None
 while True:
  response=d.call(lambda:d.api.files().list(q="'"+parent+"' in parents and trashed=false",fields="nextPageToken,files(id,name,mimeType,size)",pageSize=1000,pageToken=page))
  out.extend(response.get("files",[]));page=response.get("nextPageToken")
  if not page:return out
def sub(d,parent,name):
 rows=[a for a in listing(d,parent) if a["name"]==name and a["mimeType"]=="application/vnd.google-apps.folder"]
 return rows[0]["id"] if len(rows)==1 else None
def main():
 d=Drive(service())
 base=listing(d,ROOT)
 result={"version":"C1-0.93-2025-2026-INTEGRATION-GATE-001","generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "check":"2025/2026 raw inventory and 443-ID registry linkage; NOT 443 numeric calculation","years":{},"registry":{},"gates":{},"blockers":[]}
 for year in (2025,2026):
  yf=sub(d,ROOT,str(year));info={"year_folder_found":bool(yf),"sources":{}}
  for source in SOURCES:
   folder=sub(d,yf,source) if yf else None
   if not folder:
    info["sources"][source]={"folder_found":False,"months_with_files":[],"archive_count":0};continue
   monthly=[x for x in listing(d,folder) if re.fullmatch(r"20(?:25|26)-(?:0[1-9]|1[0-2])",x["name"]) and x["mimeType"]=="application/vnd.google-apps.folder"]
   rec={"folder_found":True,"months_with_files":[],"month_file_counts":{},"archive_count":0,"bytes":0,"extension_counts":{}}
   ext=collections.Counter()
   for m in monthly:
    fs=[x for x in listing(d,m["id"]) if x["mimeType"]!="application/vnd.google-apps.folder"]
    if fs:rec["months_with_files"].append(m["name"])
    rec["month_file_counts"][m["name"]]=len(fs)
    rec["archive_count"]+=len(fs);rec["bytes"]+=sum(int(x.get("size",0)) for x in fs)
    ext.update(x["name"].rsplit(".",1)[-1].lower() for x in fs)
   rec["months_with_files"].sort();rec["extension_counts"]=dict(ext)
   info["sources"][source]=rec
  result["years"][str(year)]=info
 try:
  raw=d.call(lambda:d.api.files().get_media(fileId=SPEC_ID)).decode("utf-8-sig")
  ids=[];groups=collections.Counter();statuses=collections.Counter()
  for line in raw.splitlines():
   if not line.startswith("|"):continue
   cols=[x.strip() for x in line.strip().strip("|").split("|")]
   if len(cols)<7 or cols[0] in ("ID","---") or not re.fullmatch(r"[A-Za-z][A-Za-z_0-9]*",cols[0]):continue
   ids.append(cols[0]);groups[cols[2]]+=1;statuses[cols[5]]+=1
  dup={k:n for k,n in collections.Counter(ids).items() if n>1}
  result["registry"]={"source_file_id":SPEC_ID,"metric_ids_read":len(ids),"unique_metric_ids":len(set(ids)),"duplicates":dup,"category_counts":dict(groups),"existing_evidence_status_counts":dict(statuses),"validated_numeric_count":0,"interpretation":"source dependency report only, not verified formula engine"}
 except Exception as e:
  result["registry"]={"status":"READ_FAILED","error":str(e)[:240]}
 result["gates"]={"raw_folder_inventory":"CHECKED","source_payload_numeric_validation":"NOT_PERFORMED","standardized_schema":"NOT_DEPLOYMENT_VERIFIED","443_formula_execution":"NOT_DEPLOYMENT_VERIFIED","announcement_PIT":"NOT_VERIFIED","production_ready":False}
 result["blockers"]=["Previous 443-indicator report explicitly states additional gaps outside 57 master/broker metrics","Financial statements, TDCC weekly holdings, historical sector membership, free float and warmup history lack full proof","Neither file existence nor a 443-ID registry implies 443-computation availability","Original four-source archives have not been fully parsed for stock-date-field complete coverage","Source-to-02_STANDARD and 443 derivation jobs not established as deployed or production passing"]
 dest=d.folder(REPORT_PARENT,"V093_2025_2026_443_INTEGRATION_GATE")
 d.put(dest,"2025_2026_443_registry_raw_linkage_preflight.json",(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode(),"application/json",overwrite=True)
 print(json.dumps({"report_folder":dest,"registry":result["registry"],"year_summary":{y:{s:{"files":v["archive_count"],"months":len(v["months_with_files"])} for s,v in z["sources"].items()} for y,z in result["years"].items()},"production_ready":False},ensure_ascii=False),flush=True)
 if result["registry"].get("unique_metric_ids")!=443:raise ValueError("443_REGISTRY_MISMATCH")
if __name__=="__main__":main()
