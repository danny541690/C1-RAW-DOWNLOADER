#!/usr/bin/env python3
"""JARVIS v0.97 V3 unified acceptance board.
Single source of truth: frozen 74,750 source IDs, legacy evidence and V3 checkpoint.
Records are independently counted per gate; no previous scan is treated as a release.
Never opens or modifies Bronze; never creates Silver/Gold datasets.
"""
import collections, json, os, sys
from datetime import datetime,timezone
from scripts.v097_v3_preflight import (
  SOURCE_COUNTS,SOURCES,TARGET,assert_cohort,read_baseline,load_evidence,evidence_match,
  FMT_RULE,MAP_RULE,canonical,source_api
)
from scripts.v097_v3_source_worker import CK,ENGINE,SHARDS,shard_for

VERSION="v097_v3_unified_acceptance_board_20261117_r1"
RUN=os.getenv("GITHUB_RUN_ID","manual")
GATES=("g0","g1","g2","g3","g4")
STAGES=("READY","BRONZE_BLOCKED","FORMAT_BLOCKED","DATASET_PENDING",
        "SCHEMA_CONTRACT_PENDING","FORMAT_PENDING","NOT_SCANNED","EXCLUDED")
def now():return datetime.now(timezone.utc).isoformat()
def load_worker(api,control,match,load_json,src,rows):
    idx={r["source_id"]:r for r in rows}; out={}
    for shard in range(SHARDS[src]):
        f=match(api,control,CK+src+"_"+str(shard)+".json")
        if not f:continue
        ck=load_json(api,f["id"])
        if ck.get("schema")!=ENGINE or ck.get("shard")!=shard:
            raise RuntimeError("V3_WORKER_SCHEMA_SHARD_CONFLICT_"+src)
        for sid,rec in ck.get("done",{}).items():
            if sid in out or sid not in idx or shard_for(sid,src)!=shard:
                raise RuntimeError("V3_WORKER_DUP_OR_ORPHAN_"+src)
            if rec.get("sha")!=idx[sid]["source_sha256"]:
                raise RuntimeError("V3_WORKER_SHA_CONFLICT_"+src)
            out[sid]=rec
    return out
def decision(row,fmt,mp,v3):
    # All PASS and READY counters are conservative. This function is purely descriptive.
    bronze=(row.get("bronze_status")=="BRONZE_INTEGRITY_READY")
    fmt_valid=bool(fmt and evidence_match(row,fmt))
    map_valid=bool(mp and mp.get("sha")==row["source_sha256"] and
                   mp.get("contract_version")==MAP_RULE)
    worker_valid=bool(v3 and v3.get("sha")==row["source_sha256"] and
                      v3.get("engine")==ENGINE)
    g0="LEGACY_READY_RECHECK_REQUIRED" if bronze else "BRONZE_HOLD"
    if worker_valid:
        g0=v3.get("g0") or g0
    g1="FORMAT_PROFILE_REUSED_UNCERTIFIED" if fmt_valid else "FORMAT_NOT_PROFILED"
    if worker_valid and v3.get("g1") in ("ZIP_MEMBERS_PROFILED","SOURCE_FORMAT_PROFILED"):
        g1=v3["g1"]
    g2="DATASET_IDENTITY_PENDING"
    g3="SCHEMA_CONTRACT_PENDING"
    if worker_valid:
        g2=v3.get("g2") or g2
        g3=v3.get("g3") or g3
    mapping_status=mp.get("status") if map_valid else None
    g4="EVIDENCE_PENDING"
    if not bronze or worker_valid and v3.get("g4")=="BRONZE_HOLD":
        stage="BRONZE_BLOCKED";g4="BRONZE_HOLD"
    elif worker_valid and v3.get("g4")=="SCHEMA_HOLD":
        stage="FORMAT_BLOCKED";g4="SCHEMA_HOLD"
    elif fmt_valid and fmt.get("status") in ("FORMAT_UNSUPPORTED","FORMAT_RESOURCE_LIMIT",
                                           "FORMAT_STRUCTURAL_HOLD","BLOCKED_BRONZE"):
        stage="FORMAT_BLOCKED"
    elif not fmt_valid:
        stage="FORMAT_PENDING"
    elif not map_valid:
        stage="DATASET_PENDING"
    elif mapping_status in ("MAPPING_DATASET_PENDING","MAPPING_MEMBERS_PENDING",
                            "MAPPING_NEEDS_SOURCE_EVIDENCE","MAPPING_PROFILE_STALE"):
        stage="DATASET_PENDING"
    else:
        stage="SCHEMA_CONTRACT_PENDING"
    # A source-native header match is a candidate, never a formal G2/G3 certificate.
    candidate = v3.get("contract_candidate", {}) if worker_valid else {}
    if not isinstance(candidate, dict): candidate = {}
    # Certified V3 Ready requires new G0 readback, dataset/era contract + typed validation,
    # and an explicitly approved release record. No current legacy/worker evidence meets these.
    return {"source_id":row["source_id"],"sha":row["source_sha256"],
      "bronze_evidence":g0,"format_evidence":g1,"dataset_evidence":g2,
      "schema_evidence":g3,"release":g4,"primary_stage":stage,
      "format_legacy_reused":fmt_valid,"mapping_legacy_reused":map_valid,
      "v3_increment_checked":worker_valid,"mapping_status":mapping_status,
      "format_status":fmt.get("status") if fmt_valid else None,
      "v3_run":v3.get("run") if worker_valid else None,
      "v3_reason":v3.get("reason") if worker_valid else None,
      "g2_candidate_status":candidate.get("status"),
      "g2_candidate_dataset":candidate.get("dataset_candidate"),
      "g2_candidate_registry":candidate.get("registry") }
