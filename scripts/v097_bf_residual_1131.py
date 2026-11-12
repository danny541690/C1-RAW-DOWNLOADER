#!/usr/bin/env python3
"""JARVIS v0.97 residual v0.93 -> v0.97 source-evidence audit.
Treats 1,131 remaining raw-audit exceptions independently of 6,358 V3 copy
exceptions. Never edits v0.93, frozen audit, V3 checkpoints or Bronze.
No unproved downloads/copies. Immutable receipts precede new checkpoints.
"""
import os,json,hashlib,re
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert,call,raw_integrity
RUN=os.getenv("GITHUB_RUN_ID","manual")
BATCH=max(1,min(100,int(os.getenv("RESIDUAL_BATCH","60"))))
NAME="v097_BF_RESIDUAL_V2"
MAX_BYTES=40*1024*1024
TARGET=1131
def now():return datetime.now(timezone.utc).isoformat()
def sha(blob):return hashlib.sha256(blob).hexdigest()
def group_status(row,rescue):
    state=row["raw_status"]
    if state=="RAW_UNKNOWN_NO_R2_RECEIPT":
        proof=rescue.get(row["file_id"])
        if not proof:raise RuntimeError("RESCUE_CHECKPOINT_NOT_FOUND_FOR_UNKNOWN")
        if proof.get("state")=="RAW_RESCUED_BASIC_CANDIDATE":
            return None
        return "RESCUE_BLOCKED"
    if state=="RAW_REVIEW_QUARANTINED":return "LEGACY_QUARANTINE_REVIEW"
    if state=="RAW_REJECT_PATH_CONFLICT":return "EVIDENCE_PATH_CONFLICT"
    if state=="RAW_UNKNOWN_SOURCE":return "SOURCE_NAMESPACE_REVIEW"
    if state=="RAW_BLOCKED_PARSER_OR_SIZE":return "STRUCTURE_OR_SIZE_REVIEW"
    # All approved / rescued raw records already passed the migration path. Never rescan them.
    return None
def relevant(api,m,c,lane):
    rows=[]
    for audit_lane in (lane,lane+6):
        a=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%audit_lane)
        if not a:raise RuntimeError("MISSING_FROZEN_AUDIT_"+str(audit_lane))
        rf=match(api,c,"v097_BF_RAW_RESCUE_V1_CK_%02d.json"%audit_lane)
        r=load_json(api,rf["id"])["done"] if rf else {}
        for row in load_json(api,a["id"])["items"]:
            category=group_status(row,r)
            if category:rows.append((row,category,audit_lane))
    return rows
def inspect(api,row,category,lane):
    fid=row["file_id"]
    report={"file_id":fid,"lane":lane,"category":category,
            "legacy_raw_state":row["raw_status"],"prior_status":row.get("prior_status"),
            "source_path":row.get("path"),"original_file_name":row.get("file_name"),
            "original_source":row.get("source"),"original_period":row.get("month"),
            "market_bronze_promoted":False,"source_modified":False,"run":RUN}
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum,parents"))
        if meta.get("name")!=row.get("file_name"):
            report.update(state="BLOCKED_SOURCE_FILENAME_CHANGED")
            return report
        size=int(meta.get("size") or 0)
        if size<1 or size>MAX_BYTES:
            report.update(state="BLOCKED_SOURCE_SIZE",size=size)
            return report
        blob=call(lambda:api.files().get_media(fileId=fid))
        if len(blob)!=size:raise ValueError("META_ACTUAL_BYTE_SIZE_CONFLICT")
        if meta.get("md5Checksum") and hashlib.md5(blob).hexdigest()!=meta["md5Checksum"]:
            raise ValueError("DRIVE_MD5_CONFLICT")
        report.update(observed_sha256=sha(blob),size=len(blob),
                      raw_structure=raw_integrity(blob,row.get("file_name") or "unknown"))
        path=str(row.get("path") or "")
        source=str(row.get("source") or "")
        month=str(row.get("month") or "")
        year=str(row.get("year") or "")
        report["path_period_and_source_match"]=bool(year and source and month and path.startswith(year+"/"+source+"/"+month+"/"))
        if category=="EVIDENCE_PATH_CONFLICT":
            report["state"]="HOLD_PATH_CONFLICT_OFFICIAL_EVIDENCE_REQUIRED"
        elif category=="SOURCE_NAMESPACE_REVIEW":
            report["state"]="HOLD_SOURCE_PROVENANCE"
        elif report["raw_structure"]!="RAW_STRUCTURE_PASS":
            report["state"]="HOLD_INVALID_OR_UNSUPPORTED_STRUCTURE"
        elif not report["path_period_and_source_match"]:
            report["state"]="HOLD_PATH_OR_PERIOD_MISMATCH"
        else:
            report["state"]="STRUCTURE_PASS_REQUIRES_DATASET_SEMANTICS_AND_ORIGINAL_RECEIPT"
    except Exception as ex:
        report.update(state="READ_OR_HASH_BLOCKED",error=type(ex).__name__+":"+str(ex)[:180])
    return report
