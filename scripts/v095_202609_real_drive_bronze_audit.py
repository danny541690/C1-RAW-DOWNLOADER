"""Actual Google Drive byte audit of September 2026 v0.95 Bronze.
No mutation, no misleading full-month PASS while source universe unapproved.
"""
import argparse,collections,csv,hashlib,io,json,os,pathlib,re,zipfile
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from scripts.v095_official_first_fallback import POLICY

ROOT="1oCcRwevEWtRRutOkXSxds5nPF4Br5two"
SOURCE_FOLDERS={"TWSE":"1abuHJHAVv_a3AOpG4hKfguyF-qpXSKm-","TPEx":"1fcWwV2qK_aoevqlDSc9_9aNJ6lKFmSQ2",
"MOPS":"14N6x7HDLt5nMwOEUE7K818iOw4NHjwWg","TDCC":"1_Pl4nN0HRXnIJSjJrt0iX2Lq7nkS1pcV",
"TAIFEX":"1fr-4WqvgHazBZV-YYreidxQ03TY5aO2o","NDC":"1JeqoAWecyvlXEo8odMvLqdVu6ddubeuJ"}
MAIN={"TWSE":"16G68HaFVX1Ddmu23xWeexhNDn0DWryet","TPEx":"1xz7SdR0itvatFQ_IaAdpsAw9fN6i-0iu",
"MOPS":"1wAHL6qfZnSC3RIKvShhL4At3ZNs32bvj","TDCC":"1sRULF-1_1UTf5x2E6mWoDVx0BgdP2GS8",
"NDC":"16hZu79uBk7OWyOnv7-4ga8QZnXl4ANWr"}
TPEX_RECOVERY=["1Tmh0sEZZCWFvdeTQ7eAOMuLX8WEY7ehR","12lSt3OY0WclDoCc6TAk3peruEW2-K9_r","1kXahDil5I6Mda5SN0XE-LG0bN8LZBm0y"]
NATIVE_TDCC_V093="1mOKduUYq2-LGonelM4fiIV-IY3HXVtm-"
def sha(b):return hashlib.sha256(b).hexdigest()
def service():
 required=("GOOGLE_CLIENT_ID","GOOGLE_CLIENT_SECRET","GOOGLE_REFRESH_TOKEN")
 if any(not os.environ.get(k) for k in required):raise RuntimeError("MISSING_GOOGLE_DRIVE_OAUTH_SECRETS")
 c=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],token_uri="https://oauth2.googleapis.com/token",
               client_id=os.environ["GOOGLE_CLIENT_ID"],client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
               scopes=["https://www.googleapis.com/auth/drive"])
 c.refresh(Request());return build("drive","v3",credentials=c,cache_discovery=False)
def listing(svc,parent):
 ret=[];page=None
 while True:
  q=svc.files().list(q="'"+parent+"' in parents and trashed=false",pageSize=1000,pageToken=page,
    fields="nextPageToken,files(id,name,size,mimeType)",orderBy="name").execute()
  ret.extend(q.get("files",[]));page=q.get("nextPageToken")
  if not page:return ret
def raw(svc,id):return svc.files().get_media(fileId=id).execute()
def validate_main(svc,source,report):
 b=raw(svc,MAIN[source]);z=zipfile.ZipFile(io.BytesIO(b))
 assert z.testzip() is None,"MAIN_ZIP_CRC_FAIL"
 names=set(z.namelist()); report["primary_zip_bytes"]=len(b)
 if source=="TDCC":
  manifest=json.loads(z.read("complement_manifest_R1.json"))
  records=[x for x in names if x.endswith(".jsonl")]
  assert len(records)==4
  report["tdcc_weekly_files"]=len(records)
  report["tdcc_native_source_lineage_from_derived_not_certified"]=True
  return
 if source=="NDC":
  assert "NDC_11509_official_series.xlsx" in names
  w=zipfile.ZipFile(io.BytesIO(z.read("NDC_11509_official_series.xlsx")))
  assert w.testzip() is None and "xl/workbook.xml" in w.namelist()
  report["ndc_11509_xlsx_structural"]="PASS"
  return
 manifest=json.loads(z.read("manifest.json"))
 expected={"TWSE":122,"TPEx":172,"MOPS":4}[source]
 assert len(manifest["units"])==expected
 statuses=collections.Counter()
 for u in manifest["units"]:
  filename=pathlib.PurePosixPath(u.get("file") or "").name
  if not filename or filename not in names:
   statuses[u["state"]+"_NO_RAW"]+=1;continue
  data=z.read(filename)
  assert sha(data)==u.get("sha256"),"MANIFEST_SHA_MISMATCH:"+u["name"]
  assert u.get("local_readback_verified") is True
  statuses["RAW_SHA_PASS"]+=1
 report["legacy_raw_unit_status"]=dict(statuses)
 report["legacy_manifest_all_market_complete"]=manifest.get("all_market_complete",False)
 if source=="TWSE":assert statuses=={"RAW_SHA_PASS":122}
 if source=="MOPS":assert statuses=={"RAW_SHA_PASS":4}
 if source=="TPEx":
  assert statuses["RAW_SHA_PASS"]==158
  assert statuses["TRANSPORT_HOLD_NO_RAW"]==9
  assert statuses["ALTERNATE_HOLD_NO_RAW"]==5