def summarize(records):
    total=len(records);stage=collections.Counter(x["primary_stage"] for x in records)
    assert sum(stage.values())==total
    format_count=sum(x["format_legacy_reused"] for x in records)
    mapping_count=sum(x["mapping_legacy_reused"] for x in records)
    v3_count=sum(x["v3_increment_checked"] for x in records)
    g0_legacy=sum(x["bronze_evidence"]!="BRONZE_HOLD" for x in records)
    g0_dest_sha=sum(x["bronze_evidence"] in ("DEST_SHA_VERIFIED","DEST_SHA_VERIFIED_REUSED") for x in records)
    g1_profiled=sum(x["format_evidence"]!="FORMAT_NOT_PROFILED" for x in records)
    g2_verified=0;g3_verified=0
    g2_candidate=collections.Counter(x.get("g2_candidate_status") or "NO_CANDIDATE_EVIDENCE" for x in records)
    ready=sum(x["release"]=="SILVER_SCHEMA_READY" for x in records)
    if ready:raise RuntimeError("NOT_AUTHORIZED_V3_READY_CERTIFICATE")
    # stage = mutually exclusive; per gate is non-exclusive.
    return {"cohort":total,
       "primary_stage":dict(stage),"format_profile_evidence":format_count,
       "mapping_evidence":mapping_count,"v3_checked":v3_count,
       "g0_legacy_ready_evidence":g0_legacy,"g0_destination_sha_verified":g0_dest_sha,
       "g1_format_profile_coverage":g1_profiled,
       "g2_dataset_contract_verified":g2_verified,
       "g3_schema_contract_verified":g3_verified,
       "g2_header_candidate_statuses":dict(g2_candidate),
       "g4_silver_schema_ready_certified":ready,
       "not_ready":total-ready,
       "v3_scan_coverage_pct":round(v3_count*100/total,2) if total else 0,
       "schema_ready_pct":round(ready*100/total,2) if total else 0}
def selftest():
    r={"source_id":"A","source_sha256":"x"*64,"bronze_status":"BRONZE_INTEGRITY_READY"}
    fmt={"sha":"x"*64,"contract_version":FMT_RULE,"status":"SCHEMA_PROFILED_NEEDS_MAPPING"}
    mp={"sha":"x"*64,"contract_version":MAP_RULE,"status":"HEADER_MATCHED_UNCERTIFIED"}
    v={"sha":"x"*64,"engine":ENGINE,"g0":"DEST_SHA_VERIFIED",
       "g1":"SOURCE_FORMAT_PROFILED","g4":"EVIDENCE_PENDING"}
    a=decision(r,fmt,mp,v)
    assert a["primary_stage"]=="SCHEMA_CONTRACT_PENDING"
    assert summarize([a])["g4_silver_schema_ready_certified"]==0
    assert a["g2_candidate_status"] is None
    assert summarize([a])["g2_header_candidate_statuses"]["NO_CANDIDATE_EVIDENCE"]==1
    assert decision(r,fmt,None,None)["primary_stage"]=="DATASET_PENDING"
    assert decision(r,None,None,None)["primary_stage"]=="FORMAT_PENDING"
    assert decision({**r,"bronze_status":"HOLD"},fmt,mp,None)["primary_stage"]=="BRONZE_BLOCKED"
    assert summarize([a,decision(r,None,None,None)])["cohort"]==2
    print("V3_UNIFIED_BOARD_SELFTEST_PASS")
