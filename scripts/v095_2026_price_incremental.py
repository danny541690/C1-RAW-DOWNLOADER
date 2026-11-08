#!/usr/bin/env python3
"""2026 TWSE / TPEx official OHLCV incremental *candidate* producer.
Every invocation processes a bounded tranche, writes immutable Bronze/Silver/
descriptive Gold with SHA readback, then records a durable Drive cursor.
Formal 443-factor/PIT/whole-year release is NOT certified by this job.
"""
import collections
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import sys
import time

from scripts import v095_ultimate_r1_november_official as base
from scripts.v093_three_year_repair import Audit, validate
from scripts.v095_r12_drive_audit_archive import OPERATIONS
from scripts.v095_2026_legacy_first import legacy_snapshot
from googleapiclient.http import MediaIoBaseUpload

OUT=pathlib.Path("v095_2026_price_incremental")
PREFIX="JARVIS_V095_2026_PRICE_CURSOR_"
SOURCES=("TWSE","TPEx")
ACTIVE_SOURCE=os.getenv("V095_PRICE_SOURCE","").strip()
if ACTIVE_SOURCE and ACTIVE_SOURCE not in SOURCES:raise ValueError("UNKNOWN_PRICE_SOURCE")
ACTIVE_SOURCES=(ACTIVE_SOURCE,) if ACTIVE_SOURCE else SOURCES
SOURCE_PREFIX=PREFIX+ACTIVE_SOURCE+"_" if ACTIVE_SOURCE else PREFIX
BATCH_DAYS=min(10,max(1,int(os.getenv("V095_2026_BATCH_DAYS","6"))))
MAX_REPAIR_PER_RUN=2
CUTOFF=min(dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date(),dt.date(2026,12,31))

def dates():
    d=dt.date(2026,1,1)
    end=CUTOFF
    result=[]
    while d<=end:
        if d.weekday()<5:result.append(d.isoformat())
        d+=dt.timedelta(days=1)
    return result

def list_cursors(d):
    out=[];token=None
    while True:
        q="'"+OPERATIONS+"' in parents and name contains '"+PREFIX+"' and trashed=false"
        x=d.files().list(q=q,fields="nextPageToken,incompleteSearch,files(id,name,mimeType)",pageSize=1000,pageToken=token).execute()
        if x.get("incompleteSearch"):raise RuntimeError("CURSOR_SEARCH_INCOMPLETE")
        out.extend(x.get("files",[]))
        token=x.get("nextPageToken")
        if not token:break
    return [x for x in out if re.fullmatch(re.escape(SOURCE_PREFIX)+r"\d{4}_\d+_[0-9a-f]{16}\.json",x["name"])]

def cursor_state(d):
    files=list_cursors(d)
    if not files:
        # Seed both source lanes from last verified single-controller cursor.
        if ACTIVE_SOURCE:
            token=SOURCE_PREFIX
            try:
                globals()["SOURCE_PREFIX"]=PREFIX
                old=list_cursors(d)
            finally:
                globals()["SOURCE_PREFIX"]=token
            if old:
                old.sort(key=lambda x:int(x["name"].split(PREFIX)[1].split("_")[0]),reverse=True)
                f=old[0];raw=d.files().get_media(fileId=f["id"]).execute()
                digest=hashlib.sha256(raw).hexdigest()
                if not f["name"].endswith("_"+digest[:16]+".json"):raise RuntimeError("LEGACY_CHECKPOINT_SHA_MISMATCH")
                rec=json.loads(raw)
                return {"offset":rec["offset"],
                        "retry_queue":[x for x in rec.get("retry_queue",[]) if x["source"]==ACTIVE_SOURCE],
                        "generation":0,"prior_sha":digest}
        return {"offset":0,"retry_queue":[],"generation":0,"prior_sha":None}
    files.sort(key=lambda x:int(x["name"].split(SOURCE_PREFIX)[1].split("_")[0]),reverse=True)
    f=files[0];raw=d.files().get_media(fileId=f["id"]).execute()
    digest=hashlib.sha256(raw).hexdigest()
    if not f["name"].endswith("_"+digest[:16]+".json"):raise RuntimeError("CHECKPOINT_SHA_MISMATCH")
    j=json.loads(raw)
    if j["generation"]!=int(f["name"].split(SOURCE_PREFIX)[1].split("_")[0]):raise RuntimeError("CURSOR_GENERATION_MISMATCH")
    if j["offset"]<0 or j["offset"]>len(dates()):raise RuntimeError("CURSOR_OUT_OF_RANGE")
    return {"offset":j["offset"],"retry_queue":j["retry_queue"],"generation":j["generation"],"prior_sha":digest}

