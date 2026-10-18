"""Manual-only minimal Google Drive credential and writable-folder canary.

Runs only after user has configured GitHub Actions secrets.
Creates a small unique test file inside a preselected folder and verifies readback.
Does not log credentials or overwrite any existing file.
"""
import hashlib, json, os, sys
from uuid import uuid4

NAMES=["GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN","GOOGLE_DRIVE_FOLDER_ID"]
missing=[n for n in NAMES if not os.environ.get(n)]
if missing:
    print("BLOCKED_MISSING_SECRETS: "+", ".join(missing))
    sys.exit(2)

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO

creds=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
    scopes=["https://www.googleapis.com/auth/drive"])
try:
    creds.refresh(Request())
    svc=build("drive","v3",credentials=creds,cache_discovery=False)
    parent=os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    folder=svc.files().get(fileId=parent,fields="id,name,mimeType").execute()
    if folder.get("mimeType")!="application/vnd.google-apps.folder":
        raise ValueError("target is not a folder")
    payload=b'{"JARVIS":"drive-write-readback-canary","production_data":false}\n'
    name="_jarvis_v093_canary_"+uuid4().hex+".json"
    obj=svc.files().create(body={"name":name,"parents":[parent]},
        media_body=MediaIoBaseUpload(BytesIO(payload),mimetype="application/json"),
        fields="id,name,parents").execute()
    fetched=svc.files().get_media(fileId=obj["id"]).execute()
    if hashlib.sha256(fetched).digest()!=hashlib.sha256(payload).digest():
        raise ValueError("DRIVE_READBACK_MISMATCH")
    print(json.dumps({"status":"PASS_DRIVE_UPLOAD_READBACK","folder_name":folder.get("name"),
          "canary_file_id":obj["id"],"bytes":len(payload),"sha256_verified":True}))
except Exception as exc:
    print(json.dumps({"status":"FAIL_DRIVE_CANARY","error_type":type(exc).__name__,
         "message":str(exc)[:160]}))
    sys.exit(1)
