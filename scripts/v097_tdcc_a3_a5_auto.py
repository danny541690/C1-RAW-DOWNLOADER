#!/usr/bin/env python3
"""JARVIS v0.97 A3-A5 incremental TDCC evidence pipeline.
Only evidence triage; never mutates v0.93, original V3 checkpoints, or market Bronze.
A3 official current snapshot is NOT an historical security master.
"""
import os, re, json, hashlib, time
from collections import Counter
from datetime import datetime, timezone
import requests
from scripts.v097_bronze_first_pipeline import service, common, match, load_json, put_once, upsert, call

RUN=os.getenv("GITHUB_RUN_ID","manual")
V4="43156776265"
LANE_CAP=max(1,min(250,int(os.getenv("TDCC_A4_BATCH","100"))))
MAX_BYTES=4*1024*1024
MASTER_URL="https://openapi.tdcc.com.tw/v1/opendata/1-1"
PREFIX="v097_TDCC_A4_V2"
CODE=re.compile(r"^[0-9]{4}[A-Z0-9]{0,2}$")
TOKEN=re.compile(r"^[A-Z0-9]{4,6}$")
FILE=re.compile(r"(?:distribution|tdcc)[_-](\d{8})[_-]([A-Za-z0-9]{4,6})_",re.I)
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def source_rows(api,q,lane):
    f=match(api,q,"v097_BF_REPAIR_V4_%s_L%02d.json"%(V4,lane))
    if not f:raise RuntimeError("MISSING_FROZEN_V4_LANE_%d"%lane)
    r=load_json(api,f["id"])
    if r.get("schema")!="v097_bf_repair_v4_lane_1":raise RuntimeError("UNEXPECTED_V4_SCHEMA")
    return [x for x in r["rows"] if x["category"]=="TDCC_IDENTITY"]
def html_identity(raw):
    # Conservative extraction: avoid guessing security ID from arbitrary filename.
    text=raw.decode("utf-8-sig",errors="replace")
    match_stock=re.search(r"<input\b[^>]*\bid\s*=\s*['\"]StockNo['\"][^>]*>",text,re.I)
    token=match_stock.group(0) if match_stock else ""
    value=re.search(r"\bvalue\s*=\s*['\"]([^'\"]+)['\"]",token,re.I)
    code=value.group(1).strip().upper() if value else None
    dates=re.findall(r"<option\b[^>]*\bvalue\s*=\s*['\"](\d{8})['\"][^>]*\bselected\b",text,re.I)
    return code,dates,bool(re.search(r"<table\b",text,re.I))
def assess(path,raw):
    m=FILE.search(str(path))
    if not m:return "QUARANTINED_FILENAME_UNPARSEABLE",{}
    day,filename_token=m.groups()
    try:
        dt=datetime.strptime(day,"%Y%m%d")
        if dt.strftime("%Y%m%d")!=day:raise ValueError("date mismatch")
    except ValueError:return "QUARANTINED_INVALID_DATE",{"date":day}
    part=re.search(r"/((?:19|20)\d{2})-(0[1-9]|1[0-2])/",str(path))
    if part and day[:6] != part.group(1)+part.group(2):
        return "QUARANTINED_PERIOD_CONFLICT",{"date":day}
    if day<"20080701":return "SOURCE_HISTORY_PRE_START_REVIEW",{"date":day}
    code,dates,has_table=html_identity(raw)
    observation={"date":day,"filename_token":filename_token,"content_security_id":code,
                 "selected_date_matches":day in dates,"has_table":has_table,
                 "filename_content_code_matches":bool(code and code==filename_token.upper())}
    if not code or not TOKEN.fullmatch(code):
        return "HOLD_CONTENT_IDENTIFIER_UNPARSEABLE",observation
    if not observation["selected_date_matches"] or not has_table:
        return "HOLD_HTML_DATE_OR_TABLE_REVIEW",observation
    if not observation["filename_content_code_matches"]:
        return "HOLD_FILENAME_CONTENT_DISAGREEMENT",observation
    if not CODE.fullmatch(code):
        # Non-standard token can be internally consistent without being a stock.
        return "HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING",observation
    return "HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING",observation
