"""Sync v0.95 data validity system rules into Drive as immutable JSON and CSV."""
import csv,hashlib,io,json,os,pathlib
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
SOURCE=pathlib.Path("config/v095_data_validity_system_rules.json")
FOLDER_ID="1igeNb_PpOgiYV13_TB1rfEPNsAoisc_Z"
def digest(b):return hashlib.sha256(b).hexdigest()
def main():
    obj=json.loads(SOURCE.read_text())
    fields=("source","dataset_id","frequency","reference_grain","release_rule","nominal_deadline","release_calendar","pit_evidence","version")
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=fields);writer.writeheader()
    for s in obj["sources"]:
        writer.writerow(dict(source=s["source"],dataset_id=s["dataset_id"],frequency=s["frequency"],
        reference_grain=";".join(s["grain"]),release_rule=s["release_rule"],
        nominal_deadline=s.get("nominal_deadline",""),
        release_calendar=json.dumps(s.get("confirmed_calendar",{}),ensure_ascii=False),
        pit_evidence=s["pit"],version=obj["version"]))
    binaries={"JARVIS_V095_SYSTEM_RULES_R2.json":SOURCE.read_bytes(),
              "JARVIS_V095_SYSTEM_RULES_R2.csv":output.getvalue().encode("utf-8-sig")}
    c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
      client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
      token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request());drive=build("drive","v3",credentials=c,cache_discovery=False)
    existing=drive.files().list(q="'"+FOLDER_ID+"' in parents and trashed=false",
      fields="nextPageToken,files(id,name)",pageSize=1000).execute()["files"]
    receipt={}
    for filename,body in binaries.items():
        match=[e for e in existing if e["name"]==filename]
        if len(match)>1:raise ValueError("Duplicate canonical rules")
        if match:
            fid=match[0]["id"];action="REUSED"
        else:
            fid=drive.files().create(body={"name":filename,"parents":[FOLDER_ID]},
              media_body=MediaIoBaseUpload(io.BytesIO(body),mimetype="application/octet-stream"),
              fields="id").execute()["id"];action="CREATED"
        if digest(drive.files().get_media(fileId=fid).execute())!=digest(body):
            raise ValueError("Drive version mismatch: "+filename)
        receipt[filename]={"id":fid,"sha256":digest(body),"action":action}
    pathlib.Path("ultimate_r1").mkdir(exist_ok=True)
    pathlib.Path("ultimate_r1/system_rules_readback.json").write_text(json.dumps(receipt,indent=2))
    print(json.dumps({"registry_rows":len(obj["sources"]),"files":receipt},ensure_ascii=False))
if __name__=="__main__":main()
