#!/usr/bin/env python3
"""JARVIS v0.97 Schema Gate V2.1 -- frozen-cohort, read-only Bronze format triage.
Reuses V2 SHA/contract results; never executes Silver/Gold or financial/PIT release.
All processing outputs are separate immutable delta evidence and isolated shard checkpoints.
"""
import collections,csv,hashlib,io,json,os,re,sys,zipfile
from datetime import datetime,timezone
from scripts.v097_schema_gate_v2 import (SOURCES,source_api,fmt,basic,period,
    SCHEMA_RULE_VERSION as OLD_CONTRACT,TERMINAL as OLD_TERMINAL)
from scripts.v097_bronze_autopilot import classify_dataset
VERSION="v097_schema_gate_v21_20261117"
CONTRACT="20261117-format-contract-v21"
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=max(10,min(250,int(os.getenv("SCHEMA_BATCH","100"))))
PLAN={"TWSE":2,"TPEx":2,"MOPS":1,"TDCC":6,"TAIFEX":1,"NDC":0,"FinMind":2}
BASE_RUN="44035354930"
OLD_PREFIX="v097_SCHEMA_V2_CK_"
CK_PREFIX="v097_SCHEMA_V21_SHARD_"
END={"SCHEMA_PROFILED_NEEDS_MAPPING","FORMAT_UNSUPPORTED","FORMAT_STRUCTURAL_HOLD",
     "SOURCE_READ_FAILED_FINAL","BLOCKED_BRONZE","SCHEMA_INPUT_READY",
     "SCHEMA_UNKNOWN_DATASET","FORMAT_RESOURCE_LIMIT"}
def sha(blob):return hashlib.sha256(blob).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def lane(sid,parts):return int(sha(sid.encode("utf8")),16)%parts
def read_baseline(api,quality,match,load_json,src):
    f=match(api,quality,"v097_Q0Q4_SOURCE_"+src+"_"+BASE_RUN+".json")
    if not f:raise RuntimeError("FROZEN_COHORT_MISSING_"+src)
    rows=load_json(api,f["id"])["records"]
    if len(rows)!=len({r["source_id"] for r in rows}):raise RuntimeError("COHORT_DUPLICATE_"+src)
    return rows
def existing_v2(api,control,match,load_json,src):
    f=match(api,control,OLD_PREFIX+src+".json")
    return load_json(api,f["id"]).get("done",{}) if f else {}
def reused(d,row):
    return bool(d and d.get("sha")==row["source_sha256"] and
                d.get("contract_version")==OLD_CONTRACT and d.get("status") in OLD_TERMINAL)
def member_manifest(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members=z.infolist()
        if not members: return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"EMPTY_ZIP"}
        if len(members)>5000:return {"status":"FORMAT_RESOURCE_LIMIT","reason":"ZIP_TOO_MANY_MEMBERS"}
        expanded=sum(m.file_size for m in members)
        if expanded>600*1024*1024:return {"status":"FORMAT_RESOURCE_LIMIT","reason":"ZIP_TOTAL_EXPANSION"}
        for m in members:
            if m.filename.startswith("/") or ".." in m.filename.replace("\\","/").split("/"):
                return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"ZIP_UNSAFE_MEMBER_PATH"}
        bad=z.testzip()
        if bad:return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"ZIP_CRC","member":bad}
        return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"ZIP",
                "members":len(members),"expanded_bytes":expanded,
                "member_extensions":dict(collections.Counter(m.filename.rsplit(".",1)[-1].lower()
                                         for m in members if not m.is_dir())),
                "member_manifest_level":"HEADER_CRC_VERIFIED_NOT_MEMBER_SCHEMA_CERTIFIED"}
