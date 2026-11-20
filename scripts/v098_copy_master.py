#!/usr/bin/env python3
"""Single master of six source ledgers for v0.93->v0.98 original bytes only."""
import argparse
import datetime as dt
import io
import json
from collections import Counter
from pathlib import Path
from googleapiclient.http import MediaIoBaseUpload
from v098_bronze_copy_only import (client, children, folder_for, read_checkpoint,
    OFFICIAL_SOURCES, TARGET, CHECKPOINTS, FOLDER_MIME)

NAME = "v098_COPY_MASTER_A1.json"

def fetch_master(api):
    matches = [x for x in children(api, CHECKPOINTS) if x["name"] == NAME]
    if len(matches) > 1:
        raise RuntimeError("Duplicate canonical master")
    if not matches:
        return None, None
    data = api.files().get_media(fileId=matches[0]["id"]).execute()
    return json.loads(data), matches[0]["id"]

def commit_master(api, data, file_id=None):
    data["updated_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf8")
    media = MediaIoBaseUpload(io.BytesIO(blob), mimetype="application/json",
                              resumable=True)
    if file_id:
        api.files().update(fileId=file_id, media_body=media,
                           supportsAllDrives=True).execute()
    else:
        api.files().create(body={"name":NAME,"parents":[CHECKPOINTS]},
                           media_body=media,fields="id",
                           supportsAllDrives=True).execute()

def ensure_target_source_directories(api):
    """Single writer creates 27 years * 6 sources before parallel jobs begin."""
    cache = {}
    for year in range(2000,2027):
        for source in OFFICIAL_SOURCES:
            folder_for(api,f"{year}/{source}/__directory_only__",cache)
    # Fail closed if any top-level year or source folder is duplicated.
    years = [f for f in children(api,TARGET) if f["mimeType"]==FOLDER_MIME
             and f["name"].isdigit() and len(f["name"])==4]
    counts=Counter(f["name"] for f in years)
    if any(v>1 for v in counts.values()):
        raise RuntimeError("Duplicate destination year directories")
    for year in years:
        sources=[x for x in children(api,year["id"])
                 if x["mimeType"]==FOLDER_MIME and x["name"] in OFFICIAL_SOURCES]
        if any(v>1 for v in Counter(x["name"] for x in sources).values()):
            raise RuntimeError("Duplicate destination source directories")

def target_inventory_issues(api, expected_by_id):
    """Reconcile target IDs, paths, names; no source-content or schema QA."""
    years=[f for f in children(api,TARGET) if f["mimeType"]==FOLDER_MIME
           and f["name"].isdigit() and len(f["name"])==4]
    duplicate=0
    extra=0
    misplaced=0
    found=set()
    for year in years:
        sources=[x for x in children(api,year["id"])
                 if x["mimeType"]==FOLDER_MIME and x["name"] in OFFICIAL_SOURCES]
        for source in sources:
            stack=[(source["id"],f"{year['name']}/{source['name']}")]
            while stack:
                parent,prefix=stack.pop()
                entries=list(children(api,parent))
                names=Counter((x["name"],x["mimeType"]==FOLDER_MIME) for x in entries)
                duplicate+=sum(v-1 for v in names.values() if v>1)
                for x in entries:
                    path=f"{prefix}/{x['name']}"
                    if x["mimeType"]==FOLDER_MIME:
                        stack.append((x["id"],path))
                    elif x["id"] not in expected_by_id:
                        extra+=1
                    else:
                        found.add(x["id"])
                        if expected_by_id[x["id"]]!=path:
                            misplaced+=1
    return {"duplicates":duplicate,"untracked_target_files":extra,
            "wrong_target_paths":misplaced,
            "missing_target_ids":len(set(expected_by_id)-found)}

