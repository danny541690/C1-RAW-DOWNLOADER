#!/usr/bin/env python3
"""V3 G2/G3 dataset-era contract discovery and conservative evidence audit.

No Bronze changes and no Silver/Gold conversions. Audits the frozen cohort,
reuses existing V2/V2.1 and V3 raw-format checkpoints, groups source-native
contracts, publishes source-specific immutable delta and unified gap report.
Only source-native audited contracts can become VERIFIED; header candidates
are never treated as a complete typed validation.
"""
import collections, hashlib, json, os, sys
from datetime import datetime, timezone
from scripts.v097_v3_preflight import (
    SOURCES, TARGET, read_baseline, assert_cohort, load_evidence, canonical,
    source_api, MAP_RULE
)
from scripts.v097_v3_source_worker import CK, SHARDS, ENGINE, shard_for
from scripts.v097_v3_contract_registry import infer, REGISTRY_VERSION, normalize
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS

VERSION="v097_g2g3_contract_discovery_20261117_r1"
RUN=os.environ.get("GITHUB_RUN_ID","manual")
def now():return datetime.now(timezone.utc).isoformat()
def get_worker(api,control,match,load_json,source,rows):
    ids={r["source_id"]:r for r in rows};result={}
    for shard in range(SHARDS[source]):
        f=match(api,control,CK+source+"_"+str(shard)+".json")
        if not f:continue
        ck=load_json(api,f["id"])
        if ck.get("schema")!=ENGINE or ck.get("shard")!=shard:
            raise RuntimeError("G2G3_WORKER_CHECKPOINT_VERSION_ERROR")
        for sid,rec in ck.get("done",{}).items():
            if sid not in ids or sid in result or shard_for(sid,source)!=shard:
                raise RuntimeError("G2G3_WORKER_DUPLICATE_OR_ORPHAN")
            if rec.get("sha")!=ids[sid]["source_sha256"]:raise RuntimeError("G2G3_SHA_CONFLICT")
            result[sid]=rec
    return result
def candidates(row,profile,mapping,v3,native=None):
    era=(profile or {}).get("historical_version")
    hint=(profile or {}).get("dataset_candidate")
    headers=(profile or {}).get("header") or (profile or {}).get("keys") or []
    if not headers and mapping and isinstance(mapping.get("mapping"),dict):
        headers=list(mapping["mapping"].values())
    samples=[]
    if headers:samples.append({"scope":"original","headers":headers,"member_sha":None})
    old_worker_native=(v3 or {}).get("new_native_evidence",{})
    for member in (old_worker_native.get("member_manifest") or []):
        hs=member.get("observed_header") or member.get("observed_keys") or []
        if hs:samples.append({"scope":member.get("path"),"headers":hs,
                               "member_sha":member.get("sha256")})
    if native and native.get('sha')==row['source_sha256']:
        for member in native.get('evidence',[]):
            hs=member.get('header') or []
            if hs:samples.append({'scope':member.get('path','native'),
                'headers':hs,'member_sha':member.get('sha')})
    result=[]
    for sample in samples:
        c=infer(row["source"],sample["headers"],era,hint)
        result.append({
            "scope":sample["scope"],"member_sha":sample["member_sha"],
            "dataset_candidate":c.get("dataset_candidate"),
            "era":era,"era_registered":c.get("era_registered",False),
            "contract_status":c["status"],"missing":c.get("missing_required",[]),
            "observed_fields":c.get("observed_fields",{}),
            "observed_header":sample["headers"][:100],
            "source_native_typed_and_row_verified":False,
            "contract_registry":REGISTRY_VERSION})
    return result