def job_for(day,source):
    cat=base.SOURCES[source]["cat"]
    month=day[:7]
    jobs=Audit.jobs(object.__new__(Audit),month,set())
    found=[j for j in jobs if j["source"]==source and j["category"]==cat and j["period"]==day]
    if len(found)!=1:raise RuntimeError("OFFICIAL_ROUTE_NOT_UNIQUE")
    return found[0]

def existing(d,source,day,job):
    ym=day[:7];month=ym.replace("-","")
    parent=base.SOURCES[source]["bronze"]
    folders=[x for x in base.ls(d,parent) if x["name"]==ym and x.get("mimeType")=="application/vnd.google-apps.folder"]
    if not folders:return None
    if len(folders)!=1:raise RuntimeError("MULTIPLE_MONTH_FOLDERS")
    prefix="V095_"+month+"_"+source+"_"+day+"_"
    matches=[x for x in base.ls(d,folders[0]["id"]) if x["name"].startswith(prefix) and x["name"].endswith(".json")]
    if not matches:return None
    if len(matches)!=1:raise RuntimeError("MULTIPLE_NATIVE_CANDIDATES")
    x=matches[0]
    raw=d.files().get_media(fileId=x["id"]).execute()
    digest=base.sha(raw)
    if x["name"]!=prefix+digest[:20]+".json":raise RuntimeError("NATIVE_SHA_FILENAME_MISMATCH")
    facts=validate(raw,source,job["category"],day)
    rows,unparsed=base.parse(raw,source,day)
    return raw,facts,rows,unparsed,"REUSED_VERIFIED_NATIVE"

def single(d,source,day):
    cfg=base.SOURCES[source];job=job_for(day,source)
    old=existing(d,source,day,job)
    if old:
        raw,facts,rows,unparsed,acquisition=old
    else:
        legacy=legacy_snapshot(d,source,day,job)
        if legacy:
            raw,facts,rows,unparsed,acquisition=legacy
        else:
            raw=base.bounded_official_request(job["url"])
        if not legacy:
            facts=validate(raw,source,job["category"],day)
            rows,unparsed=base.parse(raw,source,day)
            acquisition="LIVE_OFFICIAL_HTTP"
    digest=base.sha(raw)
    month=day[:7];stamp=month.replace("-","")
    bm=base.folder(d,cfg["bronze"],month)
    bronze_id,ba=base.save(d,bm,"V095_"+stamp+"_"+source+"_"+day+"_"+digest[:20]+".json",raw)
    for row in rows:
        row.update(bronze_file_id=bronze_id,bronze_sha256=digest,source_url=job["url"])
    sb=base.to_parquet(rows);s_sha=base.sha(sb)
    sm=base.folder(d,cfg["silver"],month+"_CANDIDATE")
    silver_id,sa=base.save(d,sm,"V095_"+stamp+"_"+source+"_"+day+"_OHLCV_"+s_sha[:20]+".parquet",sb)
    gold=[{"trade_date":r["trade_date"],"market":r["market"],"stock_id":r["stock_id"],
           "close":r["close"],"volume_shares":r["volume_shares"],"turnover_億元":r["turnover_億元"],
           "silver_file_id":silver_id,"silver_sha256":s_sha,
           "bronze_file_id":bronze_id,"bronze_sha256":digest,
           "historical_pit_verified":False,"usage":"DESCRIPTIVE_NO_BACKTEST"}
          for r in rows if r["close"] is not None and r["close"]>0]
    gb=base.to_parquet(gold)
    gm=base.folder(d,base.GOLD,month+"_DESCRIPTIVE_ONLY")
    _,ga=base.save(d,gm,"V095_"+stamp+"_"+source+"_"+day+"_PRICE_GOLD_"+base.sha(gb)[:20]+".parquet",gb)
    return {"source":source,"date":day,"rows":len(rows),"gold_rows":len(gold),
            "nonnumeric_ohlc_rows":unparsed,"source_response_rows":facts.get("rows"),
            "actions":[ba,sa,ga],"bronze_sha256":digest,"silver_sha256":s_sha,
            "acquisition":acquisition,"pit_verified":False}

