#!/usr/bin/env python3
"""2026 Jan-07 Nov v0.95 one-run real Drive inventory + stage-coverage and lineage gate.

This script inspects actual Drive metadata, old acceptance receipts, and governance
contracts. It does NOT download raw securities data or compute unverifiable Gold.
May be combined with a separately bounded, real-data BSG replay in one CI job.
"""
import csv,datetime as dt,hashlib,json,os,pathlib,re,sys,time,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/"annual_2026"
MONTHS=tuple("2026-%02d"%m for m in range(1,12))
CUTOFF="2026-11-07"
SOURCES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
BRONZE_ROOTS={"TWSE":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE",
"TPEx":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG",
"MOPS":"1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI",
"TDCC":"1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-",
"TAIFEX":"1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz",
"NDC":"1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-"}
FOLDER="application/vnd.google-apps.folder"
M_RE=re.compile(r"(?<!\d)2026[-_]?((?:0[1-9])|10|11)(?!\d)")
MAX_OBJECTS_PER_ROOT=4800
MAX_FOLDERS_PER_ROOT=100
MAX_DEPTH=3
def ym(segments):
 found=set()
 for segment in segments:
  for match in M_RE.finditer(segment):found.add("2026-"+match.group(1))
 return sorted(found)
def loadcsv(p):
 with (ROOT/p).open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def service():
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 cred=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 cred.refresh(Request())
 return build("drive","v3",credentials=cred,cache_discovery=False)
def ls(s,folder):
 token=None;rows=[]
 while True:
  last=None
  for attempt in range(3):
   try:
    d=s.files().list(q="'"+folder+"' in parents and trashed=false",
      fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime,parents)",
      pageSize=500,pageToken=token).execute()
    break
   except Exception as exc:
    last=exc
    if attempt==2:raise
    time.sleep(2**attempt)
  if d.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SEARCH")
  rows.extend(d.get("files",[]))
  if len(rows)>2000:raise RuntimeError("SINGLE_FOLDER_BUDGET_EXCEEDED")
  token=d.get("nextPageToken")
  if not token:return rows
def scan(s,stage,source,root):
 queue=collections.deque([(root,(),0)])
 data=[];folders=0;truncated=False;error=None
 while queue:
  fid,path,depth=queue.popleft()
  if folders>=MAX_FOLDERS_PER_ROOT or len(data)>=MAX_OBJECTS_PER_ROOT:
   truncated=True;break
  try:items=ls(s,fid)
  except Exception as exc:
   error={"type":type(exc).__name__,"msg":str(exc)[:130]};break
  folders+=1
  for x in items:
   parts=path+(x["name"],)
   months=ym(parts)
   if months:
    data.append({"opaque":hashlib.sha256(x["id"].encode()).hexdigest()[:18],
     "name_digest":hashlib.sha256(x["name"].encode()).hexdigest()[:16],
     "stage":stage,"source":source,"months":months,
     "is_folder":x.get("mimeType")==FOLDER,"size":x.get("size"),
     "drive_has_md5":bool(x.get("md5Checksum"))})
   if x.get("mimeType")==FOLDER and depth<MAX_DEPTH:
    # Bounded traversal of 2026 paths and intermediate source/category folders.
    if not months or any(m in MONTHS for m in months):queue.append((x["id"],parts,depth+1))
   if len(data)>=MAX_OBJECTS_PER_ROOT:truncated=True;break
  if truncated:break
 return data,{"stage":stage,"source":source,"folders_listed":folders,
  "candidate_objects":len(data),"truncated":truncated,
  "unvisited_folders":len(queue),"error":error}
