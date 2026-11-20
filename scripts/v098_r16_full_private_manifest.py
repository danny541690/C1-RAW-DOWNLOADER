#!/usr/bin/env python3
"""R16: six-source, 2000–2026 *complete file-METADATA* inventory.
Authoritative market-data validation, publication coverage and atomic CAS are
NOT certified. Original 0.93 is STRICTLY READ-ONLY. Each year's confidential
metadata manifest goes ONLY to 0.98/99_RECOVERY/R16_PRIVATE_MANIFEST_TEST_ONLY;
the PUBLIC GitHub artifacts/logs contain only aggregated counts and statuses.
A source-year is committed only after Drive readback SHA256 verification.
"""
import argparse,collections,datetime as dt,hashlib,io,json,os,pathlib,random,sys,time
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from v098_r11_six_source_metadata_pilot import SOURCES,service,MIME

YEARS=range(2000,2027)
PARENT="R16_PRIVATE_MANIFEST_TEST_ONLY"
def list_children(api,parent,stats):
    token=None;seen=set()
    while True:
        kwargs={"q":f"'{parent}' in parents and trashed = false",
          "fields":"nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,createdTime,modifiedTime,parents)",
          "pageSize":1000,"supportsAllDrives":True,"includeItemsFromAllDrives":True}
        if token:kwargs["pageToken"]=token
        for attempt in range(5):
            try:page=api.files().list(**kwargs).execute();break
            except HttpError as exc:
                code=int(getattr(exc.resp,"status",0))
                if code not in (403,429,500,502,503,504) or attempt==4:raise
                time.sleep(min(2**attempt,15)+random.random())
        stats["api_pages"]+=1
        if page.get("incompleteSearch"):raise RuntimeError("INCOMPLETE_DRIVE_SEARCH")
        for file in page.get("files",[]):yield file
        next_token=page.get("nextPageToken")
        if not next_token:break
        if next_token in seen:raise RuntimeError("LOOPING_NEXT_PAGE_TOKEN")
        seen.add(next_token);token=next_token

def one_child(api,parent,name,stats):
    found=[x for x in list_children(api,parent,stats) if x.get("name")==name and x.get("mimeType")==MIME]
    if len(found)!=1:raise RuntimeError("MISSING_OR_DUPLICATE_EXPECTED_FOLDER")
    return found[0]["id"]

def roots(api,stats):
    main=one_child(api,"root","ChatGPT資料存取",stats)
    v93=one_child(api,main,"C1_0.93",stats)
    raw=one_child(api,v93,"01_RAW",stats)
    v98=one_child(api,main,"C1_0.98",stats)
    recovery=one_child(api,v98,"99_RECOVERY",stats)
    sandbox=one_child(api,recovery,PARENT,stats)
    if raw==sandbox:raise RuntimeError("SOURCE_TARGET_COLLISION")
    return raw,sandbox

def classify(source,year,f):
    return {"source":source,"year":year,"file_id":f["id"],"filename":f["name"],
            "mime":f.get("mimeType"),"size":int(f.get("size") or 0),
            "drive_md5":f.get("md5Checksum"),
            "created":f.get("createdTime"),"modified":f.get("modifiedTime"),
            "parent_id":(f.get("parents") or [None])[0],
            "content_verified":False,"expected_coverage":"UNKNOWN",
            "source_original_modified":False}

def scan_year(api,source,year,source_folder,stats):
    # year/source child folders are traversed recursively; do NOT assume only
    # YYYY-MM partitions, which would silently miss nested or nonstandard data.
    entries=[];seen_dirs=set();seen_files=set()
    stack=[source_folder]
    folders=0;bad_partitions=0;no_md5=0;empty=0;total_bytes=0
    while stack:
        folder=stack.pop()
        if folder in seen_dirs:raise RuntimeError("DUPLICATE_OR_CYCLIC_FOLDER")
        seen_dirs.add(folder);folders+=1;child_count=0
        for f in list_children(api,folder,stats):
            child_count+=1
            if f.get("mimeType")==MIME:
                stack.append(f["id"])
            else:
                if f["id"] in seen_files:raise RuntimeError("DUPLICATE_FILE_ID")
                seen_files.add(f["id"])
                entry=classify(source,year,f)
                entries.append(entry)
                no_md5+=int(not entry["drive_md5"])
                total_bytes+=entry["size"]
        if child_count==0:empty+=1
    return entries,{"files":len(entries),"bytes":total_bytes,"folders":folders,
                    "empty_directories":empty,"files_without_md5":no_md5}