def selftest():
    def page(code="2330",date="20251107"):
        return ('<input id="StockNo" value="%s"><option value="%s" selected>ok</option><table></table>'%(code,date)).encode()
    assert assess("2025/TDCC/2025-11/distribution_20251107_2330_x.html",page())[0].startswith("HTML_CODE_CONSISTENT")
    assert assess("2025/TDCC/2025-11/distribution_20251107_YJR4_x.html",page("YJR4"))[0]=="HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING"
    assert assess("2025/TDCC/2025-11/distribution_20251007_2330_x.html",page())[0]=="QUARANTINED_PERIOD_CONFLICT"
    assert assess("2025/TDCC/2025-11/distribution_20251107_2330_x.html",page("2317"))[0]=="HOLD_FILENAME_CONTENT_DISAGREEMENT"
    assert assess("2025/TDCC/2025-11/distribution_20251107_YY0037_x.html",page("YY0037"))[0]=="HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING"
    print("A3_A5_SELFTEST_PASS",flush=True)
def a3(api):
    _,_,q,_=common(api)
    existing=match(api,q,"v097_TDCC_A3_CURRENT_%s.json"%RUN)
    if existing:
        print("A3_REUSED="+json.dumps(load_json(api,existing["id"]),ensure_ascii=False),flush=True)
        return
    evidence={"schema":"v097_tdcc_a3_official_snapshot_1","run":RUN,"utc":now(),
        "url":MASTER_URL,"historical_asof_master_verified":False,
        "historical_market_membership_authorized":False,
        "notes":"TDCC current security master cannot certify past TWSE/TPEx common-stock membership."}
    try:
        # Stream with a bounded cap; never log or persist the full provider payload.
        with requests.get(MASTER_URL,timeout=(10,75),headers={"Accept":"application/json"},stream=True) as response:
            response.raise_for_status()
            chunks=[];received=0;limit=64*1024*1024
            for chunk in response.iter_content(chunk_size=1024*1024):
                if not chunk:continue
                received+=len(chunk)
                if received>limit:raise ValueError("SNAPSHOT_EXCEEDS_64MB")
                chunks.append(chunk)
            payload=b"".join(chunks)
            data=json.loads(payload)
            evidence.update(fetch_status="CURRENT_SNAPSHOT_READABLE",http_status=response.status_code,
                bytes=received,sha256=sha(payload),
                json_container=type(data).__name__,item_count=len(data) if isinstance(data,list) else None)
    except Exception as e:
        evidence.update(fetch_status="OFFICIAL_CURRENT_SNAPSHOT_UNAVAILABLE",reason=type(e).__name__+":"+str(e)[:150])
    put_once(api,q,"v097_TDCC_A3_CURRENT_%s.json"%RUN,evidence)
    print("A3="+json.dumps(evidence,ensure_ascii=False),flush=True)
