"""September Gold index and AI read-contract QA: no false 433/443 completeness.
Reads Drive objects directly, stores versioned index with source evidence and quality hold.
"""
import collections,datetime,hashlib,io,json,os,pathlib,time
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
GOLD_ROOT="1FYIz-uylwZLM7HL-7MG2iH90BefMyXDw"
GOLD_INDICATORS="1XT_54SXjGDksTz6PAdwhsVA8czZ1FTE3"
GOVERNANCE="1igeNb_PpOgiYV13_TB1rfEPNsAoisc_Z"
OPERATIONS="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
CATALOG="1lbWk0qRZZFjpV-yL1gZNUb2pCZmHDHW7"
OUT=pathlib.Path("v095_september_ai_query")
OUT.mkdir(exist_ok=True)
def svc():
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def execute(fn):
 for trial in range(4):
  try:return fn().execute()
  except (OSError,ConnectionError,TimeoutError):
   if trial==3:raise
   time.sleep(2**trial*2)
def ls(s,parent):
 res=[];page=None
 while True:
  x=execute(lambda:s.files().list(q="'"+parent+"' in parents and trashed = false",pageToken=page,pageSize=1000,fields="nextPageToken,files(id,name,size,mimeType,modifiedTime,md5Checksum)"))
  res.extend(x.get("files",[]));page=x.get("nextPageToken")
  if not page:return res
def main():
 s=svc()
 catalog=json.loads(execute(lambda:s.files().get_media(fileId=CATALOG)).decode("utf-8"))
 ids=catalog["indicators"]
 if len(ids)!=443 or len({i["id"] for i in ids})!=443:raise ValueError("CATALOG_443_UNIQUE_IDS_NOT_MET")
 observed=[]
 roots=ls(s,GOLD_ROOT)
 for group in roots:
  if group.get("mimeType")=="application/vnd.google-apps.folder":
   for f in ls(s,group["id"]):
    row={"folder":group["name"],"name":f["name"],"file_id":f["id"],"bytes":int(f.get("size") or 0),"mime":f.get("mimeType"),"modifiedTime":f.get("modifiedTime"),"quality":"NOT_FULL_443_PIT_APPROVED"}
    observed.append(row)
  else:observed.append({"folder":"GOLD_ROOT","name":group["name"],"file_id":group["id"],"bytes":int(group.get("size") or 0),"quality":"NOT_FULL_443_PIT_APPROVED"})
 counts=dict(collections.Counter(z["folder"] for z in observed))
 # No value-bearing API proof unless each feature has explicit formula, QA and PIT.
 result={"schema":"JARVIS_V095_202609_AI_INDEX_CONTRACT_V1","month":"2026-09",
   "generated_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
   "catalog_443_unique":len(ids),"requested_433_distinct_from_443":True,
   "catalog_as_source":"v0.93 original 443 IDs; 433 must be a specified subset, no silent deletion",
   "full_443_formula_approved":False,"full_pit_verified":False,"ready_for_arbitrary_chatgpt_query":False,
   "candidate_gold_drive_entries":len(observed),"gold_folders_observed":counts,
   "query_rule":"Only read explicit quality-approved feature partitions with available_at<=asof; null_reason otherwise.",
   "example_request":{"month":"2026-09","market":"TSE","security_id":"2330","indicator_ids":["CLOSE","MA20","RS_TSE_20D"],"asof":"2026-09-30T23:59:59+08:00"},
   "example_response_contract":{"status":"NOT_READY_ALL_INDICATORS","values":None,"null_reason":"FEATURE_FORMULA_OR_PIT_NOT_CERTIFIED","source_manifest":None,"quality_evidence":None},
   "gold_objects":observed}
 b=(json.dumps(result,ensure_ascii=False,indent=2)+"\n").encode()
 (OUT/"gold_inventory_and_query_contract.json").write_bytes(b)
 name="JARVIS_V095_202609_AI_QUERY_INDEX_RUN_"+os.environ.get("GITHUB_RUN_ID","local")+".json"
 obj=execute(lambda:s.files().create(body={"name":name,"parents":[OPERATIONS]},media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype="application/json",resumable=False),fields="id"))
 if hashlib.sha256(execute(lambda:s.files().get_media(fileId=obj["id"]))).digest()!=hashlib.sha256(b).digest():raise ValueError("INDEX_READBACK_SHA_MISMATCH")
 print(json.dumps({"catalog_ids":len(ids),"gold_entries":len(observed),"gold_groups":counts,"readiness":"BLOCKED_443_PIT_NOT_PROVEN","drive_id":obj["id"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