def activate(api):
    old, fid=fetch_master(api)
    if old and old["state"] in ("COMPLETE","FINISHED_WITH_HOLD"):
        print("INACTIVE")
        return
    if old is None:
        old={"version":"v098-A1","source_folder":"0.93/01_RAW",
             "target_folder":"0.98/20_BRONZE","state":"ACTIVE",
             "sources":list(OFFICIAL_SOURCES),
             "created_utc":dt.datetime.now(dt.timezone.utc).isoformat()}
        ensure_target_source_directories(api)
        commit_master(api,old)
    else:
        ensure_target_source_directories(api)
    print("ACTIVE")

def status(api):
    data,_=fetch_master(api)
    print("ACTIVE" if data and data.get("state")=="ACTIVE" else "INACTIVE")

def finalize(api, report_dir):
    master,fid=fetch_master(api)
    if not master or master.get("state")!="ACTIVE":
        print("INACTIVE")
        return
    rows=[]
    missing=[]
    for source in OFFICIAL_SOURCES:
        path=Path(report_dir)/(source+".json")
        if not path.is_file():
            missing.append(source)
            continue
        value=json.loads(path.read_text(encoding="utf8"))
        if value.get("source")!=source:
            raise RuntimeError("Source report identity mismatch")
        rows.append(value)
    if missing:
        counters=master.setdefault("missing_report_retries",{})
        for source in missing:
            counters[source]=counters.get(source,0)+1
        master["state"]="FINISHED_WITH_HOLD" if any(counters[x]>=3 for x in missing) else "ACTIVE"
        master["last_error"]={"type":"MISSING_SOURCE_REPORT","sources":missing}
        commit_master(api,master,fid)
        print(json.dumps({"state":master["state"],"missing_source_reports":len(missing)}))
        return
    master["missing_report_retries"]={}
    total=sum(int(x["source_ids"]) for x in rows)
    received=sum(int(x["recorded_source_ids"]) for x in rows)
    remaining=sum(int(x["remaining"]) for x in rows)
    holds=sum(int(x.get("statuses",{}).get("HOLD",0)) for x in rows)
    master["last_run_summary"]={"source_ids":total,"recorded_source_ids":received,
         "remaining":remaining,"holds":holds,
         "per_source":{x["source"]:{"total":x["source_ids"],
                                   "recorded":x["recorded_source_ids"],
                                   "remaining":x["remaining"],
                                   "holds":x.get("statuses",{}).get("HOLD",0)}
                       for x in rows}}
    if remaining==0:
        expected={}
        ledger_errors=0
        for source in OFFICIAL_SOURCES:
            receipts=read_checkpoint(api,source)
            count=next(x["recorded_source_ids"] for x in rows if x["source"]==source)
            if len(receipts)!=count:
                ledger_errors+=1
            for row in receipts:
                if row.get("status")=="HOLD":
                    continue
                if not row.get("source_sha256") or row.get("source_sha256")!=row.get("target_sha256"):
                    ledger_errors+=1
                    continue
                target_id=row.get("target_id")
                if not target_id:
                    ledger_errors+=1
                elif target_id in expected and expected[target_id]!=row.get("path"):
                    ledger_errors+=1
                else:
                    expected[target_id]=row.get("path")
        issues=target_inventory_issues(api,expected)
        issues["missing_sha_evidence_or_bad_ledger"]=ledger_errors
        master["last_run_summary"]["target_reconciliation"]=issues
        master["state"]="COMPLETE" if not holds and not any(issues.values()) else "FINISHED_WITH_HOLD"
    commit_master(api,master,fid)
    print(json.dumps({"state":master["state"],"source_files":total,
         "recorded":received,"remaining":remaining,"holds":holds,
         "target_audit":master["last_run_summary"].get("target_reconciliation")}))
        
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",required=True,choices=["activate","status","finalize"])
    parser.add_argument("--reports-dir",default="source_reports")
    options=parser.parse_args()
    api=client()
    if options.mode=="activate":activate(api)
    elif options.mode=="status":status(api)
    else:finalize(api,options.reports_dir)

if __name__=="__main__":
    main()
