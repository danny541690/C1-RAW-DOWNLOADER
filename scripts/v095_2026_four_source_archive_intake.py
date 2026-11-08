#!/usr/bin/env python3
"""Safe four-source 2026 archived Bronze candidate intake.

v0.93 first: copy only original native ZIP archives after SHA/CRC and source/month
manifest verification into isolated v0.95 staging folders. Never promote archive
CRC as verified financial contents or manufacture Silver/Gold/PIT. Missing
eligible files are reported for dedicated official-source backfill adapters.
"""
import datetime as dt
import hashlib, io, json, os, pathlib, sys, zipfile
from scripts.v095_2026_annual_consolidated import service,BRONZE_ROOTS,FOLDER
from scripts.v095_2026_prior_raw_reuse_audit import YEAR_PARENT
from scripts.v095_ultimate_r1_november_official import folder,save
SOURCE=os.environ.get("V095_BRONZE_SOURCE","")
if SOURCE not in ("MOPS","TDCC","TAIFEX","NDC"):raise ValueError("INVALID_SOURCE")
MAX_SOURCE_FILES=min(int(os.environ.get("V095_ARCHIVE_BATCH","3")),6)
MAX_BYTES=20_000_000
MAX_INSPECT_PER_RUN=300

def ls(d,folder):
    rows=[];token=None
    while True:
        result=d.files().list(q="'"+folder+"' in parents and trashed=false",
          fields="nextPageToken,incompleteSearch,files(id,name,size,mimeType,md5Checksum)",pageSize=500,pageToken=token).execute()
        if result.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SOURCE_LIST")
        rows.extend(result.get("files",[]))
        if len(rows)>15000:raise RuntimeError("DRIVE_SOURCE_LIST_TOO_LARGE_FOR_BOUNDED_BATCH")
        token=result.get("nextPageToken")
        if not token:return rows
OUT=pathlib.Path("v095_2026_source_archives")
def digest(b):return hashlib.sha256(b).hexdigest()
def validate_zip(b,source,month):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
        infos=z.infolist()
        if not infos or len(infos)>200 or sum(x.file_size for x in infos)>150_000_000:raise ValueError("ZIP_EXPANSION_LIMIT")
        if any(x.flag_bits & 1 or x.file_size>MAX_BYTES or x.filename.startswith("/") or ".." in pathlib.PurePosixPath(x.filename).parts for x in infos):raise ValueError("UNSAFE_ARCHIVE")
        if z.testzip():raise ValueError("ZIP_CRC")
        manifests=[x.filename for x in infos if x.filename.endswith("manifest.json")]
        if len(manifests)!=1:raise ValueError("MISSING_OR_DUPLICATE_MANIFEST")
        m=json.loads(z.read(manifests[0]))
        if m.get("source")!=source or m.get("month")!=month:raise ValueError("MANIFEST_SOURCE_MONTH_MISMATCH")
        units=m.get("units",[])
        if not isinstance(units,list) or not units:raise ValueError("MANIFEST_NO_UNITS")
        rawmembers={pathlib.PurePosixPath(x.filename).name for x in infos if x.filename!=manifests[0]}
        for x in units:
            if not isinstance(x,dict) or not x.get("file") or pathlib.PurePosixPath(x["file"]).name not in rawmembers:
                raise ValueError("MANIFEST_MEMBER_MISSING")
            if x.get("sha256"):
                member=next(i.filename for i in infos if pathlib.PurePosixPath(i.filename).name==pathlib.PurePosixPath(x["file"]).name)
                if digest(z.read(member))!=x["sha256"]:raise ValueError("MANIFEST_MEMBER_SHA_MISMATCH")
        return len(units)
def main():
    OUT.mkdir(exist_ok=True)
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    months=[f"2026-{n:02d}" for n in range(1,today.month+1)]
    d=service()
    old=[x for x in ls(d,YEAR_PARENT) if x["name"]==SOURCE and x["mimeType"]==FOLDER]
    if len(old)!=1:raise RuntimeError("UNIQUE_LEGACY_SOURCE_DIRECTORY_MISSING")
    new=BRONZE_ROOTS[SOURCE]
    completed=[];blocked=[];scanned=0;reused=0
    for month in months:
        src=[x for x in ls(d,old[0]["id"]) if x["name"]==month and x["mimeType"]==FOLDER]
        if len(src)!=1:
            blocked.append({"month":month,"state":"V093_MONTH_FOLDER_NOT_UNIQUE_OR_MISSING"})
            continue
        items=ls(d,src[0]["id"])
        dest=folder(d,new,month+"_V093_REUSE_CANDIDATE")
        stored={x.get("md5Checksum") for x in ls(d,dest) if x.get("md5Checksum")}
        for item in sorted(items,key=lambda x:x["name"]):
            if not item["name"].lower().endswith(".zip"):continue
            if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
            if item.get("md5Checksum") and item["md5Checksum"] in stored:
                reused+=1
                continue
            scanned+=1
            try:
                if int(item.get("size",0))>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                b=d.files().get_media(fileId=item["id"]).execute()
                if len(b)>MAX_BYTES:raise ValueError("ARCHIVE_OVER_BOUNDED_LIMIT")
                members=validate_zip(b,SOURCE,month)
                name="V095_V093_"+SOURCE+"_"+month+"_"+digest(b)[:24]+".zip"
                fid,action=save(d,dest,name,b)
                completed.append({"month":month,"source":SOURCE,"member_count":members,
                                  "sha256":digest(b),"file_id":fid,"action":action,
                                  "state":"STORAGE_SHA_CRC_MANIFEST_PASS_NATIVE_SCHEMA_PENDING"})
            except Exception as e:
                blocked.append({"month":month,"name_digest":digest(item["name"].encode())[:12],
                                "reason":type(e).__name__+":"+str(e)[:110]})
        if len(completed)>=MAX_SOURCE_FILES or scanned>=MAX_INSPECT_PER_RUN:break
    out={"source":SOURCE,"run_id":os.getenv("GITHUB_RUN_ID"),"completed_archives":completed,
         "blocked":blocked[:50],"scanned":scanned,"previously_reused_archive_skips":reused,
         "new_bronze_candidate_archives":sum(x["action"]=="CREATED" for x in completed),
         "native_dataset_schema_verified":False,"silver_conversion":"BLOCKED_PENDING_APPROVED_ADAPTER",
         "gold_conversion":"BLOCKED_PENDING_SILVER_AND_PIT",
         "historical_pit_verified":False,"year_complete":False}
    (OUT/"result.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"source":SOURCE,"new_archives":out["new_bronze_candidate_archives"],
                      "scanned":scanned,"blocked":len(blocked),"unchanged_archive_skipped":reused,
                      "silver":out["silver_conversion"],"gold":out["gold_conversion"]},ensure_ascii=False))
if __name__=="__main__":main()
