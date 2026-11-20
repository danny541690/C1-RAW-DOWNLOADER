#!/usr/bin/env python3
"""R18 JARVIS repair: verify 7 exact-path conflicts and v0.93->R15 isolated copies.
Read-only on all original and target files. Save detailed lineage ONLY to
C1_0.98/99_RECOVERY/R16_PRIVATE_MANIFEST_TEST_ONLY, NOT to public GitHub.
No deletes, no Bronze/Silver/Gold, no bulk approval.
Bounded real-source and sandbox byte comparison integration test after YAML and dependency correction.
"""
import argparse,collections,hashlib,io,json,pathlib,sys,zipfile
from v098_r11_six_source_metadata_pilot import service,MIME
from v098_r16_full_private_manifest import list_children,one_child
from googleapiclient.http import MediaIoBaseUpload

SOURCES=("TWSE","TPEx")
def sha(blob):return hashlib.sha256(blob).hexdigest()
def md5(blob):return hashlib.md5(blob).hexdigest()
def safe_write(path,obj):
 p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,indent=2,sort_keys=True))
def exact(api,parent,name,stats,kind=None):
 found=[r for r in list_children(api,parent,stats) if r["name"]==name and (kind is None or r["mimeType"]==kind)]
 if len(found)!=1:raise RuntimeError("MISSING_OR_DUPLICATE_FOLDER_OR_FILE")
 return found[0]
def roots(api,stats):
 main=one_child(api,"root","ChatGPT資料存取",stats)
 v98=one_child(api,main,"C1_0.98",stats)
 recovery=one_child(api,v98,"99_RECOVERY",stats)
 manifest=one_child(api,recovery,"R16_PRIVATE_MANIFEST_TEST_ONLY",stats)
 staging=one_child(api,recovery,"R15_ISOLATED_TEST_ONLY",stats)
 return manifest,staging
def load_27(api,folder,source,stats):
 mapping={r["name"]:r for r in list_children(api,folder,stats)}
 for year in range(2000,2027):
  name=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
  if name not in mapping:raise RuntimeError("MISSING_R16_YEAR_MANIFEST")
  blob=api.files().get_media(fileId=mapping[name]["id"]).execute()
  yield year,[json.loads(x) for x in blob.splitlines() if x.strip()]
def content_profile(data):
 if data[:4]==b"PK\x03\x04":
  z=zipfile.ZipFile(io.BytesIO(data))
  corrupt=z.testzip()
  return {"type":"zip","crc_ok":corrupt is None,"members":len(z.infolist()),
    "extensions":dict(collections.Counter(pathlib.PurePosixPath(x.filename).suffix.lower() or "<none>" for x in z.infolist() if not x.is_dir()))}
 if data[:2]==b"\x1f\x8b":return {"type":"gzip","crc_ok":None}
 stripped=data.lstrip(b"\xef\xbb\xbf\t\r\n ")
 if stripped[:1] in (b"{",b"["):return {"type":"json_candidate","crc_ok":None}
 if b"," in data[:1024] or b"\t" in data[:1024]:
  return {"type":"delimited_candidate","crc_ok":None}
 return {"type":"opaque","crc_ok":None}
