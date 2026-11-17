#!/usr/bin/env python3
"""V3 source-isolated incremental Bronze->Silver-Schema inspector.
Reads raw destinations only. No Bronze writes and no Silver/Gold conversion.
A scanned ZIP does not imply a certified source-native schema.
"""
import collections, hashlib, io, json, os, sys, zipfile
from datetime import datetime, timezone
from scripts.v097_v3_preflight import (VERSION, TARGET, SOURCE_COUNTS, SOURCES,
    assert_cohort, load_evidence, evidence_fp, classify, canonical)
from scripts.v097_schema_gate_v21 import inspect, fmt
from scripts.v097_bronze_autopilot import source_api

ENGINE="v097_v3_source_worker_20261117_r1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=max(1,min(150,int(os.getenv("V3_BATCH","50"))))
SHARDS={"TWSE":2,"TPEx":2,"MOPS":1,"TDCC":3,"TAIFEX":1,"NDC":1,"FinMind":1}
MAX_ORIGINAL=65*1024*1024
MAX_EXPANDED=600*1024*1024
MAX_MEMBERS=5000
MAX_PARSED_MEMBER=6*1024*1024
CK="v097_V3_SOURCE_SHARD_CK_"
def now():return datetime.now(timezone.utc).isoformat()
def digest(b):return hashlib.sha256(b).hexdigest()
def shard_for(sid,src):return int(digest(sid.encode())[:12],16)%SHARDS[src]
def zip_profile(blob,src='TWSE'):
    result={"format":"ZIP","member_sha_all_verified":False,"member_schemas_verified":False}
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            members=[m for m in z.infolist() if not m.is_dir()]
            if not members:return {"status":"SCHEMA_HOLD","reason":"EMPTY_ZIP"}
            if len(members)>MAX_MEMBERS or sum(m.file_size for m in members)>MAX_EXPANDED:
                return {"status":"EVIDENCE_PENDING","reason":"ZIP_RESOURCE_LIMIT","members":len(members)}
            kinds=collections.Counter()
            proofs=[]
            for info in members:
                parts=info.filename.replace("\\","/").split("/")
                if info.filename.startswith("/") or ".." in parts or not info.filename.strip():
                    return {"status":"SCHEMA_HOLD","reason":"UNSAFE_ZIP_PATH"}
                h=hashlib.sha256()
                sample=bytearray()
                with z.open(info) as stream:
                    while True:
                        block=stream.read(1024*1024)
                        if not block:break
                        h.update(block)
                        if len(sample)<MAX_PARSED_MEMBER:
                            sample.extend(block[:MAX_PARSED_MEMBER-len(sample)])
                signature=fmt(info.filename,bytes(sample))
                kinds[signature]+=1
                rec={"path":info.filename,"sha256":h.hexdigest(),"bytes":info.file_size,
                     "signature":signature,"crc32":format(info.CRC,"08x")}
                if info.file_size<=MAX_PARSED_MEMBER and signature not in ("ZIP","XLSX"):
                    parsed=inspect(bytes(sample),info.filename,src) if signature in ("JSON","CSV_CANDIDATE") else {}
                    rec["observed_header"]=parsed.get("header")
                    rec["observed_keys"]=parsed.get("keys")
                    rec["format_status"]=parsed.get("status")
                else:
                    rec["format_status"]="HEADER_PENDING"
                proofs.append(rec)
            result.update({"status":"MEMBERS_HASHED_SCHEMA_PENDING","members":len(members),
                           "member_signatures":dict(kinds),"member_manifest":proofs,
                           "member_sha_all_verified":True})
            return result
    except (OSError,ValueError,zipfile.BadZipFile,RuntimeError) as e:
        return {"status":"SCHEMA_HOLD","reason":"ZIP_"+type(e).__name__}