def csv_format_check(blob,src):
    for enc in ("utf-8-sig","cp950","big5"):
        try:
            txt=blob.decode(enc)
            reader=csv.reader(io.StringIO(txt,newline=""),strict=True)
            head=next(reader,None)
            if not head or len(head)<2:continue
            widths=collections.Counter()
            rows=0
            for row in reader:
                if not row or all(not x.strip() for x in row):continue
                widths[len(row)]+=1;rows+=1
                if rows>=250000:break
            expected=len(head)
            real_bad={str(k):v for k,v in widths.items() if k!=expected}
            return {"status":"SCHEMA_PROFILED_NEEDS_MAPPING","signature":"CSV",
                    "encoding":enc,"header":head[:80],"expected_width":expected,
                    "checked_rows":rows,"width_mismatch":real_bad,
                    "reason":"CSV_WIDTH_REVIEW" if real_bad else "CSV_STRUCTURE_VALID_MAPPING_PENDING"}
        except (UnicodeError,csv.Error):continue
    return {"status":"FORMAT_UNSUPPORTED","reason":"CSV_ENCODING_OR_LAYOUT_UNKNOWN"}
def inspect(blob,path,src):
    kind=fmt(path,blob)
    if re.search(r"\.raw\.receipt_[^/]*\.json$",path,re.I):
        return {"status":"FORMAT_UNSUPPORTED","reason":"CONTROL_RECEIPT_NOT_MARKET_DATA",
                "dataset":"PROVENANCE_RECEIPT"}
    if kind=="ZIP":return member_manifest(blob)
    if kind=="CSV_CANDIDATE":return csv_format_check(blob,src)
    if kind=="JSON":
        try:
            obj=json.loads(blob.decode("utf-8-sig"))
            if not isinstance(obj,(list,dict)):
                return {"status":"FORMAT_UNSUPPORTED","reason":"JSON_SCALAR"}
            dataset=classify_dataset(src,path,obj)
            result=basic(blob,path,src)
            # A generic header match alone is not a source-native, versioned dataset release.
            result["dataset_candidate"]=dataset
            if result["status"]=="SCHEMA_INPUT_READY":
                result["status"]="SCHEMA_PROFILED_NEEDS_MAPPING"
                result["reason"]="HEADER_MATCH_PENDING_VERSIONED_DATASET_CERTIFICATION"
            if isinstance(obj,dict) and isinstance(obj.get("tables"),list):
                widths=[]
                for t in obj["tables"][:100]:
                    if isinstance(t,dict) and isinstance(t.get("fields"),list) and isinstance(t.get("data"),list):
                        bad=sum(isinstance(r,list) and len(r)!=len(t["fields"]) for r in t["data"])
                        widths.append({"fields":len(t["fields"]),"rows":len(t["data"]),"mismatched_rows":bad})
                result["table_widths"]=widths
                if any(t["mismatched_rows"] for t in widths):
                    result["reason"]="JSON_TABLE_WIDTH_CONFLICT"
            return result
        except (UnicodeError,ValueError) as e:
            return {"status":"FORMAT_STRUCTURAL_HOLD","reason":"JSON_"+type(e).__name__}
    return basic(blob,path,src)
