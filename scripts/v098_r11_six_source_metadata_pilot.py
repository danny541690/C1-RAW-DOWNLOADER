#!/usr/bin/env python3
"""JARVIS v0.98 R11: official source Drive metadata-only pilot scanner.

NO Drive write, no raw download, no Bronze copy.
R11 live gate one-time GitHub Actions trigger, read-only bounded 2026-10. The repository is PUBLIC:
the report includes ONLY aggregate counts, NEVER Drive IDs, names, MD5s or paths.
Do not classify a missing month folder as missing market data before the
Dataset Expected Coverage registry is certified.
"""
import argparse
import collections
import datetime as dt
import json
import os
import pathlib
import random
import sys
import time

SOURCES=("TWSE","TPEx","MOPS","NDC","TDCC","TAIFEX")
MIME="application/vnd.google-apps.folder"

def service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds=Credentials(token=None,refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
                      token_uri="https://oauth2.googleapis.com/token",
                      client_id=os.environ["GOOGLE_CLIENT_ID"],
                      client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
                      scopes=["https://www.googleapis.com/auth/drive"])
    # Refresh at the ORIGINAL authorized scope; all operations below are files.list only.
    creds.refresh(Request())
    return build("drive","v3",credentials=creds,cache_discovery=False)

def children(client,parent,counters):
    from googleapiclient.errors import HttpError
    token=None; seen=set()
    while True:
        kw={"q":f"'{parent}' in parents and trashed = false",
            "fields":"nextPageToken,files(id,name,mimeType,size,md5Checksum)",
            "pageSize":1000,"supportsAllDrives":True}
        if token:kw["pageToken"]=token
        for attempt in range(6):
            try: page=client.files().list(**kw).execute();break
            except HttpError as e:
                status=int(getattr(e.resp,"status",0))
                if attempt==5 or status not in (403,429,500,502,503,504):raise
                time.sleep(min(2**attempt,16)+random.random())
        counters["api_pages"]+=1
        for f in page.get("files",[]):yield f
        token=page.get("nextPageToken")
        if not token:break
        if token in seen:raise RuntimeError("REPEATED_PAGE_TOKEN")
        seen.add(token)

def unique_folder(client, parent, title, counters):
    matches=[x for x in children(client,parent,counters) if x.get("mimeType")==MIME and x.get("name")==title]
    if len(matches)>1:raise RuntimeError("DUPLICATE_REQUIRED_FOLDER")
    return matches[0]["id"] if matches else None

def unique_global_folder(client, name, counters):
    # Restrict to matching named folders; abort on ambiguity rather than choosing a random alias.
    q={"q":f"name = '{name}' and mimeType = '{MIME}' and trashed = false",
       "fields":"nextPageToken,files(id,name,mimeType,parents)","pageSize":1000}
    page=client.files().list(**q).execute()
    counters["api_pages"]+=1
    if page.get("nextPageToken"):raise RuntimeError("AMBIGUOUS_ROOT_PAGE")
    candidates=page.get("files",[])
    if len(candidates)!=1:raise RuntimeError("MISSING_OR_AMBIGUOUS_V093_ROOT")
    return candidates[0]["id"]

def probe(source,year,month,output):
    report={"source":source,"year":year,"month":month,
            "mode":"READ_ONLY_METADATA_AGGREGATE",
            "file_count":0,"file_bytes":0,"api_pages":0,
            "folders_scanned":0,"empty_directories":0,"zero_byte_files":0,
            "duplicate_md5_candidates":0,"unknown_md5_files":0,
            "month_folder":"UNKNOWN","status":"INIT",
            "required_followup":"Dataset Expected Coverage and content integrity remain unverified"}
    md5s=collections.Counter()
    try:
        c=service()
        root=unique_global_folder(c,"C1_0.93",report)
        raw=unique_folder(c,root,"01_RAW",report)
        if not raw:raise RuntimeError("SOURCE_RAW_FOLDER_MISSING")
        year_id=unique_folder(c,raw,str(year),report)
        if not year_id:
            report["status"]="YEAR_FOLDER_NOT_FOUND";return report
        source_id=unique_folder(c,year_id,source,report)
        if not source_id:
            report["status"]="SOURCE_FOLDER_NOT_FOUND";return report
        month_id=unique_folder(c,source_id,month,report)
        if not month_id:
            report["month_folder"]="NOT_PRESENT"
            report["status"]="PERIOD_FOLDER_NOT_PRESENT_COVERAGE_UNKNOWN";return report
        report["month_folder"]="PRESENT"
        todo=[month_id]; seen=set()
        while todo:
            folder=todo.pop()
            if folder in seen:raise RuntimeError("FOLDER_CYCLE")
            seen.add(folder);report["folders_scanned"]+=1
            count=0
            for f in children(c,folder,report):
                count+=1
                if f.get("mimeType")==MIME:
                    todo.append(f["id"])
                    continue
                report["file_count"]+=1
                sz=int(f.get("size") or 0)
                report["file_bytes"]+=sz
                report["zero_byte_files"]+=int(sz==0)
                if f.get("md5Checksum"):md5s[(f["md5Checksum"],sz)]+=1
                else:report["unknown_md5_files"]+=1
            if count==0:report["empty_directories"]+=1
        report["duplicate_md5_candidates"]=sum(n-1 for n in md5s.values() if n>1)
        report["status"]="METADATA_SCAN_COMPLETED_COVERAGE_UNVERIFIED"
    except Exception as exc:
        report["status"]="SCAN_ERROR"
        # Public artifact MUST NOT reveal private IDs or exception messages.
        report["error_class"]=type(exc).__name__
    finally:
        output=pathlib.Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2),encoding="utf-8")
    return report

def selftest(out):
    # Does not contact Google. Validate privacy/shape and avoid accidentally claiming content PASS.
    template={"source":"TWSE","year":2026,"month":"2026-10","status":"PERIOD_FOLDER_NOT_PRESENT_COVERAGE_UNKNOWN"}
    assert "MISSING_EXPECTED" not in template["status"]
    assert all(x not in json.dumps(template) for x in ["file_id","parent_id","md5Checksum"])
    pathlib.Path(out).parent.mkdir(parents=True,exist_ok=True)
    pathlib.Path(out).write_text(json.dumps({"status":"PASS","scope":"LOCAL_NO_API",
      "tests":["no inferred missing coverage","public aggregate privacy shape"],
      "real_scan":False}),encoding="utf-8")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",choices=SOURCES)
    p.add_argument("--year",type=int,default=2026)
    p.add_argument("--month",default="2026-10")
    p.add_argument("--out",default="r11_scan/summary.json")
    p.add_argument("--selftest",action="store_true")
    a=p.parse_args()
    if a.selftest:selftest(a.out);return
    if not a.source:p.error("--source required")
    if not(2000<=a.year<=2026 and a.month.startswith(str(a.year)+"-")):
        p.error("invalid bounded year/month")
    res=probe(a.source,a.year,a.month,a.out)
    print(json.dumps({k:v for k,v in res.items() if k in ("source","status","file_count","api_pages")}))
    if res["status"]=="SCAN_ERROR":raise SystemExit(2)
if __name__=="__main__":main()