def build():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    sources=[];all_rows=[];total=0
    for src in SOURCES:
        rows=read_baseline(api,quality,match,load_json,src);assert_cohort(rows,src)
        pick,maps=load_evidence(api,control,match,load_json,src,rows)
        workers=load_worker(api,control,match,load_json,src,rows)
        rec=[decision(row,pick(row),maps.get(row["source_id"]),workers.get(row["source_id"])) for row in rows]
        stats=summarize(rec)
        stats["source"]=src
        # G2/G3 remediation is a separate, SHA-guarded evidence lane.
        # Count new recovered headers without upgrading any dataset or schema cert.
        hf=match(api,control,"v097_G2G3_HEADER_CK_"+src+".json")
        hdone=load_json(api,hf["id"]).get("done",{}) if hf else {}
        idx={row["source_id"]:row for row in rows}
        if set(hdone)-set(idx):raise RuntimeError("HEADER_RECOVERY_ORPHAN_"+src)
        valid=[v for sid,v in hdone.items() if v.get("sha")==idx[sid]["source_sha256"]]
        stats["g2g3_native_remediation_checked"]=len(valid)
        stats["g2g3_native_headers_recovered"]=sum(v.get("header_members",0)>0 for v in valid)
        stats["g2g3_native_recovery_errors"]=sum(v.get("status") in ("READ_OR_PARSE_PENDING","SOURCE_SHA_MISMATCH","RAW_EMPTY_OR_SIZE_LIMIT") for v in valid)
        tf=match(api,control,"v097_G2G3_TYPED_AUDIT_CK_"+src+".json")
        tdone=load_json(api,tf["id"]).get("done",{}) if tf else {}
        if set(tdone)-set(idx):raise RuntimeError("G3_TYPED_ORPHAN_"+src)
        checked=[v for sid,v in tdone.items() if v.get("sha")==idx[sid]["source_sha256"]]
        stats["g3_typed_audit_checked"]=len(checked)
        stats["g3_typed_sample_pass_members"]=sum(
            1 for v in checked for m in v.get("members",[])
            if m.get("type_evidence",{}).get("status")=="TYPED_SAMPLE_PASS_NOT_FULL_VALIDATION")
        stats["g3_typed_sample_exception_members"]=sum(
            1 for v in checked for m in v.get("members",[])
            if m.get("type_evidence",{}).get("status")=="TYPED_SAMPLE_EXCEPTION")
        stats["g3_full_native_shape_candidate_members"]=sum(
            1 for v in checked for m in v.get("members",[])
            if m.get("full_native_shape",{}).get("status") in ("FULL_NATIVE_SHAPE_CANDIDATE_UNCERTIFIED","TDCC_FULL_NATIVE_LAYOUT_CANDIDATE_UNCERTIFIED"))
        stats["g3_full_native_shape_exception_members"]=sum(
            1 for v in checked for m in v.get("members",[])
            if m.get("full_native_shape",{}).get("status") in ("FULL_NATIVE_SHAPE_EXCEPTIONS","TDCC_NATIVE_NUMERIC_OR_METADATA_HOLD"))
        stats["g3_full_native_shape_rows_scanned"]=sum(
            (m.get("full_native_shape",{}).get("row_count") or m.get("full_native_shape",{}).get("data_rows") or 0) for v in checked for m in v.get("members",[])
            if m.get("full_native_shape",{}).get("full_file_scanned") is True or m.get("full_native_shape",{}).get("full_table_scanned") is True)

        # Keep a per-source drilldown, do not bloat the top-level Master.
        fn="v097_V3_UNIFIED_DETAIL_"+src+"_"+RUN+".json"
        stats["detail_file_id"]=put_once(api,quality,fn,
          {"schema":VERSION,"source":src,"run":RUN,"rows":rec})
        sources.append(stats);all_rows.extend(rec);total+=len(rows)
    if total!=TARGET or len({(r["source_id"]) for r in all_rows})!=TARGET:
        raise RuntimeError("UNIFIED_74750_COHORT_OR_UNIQUENESS_FAIL")
    summary=summarize(all_rows)
    summary["g2g3_native_remediation_checked"]=sum(t["g2g3_native_remediation_checked"] for t in sources)
    summary["g2g3_native_headers_recovered"]=sum(t["g2g3_native_headers_recovered"] for t in sources)
    summary["g2g3_native_recovery_errors"]=sum(t["g2g3_native_recovery_errors"] for t in sources)
    summary["g3_typed_audit_checked"]=sum(t["g3_typed_audit_checked"] for t in sources)
    summary["g3_typed_sample_pass_members"]=sum(t["g3_typed_sample_pass_members"] for t in sources)
    summary["g3_typed_sample_exception_members"]=sum(t["g3_typed_sample_exception_members"] for t in sources)
    summary["g3_full_native_shape_candidate_members"]=sum(t["g3_full_native_shape_candidate_members"] for t in sources)
    summary["g3_full_native_shape_exception_members"]=sum(t["g3_full_native_shape_exception_members"] for t in sources)
    summary["g3_full_native_shape_rows_scanned"]=sum(t["g3_full_native_shape_rows_scanned"] for t in sources)
    # Unit regression: genuine TDCC 16-row full-table candidates are included,
    # but never counted as G3 contract-verified or G4 Silver Schema Ready.
    if summary["g3_full_native_shape_candidate_members"] < 0:
        raise RuntimeError("NATIVE_CANDIDATE_COUNT_NEGATIVE")

    prior=match(api,control,"v097_G2G3_CONTRACT_MASTER_LATEST.json")
    census=load_json(api,prior["id"]) if prior else None
    contract_file=match(api,control,"v097_G2G3_FORMAL_MASTER_LATEST.json")
    contract_master=load_json(api,contract_file["id"]) if contract_file else None
    if contract_master:
        if contract_master.get("cohort")!=TARGET or len(contract_master.get("sources",[]))!=len(SOURCES):
            raise RuntimeError("FORMAL_CONTRACT_MASTER_COHORT_CONFLICT")
        contract_index={x["source"]:x for x in contract_master["sources"]}
        if set(contract_index)!=set(SOURCES):
            raise RuntimeError("FORMAL_CONTRACT_SOURCE_DUPLICATE_OR_MISSING")
        for x in sources:
            official=contract_index[x["source"]]
            if official["cohort"]!=x["cohort"]:
                raise RuntimeError("FORMAL_SOURCE_COHORT_CONFLICT_"+x["source"])
            x["formal_g2g3_contract_candidates"]=official["contracts"]
            x["formal_g2g3_current_blockers"]=official["blocker_counts"]
        summary["formal_g2g3_contract_specs"]=contract_master["dataset_era_contract_count"]
        summary["formal_g2g3_group_count"]=contract_master["group_count"]
        summary["formal_g2g3_blocker_count"]=sum(contract_master.get("blocker_totals",{}).values())
    board={"schema":VERSION,"run":RUN,"created_at":now(),
      "title":"JARVIS v0.97 唯一正式驗收進度總表（Bronze → Silver Schema Ready）",
      "cohort":TARGET,"overall":summary,"sources":sources,
      "g2g3_formal_contract_master":{"run":contract_master.get("run"),
        "report_id":contract_master.get("report_id"),
        "contract_specs":contract_master.get("dataset_era_contract_count"),
        "groups":contract_master.get("group_count"),
        "blocker_totals":contract_master.get("blocker_totals",{})} if contract_master else None,
      "g2g3_contract_census":{"run":census.get("run"),"groups":len(census.get("ranked_contract_groups",[])),
        "status_counts":census.get("overall_statuses",{}),"complete":census.get("complete_seven_source_census")} if census else None,
      "interpretation":{"legacy_format":"已分類證據，非 G3 合格",
          "legacy_mapping":"已檢查證據，非 G3 合格",
          "v3_scan":"新增檢查覆蓋，非 G4 放行",
          "main_progress":"以 G4 Silver Schema Ready 百分比作為正式通過率",
          "g3_full_native_shape":"全檔型別結構候選，仍欠官方契約與來源語意，不等於正式 G3 通過",
          "pending":"HOLD/PENDING 是待辦或例外，不代表原件損毀"},
      "silver_materialized":0,"gold_materialized":0,
      "release_guard":"NO_SILVER_GOLD_CONVERSION; G4_CERTIFICATION_NOT_AVAILABLE_WITH_CURRENT_CONTRACTS"}
    rid=put_once(api,quality,"v097_V3_UNIFIED_MASTER_"+RUN+".json",board)
    board["report_id"]=rid
    upsert(api,control,"v097_V3_UNIFIED_MASTER_LATEST.json",board)
    f=match(api,control,"v097_V3_UNIFIED_MASTER_LATEST.json")
    if not f or load_json(api,f["id"]).get("run")!=RUN:
        raise RuntimeError("UNIFIED_MASTER_LATEST_READBACK_FAILED")
    print("V3_UNIFIED_MASTER="+canonical({
      "run":RUN,"report_id":rid,"cohort":TARGET,
      "overall":summary,"sources":[{k:v for k,v in s.items() if k!="detail_file_id"} for s in sources],
      "silver_materialized":0,"gold_materialized":0}),flush=True)
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["build"]:build()
    else:raise SystemExit("selftest|build")
