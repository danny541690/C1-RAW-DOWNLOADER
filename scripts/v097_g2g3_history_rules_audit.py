#!/usr/bin/env python3
"""Read-only reconciliation of 11/14-11/17 G2/G3 error-history evidence and current QA.
Only publishes quality reports, never mutates Bronze or creates Silver/Gold.
"""
import collections,os,sys
from datetime import datetime,timezone
from scripts.v097_v3_preflight import SOURCES,TARGET,read_baseline,assert_cohort,source_api,canonical
from scripts.v097_g2g3_native_headers import HEADER_PREFIX,VERSION as HEADER_VERSION
from scripts.v097_g2g3_typed_contract_audit import CHECKPOINT,VERSION as TYPED_VERSION
VERSION="v097_g2g3_cross_stage_history_audit_r1"
RUN=os.environ.get("GITHUB_RUN_ID","manual")
HISTORIC_EXCEPTIONS={
 "TWSE":["ZIP_MEMBER_MANIFEST_ORIGIN_PENDING","2024_07_15_JSON_OFFICIAL_PIT_PENDING"],
 "TPEx":["DATE_PARTITION_CONFLICT_2024_09_10_VS_2026_10_16",
         "RAW_RECEIPT_IS_NOT_STOCK_QUOTE","ZIP_DATASET_IDENTITY_PENDING"],
 "MOPS":["GAAP_IFRS_XBRL_IXBRL_ERA_AND_PIT_PENDING"],
 "TDCC":["5035_SPECIAL_SECURITY_PIT_CLASS_PENDING","TWO_ZIP_429_SHARE_COUNT_AND_20_PERCENT_MISMATCH_HOLD",
         "HTML_HEADER_DISTRIBUTION_QA_PENDING"],
 "TAIFEX":["CSV_TRAILING_EMPTY_VS_SHIFTED_WIDTH","NIGHT_SESSION_TRADING_DATE"],
 "NDC":["ONE_UNDOCUMENTED_XLSX_CELL_GAP_NOT_ZERO"],
 "FinMind":["DATE_PARTITION_CONFLICT","SOURCE_PIT_AND_DATASET_VERSION_PENDING"]
}
def summary_records(source,baseline,records,expected_schema,kind):
    allowed={r["source_id"]:r["source_sha256"] for r in baseline}
    if set(records)-set(allowed):raise RuntimeError(kind+"_ORPHAN_"+source)
    mismatch=sum(1 for sid,r in records.items() if r.get("sha")!=allowed[sid])
    if mismatch:raise RuntimeError(kind+"_SOURCE_SHA_MISMATCH_"+source)
    counts=collections.Counter(r.get("status","UNSPECIFIED") for r in records.values())
    return {"count":len(records),"statuses":dict(counts),"source_sha_conflicts":mismatch,
            "missing_from_cohort":len(baseline)-len(records)}
def selftest():
    assert sum([12071,13200,1935,40384,3140,320,3700])==TARGET
    assert set(HISTORIC_EXCEPTIONS)==set(SOURCES)
    assert "TWO_ZIP_429_SHARE_COUNT_AND_20_PERCENT_MISMATCH_HOLD" in HISTORIC_EXCEPTIONS["TDCC"]
    assert "ONE_UNDOCUMENTED_XLSX_CELL_GAP_NOT_ZERO" in HISTORIC_EXCEPTIONS["NDC"]
    print("G2G3_HISTORY_CROSS_STAGE_AUDIT_SELFTEST_PASS")
