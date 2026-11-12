#!/usr/bin/env python3
"""JARVIS v0.97 Phase A integrated disposition gate.
Merge the original V3, V4 repair and V5 identity evidence into ONE per-file
immutable disposition ledger. Zero unsupported 'PASS' promotions. No raw edits.
"""
import os, json, re, hashlib
from collections import Counter
from datetime import datetime, timezone
from scripts.v097_bronze_first_pipeline import service, common, match, load_json, put_once, call
from scripts.v097_bronze_content_qa import qa_bytes
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
    if "SOURCE_ROOT_NOT_BOOTSTRAPPED:TDCC_ARCHIVE" in str(v4.get("prior_error") or ""):
        return "ARCHIVE_EVIDENCE_ONLY","INSPECT_ARCHIVE_MEMBERS_AND_SOURCE_PROVENANCE_BEFORE_MARKET_DATA_PROMOTION"
    if cat=="TDCC_IDENTITY":
        m=TDCC_FILE.search(str(v4.get("source_path") or ""))
        if not m or not TDCC_CODE.fullmatch(m.group(1).upper()):
            return "QUARANTINE_TDCC_CODE_FORMAT","NOT_ELIGIBLE_FOR_MARKET_RAW_UNTIL_OFFICIAL_SOURCE_PROOF"
        return "HOLD_HISTORICAL_MARKET_IDENTITY","VERIFY_SOURCE_HTML_AND_HISTORICAL_TSE_OTC_INSTRUMENT_MASTER"
    return "BLOCKED_EXCEPTION","SOURCE_ORIGINAL_CONTENT_OR_ADAPTER_REVIEW"