def analyse(row,profile,mapping,v3,native=None):
    if profile and profile.get("sha")!=row["source_sha256"]:profile=None
    if mapping and (mapping.get("sha")!=row["source_sha256"] or
                    mapping.get("contract_version")!=MAP_RULE):mapping=None
    if v3 and (v3.get("sha")!=row["source_sha256"] or v3.get("engine")!=ENGINE):v3=None
    observed=candidates(row,profile,mapping,v3,native)
    if row.get("bronze_status")!="BRONZE_INTEGRITY_READY":
        status="BRONZE_EVIDENCE_HOLD"
    elif not profile:
        status="FORMAT_PROFILE_PENDING"
    elif profile.get("status") in ("FORMAT_UNSUPPORTED","FORMAT_STRUCTURAL_HOLD","FORMAT_RESOURCE_LIMIT"):
        status="FORMAT_EXCEPTION"
    elif not observed:
        status="HEADER_OR_ZIP_MEMBER_PENDING"
    elif any(q["contract_status"]=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED" for q in observed):
        status="G3_HEADER_COMPLETE_TYPED_PROOF_PENDING"
    elif any(q["era_registered"] for q in observed):
        status="G2_DATASET_EDITION_CANDIDATE"
    else:
        status="G2_HISTORICAL_EDITION_PENDING"
    signature=(profile or {}).get("signature") or (v3 or {}).get("new_native_evidence",{}).get("format") or "UNKNOWN"
    era=(profile or {}).get("historical_version") or "UNKNOWN"
    if observed:
        best=sorted(observed,key=lambda x:(len(x["missing"]),not x["era_registered"]))[0]
        dataset=best.get("dataset_candidate") or "UNKNOWN"
        header_sig=hashlib.sha256(canonical([normalize(x) for x in best["observed_header"]]).encode()).hexdigest()[:16]
    else:
        best=None;dataset="UNKNOWN";header_sig="NO_OBSERVED_HEADER"
    group_kind="HEADER_LAYOUT_CANDIDATE_UNCERTIFIED" if observed else "DISCOVERY_BUCKET_NO_HEADER_NOT_CERTIFIABLE"
    group_key="|".join([row["source"],str(dataset),str(era),str(signature),header_sig])
    return {"source_id":row["source_id"],"source":row["source"],"sha":row["source_sha256"],
        "g2g3_status":status,"group_key":group_key,"group_kind":group_kind,"dataset_candidate":dataset,
        "era":era,"format_signature":signature,
        "candidate_observations":observed,
        "g2_verified":False,"g3_verified":False,"schema_ready":False,
        "profile_reused":profile is not None,"mapping_reused":mapping is not None,
        "v3_evidence_reused":v3 is not None}
def selftest():
    row={"source_id":"TEST","source":"FinMind","source_sha256":"a"*64,
         "bronze_status":"BRONZE_INTEGRITY_READY"}
    era=OFFICIAL_VERSIONS["FinMind"]["periods"][-1]["id"]
    f={"sha":"a"*64,"signature":"JSON","historical_version":era,
       "status":"SCHEMA_PROFILED_NEEDS_MAPPING",
       "header":["date","stock_id","open","max","min","close","Trading_Volume","Trading_money"]}
    a=analyse(row,f,None,None)
    assert a["g2g3_status"]=="G3_HEADER_COMPLETE_TYPED_PROOF_PENDING"
    assert not a["g3_verified"] and not a["schema_ready"]
    assert analyse(row,None,None,None)["g2g3_status"]=="FORMAT_PROFILE_PENDING"
    assert analyse(row,{**f,"sha":"b"*64},None,None)["g2g3_status"]=="FORMAT_PROFILE_PENDING"
    assert a["group_key"]==analyse(row,f,None,None)["group_key"]
    recovered={"sha":"a"*64,"evidence":[{"path":"raw.csv","sha":"b"*64,
       "header":["date","stock_id","open","max","min","close","Trading_Volume","Trading_money"]}]}
    without=analyse(row,{"sha":"a"*64,"signature":"ZIP","historical_version":era,
        "status":"SCHEMA_PROFILED_NEEDS_MAPPING"},None,None)
    with_native=analyse(row,{"sha":"a"*64,"signature":"ZIP","historical_version":era,
        "status":"SCHEMA_PROFILED_NEEDS_MAPPING"},None,None,recovered)
    assert without["g2g3_status"]=="HEADER_OR_ZIP_MEMBER_PENDING"
    assert with_native["g2g3_status"]=="G3_HEADER_COMPLETE_TYPED_PROOF_PENDING"
    assert with_native["g3_verified"] is False and with_native["schema_ready"] is False
    assert without["group_kind"]=="DISCOVERY_BUCKET_NO_HEADER_NOT_CERTIFIABLE"
    assert with_native["group_kind"]=="HEADER_LAYOUT_CANDIDATE_UNCERTIFIED"
    wrong_sha={**recovered,"sha":"c"*64}
    assert analyse(row,{"sha":"a"*64,"signature":"ZIP","historical_version":era,
        "status":"SCHEMA_PROFILED_NEEDS_MAPPING"},None,None,wrong_sha)["g2g3_status"]=="HEADER_OR_ZIP_MEMBER_PENDING"
    print("G2G3_V3_CONSERVATIVE_DISCOVERY_SELFTEST_PASS")
def source(src):
    if src not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    rows=read_baseline(api,quality,match,load_json,src)
    assert_cohort(rows,src)
    pick,mappings=load_evidence(api,control,match,load_json,src,rows)
    workers=get_worker(api,control,match,load_json,src,rows)
    hf=match(api,control,"v097_G2G3_HEADER_CK_"+src+".json")
    recovered=load_json(api,hf["id"]).get("done",{}) if hf else {}
    if set(recovered)-{r["source_id"] for r in rows}:
        raise RuntimeError("NATIVE_HEADER_CHECKPOINT_ORPHAN_"+src)
    statuses=collections.Counter();groups={};records=[]
    for row in rows:
        sid=row["source_id"]
        a=analyse(row,pick(row),mappings.get(sid),workers.get(sid),recovered.get(sid))
        records.append(a);statuses[a["g2g3_status"]]+=1
        key=a["group_key"]
        if key not in groups:
            groups[key]={"group_key":key,"source":src,"dataset_candidate":a["dataset_candidate"],
               "era":a["era"],"signature":a["format_signature"],"files":0,
               "status_counts":collections.Counter(),"examples":[], "group_kind":a["group_kind"]}
        g=groups[key];g["files"]+=1;g["status_counts"][a["g2g3_status"]]+=1
        if len(g["examples"])<3:g["examples"].append(sid)
    if sum(statuses.values())!=len(rows):raise RuntimeError("SOURCE_ACCOUNTING_DRIFT")
    out={"schema":VERSION,"run":RUN,"source":src,"cohort":len(rows),"created_at":now(),
        "statuses":dict(statuses),"contract_groups":sorted(
            [{**g,"status_counts":dict(g["status_counts"])} for g in groups.values()],
             key=lambda x:-x["files"]),"g2_verified":0,"g3_verified":0,
        "silver_gold_executed":False}
    detail_id=put_once(api,quality,"v097_G2G3_SOURCE_DETAIL_"+src+"_"+RUN+".json",
                       {"schema":VERSION,"source":src,"run":RUN,"records":records})
    out["detail_id"]=detail_id
    id=put_once(api,quality,"v097_G2G3_SOURCE_MASTER_"+src+"_"+RUN+".json",out)
    print("G2G3_SOURCE_MASTER="+canonical({"source":src,"report_id":id,"detail_id":detail_id,
          "cohort":len(rows),"status_counts":dict(statuses),"groups":len(groups),
          "largest_groups":out["contract_groups"][:8]}),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    total=0;all_status=collections.Counter();sources=[];groups=[]
    for src in SOURCES:
        f=match(api,quality,"v097_G2G3_SOURCE_MASTER_"+src+"_"+RUN+".json")
        if not f:
            sources.append({"source":src,"status":"SOURCE_JOB_FAILED_OR_NOT_PUBLISHED"})
            continue
        doc=load_json(api,f["id"])
        if doc.get("cohort")!=len(read_baseline(api,quality,match,load_json,src)):
            raise RuntimeError("G2G3_SOURCE_COHORT_CONFLICT")
        total+=doc["cohort"];all_status.update(doc["statuses"])
        sources.append({"source":src,"cohort":doc["cohort"],"status":"DONE",
                        "status_counts":doc["statuses"],"contract_groups":len(doc["contract_groups"]),
                        "detail_id":doc["detail_id"],"source_report_id":f["id"]})
        groups.extend(doc["contract_groups"])
    complete=(total==TARGET and len(sources)==7 and all(s.get("status")=="DONE" for s in sources))
    if complete and sum(all_status.values())!=TARGET:raise RuntimeError("G2G3_TOTAL_DRIFT")
    master={"schema":VERSION,"run":RUN,"created_at":now(),"cohort":TARGET,
        "scanned_sources_cohort":total,"complete_seven_source_census":complete,
        "overall_statuses":dict(all_status),"sources":sources,
        "ranked_contract_groups":sorted(groups,key=lambda g:-g["files"]),
        "g2_verified":0,"g3_verified":0,"schema_ready":0,
        "silver_materialized":0,"gold_materialized":0,
        "note":"Conservative contract groups and missing evidence. No source-native typed attestations and no release."}
    id=put_once(api,quality,"v097_G2G3_CONTRACT_MASTER_"+RUN+".json",master)
    if complete:
        upsert(api,control,"v097_G2G3_CONTRACT_MASTER_LATEST.json",{**master,"report_id":id})
    print("G2G3_CONTRACT_MASTER="+canonical({"run":RUN,"report_id":id,
         "complete":complete,"scanned":total,"statuses":dict(all_status),
         "groups":len(groups),"largest_groups":master["ranked_contract_groups"][:18],
         "g2_verified":0,"g3_verified":0,"schema_ready":0}),flush=True)
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:final()
    elif len(sys.argv)==3 and sys.argv[1]=="source":source(sys.argv[2])
    else:raise SystemExit("selftest|source SOURCE|final")
