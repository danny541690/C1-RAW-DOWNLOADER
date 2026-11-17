#!/usr/bin/env python3
"""JARVIS v0.97 Q0-Q4: evidence-only Bronze integrity + nontransforming Silver format inventory.
No originals are changed; no data downloads, numeric checks, PIT checks, actual Silver or Gold.
All reports and checkpoints are committed in Google Drive. Designed to be re-run safely.
"""
import json, os, re, sys
from datetime import datetime, timezone
from collections import Counter
from scripts.v097_bronze_autopilot import SOURCES, source_api
from scripts.v097_bronze_first_batch_v3 import ck_name
VERSION="v097_q0_q4_integrity_schema_1"
RUN=os.environ.get("GITHUB_RUN_ID","manual")
HEX=re.compile(r"[a-f0-9]{64}\Z")
PREFIX="v097_Q0Q4_"
def now(): return datetime.now(timezone.utc).isoformat()
def decide(row, copy, qa, native):
    sha=row.get("sha"); path=row.get("source_path"); dst=row.get("dest_id")
    if not isinstance(sha,str) or not HEX.fullmatch(sha) or not path or not dst:
        bronze="INTEGRITY_EVIDENCE_PENDING"
    elif (copy and qa and copy.get("state")=="COPY_MATCHED_PENDING_INDEPENDENT_QA"
         and qa.get("state")=="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"
         and copy.get("sha")==sha and copy.get("source_path")==path
         and copy.get("dest_id")==dst):
        bronze="BRONZE_INTEGRITY_READY"
    elif copy and (copy.get("sha") not in (None,sha)
        or copy.get("source_path") not in (None,path)
        or copy.get("dest_id") not in (None,dst)):
        bronze="INTEGRITY_CONFLICT"
    else: bronze="INTEGRITY_EVIDENCE_PENDING"
    if bronze!="BRONZE_INTEGRITY_READY": schema="BLOCKED_BY_BRONZE"
    elif not native: schema="SCHEMA_PENDING"
    elif str(native.get("status","")).startswith(("HOLD_","RETRY_")): schema="SCHEMA_REVIEW_REQUIRED"
    else: schema="FORMAT_PROFILED_MAPPING_PENDING"
    return bronze,schema
def selftest():
    r={"sha":"a"*64,"source_path":"old.zip","dest_id":"new"}
    c={"sha":r["sha"],"source_path":r["source_path"],"dest_id":"new",
       "state":"COPY_MATCHED_PENDING_INDEPENDENT_QA"}
    q={"state":"BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"}
    assert decide(r,c,q,None)==("BRONZE_INTEGRITY_READY","SCHEMA_PENDING")
    assert decide(r,c,q,{"status":"HOLD_NUMERIC"})==("BRONZE_INTEGRITY_READY","SCHEMA_REVIEW_REQUIRED")
    assert decide(r,c,q,{"status":"FORMAT_RECOGNIZED"})==("BRONZE_INTEGRITY_READY","FORMAT_PROFILED_MAPPING_PENDING")
    assert decide(r,{**c,"sha":"b"*64},q,None)[0]=="INTEGRITY_CONFLICT"
    assert decide(r,c,{"state":"HOLD"},None)[0]=="INTEGRITY_EVIDENCE_PENDING"
    print("Q0Q4_INTEGRITY_ONLY_NO_SILVER_GOLD_SELFTEST_PASS",flush=True)
def prepare(api,control,quality,match,load_json,src):
    inf=match(api,quality,"v097_AP_INPUT_"+src+".json")
    if not inf:raise RuntimeError("MISSING_FROZEN_INPUT_"+src)
    rows=load_json(api,inf["id"])["rows"]
    ids=[r["source_id"] for r in rows]
    idset=set(ids)
    if len(ids)!=len(idset):raise RuntimeError("DUPLICATE_FROZEN_SOURCE_ID")
    nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+src+".json")
    native=load_json(api,nf["id"]).get("done",{}) if nf else {}
    copies={}; qa={}
    for lane in range(6):
        c=match(api,control,ck_name("COPY",lane))
        q=match(api,control,ck_name("QA",lane))
        if not c or not q: raise RuntimeError("MISSING_V3_COPY_QA_CHECKPOINT")
        cc=load_json(api,c["id"]).get("done",{})
        qq=load_json(api,q["id"]).get("done",{})
        for sid,val in cc.items():
            if sid not in idset:continue
            if sid in copies:raise RuntimeError("DUPLICATE_COPY_ID_"+sid)
            copies[sid]=val;qa[sid]=qq.get(sid)
    return rows,native,copies,qa