def verify_tpex_recovery(svc,report):
 found=set()
 for fid in TPEX_RECOVERY:
  b=raw(svc,fid);z=zipfile.ZipFile(io.BytesIO(b))
  assert z.testzip() is None
  for name in z.namelist():
   m=re.search(r"(prices|institutional)_((?:2026-09-)[0-9]{2})\\.raw$",name)
   if not m:continue
   raw_bytes=z.read(name)
   obj=json.loads(raw_bytes.decode("utf-8-sig"))
   assert isinstance(obj,dict) and obj.get("tables"),"TPEX_RECOVERED_SCHEMA_INVALID"
   assert (m.group(1),m.group(2)) not in found,"DUPLICATE_TPEX_RECOVERY_UNIT"
   found.add((m.group(1),m.group(2)))
 assert len(found)==9,"OFFICIAL_TPEX_NINE_GAPS_NOT_ALL_RECOVERED"
 report["tpex_official_primary_gap_recovery"]=len(found)
 report["official_gap_remaining_within_legacy_manifest"]=0
def verify_tdcc_migration(svc,report):
 source=[x for x in listing(svc,NATIVE_TDCC_V093) if x.get("mimeType")!="application/vnd.google-apps.folder"]
 dst=listing(svc,SOURCE_FOLDERS["TDCC"])
 packages=[x for x in dst if re.fullmatch(r"TDCC_202609_NATIVE_SHARD_[012]_[0-9]{5}\\.zip",x["name"])]
 ids=set();duplicate=0;corrupt=0
 for item in packages:
  try:
   z=zipfile.ZipFile(io.BytesIO(raw(svc,item["id"])))
   if z.testzip() is not None:raise ValueError("ZIP_CRC_FAIL")
   entries=json.loads(z.read("manifest.json"))["immutable_originals"]
   for e in entries:
    b=z.read(e["archive_path"])
    if sha(b)!=e["sha256"]:raise ValueError("NATIVE_ORIGINAL_SHA_MISMATCH")
    if e["source_drive_id"] in ids:duplicate+=1
    ids.add(e["source_drive_id"])
  except Exception:corrupt+=1
 srcids={x["id"] for x in source}
 report.update(tdcc_v093_native_source_files=len(source),tdcc_v095_native_bundles=len(packages),
               tdcc_native_file_ids_verified=len(ids),tdcc_migration_missing=len(srcids-ids),
               tdcc_destination_id_outside_source=len(ids-srcids),
               tdcc_duplicate_id_count=duplicate,tdcc_bundle_failures=corrupt)
 if len(srcids-ids):report["blockers"].append("TDCC_NATIVE_10949_SOURCE_ORIGINALS_NOT_YET_ALL_MIGRATED")
 if duplicate or corrupt or ids-srcids:report["blockers"].append("TDCC_NATIVE_DUPLICATE_OR_CORRUPT_BUNDLE")
def verify_taifex(svc,report):
 f=[x for x in listing(svc,SOURCE_FOLDERS["TAIFEX"]) if x.get("mimeType")!="application/vnd.google-apps.folder"]
 hashes=collections.Counter()
 matched=0
 for x in f:
  b=raw(svc,x["id"])
  if len(b)!=int(x.get("size",len(b))):raise ValueError("TAIFEX_BYTE_SIZE_MISMATCH")
  h=sha(b);hashes[h]+=1
  if h in x["name"]:matched+=1
 assert len(f)==19
 report.update(taifex_non_tick_files=len(f),taifex_hash_suffix_verified=matched,
    taifex_identical_content_alias_extra=sum(n-1 for n in hashes.values() if n>1),
    taifex_tick_excluded_by_scope=True)
def main():
 p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCE_FOLDERS,required=True);a=p.parse_args()
 s=a.source;svc=service()
 assert POLICY["official"]["maximum_attempts_total"]==3
 assert POLICY["finmind_free"]["never_auto_replace_official"]
 report={"schema":"JARVIS_V095_202609_TRUE_DRIVE_BYTE_AUDIT_V1","source":s,"month":"2026-09",
         "actual_google_drive_byte_reads":True,"actual_finmind_requests":0,"actual_official_requests":0,
         "source_registry_universe_approved":False,"full_bronze_release_approved":False,"blockers":[]}
 try:
  if s in MAIN:validate_main(svc,s,report)
  if s=="TPEx":verify_tpex_recovery(svc,report)
  if s=="TAIFEX":verify_taifex(svc,report)
  if s=="TDCC":verify_tdcc_migration(svc,report)
  if s in ("TWSE","TPEx","MOPS","NDC","TAIFEX"):report["blockers"].append("SOURCE_DATASET_UNIVERSE_NOT_FORMALLY_APPROVED")
  report["status"]="CANDIDATE_CHECKED_WITH_BLOCKERS" if report["blockers"] else "CANDIDATE_RAW_PASS_RELEASE_UNAPPROVED"
 except Exception as e:
  report["status"]="VALIDATION_FAILURE";report["blockers"].append(type(e).__name__+":"+str(e)[:200])
 out=pathlib.Path("v095_202609_drive_byte_audit");out.mkdir(exist_ok=True)
 (out/(s+".json")).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(report,ensure_ascii=False),flush=True)
 if report["status"]=="VALIDATION_FAILURE":raise SystemExit(1)
if __name__=="__main__":main()
