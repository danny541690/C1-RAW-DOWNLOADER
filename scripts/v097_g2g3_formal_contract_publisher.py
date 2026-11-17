#!/usr/bin/env python3
"""Publish source-isolated versioned G2/G3 contract catalog and actionable blocker ledger.

Reads the latest complete frozen-cohort contract census (all 74750 source IDs)
and official-format reference registry. Does not claim verified contracts without
file-specific official native source attestations. Publishes only immutable QA
reports + the control LATEST index; never Bronze/Silver/Gold.
"""
import collections,datetime,os,sys
from scripts.v097_v3_preflight import SOURCES,TARGET,source_api,canonical
from scripts.v097_g2g3_formal_contracts_v2 import VERSION,contract,catalog,review
RUN=os.environ.get("GITHUB_RUN_ID","manual")
R_VERSION="v097_g2g3_formal_contract_publication_r2_3day_root_causes"
def source(src):
    if src not in SOURCES:raise ValueError("UNKNOWN_SOURCE")
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    f=match(api,control,"v097_G2G3_CONTRACT_MASTER_LATEST.json")
    if not f:raise RuntimeError("NO_COMPLETE_G2G3_CENSUS")
    census=load_json(api,f["id"])
    if census.get("cohort")!=TARGET or not census.get("complete_seven_source_census"):
        raise RuntimeError("CENSUS_NOT_COMPLETE_OR_FROZEN_COHORT_MISMATCH")
    subset=[g for g in census.get("ranked_contract_groups",[]) if g.get("source")==src]
    contracts=[q for q in catalog() if q["source"]==src]
    has={(c["dataset"],c["historical_era"]):c for c in contracts}
    evaluated=[];counts=collections.Counter()
    for g in subset:
        dataset=g.get("dataset_candidate")
        era=g.get("era")
        key=(dataset,era)
        desc=has.get(key)
        # Missing native headers are *not* all missing Dataset identities.
        # Reuse the source-specific root cause from the certified frozen cohort
        # census instead of lumping 50k HTML/ZIPs into a generic identity HOLD.
        reasons=g.get("status_counts",{})
        cause=next(iter(reasons)) if len(reasons)==1 else None
        if g.get("group_kind")=="DISCOVERY_BUCKET_NO_HEADER_NOT_CERTIFIABLE":
            status={
                "HTML_NATIVE_TABLE_OR_METADATA_PENDING":"HTML_NATIVE_HEADER_OR_BODY_METADATA_PENDING",
                "ZIP_MEMBER_DATASET_HEADER_PENDING":"ZIP_MEMBER_SCHEMA_AND_SOURCE_MANIFEST_PENDING",
                "WORKBOOK_SHEET_CELL_LAYOUT_PENDING":"XLSX_OR_XLS_NATIVE_SHEET_LAYOUT_PENDING",
                "PROVENANCE_RECEIPT_NOT_NUMERIC_DATASET":"PROVENANCE_ONLY_EXCLUDE_FROM_NUMERIC_READY",
                "NATIVE_HEADER_OR_DATASET_IDENTITY_PENDING":"NATIVE_FIELD_IDENTITY_OR_HEADER_PENDING"
            }.get(cause,"NO_NATIVE_HEADER_UNCERTIFIABLE")
        elif not desc:
            status="DATASET_ERA_MISSING_OR_NOT_IDENTIFIED"
        elif desc["field_spec_state"]=="MISSING_DATASET_FIELD_SPEC":
            status="REQUIRED_FIELD_CONTRACT_UNSPECIFIED"
        elif not desc["candidate_primary_key"]:
            status="NATIVE_PRIMARY_KEY_SPEC_UNDEFINED"
        else:
            status="OFFICIAL_DATASET_ERA_AND_FULL_FILE_PROOF_PENDING"
        counts[status]+=g["files"]
        evaluated.append({"group_key":g["group_key"],"dataset_candidate":dataset,
            "era":era,"group_kind":g.get("group_kind"),"files":g["files"],
            "status":status,"source_signature":g.get("signature"),
            "source_examples":g.get("examples",[]),
            "required_native_fields":list(desc.get("required_fields",{})) if desc else [],
            "candidate_primary_key":desc.get("candidate_primary_key",[]) if desc else [],
            "official_source_ref_candidates":desc.get("official_source_reference_candidates",[]) if desc else [],
            "missing_proof_requirements":(desc.get("g2_proof_requirements",[])+desc.get("g3_proof_requirements",[])) if desc else [],
            "g2_verified":False,"g3_verified":False,"silver_schema_ready":False})
    n=sum(v["files"] for v in evaluated)
    expected=next((x["cohort"] for x in census["sources"] if x["source"]==src),None)
    if expected is None or expected!=n or sum(counts.values())!=expected:
        raise RuntimeError("SOURCE_CENSUS_GROUP_COUNT_DRIFT_"+src)
    doc={"schema":R_VERSION,"contract_version":VERSION,"source":src,"run":RUN,
        "census_run":census.get("run"),"cohort":n,"contracts":contracts,
        "source_groups":evaluated,"blocker_counts":dict(counts),
        "g2_verified":0,"g3_verified":0,"silver_schema_ready":0,
        "silver_gold_materialized":False}
    rid=put_once(api,quality,"v097_G2G3_FORMAL_SOURCE_"+src+"_"+RUN+".json",doc)
    print("G2G3_FORMAL_SOURCE="+canonical({"source":src,"run":RUN,"report_id":rid,
        "cohort":n,"groups":len(subset),"contract_specs":len(contracts),
        "blocker_counts":dict(counts)}),flush=True)