def lane_run(api,lane):
    m,c,q,_=common(api)
    candidate=relevant(api,m,c,lane)
    name=NAME+"_CK_%02d.json"%lane
    f=match(api,c,name)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_bf_residual_ck_2","lane":lane,"done":{}}
    if ck.get("schema")!="v097_bf_residual_ck_2" or ck.get("lane")!=lane:
        raise RuntimeError("RESIDUAL_CHECKPOINT_CONFLICT")
    known={r["file_id"] for r,_,_ in candidate}
    if not set(ck["done"]).issubset(known):raise RuntimeError("RESIDUAL_CHECKPOINT_ORPHAN")
    todo=[(r,k,a) for r,k,a in candidate if r["file_id"] not in ck["done"]][:BATCH]
    offset=len(ck["done"])
    receipt=NAME+"_%s_L%02d_O%05d.json"%(RUN,lane,offset)
    old=match(api,q,receipt)
    if old:
        out=load_json(api,old["id"])["rows"]
        if len(out)>BATCH or not {r["file_id"] for r in out}.issubset(known):
            raise RuntimeError("RESIDUAL_RECEIPT_ORPHAN")
    else:
        out=[inspect(api,r,k,a) for r,k,a in todo]
        put_once(api,q,receipt,{"schema":"v097_bf_residual_receipt_2","run":RUN,
            "lane":lane,"offset":offset,"utc":now(),"rows":out,"promoted":0})
    for r in out:
        ck["done"][r["file_id"]]={"state":r["state"],"run":RUN,
            "source_sha256":r.get("observed_sha256"),"category":r["category"]}
    upsert(api,c,name,dict(ck,updated_at=now(),last_receipt=receipt))
    print("RESIDUAL_LANE="+json.dumps({"lane":lane,"batch":len(out),
        "processed":len(ck["done"]),"total":len(candidate),
        "remaining":len(candidate)-len(ck["done"]),"states":dict(Counter(r["state"] for r in out))},ensure_ascii=False),flush=True)
def summary(api):
    m,c,q,_=common(api)
    all_ids=set();total=done_count=0;categories=Counter();states=Counter();original_qa=Counter();sources=Counter()
    for lane in range(6):
        candidates=relevant(api,m,c,lane)
        ids={r["file_id"] for r,_,_ in candidates}
        if len(ids)!=len(candidates) or ids&all_ids:raise RuntimeError("RESIDUAL_DUPLICATE_OR_CROSS_LANE")
        all_ids.update(ids);total+=len(candidates)
        categories.update(k for _,k,_ in candidates)
        original_qa.update(str(r.get("prior_status") or "UNKNOWN") for r,_,_ in candidates)
        sources.update(str(r.get("source") or "UNKNOWN") for r,_,_ in candidates)
        f=match(api,c,NAME+"_CK_%02d.json"%lane)
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("RESIDUAL_SUMMARY_ORPHAN")
        done_count+=len(ck["done"]);states.update(v["state"] for v in ck["done"].values())
    if total!=TARGET:raise RuntimeError("RESIDUAL_EXPECTED_%d_GOT_%d"%(TARGET,total))
    remaining=total-done_count
    result={"schema":"v097_bf_residual_overview_2","run":RUN,"at":now(),
        "source_inventory":82273,"v3_copy_qa_pass":74750,
        "frozen_v3_copy_exceptions":6358,
        "residual_expected":TARGET,"residual_checked":done_count,"residual_remaining":remaining,
        "by_category":dict(categories),"by_state":dict(states),
        "by_original_qa_status":dict(original_qa),"by_original_source":dict(sources),
        "no_r2_receipt_source_rescue_blocked":categories["RESCUE_BLOCKED"],
        "market_raw_promoted":0,"historical_master_certified":False,
        "bronze_full_approved":False,"next":"Resolve source evidence / dataset adapters for held rows without touching verified 74750."}
    put_once(api,q,NAME+"_SUMMARY_%s.json"%RUN,result)
    print("RESIDUAL_SUMMARY="+json.dumps(result,ensure_ascii=False),flush=True)

