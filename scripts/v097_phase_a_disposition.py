#!/usr/bin/env python3
"""JARVIS v0.97 Phase A integrated disposition gate.
Merge the original V3, V4 repair and V5 identity evidence into ONE per-file
immutable disposition ledger. Zero unsupported 'PASS' promotions. No raw edits.
"""
import os, json, re
from collections import Counter
from datetime import datetime, timezone
from scripts.v097_bronze_first_pipeline import service, common, match, load_json, put_once
from scripts.v097_bronze_first_batch_v3 import ck_name
RUN=os.getenv("GITHUB_RUN_ID","manual")
V4_RUN="43156776265"
V5_RUN="43157865636"
EXPECTED=6358
def now():return datetime.now(timezone.utc).isoformat()
TDCC_FILE=re.compile(r"(?:distribution|tdcc)[_-]\d{8}[_-]([A-Za-z0-9]{4,6})_",re.I)
TDCC_CODE=re.compile(r"^[0-9]{4}[A-Z0-9]{0,2}$")
def evaluate(v4):
    cat=v4["category"]
    status=v4["status"]
    if status in ("REPAIR_QA_PASS","REPAIR_ALREADY_VERIFIED"):
        return "REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING","CONTENT_QA_AND_DATASET_COVERAGE_GATE"
    if cat=="CONTROL_METADATA":
        return "EXCLUDED_FROM_MARKET_RAW","KEEP_CONTROL_SIDECAR_AS_IMMUTABLE_EVIDENCE"
    if cat=="TDCC_IDENTITY":
        m=TDCC_FILE.search(str(v4.get("source_path") or ""))
        if not m or not TDCC_CODE.fullmatch(m.group(1).upper()):
            return "QUARANTINE_TDCC_CODE_FORMAT","NOT_ELIGIBLE_FOR_MARKET_RAW_UNTIL_OFFICIAL_SOURCE_PROOF"
        return "HOLD_HISTORICAL_MARKET_IDENTITY","VERIFY_SOURCE_HTML_AND_HISTORICAL_TSE_OTC_INSTRUMENT_MASTER"
    return "BLOCKED_EXCEPTION","SOURCE_ORIGINAL_CONTENT_OR_ADAPTER_REVIEW"
def build(api):
    _,c,q,_=common(api)
    allrows=[]
    orig_counter=Counter()
    for lane in range(6):
        receipt=match(api,q,"v097_BF_REPAIR_V4_%s_L%02d.json"%(V4_RUN,lane))
        v3=match(api,c,ck_name("COPY",lane))
        if not receipt or not v3:raise RuntimeError("MISSING_V4_OR_V3_LANE_%d"%lane)
        rs=load_json(api,receipt["id"])["rows"]
        snapshot=load_json(api,v3["id"])["done"]
        original={fid:r for fid,r in snapshot.items() if r.get("state")=="COPY_EXCEPTION"}
        if len(rs)!=len(original):raise RuntimeError("LANE_COUNT_NOT_MATCH_%d"%lane)
        seen=set()
        for v in rs:
            fid=v["file_id"]
            if fid in seen or fid not in original:raise RuntimeError("REPAIR_EVIDENCE_ORPHAN_%d"%lane)
            seen.add(fid)
            state,action=evaluate(v)
            if state=="REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING" and not v.get("repaired_destination_id"):
                raise RuntimeError("UNPROVEN_REPAIR_SUCCESS")
            allrows.append({"asset_id":fid,"lane":lane,"original_v3_error":original[fid].get("error"),
              "source_path":original[fid].get("source_path"),
              "category":v["category"],"v4_status":v["status"],
              "phase_a_state":state,"next_action":action,
              "source_sha":original[fid].get("sha"),
              "repaired_destination_id":v.get("repaired_destination_id"),
              "v3_receipt_run":V4_RUN,"v5_identity_run":V5_RUN})
            orig_counter[state]+=1
    v5=match(api,q,"v097_TDCC_V5_SUMMARY_%s.json"%V5_RUN)
    if not v5:raise RuntimeError("MISSING_V5_IDENTITY_EVIDENCE")
    obs=load_json(api,v5["id"])
    if obs["frozen_v3_exceptions_total"]!=EXPECTED or len(allrows)!=EXPECTED:
        raise RuntimeError("DISPOSITION_TOTAL_MISMATCH")
    if orig_counter["REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING"]!=7:
        raise RuntimeError("KNOWN_REPAIRS_COUNT_MISMATCH")
    if orig_counter["EXCLUDED_FROM_MARKET_RAW"]!=1314:
        raise RuntimeError("CONTROL_COUNT_MISMATCH")
    if (orig_counter["HOLD_HISTORICAL_MARKET_IDENTITY"] + orig_counter["QUARANTINE_TDCC_CODE_FORMAT"])!=5035:
        raise RuntimeError("TDCC_COUNT_MISMATCH")
    if orig_counter["BLOCKED_EXCEPTION"]!=2:
        raise RuntimeError("BLOCKED_COUNT_MISMATCH")
    # Immutable evidence: no modification of legacy snapshots or v0.97 original V3 checkpoints.
    totals={"schema":"v097_phase_a_disposition_1","run":RUN,"at":now(),
      "source_runs":{"v3":"43152577099","v4":V4_RUN,"v5":V5_RUN},
      "original_exception_count":EXPECTED,"unique_file_ids":len({r["asset_id"] for r in allrows}),
      "by_disposition":dict(orig_counter),
      "validated_repaired_sha_only":7,
      "control_metadata_not_market_raw":1314,
      "tdcc_pending_historical_instrument_master":orig_counter["HOLD_HISTORICAL_MARKET_IDENTITY"],
      "tdcc_code_format_quarantined":orig_counter["QUARANTINE_TDCC_CODE_FORMAT"],
      "other_remaining_review":2,
      "phase_a_complete":False,
      "all_093_original_unchanged":True,"v3_checkpoints_unchanged":True,
      "official_downloads":0,
      "source_calendar_certified":False,"bronze_semantics_certified":False,
      "next":"Resolve TDCC historical market universe using provider-backed security master; run per-file content QA and promoted-version independent SHA; resolve two non-TDCC exceptions.",
      "note":"Complete A exception accounting, not proof of full phase A repair. A cannot pass until historical TSE/OTC identity is verified."}
    put_once(api,q,"v097_PHASE_A_DISPOSITION_ROWS_%s.json"%RUN,
             {"schema":"v097_phase_a_disposition_rows_1","run":RUN,"rows":allrows})
    put_once(api,q,"v097_PHASE_A_DISPOSITION_SUMMARY_%s.json"%RUN,totals)
    print("PHASE_A="+json.dumps(totals,ensure_ascii=False),flush=True)
def selftest():
    assert evaluate({"category":"CONTROL_METADATA","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW"})[0]=="EXCLUDED_FROM_MARKET_RAW"
    assert evaluate({"category":"TDCC_IDENTITY","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW","source_path":"2025/TDCC/2025-11/distribution_20251107_YJR4_hash.html"})[0]=="QUARANTINE_TDCC_CODE_FORMAT"
    assert evaluate({"category":"TDCC_IDENTITY","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW","source_path":"2025/TDCC/2025-11/distribution_20251107_2330A_hash.html"})[0]=="HOLD_HISTORICAL_MARKET_IDENTITY"
    assert evaluate({"category":"TRANSIENT_RETRY","status":"REPAIR_QA_PASS"})[0]=="REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING"
    print("PHASE_A_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("PHASE_A_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="aggregate":build(service())
    else:raise SystemExit("BAD_MODE")
