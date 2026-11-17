#!/usr/bin/env python3
"""Incremental Silver INPUT FORMAT gate v2: reuse archived QA then inspect raw bytes only when needed.
No financial value verification, source PIT certification, Silver conversion, Gold, or raw mutation.
Source/Drive checkpoints and immutable per-run evidence files; source SHA guards every reuse.
"""
import csv,io,os,json,re,sys,zipfile,hashlib,collections
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,source_api
from scripts.v097_seven_historical_format_registry import period
VERSION="v097_schema_gate_v2_20261117"
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=min(250,max(5,int(os.getenv("SCHEMA_BATCH","75"))))
LIMIT_BYTES=65*1024*1024
MAX_ZIP_MEMBER=6*1024*1024
NATIVE_PREFIX="v097_SEVEN_FORMAT_V2_CK_"
DEEP_PREFIX="v097_SEVEN_INDEPENDENT_DEPTH_CK_"
CK_PREFIX="v097_SCHEMA_V2_CK_"
VALID={"FORMAT_STRUCTURE_PASS","SCHEMA_INPUT_READY","SCHEMA_PROFILED_NEEDS_MAPPING"}
TERMINAL={"SCHEMA_INPUT_READY","SCHEMA_PROFILED_NEEDS_MAPPING","FORMAT_UNSUPPORTED","FORMAT_STRUCTURAL_HOLD","SOURCE_READ_FAILED_FINAL"}
def utc():return datetime.now(timezone.utc).isoformat()
def h(b):return hashlib.sha256(b).hexdigest()
def fmt(name,blob):
    ext=name.lower().rsplit(".",1)[-1]
    if blob[:4]==b"PK\x03\x04":return "ZIP"
    if blob[:4]==b"%PDF":return "PDF"
    hd=blob[:1000].lstrip().lower()
    if hd.startswith((b"{",b"[")):return "JSON"
    if hd.startswith((b"<!doctype",b"<html",b"<?xml")):return "HTML_XML"
    if ext in ("csv","txt","raw") or b"," in hd:return "CSV_CANDIDATE"
    return "UNKNOWN"
def basic(blob,name):
    """Prove structural readability only; never inspect financial numeric correctness."""
    typ=fmt(name,blob)
    if typ=="ZIP":
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                parts=z.infolist()
                if not parts:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"EMPTY_ZIP"}
                if len(parts)>5000:return {"status":"FORMAT_UNSUPPORTED","reason":"ZIP_MEMBER_CAP"}
                if z.testzip() is not None:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"ZIP_CRC"}
                members=[p for p in parts if not p.is_dir() and not re.search(r"(?:^|/)(?:manifest|receipt)[^/]*\.json$",p.filename,re.I)]
                if not members:return {"status":"FORMAT_UNSUPPORTED","reason":"CONTROL_ONLY_ZIP"}
                types=collections.Counter()
                for p in members[:30]:
                    if p.file_size>MAX_ZIP_MEMBER:types["LARGE_MEMBER"]+=1;continue
                    b=z.read(p)
                    types[fmt(p.filename,b)]+=1
                return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"ZIP","member_types":dict(types),"members":len(members)}
        except Exception as e:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"ZIP_"+type(e).__name__}
    if typ=="JSON":
        try:
            obj=json.loads(blob.decode("utf-8-sig"))
            if not isinstance(obj,(dict,list)):return {"status":"FORMAT_UNSUPPORTED","reason":"JSON_SCALAR"}
            k=list(obj.keys())[:30] if isinstance(obj,dict) else []
            return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"JSON","keys":k}
        except Exception as e:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"JSON_"+type(e).__name__}
    if typ=="CSV_CANDIDATE":
        for enc in ("utf-8-sig","cp950","big5"):
            try:
                t=blob[:100000].decode(enc)
                reader=csv.reader(io.StringIO(t),strict=False)
                header=next(reader,None)
                if header is None:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"EMPTY_CSV"}
                if len(header)<2:continue
                return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"CSV","encoding":enc,"header":header[:80]}
            except (UnicodeError,csv.Error):continue
        return {"status":"FORMAT_UNSUPPORTED","reason":"CSV_UNKNOWN_ENCODING_OR_LAYOUT"}
    if typ=="HTML_XML":
        sample=blob[:50000].decode("utf-8",errors="replace").lower()
        if any(t in sample for t in ("<table","<xbrl","<html","<?xml","<ix:")):
            return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"HTML_XML"}
        return {"status":"FORMAT_UNSUPPORTED","reason":"HTML_UNKNOWN_LAYOUT"}
    if typ=="PDF":return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"PDF","reason":"PDF_FUTURE_EXTRACTION_REQUIRED"}
    return {"status":"FORMAT_UNSUPPORTED","reason":"UNKNOWN_FILE_SIGNATURE"}