def diagnose(api):
    """Small, provenance-safe format fingerprints for JSON errors & oversized files."""
    import gzip,zipfile,io
    m,c,q,_=common(api)
    chosen={}
    for lane in range(6):
        for row,category,audit_lane in relevant(api,m,c,lane):
            key=(str(row.get("source") or "UNKNOWN"),str(row.get("prior_status") or "UNKNOWN"))
            if len(chosen.get(key,[])) < 3:
                chosen.setdefault(key,[]).append((row,category))
    items=[]
    for (source,prior),rows in chosen.items():
        for row,category in rows:
            fid=row["file_id"]
            info={"source":source,"prior_status":prior,"category":category,
                  "file_id":fid,"file_name":row.get("file_name"),"path":row.get("path")}
            try:
                meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,mimeType,md5Checksum"))
                length=int(meta.get("size") or 0)
                info.update(byte_size=length,mimeType=meta.get("mimeType"))
                if 0<length<=2*1024*1024:
                    raw=call(lambda:api.files().get_media(fileId=fid))
                    stripped=raw.lstrip()
                    info.update(sha256=sha(raw),raw_magic_hex=raw[:16].hex(),
                                likely_json=stripped.startswith((b"{",b"[")),
                                likely_html=stripped.lower().startswith((b"<!doctype",b"<html")),
                                likely_zip=raw.startswith(b"PK\x03\x04"),
                                likely_gzip=raw.startswith(b"\x1f\x8b"))
                    if raw.startswith((b"{",b"[")) or stripped.startswith((b"{",b"[")):
                        try:
                            parsed=json.loads(raw.decode("utf-8-sig"))
                            info.update(json_valid=True,json_top_type=type(parsed).__name__,
                                        json_rows=len(parsed) if isinstance(parsed,list) else None)
                        except Exception as err:
                            info.update(json_valid=False,json_error=type(err).__name__+":"+str(err)[:140])
                    if raw.startswith(b"PK\x03\x04"):
                        try:
                            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                                info.update(zip_test_result=z.testzip(),zip_members=len(z.namelist()))
                        except Exception as err:
                            info.update(zip_error=type(err).__name__+":"+str(err)[:140])
                else:info["bytes_not_downloaded"]="ZERO_OR_GT_2_MB"
            except Exception as err:
                info["diagnostic_error"]=type(err).__name__+":"+str(err)[:180]
            items.append(info)
    report={"schema":"v097_bf_residual_format_diagnosis_1","run":RUN,
            "at":now(),"sample_count":len(items),"samples":items,
            "source_unchanged":True,"market_raw_promoted":0,
            "note":"These are tiny diagnostic samples, never full dataset certification."}
    put_once(api,q,"v097_BF_RESIDUAL_FORMAT_DIAG_%s.json"%RUN,report)
    counts=Counter((i["source"],i["prior_status"],i.get("likely_json"),i.get("json_valid"),
                    i.get("likely_html"),i.get("likely_zip")) for i in items)
    print("FORMAT_DIAG="+json.dumps({"run":RUN,"samples":items,"counts":{str(k):v for k,v in counts.items()}},ensure_ascii=False),flush=True)


FMT_NAME="v097_BF_RESIDUAL_FORMAT_V1"
FMT_BATCH=max(1,min(100,int(os.getenv("FORMAT_BATCH","60"))))
def format_candidates(api,m,c,lane):
    return [(r,a) for r,k,a in relevant(api,m,c,lane)
            if r.get("prior_status")=="QUARANTINED_JSON_ERROR"]
