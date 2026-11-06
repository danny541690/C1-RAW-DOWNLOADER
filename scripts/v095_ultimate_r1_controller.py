"""JARVIS v0.95 Ultimate R1 central scheduler: real Drive canary, durable gate.
For pilot this job is conservative: detects verified existing partitions, does NOT invent
six-source download adapters, does NOT promote PIT or open history when proof is missing.
"""
import concurrent.futures,datetime as dt,hashlib,io,json,os,pathlib,time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
ROOT=pathlib.Path("ultimate_r1");ROOT.mkdir(exist_ok=True)
CFG=json.loads(pathlib.Path("config/v095_ultimate_r1.json").read_text())
DRIVE=CFG["drive"];SOURCE_FOLDERS={"TWSE":"1I83nUMJjBEYJrUDj9zUDCvl4nfKEDvjE","TPEX":"15hlfRj8gTXsPpbRBZBxvRJrgTtZQT-IG","MOPS":"1ZeJyCmQg02pr9uSfMT67pNWqTaq7-EaI","TDCC":"1G4wpoeeWTTH-m6sWsT7-AArzY4Z4gzq-","TAIFEX":"1p5pXKgk3iN1ECvGdMosFP0eixvAVfIiz","NDC":"1n2VVxdsUKqmuru6qOUHW_vrU1HKk2CB-"}
SILVER_GOLD={"SILVER_TSE":"14U9bwJCipIOJvNhThliTaCBb9RSTu4Cz","SILVER_OTC":"1qHYWmIq13UUIdYil4RU5L3VRLpuQVBzk","SILVER_TDCC":"1ho4YDArOu8BwlhxyIIW0AXjvhfjF9t7r","GOLD_TSE":"1OtEVfGl83HTWnPgNYumRa0OY7BE0yBgI","GOLD_OTC":"1KUJ6FG6XMdGOpnOAiceAgE0xszTlZ0M6","GOLD_REVENUE":"1XWy7mCMqdGcJbF4owafoT6caLo3-MMyI"}
def sha(b):return hashlib.sha256(b).hexdigest()
def api():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def retry(fn):
 for i in range(4):
  try:return fn().execute()
  except (OSError,ConnectionError,TimeoutError):
   if i==3:raise
   time.sleep(min(15,2**i))
def list_files(s,p):
 out=[];token=None
 while True:
  x=retry(lambda:s.files().list(q="'"+p+"' in parents and trashed = false",fields="nextPageToken,files(id,name,mimeType,size,modifiedTime)",pageSize=1000,pageToken=token))
  out+=x.get("files",[]);token=x.get("nextPageToken")
  if not token:return out
def named(s,p,name):
 return [f for f in list_files(s,p) if f["name"]==name]