def build():
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    overall=collections.Counter();entries=[];count=0
    f=match(api,control,"v097_V3_UNIFIED_MASTER_LATEST.json")
    if not f:raise RuntimeError("UNIFIED_MASTER_LATEST_MISSING")
    unified=load_json(api,f["id"])
    if unified.get("cohort")!=TARGET or unified.get("overall",{}).get("g4_silver_schema_ready_certified",0)!=0:
        raise RuntimeError("UNIFIED_COHORT_OR_RELEASE_POLICY_CONFLICT")
    for source in SOURCES:
        rows=read_baseline(api,quality,match,load_json,source);assert_cohort(rows,source)
        count+=len(rows)
        d={"source":source,"cohort":len(rows),
            "historical_exception_categories_requiring_independent_evidence":HISTORIC_EXCEPTIONS[source]}
        for key,name,version in (("native_headers",HEADER_PREFIX+source+".json",HEADER_VERSION),
                                 ("typed_audit",CHECKPOINT+source+".json",TYPED_VERSION)):
            file=match(api,control,name)
            if not file:
                d[key]={"count":0,"statuses":{},"missing_from_cohort":len(rows),"checkpoint_missing":True}
                continue
            ck=load_json(api,file["id"])
            if ck.get("schema")!=version:raise RuntimeError("CHECKPOINT_VERSION_CONFLICT_"+key+"_"+source)
            records=ck.get("done",{})
            summary=summary_records(source,rows,records,version,key)
            if key=="typed_audit":
                full_status=collections.Counter();rowcount=0
                for v in records.values():
                    for m in v.get("members",[]):
                        obj=m.get("full_native_shape",{})
                        full_status[obj.get("status","NOT_RECORDED")]+=1
                        if obj.get("full_file_scanned"):rowcount+=obj.get("row_count",0)
                summary["full_native_shape_states"]=dict(full_status)
                summary["full_file_rows_scanned"]=rowcount
            d[key]=summary
            overall[key+"_records"]+=len(records)
        entries.append(d)
    if count!=TARGET:raise RuntimeError("TOTAL_COHORT_DRIFT")
    report={"schema":VERSION,"run":RUN,"created_at":datetime.now(timezone.utc).isoformat(),
      "frozen_cohort":TARGET,"unified_master_run":unified.get("run"),
      "g2_verified":unified.get("overall",{}).get("g2_dataset_contract_verified",0),
      "g3_verified":unified.get("overall",{}).get("g3_schema_contract_verified",0),
      "g4_ready":unified.get("overall",{}).get("g4_silver_schema_ready_certified",0),
      "seven_sources":entries,"totals":dict(overall),
      "evidence_state":"CANDIDATE_AND_STRUCTURAL_QA_ONLY",
      "historical_source_docs":[
        "https://docs.google.com/document/d/1WxGqN5d_PZnZbquDLLfvnGIFCrysiDuOZZgeDlTimVA/edit",
        "https://docs.google.com/document/d/1pqunt5SJedVyePk0OFjeHJO90BmUmSuYa2d_-ppJZIg/edit",
        "https://docs.google.com/document/d/1xVy7DkoDOIXLTORIMqF7FJBQN24OHiPk9biQbACazZY/edit"],
      "policy":"NEVER_PROMOTE_FROM_HEADER_OR_SAMPLE_ONLY; NO_BRONZE_SILVER_GOLD_WRITE"}
    fid=put_once(api,quality,"v097_G2G3_HISTORY_RULES_AUDIT_"+RUN+".json",report)
    report["report_id"]=fid
    upsert(api,control,"v097_G2G3_HISTORY_RULES_AUDIT_LATEST.json",report)
    verify=match(api,control,"v097_G2G3_HISTORY_RULES_AUDIT_LATEST.json")
    if not verify or load_json(api,verify["id"]).get("run")!=RUN:
        raise RuntimeError("AUDIT_REPORT_READBACK_FAILED")
    print("G2G3_HISTORY_AUDIT="+canonical({
        "run":RUN,"report_id":fid,"cohort":count,"totals":dict(overall),
        "sources":[{"source":r["source"],"header_checked":r["native_headers"]["count"],
          "typed_checked":r["typed_audit"]["count"],
          "full_native_shape_states":r["typed_audit"].get("full_native_shape_states",{})} for r in entries],
        "g2_verified":report["g2_verified"],"g3_verified":report["g3_verified"],
        "g4_ready":report["g4_ready"]}),flush=True)
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["build"]:build()
    else:raise SystemExit("selftest|build")