def classify_payload(raw,source):
    """Safe content sniff, not a semantic certification or admission pass."""
    plain=raw.lstrip(b"\xef\xbb\xbf\x20\r\n\t").lower()
    if plain.startswith((b"<html",b"<!doctype html")):
        kind="FULL_HTML"
    elif b"<table" in plain[:8192] or b"<div" in plain[:8192]:
        kind="HTML_FRAGMENT"
    elif plain.startswith((b"{",b"[")):
        try:
            decoded=json.loads(raw.decode("utf-8-sig"))
            return "JSON_VALID_RECHECK_SCHEMA",{"top_type":type(decoded).__name__,
                                                "records":len(decoded) if isinstance(decoded,list) else None}
        except Exception as err:
            return "JSON_ACTUAL_PARSE_FAILURE",{"error":type(err).__name__+":"+str(err)[:130]}
    elif raw.startswith(b"PK\x03\x04"):
        return "ZIP_NOT_JSON",{"magic":"PK"}
    else:
        return "UNRECOGNIZED_NOT_JSON",{"magic":raw[:16].hex()}
    import html
    page=raw.decode("utf-8-sig",errors="replace")
    tables=len(re.findall(r"<table\b",page,re.I))
    rows=len(re.findall(r"<tr\b",page,re.I))
    cells=len(re.findall(r"<t[dh]\b",page,re.I))
    has_unit=bool(re.search(r"金額單位|千元|新臺幣",page))
    suspicious=bool(re.search(r"403 Forbidden|Access Denied|404 Not Found|Internal Server Error|查無資料|系統忙碌",page,re.I))
    info={"format":kind,"tables":tables,"tr_tags":rows,"td_th_tags":cells,
          "mentions_unit":has_unit,"server_or_empty_warning":suspicious}
    if suspicious or tables==0 or rows==0 or cells==0:
        return "HOLD_HTML_ERROR_OR_NO_DATA_TABLE",info
    if source=="MOPS":
        return "MOPS_HTML_TABLE_ADAPTER_AND_FINANCIAL_UNITS_PENDING",info
    if source=="TPEx":
        return "TPEX_HTML_TABLE_ADAPTER_AND_DATASET_ORIGIN_PENDING",info
    if source=="TDCC":
        return "TDCC_HTML_TABLE_ADAPTER_AND_MARKET_SCOPE_PENDING",info
    return "HTML_DATA_TABLE_SOURCE_ADAPTER_PENDING",info
def format_lane(api,lane):
    m,c,q,_=common(api)
    src=format_candidates(api,m,c,lane)
    name=FMT_NAME+"_CK_%02d.json"%lane
    f=match(api,c,name)
    ck=load_json(api,f["id"]) if f else {"schema":"v097_format_ck_1","lane":lane,"done":{}}
    if ck.get("schema")!="v097_format_ck_1" or ck.get("lane")!=lane:raise RuntimeError("FORMAT_CK_CONFLICT")
    known={r["file_id"] for r,_ in src}
    if not set(ck["done"]).issubset(known):raise RuntimeError("FORMAT_CK_ORPHAN")
    todo=[(r,a) for r,a in src if r["file_id"] not in ck["done"]][:FMT_BATCH]
    offset=len(ck["done"])
    receipt=FMT_NAME+"_%s_L%02d_O%05d.json"%(RUN,lane,offset)
    old=match(api,q,receipt)
    if old:
        out=load_json(api,old["id"])["rows"]
        if not {a["file_id"] for a in out}.issubset(known):raise RuntimeError("FORMAT_RECEIPT_ORPHAN")
    else:
        out=[]
        for row,a in todo:
            rec={"file_id":row["file_id"],"audit_lane":a,"source":row.get("source"),
                 "prior_status":row.get("prior_status"),"file_name":row.get("file_name"),
                 "source_path":row.get("path"),"market_bronze_promoted":False}
            try:
                fid=row["file_id"]
                meta=call(lambda:api.files().get(fileId=fid,fields="id,name,size,md5Checksum"))
                length=int(meta.get("size") or 0)
                if length<1 or length>MAX_BYTES:
                    rec.update(state="SOURCE_TOO_LARGE_OR_EMPTY",bytes=length)
                else:
                    raw=call(lambda:api.files().get_media(fileId=fid))
                    if len(raw)!=length:raise ValueError("SIZE_CONFLICT")
                    if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:
                        raise ValueError("DRIVE_MD5_CONFLICT")
                    status,proof=classify_payload(raw,str(row.get("source") or ""))
                    rec.update(state=status,format_proof=proof,bytes=len(raw),sha256=sha(raw))
            except Exception as err:
                rec.update(state="FORMAT_QA_READ_ERROR",error=type(err).__name__+":"+str(err)[:130])
            out.append(rec)
        put_once(api,q,receipt,{"schema":"v097_format_receipt_1","run":RUN,
                                "lane":lane,"offset":offset,"rows":out,
                                "source_files_unchanged":True,"market_promotions":0})
    for rec in out:
        ck["done"][rec["file_id"]]={"state":rec["state"],"run":RUN,
                                  "sha256":rec.get("sha256"),"source":rec["source"]}
    upsert(api,c,name,dict(ck,updated_at=now(),last_receipt=receipt))
    print("FORMAT_LANE="+json.dumps({"lane":lane,"processed":len(ck["done"]),
        "total":len(src),"remaining":len(src)-len(ck["done"]),
        "batch":len(out),"by_state":dict(Counter(z["state"] for z in out))},ensure_ascii=False),flush=True)
