"""2026-09 v095: physically verify all inventoried Bronze files, fail closed.

Never overwrite originals. SHA256 is computed on downloaded bytes; ZIP testzip
detects corruption. A missing official dataset contract is NOT full completion.
"""
import collections, csv, datetime as dt, hashlib, io, json, os, pathlib, time, zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
BASE=pathlib.Path("governance/v095")
OUT=pathlib.Path("v095_202609_B_full_audit"); OUT.mkdir(exist_ok=True)
TARGET="1XSkUNOHSkJEbdr6UGNqescxOVBUV3Uvk"
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
    c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
                  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
    c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def call(factory):
    error=None
    for i in range(3):
        try:return factory().execute()
        except Exception as exc:
            error=exc
            if i<2:time.sleep(i+1)
    raise error
def list_dir(s,id):
    result=[];token=None
    while True:
        data=call(lambda:s.files().list(q="'"+id+"' in parents and trashed=false",pageToken=token,pageSize=1000,fields="nextPageToken,files(id,name,size,mimeType,md5Checksum)"))
        result+=data.get("files",[]);token=data.get("nextPageToken")
        if not token:return result
def run():
    src=json.loads((BASE/"202609_BRONZE_MIGRATION_RESUME_20261105.json").read_text())
    contracts=list(csv.DictReader((BASE/"DATASET_CONTRACTS.csv").open(newline="",encoding="utf-8")))
    drive=service(); details=[]; sources={}
    for group in src["source_month_folders"]:
        source=group["source"]
        observed=list_dir(drive,group["drive_folder_id"])
        by_id={x["id"]:x for x in observed}
        used=set()
        for ref in group["files"]:
            row={"source":source,"file_id":ref["id"],"file_name":ref["name"],
                 "expected_bytes":int(ref["bytes"]),"source_sha256_match_v093":"NOT_PROVEN",
                 "dataset_contract_certified":False,"status":"BLOCKED"}
            try:
                match=by_id.get(ref["id"])
                if not match or match["name"]!=ref["name"]:raise ValueError("MISSING_OR_STALE_DRIVE_ID")
                used.add(ref["id"])
                raw=call(lambda:drive.files().get_media(fileId=ref["id"]))
                row.update(actual_bytes=len(raw),sha256=sha(raw),readback_sha_verified=True)
                if len(raw)!=int(ref["bytes"]):raise ValueError("MANIFEST_BYTE_COUNT_DIFFERENCE")
                if ref["name"].lower().endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(raw)) as z:
                        member_names=z.namelist()
                        if z.testzip() is not None:raise ValueError("ZIP_MEMBER_CRC_FAILURE")
                        row["zip_member_count"]=len(member_names)
                        row["zip_crc_verified"]=True
                row["status"]="CANDIDATE_BYTES_AND_CONTAINER_PASS"
            except Exception as e:
                row["error"]=type(e).__name__+":"+str(e)[:200]
            details.append(row)
        extras=[{"file_id":x["id"],"name":x["name"]} for x in observed if x["id"] not in used]
        sources[source]={"manifest_count":len(group["files"]),
            "observed_count":len(observed),"unexpected_extra":extras}
    counts=collections.Counter(x["status"] for x in details)
    contract_by_source=collections.Counter(x["source_class_id"] for x in contracts)
    for source in sources:
        sources[source]["contract_candidates"]=contract_by_source[source]
        sources[source]["verified_candidate_bytes"]=sum(x["status"]=="CANDIDATE_BYTES_AND_CONTAINER_PASS" for x in details if x["source"]==source)
        sources[source]["candidate_not_verified"]=sources[source]["manifest_count"]-sources[source]["verified_candidate_bytes"]
    report={"schema":"JARVIS_V095_202609_FULL_BRONZE_B_CHECK_V1",
       "run_id":os.environ.get("GITHUB_RUN_ID","local"),"month":"2026-09",
       "verified_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
       "manifest_files":len(details),"status_counts":dict(counts),
       "by_source":sources,"contract_candidates":len(contracts),
       "source_v093_vs_v095_sha_comparison":"NOT_PROVEN_UNTIL_LEGACY_OBJECTS_READ",
       "source_universe_signed":False,
       "bronze_full_release":False,"silver_gold_full_release":False,
       "targeted_repairs":[{"source":x["source"],"file_id":x["file_id"],"reason":x.get("error","")}
           for x in details if x["status"]!="CANDIDATE_BYTES_AND_CONTAINER_PASS"],
       "scope_notes":["zip CRC checks container integrity, not official source semantic completeness",
                      "41 archived objects do not establish complete September dataset universe",
                      "no automatic replacement without an identified immutable original"]}
    (OUT/"bronze_manifest.json").write_text(json.dumps(details,ensure_ascii=False,indent=2)+"\n")
    (OUT/"audit_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    (OUT/"repair_queue.json").write_text(json.dumps(report["targeted_repairs"],ensure_ascii=False,indent=2)+"\n")
    raw=(json.dumps(report,ensure_ascii=False,indent=2)+"\n").encode()
    name="JARVIS_V095_202609_B_FULL_BRONZE_AUDIT_"+report["run_id"]+".json"
    created=call(lambda:drive.files().create(body={"name":name,"parents":[TARGET]},
        media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json"),fields="id,name,size"))
    check=call(lambda:drive.files().get_media(fileId=created["id"]))
    if sha(check)!=sha(raw):raise RuntimeError("REPORT_DRIVE_READBACK_HASH_MISMATCH")
    report["drive_report_id"]=created["id"]
    print(json.dumps({"run_id":report["run_id"],"manifest_files":len(details),
      "status_counts":dict(counts),"by_source":sources,
      "repair_tasks":len(report["targeted_repairs"]),
      "contract_candidates":len(contracts),"drive_report_id":created["id"],
      "full_release":"BLOCKED_UNTIL_SOURCE_CONTRACT_PIT_AND_LINEAGE"},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
