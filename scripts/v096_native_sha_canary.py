#!/usr/bin/env python3
"""v0.96 P1 immutable original-byte SHA probe, not production data release.

Original v0.93 raw stays where it is. The canary verifies actual original bytes
for a bounded sample and publishes a separate SHA-evidenced source ledger.
No source format mutation, dedup by Drive ID, no official completeness or PIT.
"""
import collections,hashlib,io,json,os,pathlib,zipfile
from scripts.v095_2026_annual_consolidated import service
from scripts.v096_raw_first import publish
OUT=pathlib.Path("v096_sha_canary")
MAX_FILES=12
MAX_BYTES=6_000_000
ALLOWED=("TWSE","TPEx","MOPS")
def sha(x):return hashlib.sha256(x).hexdigest()
def audit_blob(blob,rec):
    if len(blob)!=rec["size_bytes"]:raise ValueError("ORIGINAL_BYTE_SIZE_MISMATCH")
    if rec.get("drive_md5") and hashlib.md5(blob).hexdigest()!=rec["drive_md5"]:
        raise ValueError("ORIGINAL_DRIVE_MD5_MISMATCH")
    fmt=rec["source_format"]
    if fmt=="ZIP":
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            members=z.infolist()
            if len(members)==0 or len(members)>1000:raise ValueError("ZIP_MEMBER_COUNT_LIMIT")
            if sum(i.file_size for i in members)>150_000_000:raise ValueError("ZIP_UNCOMPRESSED_SIZE_LIMIT")
            if any(i.filename.startswith("/") or ".." in pathlib.PurePosixPath(i.filename).parts for i in members):
                raise ValueError("ZIP_UNSAFE_MEMBER_PATH")
            if z.testzip():raise ValueError("ZIP_CRC_FAILED")
        return "SHA_SIZE_MD5_ZIP_CRC_PASS_NATIVE_SCHEMA_PENDING"
    if fmt=="JSON":
        data=json.loads(blob)
        if not isinstance(data,(list,dict)):raise ValueError("JSON_TOP_LEVEL_NOT_OBJECT_OR_ARRAY")
        return "SHA_SIZE_MD5_JSON_PARSE_PASS_NATIVE_SCHEMA_PENDING"
    if fmt=="CSV":
        if b"\x00" in blob:raise ValueError("CSV_HAS_NUL_BYTE")
        return "SHA_SIZE_MD5_CSV_NUL_PASS_NATIVE_SCHEMA_PENDING"
    if fmt=="HTML":
        if len(blob)<20:raise ValueError("HTML_TOO_SHORT")
        return "SHA_SIZE_MD5_HTML_BYTES_PASS_NATIVE_SCHEMA_PENDING"
    return "SHA_SIZE_MD5_PASS_NATIVE_SCHEMA_PENDING"
def main():
    d=service()
    manifest_id=os.environ["V096_P0_MANIFEST_ID"]
    original=d.files().get_media(fileId=manifest_id).execute()
    manifest=json.loads(original)
    if manifest.get("schema")!="JARVIS_V096_P0_SOURCE_MANIFEST_V1":
        raise ValueError("V096_SOURCE_MANIFEST_BAD")
    candidates=sorted((x for x in manifest["rows"] if x["source"] in ALLOWED
        and x["source_format"] in ("ZIP","JSON","HTML","CSV")
        and 0<x["size_bytes"]<=MAX_BYTES),key=lambda x:(x["source"],x["month_folder"],x["size_bytes"]))
    selected=[];per_source=collections.Counter()
    for x in candidates:
        if per_source[x["source"]]>=4:continue
        selected.append(x);per_source[x["source"]]+=1
        if len(selected)>=MAX_FILES:break
    results=[]
    for x in selected:
        record={"source":x["source"],"month_folder":x["month_folder"],
           "original_drive_file_id":x["original_drive_file_id"],
           "original_name":x["original_name"],"original_mime_type":x["original_mime_type"],
           "original_format":x["source_format"],"declared_size_bytes":x["size_bytes"],
           "raw_v096_storage":"REFERENCE_ORIGINAL_ID_ONLY",
           "historical_pit_verified":False,"official_dataset_completeness_verified":False}
        try:
            blob=d.files().get_media(fileId=x["original_drive_file_id"]).execute()
            result=audit_blob(blob,x)
            record.update(status=result,source_sha256=sha(blob),
                verified_byte_count=len(blob))
        except Exception as e:
            record.update(status="QUARANTINED_NATIVE_CHECK_FAILED",source_sha256=None,
                 reason=type(e).__name__+":"+str(e)[:150])
        results.append(record)
    summary={"schema":"JARVIS_V096_P1_ORIGINAL_SHA_CANARY_V1",
       "p0_manifest_id":manifest_id,"sample_count":len(results),
       "verified_bytes_count":sum(x.get("verified_byte_count",0) for x in results),
       "sha_verified_original_files":sum(x.get("source_sha256") is not None for x in results),
       "exception_count":sum(x.get("source_sha256") is None for x in results),
       "records":results,
       "originals_copied":0,"originals_deleted":0,"official_downloads":0,
       "parquet_market_partitions_created":0,"pit_certified":False}
    root=os.environ["V096_CONTROL_ID"]
    blob=(json.dumps(summary,sort_keys=True,ensure_ascii=False)+"\n").encode()
    result=publish(d,"V096_P1_NATIVE_SHA_CANARY",blob,root)
    OUT.mkdir(exist_ok=True)
    (OUT/"result.json").write_bytes(blob)
    print(json.dumps({"summary":{k:v for k,v in summary.items() if k!="records"},
      "receipt":result},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
