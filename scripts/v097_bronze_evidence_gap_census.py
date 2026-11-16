#!/usr/bin/env python3
"""JARVIS v0.97: strict Bronze-only evidence gap census by frozen source ID.

Read current immutable release and independent D/preflight checkpoints.
A QA success or an official documentation page is not full-file PIT proof.
No Bronze/raw write, no Silver/Gold, no automatic READY promotion.
"""
import json,os,sys,hashlib
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,READY,source_api
from scripts.v097_seven_parser_triage import latest_complete
from scripts.v097_fullfile_pit_release_preflight import full_proof,VERSION as PREFLIGHT_VERSION

VERSION="v097_bronze_release_evidence_gap_census_v1"
def classify(row,formal,native,d,e,preflight):
    if formal["status"]==READY:return "READY_ALREADY_FORMAL"
    if not native:return "P0_MISSING_SOURCE_NATIVE_V2"
    if native.get("bronze_sha256")!=row["sha"] or not native.get("input_bytes_sha_checked"):
        return "P0_ORIGINAL_SHA_OR_BYTES_UNVERIFIED"
    if str(native.get("status","")).startswith(("HOLD_","RETRY_")):
        return "P0_HISTORICAL_FORMAT_OR_IDENTITY_HOLD"
    if not isinstance(e,dict):return "P1_MISSING_FULL_FILE_INDEPENDENT_ATTESTATION"
    if not d or d.get("status")!="D_CANDIDATE_FULL_THREE_WAY_ATTESTED":
        return "P1_D_GATE_INDEPENDENT_NUMERIC_OR_PIT_HOLD"
    status=full_proof(row["source"],row,formal,native,d,e)
    if status=="CANDIDATE_COMPLETE_EVIDENCE_REQUIRES_SIGNED_RELEASE":
        return "P0_SIGNED_RELEASE_REVIEW_REQUIRED"
    return "P1_"+status
def report_source(src,rows,formal,native,d,e,preflight):
    byid={x["source_id"]:x for x in formal}
    if len(byid)!=len(rows) or set(byid)!={x["source_id"] for x in rows}:
        raise RuntimeError("FROZEN_COHORT_FORMAL_SOURCE_ID_CONFLICT_"+src)
    if set(e)-set(byid):raise RuntimeError("EVIDENCE_ORPHANS_"+src)
    counts=Counter();samples={};no_attestation=0;pending_signed=[]
    for original in rows:
        row={**original,"source":src}
        sid=row["source_id"]
        stage=classify(row,byid[sid],native.get(sid),d.get(sid),e.get(sid),preflight.get(sid))
        counts[stage]+=1
        if len(samples.setdefault(stage,[]))<5:
            samples[stage].append({"source_id":sid,"original_sha256":row["sha"],"current_formal_status":byid[sid]["status"]})
        if stage=="P1_MISSING_FULL_FILE_INDEPENDENT_ATTESTATION":no_attestation+=1
        if stage=="P0_SIGNED_RELEASE_REVIEW_REQUIRED":pending_signed.append(sid)
    return {"total":len(rows),"formal_ready":counts["READY_ALREADY_FORMAL"],
      "formal_hold":len(rows)-counts["READY_ALREADY_FORMAL"],
      "full_file_attestation_records":len(e),"missing_attestation_on_hold":no_attestation,
      "reason_counts":dict(counts),"sample_ids_by_reason":samples,
      "candidate_signed_review_ids":pending_signed,
      "no_auto_promotion":True}
def selftest():
    r={"source_id":"a","sha":"a"*64,"source":"TWSE"}
    hold={"status":"HOLD"}
    assert classify(r,hold,None,None,None,None)=="P0_MISSING_SOURCE_NATIVE_V2"
    assert classify(r,hold,{"bronze_sha256":"b"*64},None,None,None)=="P0_ORIGINAL_SHA_OR_BYTES_UNVERIFIED"
    n={"bronze_sha256":r["sha"],"input_bytes_sha_checked":True,"status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"}
    assert classify(r,hold,n,None,None,None)=="P1_MISSING_FULL_FILE_INDEPENDENT_ATTESTATION"
    assert classify(r,{"status":READY},None,None,None,None)=="READY_ALREADY_FORMAL"
    assert set(SOURCES)=={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC","FinMind"}
    print("BRONZE_EVIDENCE_GAP_CENSUS_SELFTEST_PASS")
def run():
    api,control,quality,match,load_json,put_once,*_=source_api()
    release_run,formal=latest_complete(api,quality,match,load_json)
    totals=Counter();results={}
    for src in SOURCES:
        inp=match(api,quality,"v097_AP_INPUT_"+src+".json")
        if not inp:raise RuntimeError("MISSING_FROZEN_INPUT_"+src)
        rows=load_json(api,inp["id"])["rows"]
        def get_done(prefix):
            f=match(api,control,prefix+src+".json")
            return load_json(api,f["id"]).get("done",{}) if f else {}
        native=get_done("v097_SEVEN_FORMAT_V2_CK_")
        d=get_done("v097_D_THREE_WAY_GATE_CK_")
        preflight=get_done("v097_FULLFILE_PIT_RELEASE_CK_")
        ef=match(api,quality,"v097_INDEPENDENT_TRIPLE_NUMERIC_EVIDENCE_"+src+".json")
        att=load_json(api,ef["id"]).get("by_source_id",{}) if ef else {}
        result=report_source(src,rows,formal[src]["records"],native,d,att,preflight)
        results[src]=result;totals.update(result["reason_counts"])
    if sum(x["total"] for x in results.values())!=74750:
        raise RuntimeError("FROZEN_74750_COUNT_CHANGED")
    report={"schema":VERSION,"run":os.getenv("GITHUB_RUN_ID","manual"),
      "created_utc":datetime.now(timezone.utc).isoformat(),
      "formal_reference_run":release_run,"by_source":results,
      "overall_reasons":dict(totals),
      "formal_ready":totals["READY_ALREADY_FORMAL"],
      "formal_hold":74750-totals["READY_ALREADY_FORMAL"],
      "silver_gold_executed":False,"formal_release_mutated":False,
      "rule":"Only independently verified full-file, all-field, point-in-time proof can advance a new signed release"}
    if report["run"]!="manual":
        put_once(api,quality,"v097_BRONZE_EVIDENCE_GAP_CENSUS_"+report["run"]+".json",report)
    print("BRONZE_EVIDENCE_GAP_CENSUS="+json.dumps({
      "run":report["run"],"formal_reference_run":release_run,
      "formal_ready":report["formal_ready"],"formal_hold":report["formal_hold"],
      "overall_reasons":report["overall_reasons"],
      "by_source":{s:{"hold":x["formal_hold"],"attested_records":x["full_file_attestation_records"],
      "missing_attestation_on_hold":x["missing_attestation_on_hold"],
      "reasons":x["reason_counts"]} for s,x in results.items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif not sys.argv[1:]:run()
    else:raise SystemExit("usage: selftest | run")