def verify_targeted_bytes(api, rows):
    """Bounded original/destination byte QA. Never promote or mutate market raw."""
    max_bytes=40*1024*1024
    reports=[]
    for row in rows:
        if row["phase_a_state"] not in ("REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING","ARCHIVE_EVIDENCE_ONLY"):
            continue
        rec={"asset_id":row["asset_id"],"prior_state":row["phase_a_state"],
             "checked_at":now(),"certified_market_raw":False,"status":"REVIEW_PENDING"}
        try:
            fid=row["asset_id"]
            meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
            if int(meta.get("size") or 0)>max_bytes:raise ValueError("SOURCE_EXCEEDS_40MB_BOUND")
            blob=call(lambda:api.files().get_media(fileId=fid))
            if not blob or len(blob)>max_bytes:raise ValueError("SOURCE_BYTES_EMPTY_OR_OVERSIZE")
            sha=hashlib.sha256(blob).hexdigest()
            rec.update(source_sha256=sha,source_size=len(blob))
            expected=row.get("source_sha")
            if expected and re.fullmatch(r"[0-9a-fA-F]{64}",str(expected)) and sha.lower()!=expected.lower():
                raise ValueError("SOURCE_SHA_CHANGED")
            if meta.get("md5Checksum") and hashlib.md5(blob).hexdigest()!=meta["md5Checksum"]:
                raise ValueError("SOURCE_MD5_CHANGED")
            filename=str(meta.get("name") or "").lower()
            qa_row={"file_id":fid,"file_name":meta.get("name") or "unknown",
                "path":row.get("source_path") or "","source":"TDCC" if "TDCC" in str(row.get("source_path") or "").upper() else "UNKNOWN",
                "year":"","month":""}
            structural=qa_bytes(qa_row,blob)
            rec.update(source_structural_status=structural["status"],source_kind=structural.get("kind"))
            if row["phase_a_state"]=="ARCHIVE_EVIDENCE_ONLY":
                rec["status"]="ARCHIVE_STRUCTURE_REVIEW" if structural.get("kind")=="ZIP" else "ARCHIVE_FORMAT_REVIEW"
                rec["archive_members"]=structural.get("zip_members")
                rec["archive_member_extensions"]=structural.get("member_extensions")
            else:
                dest=row.get("repaired_destination_id")
                if not dest:raise ValueError("MISSING_REPAIR_DESTINATION")
                dmeta=call(lambda:api.files().get(fileId=dest,fields="id,name,size,md5Checksum"))
                if int(dmeta.get("size") or 0)>max_bytes:raise ValueError("DESTINATION_EXCEEDS_40MB_BOUND")
                dest_blob=call(lambda:api.files().get_media(fileId=dest))
                dest_sha=hashlib.sha256(dest_blob).hexdigest()
                rec["destination_sha256"]=dest_sha
                rec["destination_size"]=len(dest_blob)
                rec["source_destination_sha_match"]=sha==dest_sha and len(blob)==len(dest_blob)
                if not rec["source_destination_sha_match"]:raise ValueError("DESTINATION_CONTENT_MISMATCH")
                rec["status"]="BYTE_MATCH_SEMANTIC_PENDING"
        except Exception as ex:
            rec["status"]="QA_BLOCKED"
            rec["reason"]=type(ex).__name__+":"+str(ex)[:160]
        reports.append(rec)
    if len(reports)!=9:raise RuntimeError("TARGETED_QA_EXPECTED_9")
    return reports

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
    if orig_counter["ARCHIVE_EVIDENCE_ONLY"]!=2 or orig_counter["BLOCKED_EXCEPTION"]:
        raise RuntimeError("TDCC_ARCHIVE_COUNT_MISMATCH")
    # Bounded diagnostic: describe TDCC filename code shapes without making any identity claim.
    tdcc_shapes=Counter()
    tdcc_samples={}
    for r in allrows:
        if r["category"]!="TDCC_IDENTITY":continue
        p=str(r.get("source_path") or "")
        m=TDCC_FILE.search(p)
        if not m: shape="NO_RECOGNIZED_FILENAME_CODE"
        else:
            code=m.group(1).upper()
            if code.isdigit(): shape="DIGITS_ONLY"
            elif code[:4].isdigit() and any(c.isalpha() for c in code[4:]): shape="NUMERIC_PREFIX_ALPHA_SUFFIX"
            elif any(c.isalpha() for c in code): shape="MIXED_OR_ALPHA_CODE"
            else: shape="OTHER_CODE_SHAPE"
        tdcc_shapes[shape]+=1
        if shape not in tdcc_samples:tdcc_samples[shape]=p.rsplit("/",1)[-1][:120]
    if sum(tdcc_shapes.values())!=5035:raise RuntimeError("TDCC_DIAGNOSTIC_COUNT_MISMATCH")
    # Immutable evidence: no modification of legacy snapshots or v0.97 original V3 checkpoints.
    totals={"schema":"v097_phase_a_disposition_1","run":RUN,"at":now(),
      "source_runs":{"v3":"43152577099","v4":V4_RUN,"v5":V5_RUN},
      "original_exception_count":EXPECTED,"unique_file_ids":len({r["asset_id"] for r in allrows}),
      "by_disposition":dict(orig_counter),
      "tdcc_filename_shape_counts":dict(tdcc_shapes),
      "tdcc_filename_shape_examples":tdcc_samples,
      "validated_repaired_sha_only":7,
      "control_metadata_not_market_raw":1314,
      "tdcc_pending_historical_instrument_master":orig_counter["HOLD_HISTORICAL_MARKET_IDENTITY"],
      "tdcc_code_format_quarantined":orig_counter["QUARANTINE_TDCC_CODE_FORMAT"],
      "tdcc_archive_pending_member_and_source_review":orig_counter["ARCHIVE_EVIDENCE_ONLY"],
      "unknown_error_categories":orig_counter["BLOCKED_EXCEPTION"],
      "phase_a_exception_classification_complete":True,
      "phase_a_complete":False,
      "all_093_original_unchanged":True,"v3_checkpoints_unchanged":True,
      "official_downloads":0,
      "source_calendar_certified":False,"bronze_semantics_certified":False,
      "next":"Resolve TDCC historical market universe using provider-backed security master; run per-file content QA and promoted-version independent SHA; resolve two non-TDCC exceptions.",
      "note":"Complete A exception accounting, not proof of full phase A repair. A cannot pass until historical TSE/OTC identity is verified."}
    targeted=verify_targeted_bytes(api,allrows)
    totals["targeted_nine_byte_qa"] = dict(Counter(r["status"] for r in targeted))
    totals["targeted_nine_all_checked"] = True
    put_once(api,q,"v097_PHASE_A_TARGETED_QA_%s.json"%RUN,
             {"schema":"v097_phase_a_targeted_qa_1","run":RUN,"rows":targeted,
              "promoted_market_raw":0,"semantic_certified":False})
    put_once(api,q,"v097_PHASE_A_DISPOSITION_ROWS_%s.json"%RUN,
             {"schema":"v097_phase_a_disposition_rows_1","run":RUN,"rows":allrows})
    put_once(api,q,"v097_PHASE_A_DISPOSITION_SUMMARY_%s.json"%RUN,totals)
    print("PHASE_A="+json.dumps(totals,ensure_ascii=False),flush=True)
def selftest():
    assert evaluate({"category":"CONTROL_METADATA","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW"})[0]=="EXCLUDED_FROM_MARKET_RAW"
    assert evaluate({"category":"TDCC_IDENTITY","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW","source_path":"2025/TDCC/2025-11/distribution_20251107_YJR4_hash.html"})[0]=="QUARANTINE_TDCC_CODE_FORMAT"
    assert evaluate({"category":"TDCC_IDENTITY","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW","source_path":"2025/TDCC/2025-11/distribution_20251107_2330A_hash.html"})[0]=="HOLD_HISTORICAL_MARKET_IDENTITY"
    assert evaluate({"category":"UNCLASSIFIED_REVIEW","prior_error":"RuntimeError:SOURCE_ROOT_NOT_BOOTSTRAPPED:TDCC_ARCHIVE","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW"})[0]=="ARCHIVE_EVIDENCE_ONLY"
    assert evaluate({"category":"TRANSIENT_RETRY","status":"REPAIR_QA_PASS"})[0]=="REPAIRED_SHA_VERIFIED_SEMANTIC_PENDING"
    print("PHASE_A_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("PHASE_A_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="aggregate":build(service())
    else:raise SystemExit("BAD_MODE")
