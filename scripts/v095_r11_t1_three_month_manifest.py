#!/usr/bin/env python3
"""JARVIS v0.95 R11 T1: read-only bounded Drive metadata reconciliation.

No official HTTP market downloads, no raw file downloads, no Drive writes.
Drive metadata MD5 is not a SHA256 receipt and must never upgrade QA/PIT.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,re,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
MONTHS=("2026-09","2026-10","2026-11")
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
OUT=ROOT/"r11_t1_manifest"
FOLDER="application/vnd.google-apps.folder"
def load(p):return json.loads((ROOT/p).read_text())
def metadata_client():
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive.metadata.readonly"])
 c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def files_in(s,parent,max_files=1200):
 out=[];page=None
 while True:
  req=s.files().list(q="'"+parent+"' in parents and trashed=false",
    fields="nextPageToken,files(id,name,mimeType,size,md5Checksum,modifiedTime,parents)",
    pageSize=500,pageToken=page)
  response=None
  for attempt in range(3):
   try:response=req.execute();break
   except Exception:
    if attempt==2:raise
    time.sleep(2**attempt)
  out.extend(response.get("files",[]))
  if len(out)>max_files:raise RuntimeError("T1_PER_FOLDER_LIMIT_EXCEEDED")
  page=response.get("nextPageToken")
  if not page:return out
def detect_month(x):
 text=x.upper()
 p=re.search(r"(?<!\d)2026[-_]?([09][0-9])(?!\d)",text)
 if not p:return None
 val=p.group(1)
 return "2026-"+val if val in ("09","10","11") else None
def analyse(lookups,prior,config):
 """lookups: list of bounded Drive metadata row dicts, no downloaded bytes."""
 collisions=[];seen=set()
 stats={m:{s:{"canonical_items":0,"alternate_path_candidates":0,"known_sha_receipts":0,
   "stage_state":"UNVERIFIED_DATASET_COVERAGE"} for s in SOURCES} for m in MONTHS}
 for row in lookups:
  if row["id"] in seen:continue
  seen.add(row["id"])
  m=row.get("month")
  if m not in MONTHS:continue
  source=row.get("source")
  if source not in SOURCES:continue
  key="canonical_items" if row.get("canonical") else "alternate_path_candidates"
  stats[m][source][key]+=1
 prior_scoped=collections.Counter()
 for receipt in prior["immutable_receipts"]:
  key=receipt["key"]
  p=key.split("|")
  if len(p)<2 or p[1] not in SOURCES:continue
  if p[0] in MONTHS:prior_scoped[(p[0],p[1])]+=1
 for m in MONTHS:
  for s in SOURCES:stats[m][s]["known_sha_receipts"]=prior_scoped.get((m,s),0)
 by_month={m:{"canonical_source_cells_with_files":sum(stats[m][s]["canonical_items"]>0 for s in SOURCES),
      "alternate_cells_with_candidates":sum(stats[m][s]["alternate_path_candidates"]>0 for s in SOURCES),
      "dataset_expected_denominator":None,"market_data_verified_complete":False} for m in MONTHS}
 report={"schema":"JARVIS_V095_R11_T1_READONLY_MANIFEST_V1",
   "months":list(MONTHS),"source_count":6,"source_month_cells":18,
   "metadata_rows_collected":len(lookups),"unique_metadata_object_ids":len(seen),
   "month_source_matrix":stats,"summary_by_month":by_month,
   "prior_scoped_accepted_receipts":len(prior["immutable_receipts"]),
   "scope_note":"Metadata object listing only; R7 prior SHA is historic limited receipt, not current raw readback.",
   "drive_md5_is_not_sha256":True,"no_market_data_downloaded":True,
   "no_drive_objects_modified":True,"ready_download_tasks":0,"true_missing_partitions":None,
   "pit_certified":False,"production_release_approved":False,
   "known_holes":[
     "R10 canonical folder file count is not official expected denominator",
     "No cross-folder reference can be inferred solely from name/date",
     "Drive MD5 metadata cannot replace original data SHA256",
     "Staging candidate files are not automatically approved Bronze",
     "More than max folder objects causes HARD_FAIL not partial success",
     "G3 PIT and full 443 formula graph not assessed by metadata scan"
   ]}
 return report
def main():
 flags=load("governance/v095/PHASE1_FLAGS.json")
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 p=load("config/v095_r11_improvement_and_pilot_plan.json")
 prior=load("governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json")
 roots=load("config/v095_ultimate_r1.json")["drive"]
 src={
  "TWSE":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE",
  "TPEx":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG",
  "MOPS":"1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI",
  "TDCC":"1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-",
  "TAIFEX":"1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz",
  "NDC":"1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-"
 }
 s=metadata_client()
 rows=[];scanned=[];discovery_errors=[]
 for source,parent in src.items():
  try:
   top=files_in(s,parent)
   scanned.append({"root":"BRONZE_"+source,"folder_id":parent,"children":len(top)})
   for entry in top:
    if entry.get("mimeType")!=FOLDER:continue
    m=detect_month(entry["name"])
    if m not in MONTHS:continue
    children=files_in(s,entry["id"])
    scanned.append({"root":"BRONZE_"+source+"/"+m,"folder_id":entry["id"],"children":len(children)})
    for x in children:
     if x.get("mimeType")==FOLDER:continue
     rows.append({"id":x["id"],"name":x["name"],"source":source,"month":m,
      "stage":"BRONZE","canonical":True,"size":x.get("size"),"md5":x.get("md5Checksum"),"folder":entry["id"]})
  except Exception as e:discovery_errors.append({"source":source,"type":type(e).__name__,"error":str(e)[:160]})
 # Metadata-only sample of designated October-November staging and layer roots; never broad crawl.
 for stage,rootkey in (("STAGING","c1_root"),("SILVER","silver_root"),("GOLD","gold_root")):
  parent=roots[rootkey]
  try:
   entries=files_in(s,parent,max_files=1200)
   scanned.append({"root":stage,"folder_id":parent,"children":len(entries)})
   for x in entries:
    if x.get("mimeType")==FOLDER:continue
    m=detect_month(x["name"])
    if m not in MONTHS:continue
    # Unknown source remains unattributed; never guess dataset by file name alone.
    rows.append({"id":x["id"],"name":x["name"],"source":"UNKNOWN",
     "month":m,"stage":stage,"canonical":False,"size":x.get("size"),
     "md5":x.get("md5Checksum"),"folder":parent})
  except Exception as e:discovery_errors.append({"source":stage,"type":type(e).__name__,"error":str(e)[:160]})
 report=analyse(rows,prior,p)
 report.update(scanned_folders=scanned,read_errors=discovery_errors,
   "scan_status":"PASS_METADATA_PARTIAL_COVERAGE" if not discovery_errors else "BLOCKED_INCOMPLETE_METADATA_SCAN",
   "unattributed_stage_file_candidates":sum(r.get("source")=="UNKNOWN" for r in rows))
 OUT.mkdir(exist_ok=True)
 (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 (OUT/"metadata_index.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:report[k] for k in ("scan_status","metadata_rows_collected","unique_metadata_object_ids",
  "summary_by_month","unattributed_stage_file_candidates","read_errors","ready_download_tasks")},ensure_ascii=False))
 if discovery_errors:return 2
 return 0
if __name__=="__main__":sys.exit(main())