def analyze(source,out,limit=12*1024*1024):
 stat={"api_pages":0}
 summary={"source":source,"status":"INIT","duplicate_groups":0,"duplicate_ids":0,
   "metadata_equal_groups":0,"byte_sha_verified_groups":0,"byte_sha_mismatch_groups":0,
   "metadata_only_groups":0,"source_staging_bytes_sha_match":0,
   "target_profile_type":"UNKNOWN","origin_profile_type":"UNKNOWN",
   "staging_zip_crc_ok":None,"originals_modified":False,"new_upload":0,
   "eligible_for_production":False}
 private_report={"source":source,"rule":"preserve all source Drive IDs and lineage aliases",
                 "pairs":[],"target":[]}
 try:
  api=service()
  manifests,staging=roots(api,stat)
  groups=[]
  target_candidates=[]
  for year,rows in load_27(api,manifests,source,stat):
   by=collections.defaultdict(list)
   for x in rows:
    by[(x.get("parent_id"),x.get("filename"))].append(x)
    if year==2026 and x.get("drive_md5") and 0<int(x.get("size") or 0)<=262144:
     target_candidates.append(x)
   groups.extend((year,v) for v in by.values() if len(v)>1)
  for year,group in groups:
   summary["duplicate_groups"]+=1;summary["duplicate_ids"]+=len(group)-1
   if len({(r["drive_md5"],r["size"]) for r in group})==1:summary["metadata_equal_groups"]+=1
   else:summary["byte_sha_mismatch_groups"]+=1
   evidence={"year":year,"source_ids":[x["file_id"] for x in group],
             "same_folder_same_name":True,"size":[x["size"] for x in group],
             "drive_md5":[x["drive_md5"] for x in group],
             "preserve_ids":True}
   if all(0<int(r["size"])<=limit for r in group):
    blobs=[api.files().get_media(fileId=r["file_id"]).execute() for r in group]
    if any(len(b)!=int(r["size"]) or md5(b)!=r["drive_md5"] for r,b in zip(group,blobs)):
     raise RuntimeError("REAL_SOURCE_MD5_MISMATCH")
    hashes=[sha(b) for b in blobs]; evidence["sha256"]=hashes
    if len(set(hashes))==1:summary["byte_sha_verified_groups"]+=1
    else:summary["byte_sha_mismatch_groups"]+=1
   else:summary["metadata_only_groups"]+=1
   # Canonical for equivalent bytes only; never delete the other original.
   evidence["logical_canonical_id"]=min(r["file_id"] for r in group)
   private_report["pairs"].append(evidence)
  target=exact(api,staging,f"R15_SANDBOX_COPY_{source}_2026_10.bin",stat)
  b=api.files().get_media(fileId=target["id"]).execute()
  summary["target_profile_type"]=content_profile(b)["type"]
  if b[:4]==b"PK\x03\x04":summary["staging_zip_crc_ok"]=content_profile(b)["crc_ok"]
  metadata_matches=[r for r in target_candidates if r["drive_md5"]==md5(b) and int(r["size"])==len(b)]
  if not metadata_matches:raise RuntimeError("STAGING_NOT_FOUND_IN_R16_MANIFEST")
  found=False
  for r in metadata_matches:
   raw=api.files().get_media(fileId=r["file_id"]).execute()
   if md5(raw)==r["drive_md5"] and sha(raw)==sha(b):
    summary["source_staging_bytes_sha_match"]=1
    summary["origin_profile_type"]=content_profile(raw)["type"]
    private_report["target"].append({"staging_file_id":target["id"],"source_file_id":r["file_id"],
         "source_sha256":sha(raw),"target_sha256":sha(b),"source_profile":content_profile(raw),
         "target_profile":content_profile(b)})
    found=True;break
  if not found:raise RuntimeError("SOURCE_TARGET_BYTES_MISMATCH")
  # Private write: idempotent immutable report, no sensitive public output.
  name=f"R18_{source}_PRIVATE_RECONCILIATION_V1.json"
  payload=json.dumps(private_report,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
  matches=[x for x in list_children(api,manifests,stat) if x["name"]==name]
  if len(matches)>1:raise RuntimeError("DUPLICATE_PRIVATE_REPORT")
  if not matches:
   f=api.files().create(body={"name":name,"parents":[manifests]},
     media_body=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/json"),
     fields="id").execute();rid=f["id"];summary["new_upload"]=1
  else:rid=matches[0]["id"]
  if sha(api.files().get_media(fileId=rid).execute())!=sha(payload):
   raise RuntimeError("PRIVATE_REPORT_MISMATCH")
  summary["status"]="PASS_REAL_BYTES_OR_COVERAGE_HOLD" if summary["byte_sha_mismatch_groups"]==0 else "HOLD_CONTENT_MISMATCH"
 except Exception as exc:
  summary["status"]="TEST_ERROR";summary["error_class"]=type(exc).__name__
 finally:
  summary["api_pages"]=stat["api_pages"]
  safe_write(out,summary)
  print(json.dumps(summary))
 if summary["status"]!="PASS_REAL_BYTES_OR_COVERAGE_HOLD":sys.exit(2)

def selftest(path):
 assert sha(b"x")!=sha(b"y")
 assert content_profile(b'{"a":1}')["type"]=="json_candidate"
 assert content_profile(b"a,b\n1,2")["type"]=="delimited_candidate"
 safe_write(path,{"status":"PASS","tests":["byte mismatch detection","format signature"],
                 "production_bulk_migration_allowed":False})
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES)
 p.add_argument("--out",required=True);p.add_argument("--selftest",action="store_true");a=p.parse_args()
 if a.selftest:selftest(a.out)
 else:
  if not a.source:p.error("--source required")
  analyze(a.source,a.out)
