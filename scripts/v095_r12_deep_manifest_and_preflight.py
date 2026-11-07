#!/usr/bin/env python3
"""R12 2026/09-11 Drive metadata traversal and all-issue fail-closed dispatch preflight.

Zero live market data requests and zero Drive writes. No source completeness claims.
Time-aware, bounded per root. Traversal errors produce partial/blocked status.
"""
import collections,datetime as dt,hashlib,json,os,pathlib,re,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
MONTHS=("2026-09","2026-10","2026-11")
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
FOLDER_MIME="application/vnd.google-apps.folder"
OUT=ROOT/"r12_deep_manifest"
MAX_FOLDERS_PER_ROOT=110
MAX_OBJECTS_PER_ROOT=3200
MAX_DEPTH=4
MONTH_PATTERN=re.compile(r"(?<!\d)2026[-_]?(09|10|11)(?!\d)")
def month_of_path(path):
 # Process all path components; a year-month folder may be above an unlabelled file.
 months=set()
 for component in path:
  m=MONTH_PATTERN.search(component)
  if m: months.add("2026-"+m.group(1))
 return sorted(months)
def official_status(dataset,month,first_published_at=None,asof_utc="2026-11-07T00:00:00Z"):
 if first_published_at:
  try:
   p=dt.datetime.fromisoformat(first_published_at.replace("Z","+00:00"))
   a=dt.datetime.fromisoformat(asof_utc.replace("Z","+00:00"))
   if p>a:return "NOT_YET_PUBLISHED"
  except (ValueError,TypeError):return "PUBLICATION_TIMESTAMP_INVALID"
 if dataset=="TDCC_WEEKLY_OWNERSHIP" and month<"2008-07":return "NOT_APPLICABLE_TO_SERIES"
 if dataset=="TPEX_DAILY_MARKET" and month<"2003-08":return "LEGACY_DATASET_DISCOVERY_REQUIRED"
 return "EXPECTED_DENOMINATOR_UNKNOWN"
def scope_preflight(config,flags):
 items=config["issues"];ids={x["id"] for x in items}
 return {"schema":"JARVIS_V095_R12_PRELAUNCH_POLICY_V1",
  "error_id_count":len(ids),"required_issues_present":len(ids)==12,
  "security_flags_safe":flags.get("BULK_COPY_APPROVED") is False and flags.get("RELEASE_APPROVED") is False,
  "finance_backer_blocked_until_licensed":config["rules"]["license_and_finmind_access"]=="ONLY_ENABLED_AFTER_RIGHTS_VERIFIED",
  "gold_requires_pit":config["architecture"]["release_layers"]["gold"]=="VALID_FORMULA_PLUS_POINT_IN_TIME_LINEAGE",
  "source_adapters_formally_ready":False,
  "writer_fencing_formally_ready":False,
  "ready_to_download":False,
  "allowed_test":"BOUNDED_METADATA_RECONCILIATION_ONLY"}
def identity(r):
 return (r["file_id"],r["stage"])
def analyze(objects,scans,issues,plan,flags):
 dups=collections.defaultdict(list);monthly=collections.defaultdict(lambda:collections.defaultdict(lambda:{"files":0,"folders":0,"source_contract":"UNKNOWN"}))
 ambiguities=[];stage_rows=collections.Counter();by_id={}
 for r in objects:
  k=r["file_id"]
  if k in by_id and by_id[k]["logical_path"]!=r["logical_path"]:dups[k].append(r["logical_path"])
  by_id.setdefault(k,r)
  stage_rows[r["stage"]]+=1
  m=r["observed_months"]
  if len(m)>1:ambiguities.append({"id":k,"months":m,"reason":"MULTIPLE_MONTH_TOKENS"})
  for month in m:
   s=r["source"]
   monthly[month][s]["files"]+=int(not r["is_folder"])
   monthly[month][s]["folders"]+=int(r["is_folder"])
 pre=scope_preflight(plan,flags)
 has_errors=any(x.get("error") for x in scans)
 truncated=any(x.get("truncated") for x in scans)
 report={"schema":"JARVIS_V095_R12_DEEP_MANIFEST_READONLY_V1",
  "asof":"2026-11-07","months":list(MONTHS),"scan_status":
    "BLOCKED_INCOMPLETE_TRAVERSAL" if (has_errors or truncated) else "PASS_BOUNDED_TRAVERSAL_NOT_COMPLETE_SOURCE_CONTRACT",
  "objects_examined":len(objects),"unique_drive_file_ids":len(by_id),"stage_counts":dict(stage_rows),
  "duplicate_path_ids":dict(dups),"ambiguous_month_token_objects":ambiguities[:100],
  "month_source_observations":{m:dict(monthly[m]) for m in MONTHS},
  "scanned_roots":scans,"source_expected_dataset_counts":None,"missing_official_dataset_units":None,
  "source_data_downloads":0,"existing_valid_data_rechecked":0,"drive_writes":0,
  "bronze_release":False,"silver_release":False,"gold_pit_release":False,
  "preflight":pre,"open_root_issues":[x["id"] for x in plan["issues"]],
  "notes":[
   "File metadata and path-based month classification are candidates, not dataset identity.",
   "Not scanning outside declared roots and depth; missing from index cannot imply source missing.",
   "MD5 metadata is not original SHA-256; cannot certify reused content from metadata.",
   "True source-ready tasks require independently verified official publication and native byte SHA.",
   "Drive API incompleteSearch, truncated lists or scan error blocks missing determination."],
  "t2_write_gate":"BLOCKED_NOT_PROVEN"}
 return report
