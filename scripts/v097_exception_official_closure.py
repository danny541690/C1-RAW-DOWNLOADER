#!/usr/bin/env python3
"""JARVIS v0.97 official-closure controller; record evidence, not assertions.
Every frozen exception gets immutable identity and a 3-way *terminal* outcome
only after authenticated source/QA/availability receipts. Otherwise ACTIVE.
No silent 'unavailable'; absence of URL or three retries is not proof.
"""
import os,re,json,hashlib
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,upsert
from scripts.v097_v4_exception_evidence_upload import frozen_rows
from scripts.v097_bf_residual_1131 import relevant
RUN=os.getenv("GITHUB_RUN_ID","manual")
SCHEMA="v097_exception_closure_ledger_1"
NAME="v097_EXCEPTION_OFFICIAL_CLOSURE_V1"
OPTIONS=("REPAIRED_AND_CERTIFIED","OFFICIAL_REDOWNLOADED_AND_CERTIFIED","OFFICIALLY_CONFIRMED_UNAVAILABLE")
SOURCES={"TWSE":"https://www.twse.com.tw/zh/trading/historical/stock-day.html",
         "TPEx":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html",
         "MOPS":"https://mops.twse.com.tw/",
         "TDCC":"https://s.tdcc.com.tw/portal/zh/smWeb/qryStock",
         "TAIFEX":"https://www.taifex.com.tw/"}
def now():return datetime.now(timezone.utc).isoformat()
def readck(api,folder,name):
    f=match(api,folder,name)
    return load_json(api,f["id"]) if f else None
def evidences(api,m,c,q):
    rows={}
    duplicate=Counter()
    for lane in range(6):
        frozen=frozen_rows(api,q,lane)
        copies=readck(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%lane) or {"done":{}}
        if not set(copies["done"]).issubset({x["file_id"] for x in frozen}):
            raise RuntimeError("V4_STAGE_CHECKPOINT_ORPHAN")
        for row in frozen:
            fid=row["file_id"]
            if fid in rows:raise RuntimeError("V4_DUPLICATE_FILE_ID")
            x=copies["done"].get(fid,{})
            rows[fid]={"file_id":fid,"origins":["V4_FROZEN"],
                "v4_error_class":row.get("category"),
                "v4_prior_error":row.get("prior_error"),
                "source_path":row.get("source_path"),
                "quarantine_status":x.get("status","NOT_STAGED"),
                "quarantine_dest_id":x.get("dest_id"),
                "original_sha":x.get("source_sha256")}
    if len(rows)!=6358:raise RuntimeError("V4_FROZEN_COUNT_NOT_6358")
    residual_ids=set()
    for lane in range(6):
        rr=relevant(api,m,c,lane)
        checkpoints=readck(api,c,"v097_BF_RESIDUAL_V2_CK_%02d.json"%lane) or {"done":{}}
        fmt=readck(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane) or {"done":{}}
        fmtstage=readck(api,c,"v097_FORMAT_SALVAGE_HOLD_V3_CK_%02d.json"%lane) or {"done":{}}
        otherstage=readck(api,c,"v097_NONHTML_RESIDUAL_HOLD_V1_CK_%02d.json"%lane) or {"done":{}}
        mops=readck(api,c,"v097_MOPS_HTML_MATRIX_QA_V1_CK_%02d.json"%lane) or {"done":{}}
        for row,category,_ in rr:
            fid=row["file_id"]
            if fid in residual_ids:raise RuntimeError("RESIDUAL_DUPLICATE_FILE_ID")
            residual_ids.add(fid)
            item=rows.setdefault(fid,{"file_id":fid,"origins":[],"source_path":row.get("path")})
            item["origins"].append("RAW_RESIDUAL_1131")
            item["source"]=row.get("source")
            item["source_month"]=row.get("month")
            item["filename"]=row.get("file_name")
            item["original_qa_status"]=row.get("prior_status")
            item["residual_category"]=category
            item["residual_check"]=checkpoints["done"].get(fid,{}).get("state","PENDING")
            item["format_result"]=fmt["done"].get(fid,{}).get("state","NOT_APPLICABLE")
            stage=(fmtstage["done"].get(fid) or otherstage["done"].get(fid) or {})
            item["residual_quarantine_status"]=stage.get("state") or stage.get("status") or "UNKNOWN"
            item["parsed_matrix_state"]=mops["done"].get(fid,{}).get("status","NOT_APPLICABLE")
    if len(residual_ids)!=1131:raise RuntimeError("RESIDUAL_COUNT_NOT_1131")
    return rows