def inspect_one(row,fmt_evidence,map_evidence,api,call):
    baseline=classify(row,fmt_evidence,map_evidence)
    identity={"source_id":row["source_id"],"source":row["source"],
              "sha":row["source_sha256"],"destination_id":row["destination_id"],
              "source_path":row.get("source_path"),
              "evidence_fingerprint":evidence_fp(row,fmt_evidence,map_evidence),
              "engine":ENGINE,"run":RUN,"observed_at":now(),
              "silver_materialized":False,"gold_materialized":False}
    if baseline["g4"] in ("BRONZE_HOLD","SCHEMA_HOLD"):
        return {**identity,**baseline}
    reason=baseline.get("reason")
    need_bytes=(fmt_evidence is None or
                fmt_evidence.get("signature")=="ZIP" and
                map_evidence and map_evidence.get("status")=="MAPPING_MEMBERS_PENDING")
    if not need_bytes:
        return {**identity,**baseline,"reason":reason,
                "g0":"DEST_SHA_VERIFIED_REUSED" if fmt_evidence and
                (fmt_evidence.get("input_sha_verified") is True or fmt_evidence.get("input_bytes_sha_checked") is True)
                else baseline["g0"]}
    if row.get("bronze_status")!="BRONZE_INTEGRITY_READY":
        return {**identity,**baseline}
    try:
        blob=call(lambda:api.files().get_media(fileId=row["destination_id"]))
        if not blob:return {**identity,**baseline,"g0":"BRONZE_HOLD","g4":"BRONZE_HOLD","reason":"RAW_EMPTY"}
        if len(blob)>MAX_ORIGINAL:
            return {**identity,**baseline,"g0":"EVIDENCE_PENDING","reason":"RAW_OVER_SIZE_LIMIT"}
        if digest(blob)!=row["source_sha256"]:
            return {**identity,**baseline,"g0":"BRONZE_HOLD","g4":"BRONZE_HOLD","reason":"DESTINATION_SHA_MISMATCH"}
        observed=zip_profile(blob,row["source"]) if fmt(row["source_path"],blob)=="ZIP" else inspect(blob,row["source_path"],row["source"])
        if observed.get("status")=="SCHEMA_HOLD" or observed.get("status")=="FORMAT_STRUCTURAL_HOLD":
            return {**identity,**baseline,"g0":"DEST_SHA_VERIFIED","g1":"SCHEMA_HOLD",
                    "g4":"SCHEMA_HOLD","reason":observed.get("reason"),"new_native_evidence":observed}
        return {**identity,**baseline,"g0":"DEST_SHA_VERIFIED",
                "g1":"ZIP_MEMBERS_PROFILED" if observed.get("format")=="ZIP" else "SOURCE_FORMAT_PROFILED",
                "g2":"PENDING_SOURCE_DATASET_EDITION_CONTRACT","g3":"PENDING_TYPED_SCHEMA_CONTRACT",
                "g4":"EVIDENCE_PENDING","reason":"CONTRACT_EVIDENCE_REQUIRED",
                "new_native_evidence":observed}
    except Exception as e:
        return {**identity,**baseline,"g4":"RETRY_PENDING","reason":"SOURCE_READ_"+type(e).__name__}