def final():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    docs=[];total=0;blocks=collections.Counter()
    for src in SOURCES:
        file=match(api,quality,"v097_G2G3_FORMAL_SOURCE_"+src+"_"+RUN+".json")
        if not file:raise RuntimeError("SOURCE_NOT_PUBLISHED_"+src)
        d=load_json(api,file["id"])
        if d.get("source")!=src or d.get("run")!=RUN or d.get("contract_version")!=VERSION:
            raise RuntimeError("SOURCE_CONTRACT_VERSION_CONFLICT_"+src)
        docs.append({"source":src,"cohort":d["cohort"],"report_id":file["id"],
            "groups":len(d["source_groups"]),"contracts":len(d["contracts"]),
            "blocker_counts":d["blocker_counts"],"g2_verified":0,"g3_verified":0})
        blocks.update(d["blocker_counts"]);total+=d["cohort"]
    if total!=TARGET or sum(blocks.values())!=TARGET:
        raise RuntimeError("FORMAL_SOURCE_COUNT_NOT_74750")
    report={"schema":R_VERSION,"contract_version":VERSION,
        "run":RUN,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "cohort":TARGET,"sources":docs,"blocker_totals":dict(blocks),
        "dataset_era_contract_count":sum(d["contracts"] for d in docs),
        "group_count":sum(d["groups"] for d in docs),
        "g2_verified":0,"g3_verified":0,"silver_schema_ready":0,
        "policy":"CANDIDATE_ONLY_UNTIL_OFFICIAL_FILE_SPEC_AND_FULL_NATIVE_ATTESTATION; NO_SILVER_GOLD"}
    rid=put_once(api,quality,"v097_G2G3_FORMAL_MASTER_"+RUN+".json",report)
    upsert(api,control,"v097_G2G3_FORMAL_MASTER_LATEST.json",{**report,"report_id":rid})
    probe=match(api,control,"v097_G2G3_FORMAL_MASTER_LATEST.json")
    if not probe or load_json(api,probe["id"]).get("run")!=RUN:raise RuntimeError("MASTER_READBACK_FAILED")
    print("G2G3_FORMAL_MASTER="+canonical({"run":RUN,"report_id":rid,
        "cohort":TARGET,"contract_specs":report["dataset_era_contract_count"],
        "groups":report["group_count"],"blockers":dict(blocks),
        "sources":docs,"g2_verified":0,"g3_verified":0,"ready":0}),flush=True)
def selftest():
    c=catalog()
    assert len(c)>40 and {x["source"] for x in c}==set(SOURCES)
    assert all(x["promotion_state"]=="NOT_CERTIFIED" for x in c)
    assert {"HTML_NATIVE_HEADER_OR_BODY_METADATA_PENDING",
            "ZIP_MEMBER_SCHEMA_AND_SOURCE_MANIFEST_PENDING"} <= {
            "HTML_NATIVE_HEADER_OR_BODY_METADATA_PENDING",
            "ZIP_MEMBER_SCHEMA_AND_SOURCE_MANIFEST_PENDING"}

    print("G2G3_FORMAL_PUBLICATION_SELFTEST_PASS",len(c))
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["final"]:final()
    elif len(sys.argv)==3 and sys.argv[1]=="source":source(sys.argv[2])
    else:raise SystemExit("selftest|source SRC|final")