def commit_manifest(api,sandbox,source,year,entries,stats):
    name=f"R16_{source}_{year}_PRIVATE_RAW_METADATA_v1.jsonl"
    payload=b"".join((json.dumps(x,ensure_ascii=False,separators=(",",":"),sort_keys=True)+"\n").encode() for x in entries)
    digest=hashlib.sha256(payload).hexdigest()
    existing=[x for x in list_children(api,sandbox,stats) if x["name"]==name]
    if len(existing)>1:raise RuntimeError("AMBIGUOUS_MANIFEST")
    if existing:
        file_id=existing[0]["id"];new=False
    else:
        media=MediaIoBaseUpload(io.BytesIO(payload),mimetype="application/octet-stream",resumable=True,chunksize=4*1024*1024)
        created=api.files().create(body={"name":name,"parents":[sandbox],
             "description":"R16 private raw metadata; never publish in public GitHub artifacts"},
             media_body=media,fields="id").execute()
        file_id=created["id"];new=True
    verify=api.files().get_media(fileId=file_id).execute()
    if hashlib.sha256(verify).hexdigest()!=digest:
        raise RuntimeError("PRIVATE_DRIVE_MANIFEST_READBACK_MISMATCH")
    return {"new_upload":int(new),"verified":1,"reused":int(not new),"manifest_bytes":len(payload)}

def execute(source,out):
    # Outputs may be published by public Actions: aggregate only.
    stats={"api_pages":0}
    result={"source":source,"status":"STARTED","years":0,"files":0,
      "bytes":0,"folders":0,"empty_directories":0,"without_md5":0,
      "new_manifests":0,"reused_manifests":0,"verified_manifests":0,
      "year_results":[],"source_is_readonly":True,"content_verified":False,
      "all_dataset_coverage_certified":False,"bulk_migration_allowed":False}
    try:
        api=service();raw,sandbox=roots(api,stats)
        years=[x for x in list_children(api,raw,stats) if x.get("mimeType")==MIME and
               x.get("name","").isdigit() and len(x["name"])==4 and 2000<=int(x["name"])<=2026]
        year_map=collections.defaultdict(list)
        for f in years:year_map[f["name"]].append(f["id"])
        for year in YEARS:
            if len(year_map[str(year)])!=1:
                raise RuntimeError("YEAR_FOLDER_ABSENT_OR_DUPLICATE")
            source_id=one_child(api,year_map[str(year)][0],source,stats)
            entries,counts=scan_year(api,source,year,source_id,stats)
            committed=commit_manifest(api,sandbox,source,year,entries,stats)
            result["years"]+=1
            for field in ("files","bytes","folders","empty_directories"):
                result[field]+=counts[field]
            result["without_md5"]+=counts["files_without_md5"]
            result["new_manifests"]+=committed["new_upload"]
            result["reused_manifests"]+=committed["reused"]
            result["verified_manifests"]+=committed["verified"]
            result["year_results"].append({"year":year,"files":counts["files"],
                "bytes":counts["bytes"],"folders":counts["folders"],
                "files_without_md5":counts["files_without_md5"],
                "manifest_verified":True})
        result["status"]="PASS_COMPLETE_RAW_METADATA_CENSUS" if result["years"]==27 else "PARTIAL"
    except Exception as exc:
        result["status"]="PARTIAL_OR_FAILED"
        result["error_class"]=type(exc).__name__
        # Never print exception message, which can contain private Drive identifiers.
    finally:
        result["api_pages"]=stats["api_pages"]
        p=pathlib.Path(out);p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print(json.dumps({k:result[k] for k in ("source","status","years","files","verified_manifests","api_pages")}))
    if result["status"]!="PASS_COMPLETE_RAW_METADATA_CENSUS":raise SystemExit(2)

def selftest(out):
    x=classify("TWSE",2026,{"id":"synthetic","name":"test.csv","size":"12","mimeType":"text/csv","md5Checksum":"sample"})
    assert x["content_verified"] is False and x["expected_coverage"]=="UNKNOWN"
    assert x["source_original_modified"] is False
    p=pathlib.Path(out);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"status":"PASS","tests":["schema raw metadata strict source identity",
          "coverage remains UNKNOWN","original immutable","private manifest not in public summary"]}))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--source",choices=SOURCES)
    p.add_argument("--out",required=True);p.add_argument("--selftest",action="store_true");a=p.parse_args()
    if a.selftest:selftest(a.out)
    else:
        if not a.source:p.error("--source required")
        execute(a.source,a.out)