def evaluate(rows,scans,contracts,registry,manifest,checkpoints,prior,canary=None):
 statuses=collections.Counter(x.get("status") for x in contracts)
 coverage={m:{src:{"candidate_files":0,"candidate_folders":0,
  "official_expected_units":None,"verified_month_complete":False,
  "source_status":"PRESENT_UNVERIFIED" if False else "UNKNOWN"} for src in SOURCES} for m in MONTHS}
 layers={m:{"BRONZE":0,"SILVER":0,"GOLD":0,"STAGING":0,"UNKNOWN":0} for m in MONTHS}
 ambiguous=0
 for r in rows:
  if len(r["months"])!=1:ambiguous+=1;continue
  m=r["months"][0]
  layers[m][r["stage"] if r["stage"] in layers[m] else "UNKNOWN"]+=int(not r["is_folder"])
  if r["stage"]=="BRONZE" and r["source"] in SOURCES:
   key="candidate_folders" if r["is_folder"] else "candidate_files"
   coverage[m][r["source"]][key]+=1
 for m in MONTHS:
  for src in SOURCES:
   cell=coverage[m][src]
   cell["source_status"]="PRESENT_UNVERIFIED" if cell["candidate_files"] else "NOT_LOCATED_UNPROVEN_MISSING"
 official=[{"month":m,"source":src,"status":coverage[m][src]["source_status"],
   "dataset_identity":"UNKNOWN","expected_eligible_units":None,"download_allowed":False,
   "silver_allowed":False,"gold_pit_allowed":False} for m in MONTHS for src in SOURCES]
 prior_scoped=[x for x in prior["immutable_receipts"] if x.get("key","").split("|")[0] in MONTHS]
 canary_result={"status":"NOT_RUN","days":{}}
 if canary:
  canary_result={"status":"PASS_SCOPED_REUSED_NO_PIT" if not canary.get("rejected") and canary.get("completed") else "BLOCKED",
   "days":{key:{"source_rows":r["rows"],"descriptive_gold_rows":r["gold_rows"],
     "numeric_exception_rows":r["native_numeric_exception_rows"],"actions":r["actions"],
     "acquisition":r["acquisition"],"official_live_http":r["official_http_currently_available"],
     "bronze_sha256":r["sha256"],"pit":False,
     "bronze_silver_gold_lineage_scoped":bool(r.get("bronze_id") and r.get("silver_id") and r.get("gold_id"))}
     for key,r in canary.get("completed",{}).items()}}
 report={"schema":"JARVIS_C1_V095_2026_JAN_TO_NOV_07_ACTUAL_STATE_V1",
  "date_start":"2026-01-01","cutoff":CUTOFF,"calendar_months":len(MONTHS),
  "source_month_cells":len(official),"inspection_status":"BOUNDED_METADATA_PARTIAL" if all(not x["error"] and not x["truncated"] for x in scans) else "BLOCKED_INCOMPLETE_INVENTORY",
  "object_candidates":len(rows),"ambiguous_month_path_count":ambiguous,
  "coverage_source_month":coverage,"stage_candidate_files_by_month":layers,
  "eligible_dataset_denominator":None,"verified_2026_full_year_complete":False,
  "scoped_prior_receipts":len(prior_scoped),"current_canary":canary_result,
  "governance":{"manifest_rows":len(manifest),"checkpoint_rows":len(checkpoints),
   "source_registry_rows":len(registry),"source_registry_pending":sum(x.get("dataset_contract_status")=="PENDING" for x in registry),
   "dataset_contract_rows":len(contracts),"dataset_contract_status":dict(statuses),
   "production_ready_contracts":sum(x.get("status")=="READY_FOR_BRONZE_PRODUCTION" for x in contracts)},
  "source_data_downloaded":0,"silver_new_conversions":0,"gold_pit_new_computations":0,
  "all_year_tier_release":False,"official_source_missing_proven":0,
  "production_cas_proven":False,"flags_unchanged":True,
  "discovery_scans":scans,
  "blocking_causes":[
   "39 source dataset contracts lack signed native schema/availability evidence",
   "GitHub formal manifest/checkpoints have no committed rows",
   "No official expected-day/security denominators; absence in Drive is not proven source absence",
   "No actual cross-runner CAS/fenced production writer; reusable existing artifacts are not a fresh-write proof",
   "No full-year Silver transform schedule/adapters for every dataset",
   "443 Gold formula PIT and historic announcement timing not certified",
   "Bounded Drive depth cannot prove exhaustive file presence; metadata MD5 is not SHA256"
  ],"release_decision":"BLOCK_ALL_YEAR_PRODUCTION_NOT_A_COMPLETION_CLAIM"}
 return report,official
def main():
 config=json.loads((ROOT/"config/v095_ultimate_r1.json").read_text())
 flags=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 rows=[];scans=[];s=service()
 for src,fid in BRONZE_ROOTS.items():
  sub,scan_info=scan(s,"BRONZE",src,fid);rows+=sub;scans.append(scan_info)
 for stage,root in (("SILVER",config["drive"]["silver_root"]),("GOLD",config["drive"]["gold_root"])):
  sub,x=scan(s,stage,"UNKNOWN",root);rows+=sub;scans.append(x)
 root=config["drive"]["c1_root"]
 try:
  found=[x for x in ls(s,root) if x.get("mimeType")==FOLDER and x["name"]=="10_INGEST_STAGING"]
  if len(found)==1:
   sub,x=scan(s,"STAGING","UNKNOWN",found[0]["id"]);rows+=sub;scans.append(x)
  else:scans.append({"stage":"STAGING","error":{"type":"STAGING_ROOT_NOT_UNIQUE"},"truncated":False})
 except Exception as e:scans.append({"stage":"STAGING","error":{"type":type(e).__name__},"truncated":False})
 canary=None
 p=ROOT/"ultimate_r1/november_latest_bsg.json"
 if p.exists():canary=json.loads(p.read_text())
 prior=json.loads((ROOT/"governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json").read_text())
 rep,items=evaluate(rows,scans,
  loadcsv("governance/v095/DATASET_CONTRACTS.csv"),
  loadcsv("governance/v095/SOURCE_REGISTRY.csv"),
  loadcsv("governance/v095/MANIFEST_INDEX.csv"),
  loadcsv("governance/v095/CHECKPOINTS.csv"),prior,canary)
 OUT.mkdir(exist_ok=True)
 (OUT/"report.json").write_text(json.dumps(rep,ensure_ascii=False,indent=2)+"\n")
 with (OUT/"source_month_status.csv").open("w",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
 (OUT/"sanitized_file_index.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps({k:rep[k] for k in ("inspection_status","object_candidates","source_month_cells",
  "scoped_prior_receipts","governance","current_canary","release_decision")},ensure_ascii=False))
 return 0 if rep["inspection_status"].startswith("BOUNDED") else 2
if __name__=="__main__":sys.exit(main())