def format_summary(api):
    m,c,q,_=common(api)
    expected=0;checked=0;counts=Counter();seen=set()
    for lane in range(6):
        src=format_candidates(api,m,c,lane)
        ids={r["file_id"] for r,a in src}
        if ids&seen or len(ids)!=len(src):raise RuntimeError("FORMAT_DUPLICATE")
        seen.update(ids);expected+=len(ids)
        f=match(api,c,FMT_NAME+"_CK_%02d.json"%lane)
        ck=load_json(api,f["id"]) if f else {"done":{}}
        if not set(ck["done"]).issubset(ids):raise RuntimeError("FORMAT_ORPHAN")
        checked+=len(ck["done"])
        counts.update(v["state"] for v in ck["done"].values())
    if expected!=1104:raise RuntimeError("EXPECTED_1104_GOT_%d"%expected)
    result={"schema":"v097_bf_format_qa_summary_1","run":RUN,
            "files_expected":1104,"checked":checked,"remaining":expected-checked,
            "by_state":dict(counts),"market_raw_promoted":0,
            "original_v093_unchanged":True,
            "next":"Use official dataset-specific HTML adapters with period and source provenance before any Bronze copy."}
    put_once(api,q,FMT_NAME+"_SUMMARY_%s.json"%RUN,result)
    print("FORMAT_SUMMARY="+json.dumps(result,ensure_ascii=False),flush=True)

def selftest():
    assert group_status({"raw_status":"RAW_REVIEW_QUARANTINED","file_id":"x"}, {})=="LEGACY_QUARANTINE_REVIEW"
    assert group_status({"raw_status":"RAW_UNKNOWN_NO_R2_RECEIPT","file_id":"x"},{"x":{"state":"RAW_RESCUE_BLOCKED"}})=="RESCUE_BLOCKED"
    assert group_status({"raw_status":"RAW_UNKNOWN_NO_R2_RECEIPT","file_id":"x"},{"x":{"state":"RAW_RESCUED_BASIC_CANDIDATE"}}) is None
    assert group_status({"raw_status":"RAW_REJECT_PATH_CONFLICT","file_id":"x"}, {})=="EVIDENCE_PATH_CONFLICT"
    assert group_status({"raw_status":"A_PASS_CANDIDATE_R2_BYTES","file_id":"x"}, {}) is None
    assert group_status({"raw_status":"RAW_RESCUED_BASIC_CANDIDATE","file_id":"x"}, {}) is None
    assert sum((1104,19,6,1,1))==TARGET
    st,p=classify_payload(b"<html><table><tr><td>1</td></tr></table></html>","TPEx")
    assert st=="TPEX_HTML_TABLE_ADAPTER_AND_DATASET_ORIGIN_PENDING" and p["tables"]==1
    assert classify_payload(b"{invalid", "MOPS")[0]=="JSON_ACTUAL_PARSE_FAILURE"
    print("RESIDUAL_SELFTEST_PASS",flush=True)
if __name__=="__main__":
    mode=os.getenv("RESIDUAL_MODE","selftest")
    if mode=="selftest":selftest()
    else:
        api=service()
        if mode=="lane":lane_run(api,int(os.environ["RESIDUAL_LANE"]))
        elif mode=="aggregate":summary(api)
        elif mode=="diagnose":diagnose(api)
        elif mode=="format_lane":format_lane(api,int(os.environ["FORMAT_LANE"]))
        elif mode=="format_summary":format_summary(api)
        else:raise SystemExit("BAD_MODE")
