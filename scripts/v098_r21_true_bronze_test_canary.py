#!/usr/bin/env python3
"""R21 v098 real BRONZE-path TEST-ONLY canary. Original 0.93 read-only.
Only writes into 20_BRONZE/_PILOT_PENDING_G01/R21_TEST_ONLY_NO_SILVER_INGEST.
One immutable source original per official source (max 1MB); SHA256 readback,
MD5 source metadata, ZIP CRC where relevant; replay reuses exact file contents.
No real Bronze production cohort, Silver, Gold, or release marker is written.
Second bounded R21 six-source replay check: no duplicate target copies.
"""
import argparse,hashlib,io,json,pathlib,sys,zipfile
from googleapiclient.http import MediaIoBaseUpload
from v098_r11_six_source_metadata_pilot import SOURCES,service
from v098_r16_full_private_manifest import list_children,one_child
CAP=1048576
def digest(b):return hashlib.sha256(b).hexdigest()
def report(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True))
 print(json.dumps({k:v for k,v in obj.items() if k in ("source","status","new_upload","reused","verified","payload_size","original_type")}))
def run(source,out):
 stats={"api_pages":0}
 outdata={"source":source,"status":"STARTED","new_upload":0,"reused":0,
          "verified":0,"payload_size":0,"original_type":"UNKNOWN",
          "source_original_unchanged":True,"production_silver_gold_disabled":True,
          "bulk_migration_allowed":False}
 try:
  api=service()
  main=one_child(api,"root","ChatGPT資料存取",stats)
  v98=one_child(api,main,"C1_0.98",stats)
  bronze=one_child(api,v98,"20_BRONZE",stats)
  pilot=one_child(api,bronze,"_PILOT_PENDING_G01",stats)
  target=one_child(api,pilot,"R21_TEST_ONLY_NO_SILVER_INGEST",stats)
  recovery=one_child(api,v98,"99_RECOVERY",stats)
  private=one_child(api,recovery,"R16_PRIVATE_MANIFEST_TEST_ONLY",stats)
  names={x["name"]:x["id"] for x in list_children(api,private,stats)}
  candidate=None
  for year in range(2026,1999,-1):
   key=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
   if key not in names:raise RuntimeError("R16_YEAR_MANIFEST_MISSING")
   b=api.files().get_media(fileId=names[key]).execute()
   rows=[json.loads(line) for line in b.splitlines() if line.strip()]
   eligible=[r for r in rows if 0<int(r.get("size") or 0)<=CAP and r.get("drive_md5")]
   if eligible:
    candidate=min(eligible,key=lambda r:(int(r["size"]),r["file_id"]))
    break
  if not candidate:
   outdata["status"]="NO_ELIGIBLE_SAMPLE_COVERAGE_HOLD"
  else:
   raw=api.files().get_media(fileId=candidate["file_id"]).execute()
   if len(raw)!=int(candidate["size"]) or hashlib.md5(raw).hexdigest()!=candidate["drive_md5"]:
    raise RuntimeError("SOURCE_MD5_OR_SIZE_MISMATCH")
   if raw[:4]==b"PK\x03\x04":
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
     if z.testzip() is not None:raise RuntimeError("SOURCE_ZIP_CRC_FAILED")
    outdata["original_type"]="ZIP"
   elif raw.lstrip().startswith((b"{",b"[")):outdata["original_type"]="JSON"
   else:outdata["original_type"]="OTHER"
   filename=f"R21_TEST_ONLY_{source}_SOURCE_COPY.bin"
   existing=[r for r in list_children(api,target,stats) if r["name"]==filename]
   if len(existing)>1:raise RuntimeError("DUPLICATE_TARGET_NAME")
   if existing:
    file_id=existing[0]["id"]
    outdata["reused"]=1
   else:
    media=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/octet-stream",resumable=False)
    result=api.files().create(body={"name":filename,"parents":[target],
             "description":"R21 test-only canary; exclude from Silver Gold and production Bronze"},
             media_body=media,fields="id").execute()
    file_id=result["id"];outdata["new_upload"]=1
   final=api.files().get_media(fileId=file_id).execute()
   if len(final)!=len(raw) or digest(final)!=digest(raw):
    raise RuntimeError("SOURCE_TARGET_SHA256_MISMATCH")
   outdata.update({"status":"PASS_TEST_ONLY_BRONZE_PATH_SHA256","verified":1,
                   "payload_size":len(raw),"path_verified":True,
                   "production_bronze_committed":False})
 except Exception as e:
  outdata.update({"status":"FAIL_TEST_ONLY","error_class":type(e).__name__})
 finally:
  outdata["api_pages"]=stats["api_pages"];report(out,outdata)
 if outdata["status"]=="FAIL_TEST_ONLY":sys.exit(2)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES,required=True)
 p.add_argument("--out",required=True);a=p.parse_args();run(a.source,a.out)