def source(src,shard):
    if src not in PLAN or PLAN[src]==0 or not (0<=shard<PLAN[src]):
        raise ValueError("INVALID_SOURCE_SHARD")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src)
    old=existing_v2(api,control,match,load_json,src)
    candidates=[r for r in rows if lane(r["source_id"],PLAN[src])==shard]
    ckname=CK_PREFIX+src+"_"+str(shard)+".json"
    cf=match(api,control,ckname)
    ck=load_json(api,cf["id"]) if cf else {"schema":VERSION,"source":src,"shard":shard,"done":{},"run_history":[]}
    if ck.get("schema")!=VERSION or ck.get("shard")!=shard:
        raise RuntimeError("SHARD_CHECKPOINT_VERSION_CONFLICT")
    own=ck["done"]
    allowed={r["source_id"] for r in candidates}
    if set(own)-allowed:raise RuntimeError("CHECKPOINT_ORPHAN")
    eligible=[r for r in candidates if not reused(old.get(r["source_id"]),r)
              and not (r["source_id"] in own and own[r["source_id"]].get("sha")==r["source_sha256"]
                       and own[r["source_id"]].get("status") in END
                       and own[r["source_id"]].get("contract_version")==CONTRACT)]
    eligible.sort(key=lambda r:(r.get("silver_input_status") not in ("SCHEMA_REVIEW_REQUIRED","SCHEMA_PENDING"),r["source_id"]))
    new={}
    for row in eligible[:BATCH]:
        sid=row["source_id"];s=row["source_sha256"]
        if row["bronze_status"]!="BRONZE_INTEGRITY_READY":
            verdict={"status":"BLOCKED_BRONZE","reason":row["bronze_status"]}
        else:
            try:
                blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
                if len(blob)>65*1024*1024:
                    verdict={"status":"FORMAT_RESOURCE_LIMIT","reason":"RAW_BYTES_OVER_65MB"}
                elif sha(blob)!=s:
                    verdict={"status":"FORMAT_STRUCTURAL_HOLD","reason":"SOURCE_SHA_MISMATCH"}
                else:
                    verdict=inspect(blob,row["source_path"],src)
                verdict["input_sha_verified"]=sha(blob)==s
            except Exception as e:
                attempts=own.get(sid,{}).get("attempts",0)+1
                verdict={"status":"SOURCE_READ_FAILED_FINAL" if attempts>=3 else "RETRY_SOURCE_READ",
                         "reason":type(e).__name__,"attempts":attempts}
        try:
            m=re.search(r"((?:19|20)\d{2})-(0[1-9]|1[0-2])",row["source_path"])
            hv=period(src,m.group(0))["id"] if m else "UNKNOWN_PERIOD"
        except Exception:hv="UNKNOWN_PERIOD"
        new[sid]={**verdict,"source_id":sid,"source":src,"sha":s,"historical_version":hv,
                  "contract_version":CONTRACT,"run":RUN,"shard":shard,"checked_at":utc(),
                  "silver_gold_executed":False,"official_numeric_verified":False,
                  "silver_input_ready_certified":False}
    if new:
        fn="v097_SCHEMA_V21_DELTA_"+src+"_"+str(shard)+"_"+RUN+".json"
        rid=put_once(api,quality,fn,{"schema":VERSION,"source":src,"shard":shard,"run":RUN,"records":new})
        own.update(new)
        ck["done"]=own;ck["last_run"]=RUN;ck["updated_at"]=utc()
        ck["run_history"]=(ck.get("run_history",[])+[{"run":RUN,"delta_id":rid,"n":len(new)}])[-200:]
        upsert(api,control,ckname,ck)
        verify=match(api,control,ckname)
        if not verify or len(load_json(api,verify["id"]).get("done",{}))!=len(own):
            raise RuntimeError("CHECKPOINT_READBACK_MISMATCH")
    print("SCHEMA_V21_PROGRESS="+json.dumps({"run":RUN,"source":src,"shard":shard,
          "cohort_shard":len(candidates),"old_reused":sum(reused(old.get(r["source_id"]),r) for r in candidates),
          "v21_processed":len(own),"new":len(new),"remaining":len(eligible)-len(new)},ensure_ascii=False),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    total=0;overall={};counts=collections.Counter();sources=[];error_rows=[]
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src);total+=len(rows)
        old=existing_v2(api,control,match,load_json,src)
        done={};new_count=0
        for shard in range(PLAN[src]):
            f=match(api,control,CK_PREFIX+src+"_"+str(shard)+".json")
            if f:
                ck=load_json(api,f["id"])
                if ck.get("schema")!=VERSION:raise RuntimeError("SHARD_VERSION_CONFLICT")
                for sid,v in ck.get("done",{}).items():
                    if sid in done or lane(sid,PLAN[src])!=shard:raise RuntimeError("DUPLICATE_OR_WRONG_SHARD")
                    done[sid]=v
        c=collections.Counter()
        for row in rows:
            sid=row["source_id"];s=row["source_sha256"]
            if sid in done and done[sid].get("sha")==s and done[sid].get("status") in END:
                c[done[sid]["status"]]+=1;new_count+=1
                if done[sid]["status"] not in ("SCHEMA_INPUT_READY","SCHEMA_PROFILED_NEEDS_MAPPING"):
                    v=done[sid];error_rows.append({"source_id":sid,"source":src,"sha":s,"status":v["status"],"reason":v.get("reason"),"shard":v.get("shard"),"run":v.get("run")})
            elif reused(old.get(sid),row):
                c["V2_REUSED_"+old[sid]["status"]]+=1
                if old[sid]["status"] not in ("SCHEMA_INPUT_READY","SCHEMA_PROFILED_NEEDS_MAPPING"):
                    error_rows.append({"source_id":sid,"source":src,"sha":s,"status":"V2_REUSED_"+old[sid]["status"],"reason":old[sid].get("reason"),"run":old[sid].get("run")})
            else:c["PENDING"]+=1
        if sum(c.values())!=len(rows):raise RuntimeError("SOURCE_COUNT_DRIFT")
        counts.update(c);sources.append({"source":src,"cohort":len(rows),"v21_done":new_count,
                                      "status_counts":dict(c)})
    if total!=74750:raise RuntimeError("COHORT_TOTAL_DRIFT")
    outstanding=counts.get("PENDING",0)
    result={"schema":VERSION,"run":RUN,"created_at":utc(),"cohort":total,
            "finalized":total-outstanding,"remaining":outstanding,"statuses":dict(counts),
            "sources":sources,"silver_gold_executed":False,"silver_input_ready_certified":0,
            "note":"Format classification only; V2 archived SHA results reused unchanged. No numeric or PIT release."}
    error_id=put_once(api,quality,"v097_SCHEMA_V21_ERROR_LEDGER_"+RUN+".json",
         {"schema":VERSION,"run":RUN,"cohort":total,"count":len(error_rows),
          "records":error_rows,"note":"Only terminal non-mapping exceptions. All per-file mapping-pending evidence lives in V2/V21 checkpoints and immutable deltas."})
    result["error_ledger_id"]=error_id
    result["mapping_pending"]=sum(v for k,v in counts.items() if "SCHEMA_PROFILED_NEEDS_MAPPING" in k)
    fid=put_once(api,quality,"v097_SCHEMA_V21_MASTER_"+RUN+".json",result)
    upsert(api,control,"v097_SCHEMA_V21_MASTER_LATEST.json",{**result,"report_id":fid})
    f=match(api,control,"v097_SCHEMA_V21_MASTER_LATEST.json")
    if not f or load_json(api,f["id"]).get("run")!=RUN:raise RuntimeError("MASTER_READBACK_FAILED")
    print("SCHEMA_V21_MASTER="+json.dumps({**result,"sources":"seven","report_id":fid},ensure_ascii=False),flush=True)
