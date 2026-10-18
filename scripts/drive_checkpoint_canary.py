"""Cross-job Drive checkpoint canary. No raw stock data or secret values in logs."""
import hashlib, io, json, os, sys
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

def main():
    required=("GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN","GOOGLE_DRIVE_FOLDER_ID","GITHUB_RUN_ID","MODE")
    absent=[key for key in required if not os.environ.get(key)]
    if absent: raise ValueError("missing environment keys: "+",".join(absent))
    creds=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
         token_uri="https://oauth2.googleapis.com/token",client_id=os.environ["GOOGLE_CLIENT_ID"],
         client_secret=os.environ["GOOGLE_CLIENT_SECRET"],scopes=["https://www.googleapis.com/auth/drive"])
    creds.refresh(Request())
    api=build("drive","v3",credentials=creds,cache_discovery=False)
    parent=os.environ["GOOGLE_DRIVE_FOLDER_ID"]
    folder_name="JARVIS_V093_CHECKPOINT_CANARY_"+os.environ["GITHUB_RUN_ID"]
    def children(parent_id,name):
        q="name = '"+name.replace("'","\\'")+"' and '"+parent_id+"' in parents and trashed = false"
        matches=api.files().list(q=q,fields="files(id,name,mimeType),nextPageToken",pageSize=100).execute().get("files",[])
        if len(matches)>1: raise ValueError("duplicate checkpoint object")
        return matches
    folders=children(parent,folder_name)
    if os.environ["MODE"]=="write":
        if folders: raise ValueError("canary folder already exists")
        folder=api.files().create(body={"name":folder_name,"parents":[parent],"mimeType":"application/vnd.google-apps.folder"},fields="id").execute()["id"]
        raw=b'{"source":"SIMULATION_ONLY","year":2024,"month":1,"unit":"canary-unit","status":"SAVED_BASIC_VALID"}\n'
        digest=hashlib.sha256(raw).hexdigest()
        api.files().create(body={"name":"unit.json","parents":[folder]},
             media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json"),fields="id").execute()
        got=children(folder,"unit.json")
        if len(got)!=1: raise ValueError("unit not persisted")
        if hashlib.sha256(api.files().get_media(fileId=got[0]["id"]).execute()).hexdigest()!=digest:
            raise ValueError("unit readback mismatch")
        checkpoint=json.dumps({"year":2024,"month":1,"unit":"canary-unit","status":"SAVED_BASIC_VALID",
             "sha256":digest,"bytes":len(raw),"simulated":True},sort_keys=True).encode()
        api.files().create(body={"name":"checkpoint.json","parents":[folder]},
             media_body=MediaIoBaseUpload(io.BytesIO(checkpoint),mimetype="application/json"),fields="id").execute()
        print(json.dumps({"phase":"WRITE","result":"PASS","unit_bytes":len(raw),"checkpoint_bytes":len(checkpoint),"simulated":True}))
    elif os.environ["MODE"]=="resume":
        if len(folders)!=1: raise ValueError("canary folder absent")
        folder=folders[0]["id"]
        checkpoints=children(folder,"checkpoint.json")
        units=children(folder,"unit.json")
        if len(checkpoints)!=1 or len(units)!=1: raise ValueError("missing checkpoint/unit")
        checkpoint=json.loads(api.files().get_media(fileId=checkpoints[0]["id"]).execute())
        raw=api.files().get_media(fileId=units[0]["id"]).execute()
        if checkpoint["status"]!="SAVED_BASIC_VALID" or checkpoint["sha256"]!=hashlib.sha256(raw).hexdigest():
            raise ValueError("resume validation mismatch")
        print(json.dumps({"phase":"RESUME_DIFFERENT_GITHUB_JOB","result":"PASS","refetch_count":0,
              "reupload_count":0,"sha256_verified":True,"simulated":True}))
    else: raise ValueError("invalid MODE")

if __name__=="__main__":
    try: main()
    except Exception as e:
        print(json.dumps({"result":"FAIL","error_type":type(e).__name__,"error":str(e)[:150]}))
        sys.exit(1)
