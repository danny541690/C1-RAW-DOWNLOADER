#!/usr/bin/env python3
"""JARVIS C1 v0.96 RAW First P0: bounded legacy archive inventory, NOT download.

The original v0.93 file remains immutable at its Drive ID. This pilot writes
only manifests and reports to a *separate* new v0.96 Drive namespace. No official
HTTP, no bulk copy, no 443 factor or PIT certification. A partial folder listing
is explicitly marked incomplete rather than invented as data coverage.
"""
import argparse,collections,datetime as dt,hashlib,io,json,os,pathlib,re
from googleapiclient.http import MediaIoBaseUpload

LEGACY_ROOTS={"2025":"1VB9s43UHEQeZbPbLHOCcFAQewUDfjBOm",
              "2026":"1CAlRsbDEKTrb9BJlJ604SwYwQWRU3lpK"}
SOURCE_NAMES=("TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC")
FOLDER="application/vnd.google-apps.folder"
DEFAULT_MONTHS=("2025-01","2026-10")
OUT=pathlib.Path("v096_run")
MAX_ITEMS=250
def sha(blob):return hashlib.sha256(blob).hexdigest()
def classify(name):
    ext=pathlib.PurePosixPath(name).suffix.lower()
    return {"zip":"ZIP","csv":"CSV","json":"JSON","jsonl":"JSONL","xlsx":"XLSX","xls":"XLS","html":"HTML","htm":"HTML","parquet":"PARQUET"}.get(ext.lstrip("."),"OTHER")
def safe_months(value):
    months=tuple(x.strip() for x in value.split(",") if x.strip())
    if not 1<=len(months)<=4 or len(set(months))!=len(months):raise ValueError("V096_PILOT_MONTHS_1_TO_4")
    for x in months:
        if not re.fullmatch(r"202[56]-(?:0[1-9]|1[0-2])",x):
            raise ValueError("V096_2025_2026_PILOT_ONLY")
        if x[:4]=="2026" and x>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m"):
            raise ValueError("V096_FUTURE_MONTH")
    return months
def list_bounded(d,parent,max_items=MAX_ITEMS,only_folders=False):
    q="'"+parent+"' in parents and trashed=false"
    if only_folders:q+=" and mimeType='"+FOLDER+"'"
    result=[];token=None;partial=False
    while len(result)<max_items:
        page=d.files().list(q=q,pageSize=min(200,max_items-len(result)),
          fields="nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime)",
          pageToken=token).execute()
        if page.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_SEARCH")
        result.extend(page.get("files",[]))
        token=page.get("nextPageToken")
        if not token:break
    if token:partial=True
    return result,partial
def inventory(d,months):
    rows=[];issues=[];folders_checked=0;partial_folders=0;seen_ids=set()
    for year,ym_list in sorted(((year,[m for m in months if m[:4]==year]) for year in LEGACY_ROOTS),key=lambda x:x[0]):
        if not ym_list:continue
        sources,part=list_bounded(d,LEGACY_ROOTS[year],max_items=60,only_folders=True)
        if part:raise RuntimeError("LEGACY_ROOT_SOURCE_LIST_PARTIAL")
        srcmap=collections.defaultdict(list)
        for item in sources:srcmap[item["name"]].append(item)
        for source in SOURCE_NAMES+("TDCC_ARCHIVE",):
            # The TDCC_ARCHIVE directory is confirmed for 2026, but optional in 2025.
            found=srcmap[source]
            if not found:
                if source!="TDCC_ARCHIVE":issues.append({"source":source,"year":year,"state":"SOURCE_DIR_MISSING"})
                continue
            if len(found)!=1:
                issues.append({"source":source,"year":year,"state":"AMBIGUOUS_SOURCE_DIR"});continue
            dirs,dir_part=list_bounded(d,found[0]["id"],max_items=70,only_folders=True)
            if dir_part:issues.append({"source":source,"year":year,"state":"PARTIAL_SOURCE_DIR_LIST"})
            mmap=collections.defaultdict(list)
            for item in dirs:mmap[item["name"]].append(item)
            for month in ym_list:
                entries=mmap.get(month,[])
                if not entries:
                    issues.append({"source":source,"month":month,"state":"LEGACY_MONTH_FOLDER_NOT_FOUND_NOT_OFFICIAL_GAP"})
                    continue
                if len(entries)>1:
                    issues.append({"source":source,"month":month,"state":"AMBIGUOUS_MONTH_FOLDER"});continue
                files,partial=list_bounded(d,entries[0]["id"])
                folders_checked+=1;partial_folders+=int(partial)
                if partial:issues.append({"source":source,"month":month,"state":"PARTIAL_FILE_PAGE_NOT_COVERAGE"})
                for file in files:
                    if file.get("mimeType")==FOLDER:continue
                    fileid=file["id"]
                    if fileid in seen_ids:continue
                    seen_ids.add(fileid)
                    rows.append({"legacy_version":"v0.93","source":source,"month_folder":month,
                     "original_drive_file_id":fileid,"original_folder_id":entries[0]["id"],
                     "original_name":file["name"],"original_mime_type":file.get("mimeType"),
                     "size_bytes":int(file.get("size") or 0),"drive_md5":file.get("md5Checksum"),
                     "source_format":classify(file["name"]),"source_sha256":None,
                     "sha_status":"UNVERIFIED_METADATA_ONLY","source_native_schema_verified":False,
                     "raw_v096_storage":"REFERENCE_ORIGINAL_ID_ONLY",
                     "source_publication_time":None,"historical_pit_verified":False,
                     "market_data_rewritten":False,"original_file_deleted":False})
    summary={"schema":"JARVIS_V096_P0_INVENTORY_V1","months_requested":list(months),
       "legacy_files_indexed":len(rows),"folders_checked":folders_checked,
       "partial_folder_lists":partial_folders,"issues":issues,
       "source_format_counts":dict(collections.Counter(x["source_format"] for x in rows)),
       "actual_raw_byte_sha_verified":0,"silver_partitions_created":0,
       "gold_indicators_created":0,"official_downloads":0,
       "full_source_completeness_certified":False,"v095_mutated":False,
       "v093_mutated":False,"PIT_certified":False}
    return rows,summary
