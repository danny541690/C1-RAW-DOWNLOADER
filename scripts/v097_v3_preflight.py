#!/usr/bin/env python3
"""JARVIS v0.97 pre-Silver V3: safe checkpoint and evidence reconciler.
This module never modifies Bronze, produces Silver, or produces Gold.
All readiness decisions are conservative: legacy header matches are NOT certified.
"""
import collections, hashlib, json, os, sys
from datetime import datetime, timezone
from scripts.v097_schema_gate_v21 import SOURCES, PLAN, VERSION as FMT_VERSION, CONTRACT as FMT_RULE, read_baseline, existing_v2, reused, lane, END
from scripts.v097_silver_schema_mapping_v1 import VERSION as MAP_VERSION, CONTRACT as MAP_RULE
from scripts.v097_bronze_autopilot import source_api

VERSION="v097_bronze_to_silver_schema_v3_20261117"
TARGET=74750
SOURCE_COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}
RESOLVED={"SILVER_SCHEMA_READY","BRONZE_HOLD","SCHEMA_HOLD","EVIDENCE_PENDING","SCOPE_EXCLUDED","CONFIRMED_EXCEPTION"}
CONTROL_PREFIX="v097_V3_"
def now():return datetime.now(timezone.utc).isoformat()
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def fingerprint(v):return hashlib.sha256(canonical(v).encode()).hexdigest()
def assert_cohort(rows,source):
    if len(rows)!=SOURCE_COUNTS[source]:raise RuntimeError("COHORT_SIZE_DRIFT_"+source)
    ids=[r["source_id"] for r in rows]
    if len(set(ids))!=len(ids):raise RuntimeError("COHORT_DUPLICATE_"+source)
    for r in rows:
        if not r.get("source_sha256") or not r.get("destination_id"):
            raise RuntimeError("COHORT_MISSING_ORIGINAL_SHA_OR_DEST_"+source)
def evidence_match(row,proof,version=None):
    if not proof or proof.get("sha")!=row["source_sha256"]:return False
    return version is None or proof.get("contract_version")==version
def classify(row,format_evidence,mapping_evidence):
    # Old bronze_status is a reusable pointer, not proof of raw file readback in V3.
    bronze=row.get("bronze_status")
    if bronze!="BRONZE_INTEGRITY_READY":
        return {"g0":"BRONZE_HOLD","g1":"BLOCKED","g2":"BLOCKED","g3":"BLOCKED",
                "g4":"BRONZE_HOLD","reason":"BASELINE_BRONZE_NOT_READY","old_bronze_status":bronze}
    g0="LEGACY_BRONZE_REUSABLE_VERIFY_LINEAGE"
    if not format_evidence:return {"g0":g0,"g1":"PENDING","g2":"PENDING","g3":"PENDING",
                                   "g4":"EVIDENCE_PENDING","reason":"FORMAT_NOT_PROFILED"}
    kind=format_evidence.get("status","")
    if kind in ("FORMAT_STRUCTURAL_HOLD","BLOCKED_BRONZE","SOURCE_READ_FAILED_FINAL"):
        return {"g0":g0,"g1":"HOLD","g2":"BLOCKED","g3":"BLOCKED",
                "g4":"SCHEMA_HOLD","reason":kind}
    if kind in ("FORMAT_UNSUPPORTED","FORMAT_RESOURCE_LIMIT","SCHEMA_UNKNOWN_DATASET"):
        return {"g0":g0,"g1":"EXCEPTION","g2":"PENDING","g3":"PENDING",
                "g4":"EVIDENCE_PENDING","reason":kind}
    if kind not in END:return {"g0":g0,"g1":"PENDING","g2":"PENDING","g3":"PENDING",
                               "g4":"EVIDENCE_PENDING","reason":"FORMAT_NONTERMINAL"}
    if not mapping_evidence:return {"g0":g0,"g1":"PROFILED","g2":"PENDING","g3":"PENDING",
                                    "g4":"EVIDENCE_PENDING","reason":"MAPPING_NOT_CHECKED"}
    m=mapping_evidence.get("status")
    if m=="MAPPING_FORMAT_EXCEPTION":
        return {"g0":g0,"g1":"EXCEPTION","g2":"PENDING","g3":"PENDING",
                "g4":"EVIDENCE_PENDING","reason":m}
    return {"g0":g0,"g1":"PROFILED","g2":"PENDING","g3":"PENDING",
            "g4":"EVIDENCE_PENDING","reason":m or "SOURCE_NATIVE_CONTRACT_MISSING"}
def evidence_fp(row,fmt,mp):
    return fingerprint({"source_id":row["source_id"],"sha":row["source_sha256"],
      "dest":row["destination_id"],"old_bronze":row.get("bronze_status"),
      "format_version":FMT_RULE,"format_sha":fmt.get("sha") if fmt else None,
      "format_status":fmt.get("status") if fmt else None,"format_run":fmt.get("run") if fmt else None,
      "mapping_version":MAP_RULE,"mapping_fingerprint":mp.get("evidence_fingerprint") if mp else None,
      "mapping_status":mp.get("status") if mp else None})