def reusable(native,deep,sha):
    """Prior evidence can identify format but cannot certify unknown field mappings."""
    for evidence in (native,deep):
        if not evidence:continue
        if (evidence.get("bronze_sha256") or evidence.get("original_sha256"))!=sha:continue
        if evidence.get("input_bytes_sha_checked") is True:
            status=str(evidence.get("status",""))
            if status.startswith("RETRY_"):continue
            if status.startswith("HOLD_ORIGINAL_SHA_MISMATCH"):return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"PREVIOUS_SHA_MISMATCH"}
            det=evidence.get("parser_detail") or {}
            sig=(det.get("deep_content") or {}).get("signature") or evidence.get("format_signature")
            if sig:return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":sig,"evidence":"V2_SHA_MATCH","old_status":status}
    return None
def source(src):
    if src not in SOURCES:raise ValueError(src)
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    # Frozen Q0Q4 baseline, do not permit changed cohort; source report is immutable.
    base=match(api,quality,"v097_Q0Q4_SOURCE_"+src+"_44035354930.json")
    if not base:raise RuntimeError("Q0Q4_BASELINE_MISSING")
    rows=load_json(api,base["id"])["records"]
    if len(rows)!=len({r["source_id"] for r in rows}):raise RuntimeError("BASE_DUPLICATE")
    nf=match(api,control,NATIVE_PREFIX+src+".json")
    df=match(api,control,DEEP_PREFIX+src+".json")
    native=load_json(api,nf["id"]).get("done",{}) if nf else {}
    deep=load_json(api,df["id"]).get("done",{}) if df else {}
    ckname=CK_PREFIX+src+".json"
    cf=match(api,control,ckname)
    ck=load_json(api,cf["id"]) if cf else {"schema":VERSION,"source":src,"done":{},"run_history":[]}
    if ck.get("schema")!=VERSION:raise RuntimeError("CHECKPOINT_VERSION_CONFLICT")
    done=ck["done"]
    ids={r["source_id"] for r in rows}
    if set(done)-ids:raise RuntimeError("CHECKPOINT_ORPHAN")
    batch=[]
    # Priority to actual format unknown, then reviewed, then already profiled
    priority={"SCHEMA_REVIEW_REQUIRED":0,"SCHEMA_PENDING":1,"FORMAT_PROFILED_MAPPING_PENDING":2}
    for r in sorted(rows,key=lambda r:priority.get(r["silver_input_status"],3)):
        sid=r["source_id"]
        d=done.get(sid)
        if d and d.get("sha")==r["source_sha256"] and (
             d.get("status") in TERMINAL or
             (d.get("status")=="RETRY_SOURCE_READ" and d.get("attempts",0)>=3)):
            continue
        batch.append(r)
        if len(batch)>=BATCH:break
    new={}
    for r in batch:
        sid=r["source_id"];sha=r["source_sha256"]
        if r["bronze_status"]!="BRONZE_INTEGRITY_READY":
            verdict={"status":"BLOCKED_BRONZE","reason":r["bronze_status"]}
        else:
            verdict=reusable(native.get(sid),deep.get(sid),sha)
            if not verdict:
                try:
                    blob=call(lambda:api.files().get_media(fileId=r["destination_id"]))
                    if len(blob)>LIMIT_BYTES:verdict={"status":"FORMAT_UNSUPPORTED","reason":"FILE_TOO_LARGE"}
                    elif h(blob)!=sha:verdict={"status":"FORMAT_STRUCTURAL_HOLD","reason":"DRIVE_SHA_MISMATCH"}
                    else:verdict=basic(blob,r["source_path"])
                    verdict["input_bytes_sha_checked"]=h(blob)==sha
                except Exception as e:
                    attempts=done.get(sid,{}).get("attempts",0)+1
                    verdict={"status":"RETRY_SOURCE_READ" if attempts<3 else "SOURCE_READ_FAILED_FINAL",
                             "reason":type(e).__name__,"attempts":attempts}
        try:
            mm=re.search(r"((?:19|20)\d{2})-(0[1-9]|1[0-2])",r["source_path"])
            version=period(src,mm.group(0))["id"] if mm else "HISTORICAL_VERSION_UNKNOWN"
        except Exception:version="HISTORICAL_VERSION_UNKNOWN"
        new[sid]={**verdict,"source_id":sid,"source":src,"sha":sha,"historical_version":version,
                  "silver_gold_executed":False,"run":RUN,"checked_at":utc()}
    # Atomic immutable delta before editable checkpoint: crash after delta is recoverable.
    if new:
        name="v097_SCHEMA_V2_DELTA_"+src+"_"+RUN+".json"
        receipt=put_once(api,quality,name,{"schema":VERSION,"run":RUN,"source":src,"records":new})
        done.update(new)
        ck["run_history"]=(ck.get("run_history",[])+[{"run":RUN,"delta_id":receipt,"n":len(new)}])[-100:]
        ck["done"]=done;ck["last_run"]=RUN;ck["updated_at"]=utc()
        upsert(api,control,ckname,ck)
        verified=match(api,control,ckname)
        if not verified or len(load_json(api,verified["id"]).get("done",{}))!=len(done):
            raise RuntimeError("DRIVE_CHECKPOINT_READBACK_MISMATCH")
    counts=collections.Counter(r.get("status") for r in done.values())
    remaining=len(rows)-sum(1 for r in rows if r["source_id"] in done and done[r["source_id"]].get("status") in TERMINAL)
    print("SCHEMA_V2_PROGRESS="+json.dumps({"source":src,"total":len(rows),"processed":len(done),
        "new":len(new),"remaining":remaining,"statuses":dict(counts),"run":RUN},ensure_ascii=False),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    total=0;counts=collections.Counter();reports=[]
    for src in SOURCES:
        ckf=match(api,control,CK_PREFIX+src+".json")
        inf=match(api,quality,"v097_Q0Q4_SOURCE_"+src+"_44035354930.json")
        if not inf:raise RuntimeError("BASELINE_MISSING_"+src)
        n=len(load_json(api,inf["id"])["records"]);total+=n
        ck=load_json(api,ckf["id"]) if ckf else {"done":{}}
        done=ck.get("done",{})
        c=collections.Counter(v.get("status") for v in done.values())
        counts.update(c)
        reports.append({"source":src,"total":n,"processed":len(done),"statuses":dict(c),
            "checkpoint_id":ckf["id"] if ckf else None})
    if total!=74750:raise RuntimeError("BASELINE_COUNT_CONFLICT")
    finalized=sum(v for k,v in counts.items() if k in TERMINAL)
    result={"schema":VERSION,"run":RUN,"created_at":utc(),"cohort":total,"processed":sum(x["processed"] for x in reports),
            "finalized":finalized,"remaining":total-finalized,"counts":dict(counts),
            "sources":reports,"silver_gold_executed":False,"silver_input_ready_certified":0,
            "note":"Schema-profile classification is NOT Silver Input Ready; mappings still need explicit verified contracts"}
    name="v097_SCHEMA_V2_MASTER_"+RUN+".json"
    fid=put_once(api,quality,name,result)
    upsert(api,control,"v097_SCHEMA_V2_MASTER_LATEST.json",{**result,"report_id":fid})
    print("SCHEMA_V2_MASTER="+json.dumps({**result,"sources":"seven","report_id":fid},ensure_ascii=False),flush=True)
def selftest():
    assert basic(b'{"tables":[{"fields":["date","code"]}]}',"a.json")["signature"]=="JSON"
    assert basic("日期,代碼\n2026-11-17,2330".encode(),"a.csv")["signature"]=="CSV"
    assert basic(b"x","a.zip")["status"]=="FORMAT_UNSUPPORTED"
    assert reusable({"bronze_sha256":"a"*64,"input_bytes_sha_checked":True,
                     "status":"CONTENT_PARSED","parser_detail":{"deep_content":{"signature":"JSON_CANDIDATE"}}},None,"a"*64)["status"]=="SCHEMA_PROFILED_NEEDS_MAPPING"
    assert reusable({"bronze_sha256":"b"*64,"input_bytes_sha_checked":True},None,"a"*64) is None
    print("SCHEMA_V2_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:final()
    elif len(sys.argv)==2 and sys.argv[1] in SOURCES:source(sys.argv[1])
    else:raise SystemExit("selftest | SOURCE | final")