def commit_cursor(d,record):
    raw=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(",",":"))+"\n").encode()
    digest=hashlib.sha256(raw).hexdigest()
    name=PREFIX+f"{record['generation']:04d}_"+str(os.getenv("GITHUB_RUN_ID","0"))+"_"+digest[:16]+".json"
    conflicts=[x for x in list_cursors(d) if x["name"].startswith(PREFIX+f"{record['generation']:04d}_")]
    if conflicts:raise RuntimeError("CONCURRENT_CURSOR_GENERATION_COLLISION")
    x=d.files().create(body={"name":name,"parents":[OPERATIONS],
      "description":"v0.95 2026 TWSE/TPEx scoped BSG progress; not PIT-certified"},
      media_body=MediaIoBaseUpload(io.BytesIO(raw),mimetype="application/json",resumable=False),fields="id").execute()
    read=d.files().get_media(fileId=x["id"]).execute()
    if hashlib.sha256(read).hexdigest()!=digest:raise RuntimeError("DRIVE_CURSOR_SHA_READBACK")
    return digest

def main():
    OUT.mkdir(exist_ok=True)
    flags=json.loads(pathlib.Path("governance/v095/PHASE1_FLAGS.json").read_text())
    assert not flags["BULK_COPY_APPROVED"] and not flags["RELEASE_APPROVED"]
    d=base.api();state=cursor_state(d)
    calendar=dates()
    start=state["offset"]
    selected=calendar[start:start+BATCH_DAYS]
    queue=list(state["retry_queue"])
    tasks=[(s,day,False) for day in selected for s in ACTIVE_SOURCES]
    repair=queue[:MAX_REPAIR_PER_RUN]
    tasks.extend((i["source"],i["date"],True) for i in repair)
    queue=queue[MAX_REPAIR_PER_RUN:]
    done=[];failed=[];new_files=collections.Counter()
    for source,day,retry in tasks:
        try:
            result=single(d,source,day)
            done.append(result)
            for stage,action in zip(("BRONZE","SILVER","GOLD"),result["actions"]):
                if action=="CREATED":new_files[stage]+=1
        except Exception as exc:
            err={"source":source,"date":day,"kind":type(exc).__name__,
                 "message":str(exc)[:180],"retry":retry}
            failed.append(err)
            prior=next((x for x in repair if x["source"]==source and x["date"]==day),None)
            attempts=(prior or {}).get("attempts",0)+1
            if attempts<5:
                queue.append({"source":source,"date":day,"attempts":attempts})
            else:err["quarantined_after_cycles"]=attempts
    # Preserve actionable errors in both artifact and job log; never hide a partial batch as year completion.
    for failure in failed:
        print(json.dumps({"state":"SOURCE_DAY_FAILED", **failure},ensure_ascii=False),flush=True)
    report={"schema":"V095_2026_PRICE_INCREMENTAL_CANDIDATE_V1","active_source":ACTIVE_SOURCE or "TWSE_TPEx",
            "run_id":os.getenv("GITHUB_RUN_ID"),"start_offset":start,
            "next_offset":start+len(selected),"eligible_weekdays_so_far":len(calendar),
            "selected_new_days":selected,"completed":done,"failed":failed,
            "retry_queue_length":len(queue),"created_by_stage":dict(new_files),
            "production_release":False,"year_complete":False,"pit_certified":False}
    (OUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    receipt={"generation":state["generation"]+1,"offset":start+len(selected),
             "retry_queue":queue,"prior_sha":state["prior_sha"],"run_id":os.getenv("GITHUB_RUN_ID"),
             "success_units":len(done),"failed_units":len(failed),"created_by_stage":dict(new_files),
             "failed_items":failed,"latest_cutoff":CUTOFF.isoformat()}
    receipt_sha=commit_cursor(d,receipt)
    report["durable_cursor_sha256"]=receipt_sha
    (OUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"run_id":report["run_id"],"new_days":len(selected),
        "next_offset":receipt["offset"],"total_candidate_weekdays":len(calendar),
        "completed_units":len(done),"failed_units":len(failed),
        "created_by_stage":dict(new_files),"retry_queue_length":len(queue),
        "checkpoint_committed":True,"year_complete":False,"PIT":False},ensure_ascii=False),flush=True)
    # Failed units remain explicit; a complete yearly release requires separate PIT/coverage certification.
    return 0

if __name__=="__main__":
    sys.exit(main())