def find_exact(d,parent,name):
    query="'"+(parent or "root")+"' in parents and name='"+name.replace("'","\\'")+"' and trashed=false"
    result=[];token=None
    while True:
        page=d.files().list(q=query,fields="nextPageToken,incompleteSearch,files(id,name,mimeType)",pageSize=100,pageToken=token).execute()
        if page.get("incompleteSearch"):raise RuntimeError("DRIVE_INCOMPLETE_FOLDER_LOOKUP")
        result.extend(page.get("files",[]));token=page.get("nextPageToken")
        if not token:break
    return result
def ensure_folder(d,parent,name):
    rows=find_exact(d,parent,name)
    folders=[x for x in rows if x.get("mimeType")==FOLDER]
    if len(rows)>1 or (rows and not folders):raise RuntimeError("DRIVE_V096_FOLDER_NAME_CONFLICT")
    if folders:return folders[0]["id"]
    body={"name":name,"mimeType":FOLDER}
    if parent:body["parents"]=[parent]
    return d.files().create(body=body,fields="id").execute()["id"]
def publish(d,name,blob,control):
    target=name+"_"+sha(blob)[:24]+".json"
    exists=find_exact(d,control,target)
    if len(exists)>1:raise ValueError("V096_MANIFEST_NAME_COLLISION")
    if exists:
        fid=exists[0]["id"];status="REUSED"
    else:
        fid=d.files().create(body={"name":target,"parents":[control]},
            media_body=MediaIoBaseUpload(io.BytesIO(blob),mimetype="application/json",resumable=False),
            fields="id").execute()["id"]
        status="CREATED"
    remote=d.files().get_media(fileId=fid).execute()
    if sha(remote)!=sha(blob):raise ValueError("V096_MANIFEST_REMOTE_READBACK_SHA")
    return {"id":fid,"name":target,"sha256":sha(blob),"readback":"PASS","state":status}
def main():
    from scripts.v095_2026_annual_consolidated import service
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("inventory","audit"),default="inventory")
    args=parser.parse_args()
    OUT.mkdir(exist_ok=True)
    months=safe_months(os.getenv("V096_PILOT_MONTHS",",".join(DEFAULT_MONTHS)))
    if args.mode=="audit":
        from scripts.v096_raw_first_audit import run
        run()
        return
    d=service();rows,summary=inventory(d,months)
    manifest_bytes=(json.dumps({"schema":"JARVIS_V096_P0_SOURCE_MANIFEST_V1","rows":rows},
                        ensure_ascii=False,sort_keys=True)+"\n").encode()
    summary_bytes=(json.dumps(summary,ensure_ascii=False,sort_keys=True)+"\n").encode()
    (OUT/"manifest.json").write_bytes(manifest_bytes)
    (OUT/"inventory_report.json").write_bytes(summary_bytes)
    parent=os.getenv("V096_PARENT_FOLDER_ID")
    root=ensure_folder(d,parent,"JARVIS_C1_v096")
    control=ensure_folder(d,root,"00_CONTROL")
    for name in ("01_RAW_ORIGINAL","02_RAW_PARQUET","03_QUARANTINE","04_REPORTS","99_FUTURE"):
        ensure_folder(d,root,name)
    published=[publish(d,"V096_P0_SOURCE_MANIFEST",manifest_bytes,control),
               publish(d,"V096_P0_INVENTORY_REPORT",summary_bytes,control)]
    status={"root_id":root,"control_id":control,"publication":published,**summary}
    (OUT/"execution.json").write_text(json.dumps(status,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(status,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