def a4(api,lane):
    _,c,q,_=common(api)
    rows=source_rows(api,q,lane)
    ck_name="%s_CK_L%02d.json"%(PREFIX,lane)
    f=match(api,c,ck_name)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_tdcc_a4_checkpoint_2","lane":lane,"done":{}}
    if ck.get("schema")!="v097_tdcc_a4_checkpoint_2" or ck.get("lane")!=lane:
        raise RuntimeError("A4_CHECKPOINT_SCHEMA_CONFLICT")
    done=ck["done"]
    todo=[x for x in rows if x["file_id"] not in done][:LANE_CAP]
    receipt="%s_%s_L%02d.json"%(PREFIX,RUN,lane)
    prior_receipt=match(api,q,receipt)
    if prior_receipt:
        prior=load_json(api,prior_receipt["id"])
        outcomes=prior["items"]
        for item in outcomes:
            done[item["file_id"]]={"status":item["status"],"run":RUN}
        upsert(api,c,ck_name,{"schema":"v097_tdcc_a4_checkpoint_2","lane":lane,"done":done,"updated_at":now()})
        print("A4_REPLAY_RECOVERED="+json.dumps({"lane":lane,"recovered":len(outcomes),"processed":len(done)},ensure_ascii=False),flush=True)
        return
    outcomes=[]
    for r in todo:
        fid=r["file_id"]
        rec={"file_id":fid,"lane":lane,"at":now(),
             "market_membership_certified":False,"official_source_provenance_certified":False}
        for attempt in range(3):
            try:
                meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
                if int(meta.get("size") or 0)>MAX_BYTES:raise ValueError("OVER_SIZE_LIMIT")
                raw=call(lambda:api.files().get_media(fileId=fid))
                if not raw or len(raw)>MAX_BYTES:raise ValueError("EMPTY_OR_LARGE")
                status,obs=assess(r.get("source_path") or "",raw)
                rec.update(status=status,observations=obs,source_sha256=sha(raw),bytes=len(raw))
                if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
                    rec["status"]="QUARANTINED_DRIVE_MD5_CONFLICT"
                break
            except Exception as e:
                rec.update(status="READ_FAILED",error=type(e).__name__+":"+str(e)[:120])
                if isinstance(e,ValueError):break
                if attempt<2:time.sleep(1+attempt)
        outcomes.append(rec)
    put_once(api,q,receipt,{"schema":"v097_tdcc_a4_lane_2","run":RUN,"lane":lane,
        "items":outcomes,"batch":len(outcomes),"utc":now(),"market_promotions":0})
    # Receipt first, then checkpoint; replay-safe after interruption.
    for r in outcomes:done[r["file_id"]]={"status":r["status"],"run":RUN}
    upsert(api,c,ck_name,{"schema":"v097_tdcc_a4_checkpoint_2","lane":lane,"done":done,"updated_at":now()})
    counts=Counter(r["status"] for r in outcomes)
    print("A4="+json.dumps({"lane":lane,"batch":len(outcomes),"processed":len(done),
       "total":len(rows),"remaining":max(0,len(rows)-len(done)),"statuses":dict(counts)},ensure_ascii=False),flush=True)
def a5(api):
    _,c,q,_=common(api)
    existing=match(api,q,"v097_TDCC_A5_V2_SUMMARY_%s.json"%RUN)
    if existing:
        print("A5_REUSED="+json.dumps(load_json(api,existing["id"]),ensure_ascii=False),flush=True)
        return
    counts=Counter();remaining=0;processed=0;total=0;seen=set()
    for lane in range(6):
        rows=source_rows(api,q,lane)
        for r in rows:
            if r["file_id"] in seen:raise RuntimeError("A5_DUPLICATED_ORIGINAL_ASSET")
            seen.add(r["file_id"])
        total+=len(rows)
        f=match(api,c,"%s_CK_L%02d.json"%(PREFIX,lane))
        ck=load_json(api,f["id"]) if f else {"done":{}}
        done=ck["done"]
        if not set(done).issubset({r["file_id"] for r in rows}):raise RuntimeError("A5_ORPHAN_CHECKPOINT")
        processed+=len(done);remaining+=len(rows)-len(done)
        counts.update(v["status"] for v in done.values())
    if total!=5035 or processed+remaining!=total:raise RuntimeError("A5_ACCOUNTING_FAIL")
    report={"schema":"v097_tdcc_a5_overview_2","run":RUN,"at":now(),
        "tdcc_exception_total":total,"checked":processed,"remaining":remaining,
        "by_status":dict(counts),"market_identity_certified":0,
        "official_provenance_certified":0,"market_raw_promoted":0,
        "all_exceptions_triaged":remaining==0,
        "phase_a_certified":False,
        "blockers":["Historical as-of TWSE/TPEx common-stock master not yet certified",
                    "Per-file official TDCC origin evidence not yet certified"],
        "note":"Processed means inspected with receipts, not historical market eligibility."}
    put_once(api,q,"v097_TDCC_A5_V2_SUMMARY_%s.json"%RUN,report)
    print("A5="+json.dumps(report,ensure_ascii=False),flush=True)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as g:g.write("remaining=%d\n"%remaining)
if __name__=="__main__":
    mode=os.getenv("TDCC_A_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="a3":a3(api)
        elif mode=="a4":a4(api,int(os.environ["TDCC_A_LANE"]))
        elif mode=="a5":a5(api)
        else:raise SystemExit("BAD_TDCC_A_MODE")
