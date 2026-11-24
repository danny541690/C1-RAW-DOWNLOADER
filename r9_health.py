import os,json,hashlib,io,uuid,sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
tests={}
stage="oauth"
created=None
svc=None
report=None
def check(k,v):
    tests[k]="PASS" if v else "FAIL"
    if not v: raise RuntimeError(k)
def folder(parent,name):
    q="'"+parent+"' in parents and trashed=false and mimeType='application/vnd.google-apps.folder' and name='"+name+"'"
    out=[]; token=None
    while True:
        r=svc.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,parents)",pageToken=token,pageSize=100).execute()
        if r.get("incompleteSearch"): raise RuntimeError("incomplete_search")
        out.extend(r.get("files",[])); token=r.get("nextPageToken")
        if not token: break
    if len(out)!=1: raise RuntimeError("folder_not_unique")
    return out[0]["id"]
def put(parent,name,data):
    return svc.files().create(body={"name":name,"parents":[parent]},media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/json",resumable=False),fields="id,parents").execute()["id"]
try:
    keys=["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN"]
    check("secret_presence",all(os.environ.get(k) for k in keys))
    c=Credentials(None,refresh_token=os.environ[keys[2]],token_uri="https://oauth2.googleapis.com/token",client_id=os.environ[keys[0]],client_secret=os.environ[keys[1]])
    c.refresh(Request()); check("oauth",bool(c.token))
    svc=build("drive","v3",credentials=c,cache_discovery=False)
    stage="account"
    account=svc.about().get(fields="user(emailAddress)").execute()["user"]["emailAddress"]
    check("account",account.lower()==os.environ["GITHUB_REPOSITORY_OWNER"].lower()+"@gmail.com")
    stage="folder"
    db=folder(folder("root","ChatGPT資料存取"),"C1_0.98")
    cmd=folder(db,"00_COMMAND")
    dest=folder(cmd,"CONNECTION_HEALTH_V1")
    check("folder",True)
    stage="canary"
    nonce=uuid.uuid4().hex
    data=json.dumps({"nonce":nonce}).encode()
    created=put(dest,"_R9_CANARY_"+nonce+".json",data)
    check("write",True)
    got=svc.files().get_media(fileId=created).execute()
    check("sha256",hashlib.sha256(got).digest()==hashlib.sha256(data).digest())
    svc.files().delete(fileId=created).execute(); created=None
    check("cleanup",True)
    stage="report"
    body=json.dumps({"repo":os.environ["GITHUB_REPOSITORY"],"run_id":os.environ["GITHUB_RUN_ID"],"database_id":db,"command_id":cmd,"tests":tests},sort_keys=True).encode()
    report=put(dest,"R9_CANARY_"+os.environ["GITHUB_REPOSITORY"].split("/")[-1]+"_"+os.environ["GITHUB_RUN_ID"]+".json",body)
    check("report_readback",svc.files().get_media(fileId=report).execute()==body)
except Exception as e:
    tests.setdefault(stage,"FAIL")
    print("R9_CANARY_ERROR",stage,type(e).__name__)
    sys.exit(1)
finally:
    if created and svc:
        try: svc.files().delete(fileId=created).execute()
        except Exception: print("R9_CANARY_CLEANUP_FAILED")
    print("R9_CANARY_STATUS",json.dumps(tests,sort_keys=True))