def selftest():
    assert sum(PLAN.values())==14
    assert all(0<=lane("x",n)<n for n in (1,2,6))
    assert len({lane(str(i),6) for i in range(500)})==6
    s=b"date,code,close\n2026-11-17,2330,1\n"
    assert inspect(s,"test.csv","TWSE")["status"]=="SCHEMA_PROFILED_NEEDS_MAPPING"
    j=b'{"tables":[{"fields":["date","code","close"],"data":[["2026","2330","1"]]}]}'
    assert inspect(j,"stock_day.json","TWSE")["status"]=="SCHEMA_PROFILED_NEEDS_MAPPING"
    assert inspect(b'{"ok":1}',"a.raw.receipt_1.json","TPEx")["reason"]=="CONTROL_RECEIPT_NOT_MARKET_DATA"
    b=io.BytesIO()
    with zipfile.ZipFile(b,"w") as z:z.writestr("data.csv",s)
    assert member_manifest(b.getvalue())["members"]==1
    assert reused({"sha":"abc","contract_version":OLD_CONTRACT,"status":"SCHEMA_PROFILED_NEEDS_MAPPING"},{"source_sha256":"abc"})
    print("SCHEMA_V21_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:final()
    elif len(sys.argv)==3:source(sys.argv[1],int(sys.argv[2]))
    else:raise SystemExit("selftest | SOURCE SHARD | final")