def save_bytes(s,parent,name,b,overwrite_if_changed=False):
 old=named(s,parent,name)
 if old:
  if len(old)!=1:raise ValueError("AMBIGUOUS_DRIVE_REPORT_"+name)
  oid=old[0]["id"]
  if sha(retry(lambda:s.files().get_media(fileId=oid)))==sha(b):return {"id":oid,"action":"UNCHANGED","sha":sha(b)}
  if overwrite_if_changed:
   x=retry(lambda:s.files().update(fileId=oid,media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json"),fields="id"))
   oid=x["id"]
  else:raise ValueError("IMMUTABLE_SPEC_MISMATCH_USE_NEW_VERSION")
 else:
  oid=retry(lambda:s.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/octet-stream"),fields="id"))["id"]
 if sha(retry(lambda:s.files().get_media(fileId=oid)))!=sha(b):raise ValueError("DRIVE_SHA_READBACK_MISMATCH_"+name)
 return {"id":oid,"action":"CREATED_OR_UPDATED","sha":sha(b)}
def check_source(pair):
 name,fid=pair
 # Each worker has its own service to avoid shared httplib2 transport races.
 s=api();rows=list_files(s,fid);parts={x["name"]:x["id"] for x in rows if x.get("mimeType")=="application/vnd.google-apps.folder"}
 result={}
 for m in ("2026-11","2026-10","2026-09"):
  mid=parts.get(m)
  if not mid:result[m]={"status":"NO_V095_MONTH_FOLDER","files":0,"drive_folder_id":None};continue
  objects=list_files(s,mid)
  result[m]={"status":"OBSERVED_BRONZE_OBJECTS_NOT_FULL_SOURCE_CONTRACT" if objects else "EMPTY_MONTH_FOLDER","files":len(objects),"drive_folder_id":mid}
 return name,result
def existing(s):
 result={}
 for label,fid in SILVER_GOLD.items():
  try:
   x=retry(lambda:s.files().get(fileId=fid,fields="id,name,size,trashed"))
   result[label]={"file_id":fid,"size_bytes":int(x.get("size") or 0),"status":"EXISTS_CANDIDATE" if not x.get("trashed") else "TRASHED"}
  except Exception as e:result[label]={"file_id":fid,"status":"NOT_VERIFIED","error":str(e)[:90]}
 return result
def main():
 run=os.environ.get("GITHUB_RUN_ID","local")
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:srcs=dict(pool.map(check_source,SOURCE_FOLDERS.items()))
 s=api();candidate=existing(s)
 cat=json.loads(retry(lambda:s.files().get_media(fileId=DRIVE["catalog_443_file"])).decode())
 ids=cat.get("indicators",[])
 if len(ids)!=443 or len({i["id"] for i in ids})!=443:raise ValueError("443_CATALOG_NOT_STABLE")
 observed=sum(srcs[x][m]["files"]>0 for x in SOURCE_FOLDERS for m in ("2026-11","2026-10","2026-09"))
 blocked=[]
 for name in SOURCE_FOLDERS:
  for month in ("2026-11","2026-10","2026-09"):
   row=srcs[name][month]
   if row["files"]==0:blocked.append({"task_id":"V095:BRONZE:"+name+":"+month,"source":name,"month":month,"state":"WAITING_V093_OR_OFFICIAL_EXACT_CONTRACT","reason":row["status"]})
 blocked.append({"task_id":"V095:GOLD:443:PIT","state":"BLOCKED_FORMULA_AND_HISTORICAL_PIT","reason":"Catalog ID count is not 443 formula certification."})
 # Gate is evidence-driven, not a hardcoded permanent False.
 # Acceptance document is a separate formal evidence receipt; never infer signoff
 # from the count of folders or from a successful GitHub job alone.
 acceptance_name="JARVIS_V095_ULTIMATE_R1_PILOT_ACCEPTANCE_SIGNED.json"
 acceptance_files=named(s,DRIVE["governance"],acceptance_name)
 witness=None
 if len(acceptance_files)==1:
  try:witness=json.loads(retry(lambda:s.files().get_media(fileId=acceptance_files[0]["id"])).decode("utf-8"))
  except (ValueError,UnicodeError,KeyError):witness=None
 requirements=("bronze_source_contract_sha_pass","silver_schema_quality_pass",
  "gold_monthly_eligible_formula_pass","pit_publication_evidence_pass",
  "lineage_reverse_qa_pass","all_pilot_exceptions_classified")
 pilot_pass=(observed==18 and len(ids)==443 and
  all(x["status"]=="EXISTS_CANDIDATE" for x in candidate.values()) and
  isinstance(witness,dict) and
  witness.get("schema")=="JARVIS_V095_ULTIMATE_R1_PILOT_SIGNOFF_V1" and
  witness.get("scope")==["2026-11","2026-10","2026-09"] and
  all(witness.get(k) is True for k in requirements) and
  len(witness.get("source_sha256_evidence",[]))>=18 and
  bool(witness.get("pit_evidence_document_id")))
 report={"schema":"JARVIS_V095_ULTIMATE_R1_PILOT_REPORT","run_id":run,
 "date_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"scope":["2026-11","2026-10","2026-09"],
 "controller":"ONE_15_MIN_CRON","slot_capacity":{"BRONZE":6,"SILVER":4,"GOLD":4,"active_limit":CFG["orchestrator"]["global_max_active"]},
 "bronze":srcs,"silver_gold_existing_candidates":candidate,"catalog_ids":len(ids),"observed_source_month_cells":observed,"expected_source_month_cells":18,"missing_source_month_cells":18-observed,
 "pit_full_pass":False,"all_443_formula_pass":False,"full_bronze_contract_pass":False,
 "historical_before_september_allowed":pilot_pass,
 "historical_mode":"PILOT_PASSED_HISTORY_ADAPTER_REQUIRED" if pilot_pass else "BLOCKED_PENDING_PILOT_ACCEPTANCE","history_next_month":"2026-08" if pilot_pass else None,"formal_acceptance_evidence":acceptance_files[0]["id"] if pilot_pass else None,"queue":blocked,
 "retry":"ONLY_DUE_TRANSIENT_ERRORS; permanent contract gaps do not hot-loop",
 "actions_performed":["read Drive source month folders","inspect six existing Silver Gold candidate objects","verify 443 IDs","prepare blocked queue","archive specification to Drive"],
 "actions_not_performed":["download missing official datasets","convert unverified months","certify 443 formulas","certify historical PIT","open history 2026-08 to 2000"]}
 raw=json.dumps(report,ensure_ascii=False,indent=2).encode()
 (ROOT/"pilot_latest_to_202609_report.json").write_bytes(raw)
 (ROOT/"pending_queue.json").write_text(json.dumps(blocked,ensure_ascii=False,indent=2))
 configbytes=pathlib.Path("config/v095_ultimate_r1.json").read_bytes()
 specbytes=pathlib.Path("governance/v095/JARVIS_V095_ULTIMATE_R1_SPEC_20261106.md").read_bytes()
 published={}
 for filename,b in [("JARVIS_V095_ULTIMATE_R1_SPEC_20261106.md",specbytes),("JARVIS_V095_ULTIMATE_R1_CONFIG_20261106_"+sha(configbytes)[:16]+".json",configbytes)]:
  published[filename]=save_bytes(s,DRIVE["governance"],filename,b)
 policy_file=pathlib.Path("config/v095_publication_availability_policy.json")
 policybytes=policy_file.read_bytes()
 publication_doc=pathlib.Path("governance/v095/JARVIS_V095_OFFICIAL_PUBLICATION_PIT_RULES_20261106.md").read_bytes()
 for filename,data in [
  ("JARVIS_V095_PUBLICATION_AVAILABILITY_"+sha(policybytes)[:16]+".json",policybytes),
  ("JARVIS_V095_OFFICIAL_PUBLICATION_PIT_RULES_"+sha(publication_doc)[:16]+".md",publication_doc)]:
  published[filename]=save_bytes(s,DRIVE["governance"],filename,data)
 # Create immutable run receipt so no data/state is overwritten, but heartbeat cron won't flood Drive:
 # save on initial run/manual, or if a new source-month object appears (checkpoint fingerprint).
 fingerprint=sha(json.dumps({"bronze":srcs,"candidate":candidate,"queue":blocked},sort_keys=True,ensure_ascii=False).encode())
 state_name=CFG["state"]["manifest_name"];prev=named(s,DRIVE["operations"],state_name)
 previous=None
 if len(prev)==1:
  try:previous=json.loads(retry(lambda:s.files().get_media(fileId=prev[0]["id"])).decode())
  except Exception:previous=None
 state={"schema":"JARVIS_V095_ULTIMATE_R1_CHECKPOINT_V1","fingerprint":fingerprint,"scope":report["scope"],"pilot_gate":"PASSED_HISTORY_READY" if pilot_pass else "BLOCKED","last_change_run":run if (not previous or previous.get("fingerprint")!=fingerprint) else previous.get("last_change_run"),
  "last_check_run":run,"latest_source_month_cells":observed,"pending_count":len(blocked),
  "report_file_name":CFG["state"]["reports_prefix"]+run+".json" if (not previous or previous.get("fingerprint")!=fingerprint) else previous.get("report_file_name")}
 if not previous or previous.get("fingerprint")!=fingerprint:
  name=CFG["state"]["reports_prefix"]+run+".json"
  published["pilot_report"]=save_bytes(s,DRIVE["operations"],name,raw)
 published["checkpoint"]=save_bytes(s,DRIVE["operations"],state_name,json.dumps(state,ensure_ascii=False,indent=2).encode(),overwrite_if_changed=True)
 report["drive_published"]=published
 (ROOT/"published_readback.json").write_text(json.dumps(published,ensure_ascii=False,indent=2))
 print(json.dumps({"run_id":run,"bronze_source_month_cells":observed,"expected":18,"catalog":len(ids),
   "pilot_gate":"PILOT_PASSED_HISTORY_ADAPTER_REQUIRED" if pilot_pass else "BLOCKED_PENDING_QA_PIT_MISSING_SOURCES","history_before_202609":pilot_pass,
   "drive_documents":{k:v["id"] for k,v in published.items()}},ensure_ascii=False))
if __name__=="__main__":main()