def source(src,shard):
    if src not in SHARDS or not 0<=shard<SHARDS[src]:raise ValueError("BAD_SOURCE_SHARD")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    from scripts.v097_v3_preflight import read_baseline
    rows=read_baseline(api,quality,match,load_json,src)
    assert_cohort(rows,src)
    pick,maps=load_evidence(api,control,match,load_json,src,rows)
    queue=[r for r in rows if shard_for(r["source_id"],src)==shard]
    ckname=CK+src+"_"+str(shard)+".json"
    cf=match(api,control,ckname)
    ck=load_json(api,cf["id"]) if cf else {"schema":ENGINE,"source":src,"shard":shard,"done":{}}
    if ck.get("schema")!=ENGINE or ck.get("shard")!=shard:raise RuntimeError("CK_VERSION_OR_SHARD_CONFLICT")
    done=ck["done"]
    allowed={r["source_id"] for r in queue}
    if set(done)-allowed:raise RuntimeError("CK_ORPHAN_OR_CROSS_SHARD")
    batch=[]
    for r in queue:
        e=pick(r);mp=maps.get(r["source_id"])
        if mp and mp.get("sha")!=r["source_sha256"]:mp=None
        current=evidence_fp(r,e,mp)
        prior=done.get(r["source_id"])
        if prior and prior.get("evidence_fingerprint")==current and prior.get("engine")==ENGINE and prior.get("g4")!="RETRY_PENDING":
            continue
        if prior and prior.get("g4")=="RETRY_PENDING" and prior.get("attempts",0)>=3:continue
        batch.append((r,e,mp))
        if len(batch)>=BATCH:break
    new={}
    for r,e,mp in batch:
        rec=inspect_one(r,e,mp,api,call)
        prior=done.get(r["source_id"],{})
        if rec["g4"]=="RETRY_PENDING":
            rec["attempts"]=prior.get("attempts",0)+1
            if rec["attempts"]>=3:rec["g4"]="CONFIRMED_EXCEPTION";rec["reason"]="SOURCE_READ_FAILED_AFTER_3"
        new[r["source_id"]]=rec
    if new:
        delta=put_once(api,quality,"v097_V3_WORKER_DELTA_"+src+"_"+str(shard)+"_"+RUN+".json",
                       {"schema":ENGINE,"source":src,"shard":shard,"run":RUN,"records":new})
        done.update(new)
        ck["last_run"]=RUN;ck["done"]=done
        ck["history"]=(ck.get("history",[])+[{"run":RUN,"delta_id":delta,"n":len(new)}])[-100:]
        upsert(api,control,ckname,ck)
        readback=match(api,control,ckname)
        if not readback or len(load_json(api,readback["id"]).get("done",{}))!=len(done):
            raise RuntimeError("CHECKPOINT_READBACK_FAILED")
    summary={"schema":ENGINE,"source":src,"shard":shard,"cohort":len(queue),"done":len(done),
             "new":len(new),"remaining":len(queue)-len(done),"states":dict(collections.Counter(v["g4"] for v in done.values()))}
    print("V3_WORKER_PROGRESS="+canonical(summary),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    overall=collections.Counter();reports=[];total=0;errors=[]
    from scripts.v097_v3_preflight import read_baseline
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src);total+=len(rows);idx={r["source_id"]:r for r in rows}
        done={}
        for shard in range(SHARDS[src]):
            f=match(api,control,CK+src+"_"+str(shard)+".json")
            if not f:continue
            ck=load_json(api,f["id"])
            if ck.get("schema")!=ENGINE or ck.get("shard")!=shard:raise RuntimeError("CHECKPOINT_SCHEMA_CONFLICT")
            for sid,entry in ck.get("done",{}).items():
                if sid in done or sid not in idx or shard_for(sid,src)!=shard:
                    raise RuntimeError("DUPLICATE_OR_BAD_SHARD")
                if entry.get("sha")!=idx[sid]["source_sha256"]:raise RuntimeError("SOURCE_SHA_CHANGED")
                done[sid]=entry
        c=collections.Counter()
        for r in rows:
            v=done.get(r["source_id"]);status=v["g4"] if v else "NOT_CHECKED"
            c[status]+=1
            if v and status in ("BRONZE_HOLD","SCHEMA_HOLD","CONFIRMED_EXCEPTION","RETRY_PENDING"):
                errors.append({"source":src,"source_id":r["source_id"],"status":status,
                               "reason":v.get("reason"),"run":v.get("run")})
        overall.update(c)
        reports.append({"source":src,"cohort":len(rows),"checked":len(done),"statuses":dict(c)})
    if total!=TARGET or sum(overall.values())!=TARGET:raise RuntimeError("COHORT_RECONCILE_FAILED")
    out={"schema":ENGINE,"run":RUN,"created_at":now(),"cohort":total,"sources":reports,
         "statuses":dict(overall),"checked":total-overall["NOT_CHECKED"],
         "not_checked":overall["NOT_CHECKED"],"schema_ready_certified":0,
         "silver_materialized":0,"gold_materialized":0,
         "note":"V3 source-native format deep evidence only. No contract has release approval, no automatic Ready promotion."}
    eid=put_once(api,quality,"v097_V3_ERROR_LEDGER_"+RUN+".json",
                  {"run":RUN,"schema":ENGINE,"count":len(errors),"records":errors})
    out["error_ledger_id"]=eid
    rid=put_once(api,quality,"v097_V3_MASTER_"+RUN+".json",out)
    print("V3_MASTER="+canonical({**out,"report_id":rid}),flush=True)
def selftest():
    from scripts.v097_v3_preflight import fingerprint
    assert sum(SHARDS.values())==11
    assert all(shard_for("a"+str(i),src)<SHARDS[src] for src in SOURCES for i in range(20))
    assert zip_profile(b"bad")["status"]=="SCHEMA_HOLD"
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w") as z:
        z.writestr("day.csv","日期,證券代號,收盤價\n2026-11-16,2330,100\n")
    z=zip_profile(bio.getvalue())
    assert z["status"]=="MEMBERS_HASHED_SCHEMA_PENDING" and z["member_sha_all_verified"]
    assert z["member_manifest"][0]["sha256"]==digest("日期,證券代號,收盤價\n2026-11-16,2330,100\n".encode())
    assert z["member_schemas_verified"] is False
    print("V3_SOURCE_WORKER_SAFETY_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==2 and sys.argv[1]=="final":final()
    elif len(sys.argv)==3:source(sys.argv[1],int(sys.argv[2]))
    else:raise SystemExit("selftest|SOURCE SHARD|final")
