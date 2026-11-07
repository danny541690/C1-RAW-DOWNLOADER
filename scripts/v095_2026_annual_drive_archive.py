#!/usr/bin/env python3
"""One-run 2026 annual acceptance state archive, never writes source market data."""
import hashlib,io,json,os,pathlib,sys
from scripts.v095_r12_drive_audit_archive import drive,OPERATIONS
from googleapiclient.http import MediaIoBaseUpload
ROOT=pathlib.Path(__file__).resolve().parents[1]
def payload(report,run_id):
 assert report["date_start"]=="2026-01-01" and report["cutoff"]=="2026-11-07"
 assert not report["all_year_tier_release"] and not report["production_cas_proven"]
 data={k:report[k] for k in ("schema","date_start","cutoff","calendar_months",
   "source_month_cells","inspection_status","object_candidates",
   "ambiguous_month_path_count","stage_candidate_files_by_month",
   "eligible_dataset_denominator","scoped_prior_receipts","current_canary",
   "governance","source_data_downloaded","silver_new_conversions",
   "gold_pit_new_computations","all_year_tier_release","official_source_missing_proven",
   "production_cas_proven","blocking_causes","release_decision")}
 if report.get("prior_raw_archive"):
  data["prior_raw_archive"]=report["prior_raw_archive"]
 data["run_id"]=str(run_id);data["record_type"]="AUDIT_AND_SCOPED_CANARY_NOT_FULL_YEAR_RELEASE"
 return (json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
def main():
 report=json.loads((ROOT/"annual_2026/report.json").read_text())
 flags=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
 assert flags["BULK_COPY_APPROVED"] is False and flags["RELEASE_APPROVED"] is False
 data=payload(report,os.getenv("GITHUB_RUN_ID","LOCAL"))
 sha=hashlib.sha256(data).hexdigest()
 name="JARVIS_v095_2026_YTD_ACCEPTANCE_"+str(os.getenv("GITHUB_RUN_ID","LOCAL"))+"_"+sha[:16]+".json"
 s=drive()
 def find():
  out=[];token=None
  while True:
   a=s.files().list(q="'"+OPERATIONS+"' in parents and name='"+name+"' and trashed=false",
     fields="nextPageToken,incompleteSearch,files(id,name)",pageSize=100,pageToken=token).execute()
   if a.get("incompleteSearch"):raise ValueError("INCOMPLETE_DRIVE_LIST")
   out+=a.get("files",[]);token=a.get("nextPageToken")
   if not token:return out
 matched=find()
 if len(matched)>1:raise ValueError("AUDIT_REPORT_MULTIPLE_IDENTICAL_NAMES")
 if matched:
  fid=matched[0]["id"];action="REUSED"
 else:
  x=s.files().create(body={"name":name,"parents":[OPERATIONS],
      "description":"JARVIS v095 2026 YTD real data stage inventory audit (not formal release)"},
      media_body=MediaIoBaseUpload(io.BytesIO(data),mimetype="application/json",resumable=False),
      fields="id").execute()
  fid=x["id"];action="CREATED"
 read=s.files().get_media(fileId=fid).execute()
 if hashlib.sha256(read).hexdigest()!=sha:raise RuntimeError("DRIVE_SHA256_AUDIT_READBACK_FAILED")
 if len(find())!=1:raise RuntimeError("DUPLICATE_AUDIT_REPORT")
 receipt={"status":"PASS_OPERATIONS_AUDIT_SHA_READBACK","run_id":os.getenv("GITHUB_RUN_ID"),
  "sha256":sha,"action":action,"2026_year_market_data_complete":False,
  "bronze_market_source_new_downloads":report["source_data_downloaded"]}
 (ROOT/"annual_2026/drive_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(receipt,ensure_ascii=False))
if __name__=="__main__":sys.exit(main())
