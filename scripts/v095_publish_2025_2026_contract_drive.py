#!/usr/bin/env python3
"""Read-after-write SHA archive of complete 2025-2026 unattended operating contract."""
import hashlib,io,json,os,pathlib
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
SRC=pathlib.Path("governance/v095/JARVIS_V095_2025_2026_AUTONOMOUS_EXECUTION_SOP_20261108.md")
OUT=pathlib.Path("v095_2025_2026_autonomous_contract")
def sha(x):return hashlib.sha256(x).hexdigest()
def main():
 flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 raw=SRC.read_bytes()
 if len(raw)<2000:raise ValueError("TWO_YEAR_SOP_TOO_SHORT")
 h=sha(raw);name="JARVIS_V095_2025_2026_AUTONOMOUS_SOP_"+h[:24]+".md"
 d=drive()
 q="'"+OPS+"' in parents and name = '"+name+"' and trashed=false"
 rows=[];page=None
 while True:
  x=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=100,pageToken=page).execute()
  if x.get("incompleteSearch"):raise ValueError("INCOMPLETE_CONTRACT_LIST")
  rows.extend(x.get("files",[]));page=x.get("nextPageToken")
  if not page:break
 if len(rows)>1:raise ValueError("DUPLICATE_CONTRACT_NAME")
 if rows:fid=rows[0]["id"];status="REUSED"
 else:
  fid=d.files().create(body={"name":name,"parents":[OPS],
    "description":"2025-2026 candidate autonomous SOP, no 443 or historical PIT release"},
    media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="text/markdown",resumable=False),
    fields="id").execute()["id"]
  status="CREATED"
 if sha(d.files().get_media(fileId=fid).execute())!=h:raise ValueError("REMOTE_CONTRACT_SHA_MISMATCH")
 OUT.mkdir(exist_ok=True)
 result={"scope":"2025-2026","sha256":h,"drive_id":fid,"drive_sha_readback":"PASS",
  "status":status,"name":name,"full_443_PIT_certified":False,"production_released":False}
 (OUT/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