def source_from(x):
    source=x.get("source")
    if source: return source
    cls=str(x.get("v4_error_class") or "")
    if cls.startswith("TDCC"):return "TDCC"
    return "UNKNOWN"
def classify(x):
    """Only material official certified receipts qualify; evidence-copy alone never does."""
    source=source_from(x)
    has_evidence=x.get("quarantine_status")=="V097_V4_QUARANTINE_SHA_PASS" or x.get("residual_quarantine_status") in ("STAGED_SHA_VERIFIED_IN_097_FORMAT_QUARANTINE","STAGED_OTHER27_SHA_PASS")
    parsed=x.get("parsed_matrix_state")=="MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING"
    # Do not mistake staged data or source page links for a verified official per-dataset download.
    if parsed:
        step="VERIFY_PIT_PERIOD_ACCOUNTING_AND_MARKET_SCOPE"
    elif has_evidence:
        step="VALIDATE_DATASET_SCHEMA_ORIGINAL_SOURCE_AND_PUBLICATION_TIME"
    else:
        step="PRESERVE_ORIGINAL_IN_097_QUARANTINE_AND_VERIFY_SHA"
    if source=="UNKNOWN":step="RESOLVE_ORIGINAL_SOURCE_AND_DATASET_IDENTITY"
    return {"decision":"ACTIVE_NOT_CERTIFIED","next_step":step,
            "official_source_catalog_url":SOURCES.get(source),
            "official_dataset_url_verified":False,
            "official_redownload_attempts_verified":0,
            "unavailable_official_evidence":False,
            "market_bronze_admitted":False}
def run(api):
    m,c,q,_=common(api)
    data=evidences(api,m,c,q)
    total=len(data)
    out=[];counts=Counter();overlap=0
    for fid in sorted(data):
        x=data[fid]
        if len(x["origins"])>1:overlap+=1
        doc={**x,**classify(x)}
        out.append(doc);counts[doc["decision"]]+=1
    if counts.get("ACTIVE_NOT_CERTIFIED",0)!=total:raise RuntimeError("UNEXPECTED_TERMINAL_WITHOUT_PROOF")
    # List is versioned evidence; never edit 0.93, Bronze, existing receipts.
    report={"schema":SCHEMA,"run":RUN,"at":now(),"v4_frozen":6358,
        "raw_residual_frozen":1131,"overlap_count":overlap,"unique_exception_files":total,
        "terminal_choices":list(OPTIONS),"by_state":dict(counts),
        "certified_repaired":0,"certified_official_redownload":0,
        "certified_unavailable":0,"active":total,
        "proof_gate":"Terminal status requires actual verified dataset/date/source receipt, SHA and admission QA; unavailable requires official document proving that exact dataset/date cannot be obtained.",
        "notes":"No fabricated official endpoint or automatic false closure. Only known errors; does not prove whole 2000-2026 coverage.",
        "records":out}
    # One immutable complete ledger plus compact rollup.
    put_once(api,q,"%s_RECORDS_%s.json"%(NAME,RUN),report)
    summary={k:v for k,v in report.items() if k!="records"}
    put_once(api,q,"%s_SUMMARY_%s.json"%(NAME,RUN),summary)
    print("OFFICIAL_CLOSURE_SUMMARY="+json.dumps(summary,ensure_ascii=False),flush=True)
def selftest():
    assert len(OPTIONS)==3 and len(set(OPTIONS))==3
    assert classify({"source":"MOPS","parsed_matrix_state":"MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING"})["decision"]=="ACTIVE_NOT_CERTIFIED"
    assert classify({"source":"TDCC","quarantine_status":"V097_V4_QUARANTINE_SHA_PASS"})["decision"]=="ACTIVE_NOT_CERTIFIED"
    print("OFFICIAL_CLOSURE_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("OFFICIAL_CLOSURE_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="ledger":run(service())
    else:raise SystemExit("INVALID_MODE")