def source(src):
    if src not in SOURCES:raise RuntimeError("UNKNOWN_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,_=source_api()
    # One immutable baseline run output per source, plus stable checkpoint.
    ckname=PREFIX+"CK_"+src+".json"
    ckfile=match(api,control,ckname)
    if ckfile:
        prev=load_json(api,ckfile["id"])
        if (prev.get("schema")==VERSION and prev.get("finished") is True and
            prev.get("report_id") and prev.get("count",0)>0):
            rid=prev["report_id"]
            print("Q0Q4_SOURCE_REUSED="+json.dumps({"source":src,"report_id":rid,
                "counts":prev.get("counts",{}),"run":RUN}),flush=True)
            return
    rows,native,copies,qa=prepare(api,control,quality,match,load_json,src)
    counts=Counter();recs=[]
    for row in rows:
        sid=row["source_id"]
        b,s=decide(row,copies.get(sid),qa.get(sid),native.get(sid))
        counts["bronze:"+b]+=1;counts["schema:"+s]+=1
        recs.append({"source_id":sid,"source":src,"source_sha256":row.get("sha"),
           "destination_id":row.get("dest_id"),"source_path":row.get("source_path"),
           "bronze_status":b,"silver_input_status":s,
           "historical_profile_status":(native.get(sid) or {}).get("status"),
           "evidence_type":"V3_INDEPENDENT_SHA_QA" if b=="BRONZE_INTEGRITY_READY" else "MISSING_OR_CONFLICT",
           "silver_conversion_executed":False})
    report={"schema":VERSION,"run":RUN,"source":src,"count":len(recs),
            "counts":dict(counts),"records":recs,
            "validity":"FROZEN_EXISTING_BYTE_EVIDENCE_ONLY",
            "recheck_note":"Existing V3 source/dest readback receipts are reused; not a new download.",
            "silver_schema_ready_certified":False,"silver_gold_executed":False,
            "created_at":now()}
    name=PREFIX+"SOURCE_"+src+"_"+RUN+".json"
    fid=put_once(api,quality,name,report)
    ck={"schema":VERSION,"source":src,"finished":True,"count":len(recs),
       "counts":dict(counts),"report_id":fid,"report_name":name,
       "last_run":RUN,"updated_at":now(),"silver_gold_executed":False}
    upsert(api,control,ckname,ck)
    chk=match(api,control,ckname)
    if not chk or load_json(api,chk["id"]).get("report_id")!=fid:
        raise RuntimeError("DRIVE_CHECKPOINT_READBACK_FAILED")
    print("Q0Q4_SOURCE_REPORT="+json.dumps({k:v for k,v in ck.items() if k!="schema"},ensure_ascii=False),flush=True)
def finalize():
    api,control,quality,match,load_json,put_once,upsert,_=source_api()
    files=[];sumc=Counter();total=0;complete=True
    for src in SOURCES:
        f=match(api,control,PREFIX+"CK_"+src+".json")
        if not f: complete=False;continue
        ck=load_json(api,f["id"])
        if ck.get("schema")!=VERSION or not ck.get("finished"):complete=False;continue
        report=load_json(api,ck["report_id"])
        if report.get("schema")!=VERSION or report.get("source")!=src or report.get("count")!=ck.get("count"):
            raise RuntimeError("SOURCE_REPORT_CK_MISMATCH_"+src)
        total+=ck["count"];sumc.update(ck["counts"])
        files.append({"source":src,"report_id":ck["report_id"],"count":ck["count"],
           "last_run":ck["last_run"],"counts":ck["counts"]})
    if complete and total!=74750:raise RuntimeError("COHORT_NOT_74750_"+str(total))
    report={"schema":VERSION,"run":RUN,"created_at":now(),"source_count":len(files),
        "total":total,"complete":complete and total==74750,"counts":dict(sumc),
        "source_reports":files,"originals_unchanged":True,"silver_gold_executed":False,
        "silver_schema_ready_certified":False}
    name=PREFIX+"MASTER_"+RUN+".json"
    fid=put_once(api,quality,name,report)
    upsert(api,control,PREFIX+"MASTER_LATEST.json",{**report,"report_id":fid})
    print("Q0Q4_MASTER="+json.dumps({**report,"source_reports":"7 source reports","report_id":fid},ensure_ascii=False),flush=True)
    if not report["complete"]:raise RuntimeError("INCOMPLETE_RETRY_WATCHDOG")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:finalize()
    elif len(sys.argv)==2 and sys.argv[1] in SOURCES:source(sys.argv[1])
    else:raise SystemExit("usage: selftest | SOURCE | final")
