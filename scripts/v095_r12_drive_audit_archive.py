#!/usr/bin/env python3
"""Write ONLY a small sanitized R12 audit record to v0.95 Google Drive Operations.

No Bronze/Silver/Gold mutation. Source manifest with private Drive IDs stays
on ephemeral runner. Re-runs reuse audit records by content hash and readback.
"""
import hashlib,io,json,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
DIR=ROOT/"r12_deep_manifest"
OPERATIONS=json.loads((ROOT/"config/v095_ultimate_r1.json").read_text())["drive"]["operations"]
def canonical_bytes(run_id,deep,gov):
 obj={"schema":"JARVIS_V095_R12_DRIVE_AUDIT_ARCHIVE_V1","run_id":str(run_id),
      "version":"v0.95","scope":["2026-09","2026-10","2026-11"],
      "scan_status":deep["scan_status"],
      "objects_examined":deep["objects_examined"],
      "stage_counts":deep["stage_counts"],
      "download_count":deep["source_data_downloads"],
      "drive_market_data_writes":deep["drive_writes"],
      "expected_denominator":"UNKNOWN",
      "manifest_rows":gov["manifest_data_rows"],
      "checkpoint_rows":gov["checkpoint_data_rows"],
      "registered_sources":gov["source_registry_rows"],
      "source_contracts":gov["dataset_contract_rows"],
      "source_contracts_ready":gov["production_ready_dataset_contracts"],
      "unresolved_issue_ids":deep["open_root_issues"],
      "bulk_approved":False,"release_approved":False,
      "record_type":"OPERATIONS_AUDIT_NOT_OFFICIAL_MARKET_DATA",
      "next_test":"ONE_SCOPED_OFFICIAL_BRONZE_WRITE_CAS_READBACK_ONLY_AFTER_APPROVAL"}
 assert obj["download_count"]==0 and obj["drive_market_data_writes"]==0
 assert obj["manifest_rows"]>=0 and obj["checkpoint_rows"]>=0
 return (json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def drive():
 from google.oauth2.credentials import Credentials
 from google.auth.transport.requests import Request
 from googleapiclient.discovery import build
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
  client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
  token_uri="https://oauth2.googleapis.com/token",scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request())
 return build("drive","v3",credentials=c,cache_discovery=False)
def execute():
 deep=json.loads((DIR/"public_report.json").read_text())
 gov=json.loads((ROOT/"r12_governance_gaps/result.json").read_text())
 flags=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
 assert not flags["BULK_COPY_APPROVED"] and not flags["RELEASE_APPROVED"]
 assert deep["scan_status"].startswith("PASS_"),"DO_NOT_ARCHIVE_FAILED_AS_PASS"
 raw=canonical_bytes(os.environ.get("GITHUB_RUN_ID","LOCAL"),deep,gov)
 sha=hashlib.sha256(raw).hexdigest()
 name="JARVIS_V095_R12_AUDIT_"+str(os.environ.get("GITHUB_RUN_ID","LOCAL"))+"_"+sha[:16]+".json"
 s=drive()
 def listing():
  result=s.files().list(q="'"+OPERATIONS+"' in parents and name='"+name+"' and trashed=false",
    fields="nextPageToken,incompleteSearch,files(id,name,size)",pageSize=100).execute()
  if result.get("incompleteSearch") or result.get("nextPageToken"):
   raise ValueError("INCOMPLETE_DRIVE_AUDIT_NAME_LIST")
  return result.get("files",[])
 found=listing()
 if len(found)>1:raise ValueError("DUPLICATE_SAME_NAME_DRIVE_AUDIT")
 if found:
  file_id=found[0]["id"];action="REUSED"
 else:
  from googleapiclient.http import MediaIoBaseUpload
  f=s.files().create(body={"name":name,"parents":[OPERATIONS],
   "description":"JARVIS v0.95 R12 sanitized weekly read-only issue and governance status"},
   media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=False),
   fields="id").execute()
  file_id=f["id"];action="CREATED"
 import googleapiclient.http
 fetched=s.files().get_media(fileId=file_id).execute()
 if hashlib.sha256(fetched).hexdigest()!=sha:raise AssertionError("DRIVE_AUDIT_READBACK_SHA_MISMATCH")
 if len(listing())!=1:raise AssertionError("DRIVE_AUDIT_DUPLICATE_AFTER_COMMIT")
 receipt={"result":"PASS_DRIVE_AUDIT_BYTES_READBACK","run_id":os.environ.get("GITHUB_RUN_ID"),
          "action":action,"content_sha256":sha,
          "market_data_downloaded":False,"market_data_mutated":False}
 (ROOT/"r12_governance_gaps/drive_audit_receipt_public.json").write_text(
   json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(receipt,ensure_ascii=False))
 return 0
if __name__=="__main__":sys.exit(execute())
