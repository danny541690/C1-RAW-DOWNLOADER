#!/usr/bin/env python3
"""v0.97: read-only metadata inventory of legacy 0.93 RAW; 6 independent lanes.

No legacy or market files are modified, moved, copied, downloaded or re-downloaded.
Detailed inventory is written only to the user's private Google Drive.
"""
import csv
import io
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

FOLDER = "application/vnd.google-apps.folder"
ROOT = "ChatGPT資料存取"
OLD = "C1_0.93"
NEW = "JARVIS_C1_v097_LIFECYCLE"
FILE_FIELDS = "nextPageToken,incompleteSearch,files(id,name,mimeType,size,md5Checksum,modifiedTime,createdTime)"
SOURCES = ["TWSE", "TPEx", "MOPS", "TDCC", "TAIFEX", "NDC", "FinMind", "XQ"]
MAX_WORKERS = 6

def client():
    required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
    absent = [key for key in required if not os.environ.get(key)]
    if absent:
        raise RuntimeError("Required Google OAuth secrets are unavailable: " + ",".join(absent))
    cred = Credentials(
        None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    cred.refresh(Request())
    return build("drive", "v3", credentials=cred, cache_discovery=False)

def retry(fn):
    for attempt in range(6):
        try:
            return fn()
        except Exception as err:
            status = getattr(getattr(err, "resp", None), "status", None)
            if status not in (403, 429, 500, 502, 503, 504) or attempt == 5:
                raise
            time.sleep(min(2 ** attempt, 30))
    raise AssertionError("unreachable")

def list_children(api, parent):
    result = []
    token = None
    while True:
        params = dict(
            q="'%s' in parents and trashed = false" % parent,
            fields=FILE_FIELDS, pageSize=1000,
            orderBy="name", supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        if token:
            params["pageToken"] = token
        data = retry(lambda: api.files().list(**params).execute())
        if data.get("incompleteSearch"):
            raise RuntimeError("Incomplete Drive search; no completion claim")
        result.extend(data.get("files", []))
        token = data.get("nextPageToken")
        if not token:
            return result

def find_folder(api, parent, name):
    matches = [x for x in list_children(api, parent)
               if x["name"] == name and x["mimeType"] == FOLDER]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one folder named %s; found %s" % (name, len(matches)))
    return matches[0]["id"]

def locations(api):
    container = find_folder(api, "root", ROOT)
    legacy = find_folder(api, container, OLD)
    v097 = find_folder(api, container, NEW)
    raw = find_folder(api, legacy, "01_RAW")
    control = find_folder(api, v097, "00_SYSTEM_CONTROL")
    manifest = find_folder(api, control, "03_RUN_MANIFESTS")
    reports = find_folder(api, v097, "10_REPORTS_DASHBOARDS")
    coverage = find_folder(api, reports, "01_DATA_COVERAGE")
    return raw, manifest, coverage

def write_private(api, parent, filename, data, mimetype):
    if isinstance(data, str):
        data = data.encode("utf-8")
    body = {"name": filename, "parents": [parent], "mimeType": mimetype}
    media = MediaInMemoryUpload(data, mimetype=mimetype, resumable=False)
    return retry(lambda: api.files().create(body=body, media_body=media, fields="id,name,size").execute())

def get_private_by_name(api, parent, name):
    arr = [f for f in list_children(api, parent) if f["name"] == name]
    if len(arr) != 1:
        raise RuntimeError("Missing or duplicate inventory lane: %s (%d)" % (name, len(arr)))
    return json.loads(retry(lambda: api.files().get_media(fileId=arr[0]["id"]).execute()).decode("utf-8"))

def classify(path, name, is_folder):
    p = path.split("/")
    if any("CANARY" in x.upper() or x.upper().startswith("_") for x in p+[name]):
        return "TEST_OR_CONTROL"
    if len(p) > 1 and p[1] == "TDCC_ARCHIVE":
        return "ARCHIVAL_SEPARATE"
    if len(p) < 2 or p[1] not in SOURCES:
        return "SOURCE_UNKNOWN"
    if is_folder:
        return "FOLDER_ONLY"
    if not re.search(r"\.(zip|csv|json|xlsx|xls|pdf|parquet|txt|html|xml|gz)$", name, re.I):
        return "FORMAT_REVIEW"
    if name.upper().startswith(("LIVE_FIVE_STAGE", "L1_RAW_QA", "JARVIS_V093_CHECKPOINT")):
        return "BATCH_EVIDENCE_REVIEW"
    return "CANDIDATE_RAW_UNVERIFIED"

def scan_lane(api, lane, run_id):
    raw, manifests, _ = locations(api)
    roots = list_children(api, raw)
    years = sorted([x for x in roots if re.fullmatch(r"20(0\d|1\d|2[0-6])", x["name"]) and x["mimeType"] == FOLDER], key=lambda x:x["name"])
    if len(years) != 27:
        raise RuntimeError("Unexpected year folder coverage: %s" % len(years))
    chosen = [x for i,x in enumerate(years) if i % MAX_WORKERS == lane]
    inventory = []
    directories = []
    errors = []
    if lane == 0:
        for x in roots:
            if x not in years:
                cls = classify("", x["name"], x["mimeType"] == FOLDER)
                directories.append(dict(year="",source="",month="",path=x["name"],id=x["id"],status="TOP_LEVEL_EXCLUDED",class_=cls))
    for yr in chosen:
        year = yr["name"]
        stack = [(yr["id"], year)]
        visited = set()
        while stack:
            fid, path = stack.pop()
            if fid in visited:
                errors.append(dict(path=path,error="DUPLICATE_FOLDER_ID"))
                continue
            visited.add(fid)
            parts = path.split("/")
            source = parts[1] if len(parts)>1 else ""
            month = next((s for s in parts[2:] if re.fullmatch(r"\d{4}-\d{2}",s)), "")
            try:
                contents = list_children(api, fid)
            except Exception as exc:
                errors.append(dict(path=path,error=type(exc).__name__,detail=str(exc)[:140]))
                continue
            directories.append(dict(year=year,source=source,month=month,path=path,id=fid,
                                    status="LISTED",child_count=len(contents)))
            for ch in contents:
                childpath = path + "/" + ch["name"]
                if ch["mimeType"] == FOLDER:
                    stack.append((ch["id"], childpath))
                else:
                    cls=classify(path,ch["name"],False)
                    inventory.append(dict(year=year,source=source,month=month,path=childpath,
                        file_id=ch["id"],file_name=ch["name"],mime=ch["mimeType"],
                        size_bytes=ch.get("size",""),md5=ch.get("md5Checksum",""),
                        created_at=ch.get("createdTime",""),modified_at=ch.get("modifiedTime",""),
                        classification=cls,sha256_status="NOT_CHECKED",content_status="NOT_CHECKED"))
    document=dict(schema="v097_inventory_1",run_id=run_id,lane=lane,source_root="C1_0.93/01_RAW",
                  fetched_at=datetime.now(timezone.utc).isoformat(),
                  years=[x["name"] for x in chosen],files=inventory,folders=directories,errors=errors)
    name=f"v097_inventory_{run_id}_lane{lane}.json"
    write_private(api, manifests, name, json.dumps(document,ensure_ascii=False,separators=(",",":")), "application/json")
    print("Lane %d: years=%d directories=%d metadata_files=%d errors=%d; uploaded private Drive result."%
          (lane,len(chosen),len(directories),len(inventory),len(errors)))

def csv_bytes(rows, cols):
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=cols,extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig")

def aggregate(api, run_id):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    _, manifests, reports = locations(api)
    data=[get_private_by_name(api,manifests,f"v097_inventory_{run_id}_lane{i}.json") for i in range(6)]
    allfiles=[f for d in data for f in d["files"]]
    dirs=[f for d in data for f in d["folders"]]
    errs=[dict(lane=d["lane"],**e) for d in data for e in d["errors"]]
    if errs:
        state="PARTIAL_FOLDER_ERRORS"
    else:
        state="METADATA_LIST_COMPLETE_CONTENT_UNVERIFIED"
    matrix=[]
    grouped=defaultdict(list)
    for r in allfiles: grouped[(r["year"],r["source"])].append(r)
    dfolders=defaultdict(list)
    for d in dirs: dfolders[(d["year"],d["source"])].append(d)
    for year in range(2000,2027):
        for src in SOURCES+["TDCC_ARCHIVE"]:
            records=grouped[(str(year),src)]
            sub=dfolders[(str(year),src)]
            if src=="TDCC_ARCHIVE" and not sub:
                continue
            matrix.append(dict(year=year,source=src,files=len(records),
                total_bytes=sum(int(r["size_bytes"]) for r in records if str(r["size_bytes"]).isdigit()),
                monthly_folders=len([x for x in sub if re.fullmatch(r"\d{4}-\d{2}",x["path"].split("/")[-1])]),
                candidate_raw=sum(r["classification"]=="CANDIDATE_RAW_UNVERIFIED" for r in records),
                suspected_batches=sum(r["classification"]=="BATCH_EVIDENCE_REVIEW" for r in records),
                metadata_state="LISTED" if sub else "MISSING_SOURCE_FOLDER",
                content_validation="NOT_CHECKED"))
    findings=[]
    for f in allfiles:
        if f["classification"] not in ("CANDIDATE_RAW_UNVERIFIED",):
            findings.append(dict(severity="REVIEW",kind=f["classification"],path=f["path"],file_id=f["file_id"]))
        if f["size_bytes"]=="0":
            findings.append(dict(severity="REVIEW",kind="ZERO_BYTE",path=f["path"],file_id=f["file_id"]))
        if f["month"] and f["month"]>"2026-11":
            findings.append(dict(severity="REVIEW",kind="FUTURE_MONTH_FOLDER",path=f["path"],file_id=f["file_id"]))
    for e in errs:
        findings.append(dict(severity="ERROR",kind=e["error"],path=e["path"],file_id=""))
    paths=[dict(source_path=f["path"],source_file_id=f["file_id"],source=f["source"],
                year=f["year"],month=f["month"],destination_dataset="TO_BE_CONFIRMED",
                destination_prefix="02_DATA_LAKE/01_BRONZE_ORIGINAL/"+f["source"]+"/",
                mapping_state="DRAFT_METADATA_ONLY",classification=f["classification"]) for f in allfiles]
    wb=Workbook()
    wb.remove(wb.active)
    tabs=[
      ("00_總覽",[dict(metric=k,value=v) for k,v in [
         ("run_id",run_id),("status",state),("file_count",len(allfiles)),("folder_count",len(dirs)),
         ("errors",len(errs)),("candidate_raw_unverified",sum(f["classification"]=="CANDIDATE_RAW_UNVERIFIED" for f in allfiles)),
         ("metadata_only","YES"),("sha256_checked",0),("content_validated",0),("migration_executed",0)]],["metric","value"]),
      ("01_全量檔案",allfiles,["year","source","month","path","file_id","file_name","mime","size_bytes","md5","created_at","modified_at","classification","sha256_status","content_status"]),
      ("02_來源年度",matrix,["year","source","files","total_bytes","monthly_folders","candidate_raw","suspected_batches","metadata_state","content_validation"]),
      ("03_遷移對照",paths,["source_path","source_file_id","source","year","month","destination_dataset","destination_prefix","mapping_state","classification"]),
      ("04_異常清單",findings,["severity","kind","path","file_id"]),
      ("05_目錄清單",dirs,["year","source","month","path","id","status","child_count"]),
      ("06_工作線",[dict(lane=d["lane"],years=",".join(d["years"]),files=len(d["files"]),folders=len(d["folders"]),errors=len(d["errors"])) for d in data],["lane","years","files","folders","errors"])
    ]
    for tab,rows,cols in tabs:
        ws=wb.create_sheet(tab)
        ws.append(cols)
        for r in rows:
            ws.append([str(r.get(c,"")) if r.get(c,None) is not None else "" for c in cols])
        ws.freeze_panes="A2"
        ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]:
            cell.font=Font(color="FFFFFF",bold=True)
            cell.fill=PatternFill("solid",fgColor="17365D")
        for idx,col in enumerate(cols,1):
            ws.column_dimensions[get_column_letter(idx)].width=min(60,max(15,len(col)+5))
    buf=io.BytesIO()
    wb.save(buf)
    prefix=f"JARVIS_v097_v093_inventory_{run_id}"
    write_private(api,reports,prefix+".xlsx",buf.getvalue(),"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    write_private(api,reports,prefix+"_files.csv",csv_bytes(allfiles,tabs[1][2]),"text/csv")
    write_private(api,reports,prefix+"_exceptions.csv",csv_bytes(findings,tabs[4][2]),"text/csv")
    write_private(api,reports,prefix+"_migration.csv",csv_bytes(paths,tabs[3][2]),"text/csv")
    print("Aggregate completed. files=%d folders=%d errors=%d findings=%d status=%s. Private Drive reports published."%
          (len(allfiles),len(dirs),len(errs),len(findings),state))

def main():
    run_id=os.environ.get("GITHUB_RUN_ID","manual")
    mode=os.environ.get("INVENTORY_MODE","lane")
    api=client()
    if mode=="aggregate":
        aggregate(api,run_id)
    else:
        lane=int(os.environ.get("INVENTORY_LANE","0"))
        if not 0<=lane<6: raise ValueError("lane must be 0..5")
        scan_lane(api,lane,run_id)

if __name__=="__main__":
    main()
