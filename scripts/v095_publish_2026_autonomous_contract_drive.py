#!/usr/bin/env python3
"""Immutable and SHA-readback publish of the 2026 autonomous controller contract."""
import hashlib,io,json,os,pathlib
from googleapiclient.http import MediaIoBaseUpload
from scripts.v095_market_release_calendar_drive_archive import drive,OPS
SRC=pathlib.Path("governance/v095/JARVIS_V095_2026_AUTONOMOUS_CONTROLLER_CONTRACT_20261108.md")
OUT=pathlib.Path("v095_2026_controller")
def main():
    flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
    assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
    data=SRC.read_bytes()
    assert len(data)>2500
    sha=hashlib.sha256(data).hexdigest()
    name="JARVIS_V095_2026_AUTONOMOUS_CONTRACT_"+sha[:24]+".md"
    d=drive()
    q="'"+OPS+"' in parents and name = '"+name+"' and trashed = false"
    files=[];page=None
    while True:
        response=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=100,pageToken=page).execute()
        if response.get("incompleteSearch"):raise RuntimeError("DRIVE_LIST_INCOMPLETE")
        files.extend(response.get("files",[]));page=response.get("nextPageToken")
        if not page:break
    if len(files)>1:raise RuntimeError("DUPLICATE_CONTRACT_NAMES")
    if files:
        fid=files[0]["id"];action="REUSED"
    else:
        x=d.files().create(body={"name":name,"parents":[OPS],
                    "description":"2026 scope only; not a 443-formula or PIT release certificate"},
                    media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="text/markdown",resumable=False),
                    fields="id").execute()
        fid=x["id"];action="CREATED"
    back=d.files().get_media(fileId=fid).execute()
    if hashlib.sha256(back).hexdigest()!=sha:raise RuntimeError("DRIVE_CONTRACT_SHA_READBACK_FAILED")
    OUT.mkdir(exist_ok=True)
    result={"drive_sha_readback":"PASS","drive_id":fid,"sha256":sha,
            "action":action,"file_name":name,"scope":"2026_only","released":False}
    (OUT/"drive_contract_receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