def api():
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 cred=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 cred.refresh(Request())
 return build("drive","v3",credentials=cred,cache_discovery=False)
def ls(s,folder):
 page=None;rows=[]
 while True:
  result=None
  for attempt in range(3):
   try:
    result=s.files().list(q="'"+folder+"' in parents and trashed=false",
      fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime,parents)",
      pageSize=500,pageToken=page).execute()
    break
   except Exception:
    if attempt==2:raise
    time.sleep(2**attempt)
  if result.get("incompleteSearch"):raise ValueError("DRIVE_INCOMPLETE_SEARCH")
  rows+=result.get("files",[])
  if len(rows)>1100:raise ValueError("DRIVE_PER_FOLDER_BOUND_EXCEEDED")
  page=result.get("nextPageToken")
  if not page:break
 return rows
def traverse(s,stage,source,root_id):
 queue=collections.deque([(root_id,(),0)])
 rows=[];folders=0;trunc=False;error=None
 while queue:
  folder,path,depth=queue.popleft()
  if folders>=MAX_FOLDERS_PER_ROOT or len(rows)>=MAX_OBJECTS_PER_ROOT:
   trunc=True;break
  folders+=1
  try:children=ls(s,folder)
  except Exception as e:
   error={"type":type(e).__name__,"description":str(e)[:160],"folder":folder}
   break
  for f in children:
   subpath=path+(f["name"],)
   mo=month_of_path(subpath)
   rows.append({"file_id":f["id"],"name":f["name"],"stage":stage,"source":source,
    "logical_path":"/".join(subpath),"observed_months":mo,
    "is_folder":f.get("mimeType")==FOLDER_MIME,"size_bytes":f.get("size"),
    "drive_md5_not_sha256":f.get("md5Checksum"),"parent_id":folder})
   if f.get("mimeType")==FOLDER_MIME and depth<MAX_DEPTH:
    # Target months when known, or unlabeled first-level source/market/category folders.
    # Unknown paths are traversed boundedly for discovery, not inferred as complete.
    if (not mo or any(m in MONTHS for m in mo)):queue.append((f["id"],subpath,depth+1))
   if len(rows)>=MAX_OBJECTS_PER_ROOT:trunc=True;break
  if trunc:break
 return rows,{"stage":stage,"source":source,"root_id":root_id,"folders_listed":folders,
  "objects_seen":len(rows),"remaining_queued_folders":len(queue),"truncated":trunc,"error":error}
def main():
 plan=json.loads((ROOT/"config/v095_r11_improvement_and_pilot_plan.json").read_text())
 flags=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 cfg=json.loads((ROOT/"config/v095_ultimate_r1.json").read_text())
 roots=cfg["drive"]
 from v095_r11_t1_three_month_manifest import detect_month
 bronze={
  "TWSE":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE",
  "TPEx":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG",
  "MOPS":"1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI",
  "TDCC":"1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-",
  "TAIFEX":"1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz",
  "NDC":"1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-"}
 targets=[("BRONZE",k,v) for k,v in bronze.items()]
 targets+= [("SILVER","UNKNOWN",roots["silver_root"]),("GOLD","UNKNOWN",roots["gold_root"])]
 s=api()
 try:
  first=ls(s,roots["c1_root"])
  matches=[x for x in first if x.get("mimeType")==FOLDER_MIME and x.get("name")=="10_INGEST_STAGING"]
  if len(matches)==1:targets.append(("STAGING","UNKNOWN",matches[0]["id"]))
  else:targets.append(("STAGING","UNKNOWN","MISSING_OR_AMBIGUOUS"))
 except Exception:targets.append(("STAGING","UNKNOWN","MISSING_OR_AMBIGUOUS"))
 allrows=[];scans=[]
 for stage,source,root in targets:
  if root=="MISSING_OR_AMBIGUOUS":
   scans.append({"stage":stage,"source":source,"truncated":False,
     "error":{"type":"STAGING_ROOT_UNRESOLVED"}})
   continue
  rows,record=traverse(s,stage,source,root)
  allrows+=rows;scans.append(record)
 report=analyze(allrows,scans,[],plan,flags)
 OUT.mkdir(exist_ok=True)
 (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
 (OUT/"metadata_index.json").write_text(json.dumps(allrows,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:report[k] for k in ("scan_status","objects_examined","unique_drive_file_ids",
  "stage_counts","source_data_downloads","drive_writes","source_expected_dataset_counts",
  "t2_write_gate")},ensure_ascii=False),flush=True)
 if report["scan_status"].startswith("BLOCKED_"):return 2
 return 0
if __name__=="__main__":sys.exit(main())