def format_index(api,control,match,load_json,src):
    fmt={}
    for shard in range(PLAN[src]):
        f=match(api,control,"v097_SCHEMA_V21_SHARD_"+src+"_"+str(shard)+".json")
        if not f:continue
        ck=load_json(api,f["id"])
        if ck.get("schema")!=FMT_VERSION:raise RuntimeError("FORMAT_CHECKPOINT_CONFLICT")
        for sid,record in ck.get("done",{}).items():
            if sid in fmt or lane(sid,PLAN[src])!=shard:raise RuntimeError("FORMAT_SHARD_CONFLICT")
            fmt[sid]=record
    return fmt
def load_evidence(api,control,match,load_json,src,rows):
    fmt=format_index(api,control,match,load_json,src)
    old=existing_v2(api,control,match,load_json,src)
    mf=match(api,control,"v097_SCHEMA_MAPPING_V1_CK_"+src+".json")
    maps=load_json(api,mf["id"]).get("done",{}) if mf else {}
    baseline={r["source_id"] for r in rows}
    if set(fmt)-baseline or set(maps)-baseline:raise RuntimeError("ORPHAN_CHECKPOINT_"+src)
    def pick(row):
        sid=row["source_id"]
        f=fmt.get(sid)
        if evidence_match(row,f,FMT_RULE) and f.get("status") in END:return f
        f=old.get(sid)
        if reused(f,row):return f
        return None
    return pick,maps
def snapshot():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    result={"schema":VERSION,"run":os.getenv("GITHUB_RUN_ID","manual"),
      "created_at":now(),"cohort":TARGET,"sources":[],"overall":{},
      "silver_materialized":0,"gold_materialized":0,
      "release_policy":"DISABLED_UNTIL_SOURCE_DATASET_ERA_CONTRACT_AND_G0_READBACK_VERIFIED"}
    overall=collections.Counter()
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src)
        assert_cohort(rows,src)
        pick,maps=load_evidence(api,control,match,load_json,src,rows)
        counts=collections.Counter();g0=collections.Counter();reused_count=0
        for row in rows:
            fmt=pick(row)
            mp=maps.get(row["source_id"])
            if mp and (mp.get("sha")!=row["source_sha256"] or mp.get("contract_version")!=MAP_RULE):
                mp=None
            v=classify(row,fmt,mp)
            counts[v["g4"]]+=1;g0[v["g0"]]+=1
            if fmt:reused_count+=1
            if v["g4"]=="SILVER_SCHEMA_READY":raise RuntimeError("UNAUTHORIZED_READY_PROMOTION")
        if sum(counts.values())!=len(rows):raise RuntimeError("SOURCE_ACCOUNTING_DRIFT")
        overall.update(counts)
        result["sources"].append({"source":src,"cohort":len(rows),
          "format_evidence_reused":reused_count,"mapping_checked":sum(1 for r in rows if r["source_id"] in maps),
          "g0":dict(g0),"g4":dict(counts)})
    if sum(overall.values())!=TARGET:raise RuntimeError("TOTAL_DRIFT")
    result["overall"]=dict(overall)
    result["silver_schema_ready_certified"]=0
    # Safety: snapshot writes only a separate QA report, never edits prior checkpoints.
    name="v097_V3_PREFLIGHT_SNAPSHOT_"+result["run"]+".json"
    fid=put_once(api,quality,name,result)
    result["report_id"]=fid
    print("V3_PREFLIGHT_SNAPSHOT="+canonical(result),flush=True)
def selftest():
    assert sum(SOURCE_COUNTS.values())==TARGET
    row={"source_id":"test","source_sha256":"a"*64,"destination_id":"D","bronze_status":"BRONZE_INTEGRITY_READY"}
    assert classify(row,None,None)["g4"]=="EVIDENCE_PENDING"
    fmt={"sha":"a"*64,"status":"SCHEMA_PROFILED_NEEDS_MAPPING"}
    assert classify(row,fmt,None)["g4"]=="EVIDENCE_PENDING"
    assert classify(row,fmt,{"status":"HEADER_MATCHED_UNCERTIFIED"})["g4"]=="EVIDENCE_PENDING"
    assert classify(row,{"sha":"a"*64,"status":"FORMAT_STRUCTURAL_HOLD"},None)["g4"]=="SCHEMA_HOLD"
    assert classify({**row,"bronze_status":"BRONZE_INTEGRITY_HOLD"},fmt,None)["g4"]=="BRONZE_HOLD"
    assert evidence_match(row,{"sha":"b"*64,"contract_version":FMT_RULE},FMT_RULE) is False
    assert evidence_fp(row,fmt,None)!=evidence_fp(row,{**fmt,"status":"FORMAT_STRUCTURAL_HOLD"},None)
    assert RESOLVED.issuperset({"SILVER_SCHEMA_READY","SCHEMA_HOLD","BRONZE_HOLD"})
    print("V3_PREFLIGHT_NEGATIVE_TESTS_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["snapshot"]:snapshot()
    else:raise SystemExit("usage: selftest|snapshot")
