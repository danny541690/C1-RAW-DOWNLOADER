#!/usr/bin/env python3
"""Archive generated G0 report and 59,172 source/day states to Google Drive.
All objects are immutable by SHA, read back after upload, never Bronze inputs.
"""
import hashlib,io,json,pathlib,os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
ROOT=pathlib.Path("v095_market_release_calendar")
OPS=json.loads(pathlib.Path("config/v095_ultimate_r1.json").read_text())["drive"]["operations"]
def sha(b):return hashlib.sha256(b).hexdigest()
def drive():
    c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
      client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
      token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request())
    return build("drive","v3",credentials=c,cache_discovery=False)
def archive(s,path):
    b=path.read_bytes();digest=sha(b)
    name="JARVIS_V095_G0_2000_2026_"+path.stem+"_"+digest[:24]+path.suffix
    q="'"+OPS+"' in parents and name = '"+name+"' and trashed = false"
    items=[];page=None
    while True:
        x=s.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,size)",
            pageSize=100,pageToken=page).execute()
        if x.get("incompleteSearch"):raise RuntimeError("DRIVE_G0_LIST_INCOMPLETE")
        items+=x.get("files",[]);page=x.get("nextPageToken")
        if not page:break
    if len(items)>1:raise RuntimeError("AMBIGUOUS_G0_ARCHIVE")
    if items: fid=items[0]["id"];action="REUSED"
    else:
        media="text/csv" if path.suffix==".csv" else "application/json"
        x=s.files().create(body={"name":name,"parents":[OPS],
          "description":"JARVIS G0 calendar evidence; 2000-2025 unknown days not certified"},
          media_body=MediaIoBaseUpload(io.BytesIO(b),mimetype=media,resumable=True),
          fields="id").execute()
        fid=x["id"];action="CREATED"
    back=s.files().get_media(fileId=fid).execute()
    if sha(back)!=digest:raise RuntimeError("DRIVE_G0_SHA_READBACK_FAILED")
    return {"file":path.name,"action":action,"sha256":digest,"drive_file_id":fid,"bytes":len(b)}
def main():
    report=json.loads((ROOT/"report.json").read_text())
    if report["g0_coverage_denominator_certified"] or report["PIT_APPROVED"]:
        raise RuntimeError("NOT_ALLOWED_TO_ARCHIVE_FALSE_COMPLETION")
    s=drive()
    receipt=[archive(s,ROOT/name) for name in ("market_dates_2000_2026.csv","report.json")]
    source_audit=ROOT/"six_source_date_quality.json"
    if source_audit.is_file():receipt.append(archive(s,source_audit))
    supplementary=ROOT/"historic_weekday_no_market_row_candidates.csv"
    if supplementary.is_file():receipt.append(archive(s,supplementary))
    p=ROOT/"drive_receipt.json"
    p.write_text(json.dumps({"run_id":os.getenv("GITHUB_RUN_ID"),"files":receipt,
           "readback_verified":True,"historical_release_certified":False},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"g0_archive":"DRIVE_SHA_READBACK_PASS","count":len(receipt),
        "actions":[x["action"] for x in receipt],"year_complete":False}))
if __name__=="__main__":main()
