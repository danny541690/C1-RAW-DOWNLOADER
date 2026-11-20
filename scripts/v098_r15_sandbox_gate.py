#!/usr/bin/env python3
"""R15: isolated Drive sandbox tests and 27-year source directory presence census.
Only writes to C1_0.98/99_RECOVERY/R15_ISOLATED_TEST_ONLY.
Never modifies v0.93, v0.98 Bronze, Silver or Gold. PUBLIC repo output is
aggregate only: no original IDs, titles, bytes, hashes or private filenames.
Production atomic CAS/Lease and full dataset file coverage are NOT certified.
"""
import argparse,hashlib,io,json,os,pathlib,sys,datetime as dt
from v098_r11_six_source_metadata_pilot import SOURCES,service,children,unique_folder,unique_global_folder,MIME
from googleapiclient.http import MediaIoBaseUpload

def report(path,record):
    p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(record,indent=2,sort_keys=True),encoding="utf8")
    print(json.dumps({k:v for k,v in record.items() if k in ("mode","source","status","files","month_folders","years_found","result","new_upload","verified")}))
def scopes(api):
    stats={"api_pages":0}
    v93=unique_global_folder(api,"C1_0.93",stats)
    raw=unique_folder(api,v93,"01_RAW",stats)
    v98=unique_global_folder(api,"C1_0.98",stats)
    rec=unique_folder(api,v98,"99_RECOVERY",stats)
    sandbox=unique_folder(api,rec,"R15_ISOLATED_TEST_ONLY",stats) if rec else None
    if not all((raw,sandbox)):raise RuntimeError("EXPECTED_ROOT_NOT_FOUND")
    return raw,sandbox,stats

def matching(api,parent,name,stats):
    return [f for f in children(api,parent,stats) if f.get("name")==name]
def test_file(api,sandbox,name,body,stats):
    existing=matching(api,sandbox,name,stats)
    if len(existing)>1:raise RuntimeError("DUPLICATE_SANDBOX_FILE")
    expected=hashlib.sha256(body).hexdigest()
    if existing:
        fid=existing[0]["id"]; uploaded=False
    else:
        media=MediaIoBaseUpload(io.BytesIO(body),mimetype="application/octet-stream",resumable=False)
        f=api.files().create(body={"name":name,"parents":[sandbox],
                                   "description":"R15 isolated test-only; immutable verification artifact"},
                             media_body=media,fields="id").execute()
        fid=f["id"];uploaded=True
    reread=api.files().get_media(fileId=fid).execute()
    if hashlib.sha256(reread).hexdigest()!=expected:
        raise RuntimeError("SANDBOX_HASH_MISMATCH")
    return {"new_upload":int(uploaded),"verified":1,"replayed":int(not uploaded)}

def ledgertest(api,sandbox,stats):
    # Synthetic only; no real transaction or source file identifiers.
    tasks={src:{"task_key":hashlib.sha256(("R15-SYNTHETIC|"+src).encode()).hexdigest(),
                "source":src,"status":"COMMITTED_TEST","attempt":1} for src in SOURCES}
    payload={"version":"R15-SYNTHETIC-V1","status":"TEST_ONLY",
             "writer":"SINGLE_GITHUB_WORKFLOW","tasks":tasks,
             "production_transactional_CAS":False}
    body=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    result=test_file(api,sandbox,"R15_SYNTHETIC_MASTER_STATE_V1.json",body,stats)
    return {"mode":"sandbox_ledger","status":"PASS_SANDBOX_DRIVE_READBACK",
            **result,"committed_test_tasks":6,"production_atomic_CAS":False}

def copytest(api,raw,sandbox,source,stats,cap=262144):
    yr=unique_folder(api,raw,"2026",stats)
    src=unique_folder(api,yr,source,stats) if yr else None
    month=unique_folder(api,src,"2026-10",stats) if src else None
    if not month:return {"source":source,"mode":"sandbox_copy","status":"COVERAGE_UNKNOWN",
                         "verified":0,"new_upload":0}
    stack=[month];seen=set();chosen=None
    while stack and chosen is None:
        folder=stack.pop()
        if folder in seen:raise RuntimeError("DIRECTORY_LOOP")
        seen.add(folder)
        for f in children(api,folder,stats):
            if f.get("mimeType")==MIME:stack.append(f["id"])
            elif 0<int(f.get("size") or 0)<=cap and f.get("md5Checksum"):
                chosen=f;break
    if chosen is None:return {"source":source,"mode":"sandbox_copy","status":"NO_ELIGIBLE_SMALL_SAMPLE",
                               "verified":0,"new_upload":0}
    body=api.files().get_media(fileId=chosen["id"]).execute()
    if len(body)!=int(chosen["size"]) or len(body)>cap:raise RuntimeError("SOURCE_SIZE_MISMATCH")
    if hashlib.md5(body).hexdigest()!=chosen["md5Checksum"]:raise RuntimeError("SOURCE_MD5_MISMATCH")
    result=test_file(api,sandbox,f"R15_SANDBOX_COPY_{source}_2026_10.bin",body,stats)
    return {"source":source,"mode":"sandbox_copy","status":"PASS_SOURCE_TARGET_SHA256",
            **result,"size_bytes":len(body),"production_bronze_written":False}

def inventory(api,raw,source,stats):
    year_folders=list(children(api,raw,stats))
    yearmap={}
    for f in year_folders:
        if f.get("mimeType")==MIME and f.get("name","").isdigit() and len(f["name"])==4 and 2000<=int(f["name"])<=2026:
            if f["name"] in yearmap:raise RuntimeError("DUPLICATE_YEAR_FOLDER")
            yearmap[f["name"]]=f["id"]
    n_year=0;n_source=0;n_months=0;n_unknown=0
    for y in range(2000,2027):
        parent=yearmap.get(str(y))
        if not parent:
            n_unknown+=1;continue
        n_year+=1
        f=unique_folder(api,parent,source,stats)
        if not f:
            n_unknown+=1;continue
        n_source+=1
        months=[x for x in children(api,f,stats) if x.get("mimeType")==MIME and
                x.get("name","").startswith(f"{y}-")]
        n_months+=len(months)
    return {"mode":"year_directory_inventory","source":source,"status":"PASS_DIRECTORY_PRESENCE_ONLY",
            "years_found":n_year,"source_years":n_source,
            "month_folders":n_months,"year_or_source_unknown":n_unknown,
            "api_pages":stats["api_pages"],"datasets_validated":0,"files":0,
            "complete_file_inventory":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("mode",choices=("ledger","copy","inventory"))
    p.add_argument("--source",choices=SOURCES)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    if a.mode in ("copy","inventory") and not a.source:p.error("--source required")
    result={"mode":a.mode,"source":a.source,"status":"INIT"}
    try:
        api=service()
        raw,sandbox,stats=scopes(api)
        if a.mode=="ledger":result=ledgertest(api,sandbox,stats)
        elif a.mode=="copy":result=copytest(api,raw,sandbox,a.source,stats)
        else:result=inventory(api,raw,a.source,stats)
        result["api_pages"]=stats["api_pages"]
    except Exception as e:
        result={"mode":a.mode,"source":a.source,"status":"TEST_ERROR",
                "error_class":type(e).__name__}
    finally:report(a.out,result)
    if result["status"]=="TEST_ERROR":sys.exit(2)
if __name__=="__main__":main()
