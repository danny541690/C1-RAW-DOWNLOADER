#!/usr/bin/env python3
"""Verify actual original bytes of 39 uncategorized v0.97 exceptions.
All file IDs grounded in frozen 6358 V4 and 1131 residual manifests.
Recheck SHA, ZIP CRC, JSON object shape, HTML table presence and original
date/source path, reporting per-source content evidence for further official
dataset-level compare. Does NOT admit nonmarket or unverified source.
"""
import os,re,json,hashlib,io,zipfile
from collections import Counter
from datetime import datetime,timezone
from bs4 import BeautifulSoup
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once,call,raw_integrity
from scripts.v097_v4_exception_evidence_upload import frozen_rows
from scripts.v097_bf_residual_1131 import relevant
RUN=os.getenv("GITHUB_RUN_ID","manual")
def sha(b):return hashlib.sha256(b).hexdigest()
def detect(raw,name):
    fmt="UNKNOWN";facts={}
    if raw.startswith(b"PK\x03\x04"):
        fmt="ZIP"
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            items=z.infolist()
            bad=z.testzip()
            facts={"members":len(items),"crc_ok":bad is None,"member_names":[x.filename for x in items[:12]],
                   "uncompressed_size":sum(x.file_size for x in items)}
            if bad is not None:raise ValueError("ZIP_CRC_INVALID")
            if facts["uncompressed_size"]>250_000_000:raise ValueError("ZIP_TOTAL_BYTES_OVER_LIMIT")
    elif raw.lstrip().startswith((b"{",b"[")):
        fmt="JSON"
        j=json.loads(raw.decode("utf-8-sig"))
        facts={"root_type":type(j).__name__,
               "keys":list(j)[:20] if isinstance(j,dict) else [],
               "rows":len(j) if isinstance(j,list) else None}
    elif b"<table" in raw[:500000].lower() or b"<html" in raw[:50000].lower():
        fmt="HTML"
        soup=BeautifulSoup(raw.decode("utf-8-sig",errors="replace"),"html.parser")
        facts={"tables":len(soup.find_all("table")),"head_text":soup.get_text(" ",strip=True)[:200]}
    elif raw.startswith(b"%PDF-"):fmt="PDF"
    else:
        fmt="OTHER"
        facts={"first_16_bytes_hex":raw[:16].hex()}
    return fmt,facts
def main():
 api=service();m,c,q,_=common(api)
 candidates={}
 for lane in range(6):
    stage=match(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%lane)
    done=load_json(api,stage["id"])["done"]
    for row in frozen_rows(api,q,lane):
        if row["category"]!="UNCLASSIFIED_REVIEW":continue
        fid=row["file_id"]
        candidates[fid]={"fid":fid,"source":"TDCC_ARCHIVE","path":row.get("source_path"),
           "expected_sha":done.get(fid,{}).get("source_sha256"),"kind":"V4_UNCLASSIFIED"}
    fmt=match(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane)
    fm=load_json(api,fmt["id"])["done"] if fmt else {}
    for row,kind,_ in relevant(api,m,c,lane):
        fid=row["file_id"]
        if row.get("source") in ("TDCC","TPEx","MOPS"): 
            # Five financial IFRS/revenue cases, one TPEx archive, 17 TDCC structure
            if row["source"]=="MOPS" and fm.get(fid,{}).get("state")!="MOPS_HTML_TABLE_ADAPTER_AND_FINANCIAL_UNITS_PENDING":
                continue
            if row["source"]=="TPEx" and fm.get(fid,{}).get("state")!="TPEX_HTML_TABLE_ADAPTER_AND_DATASET_ORIGIN_PENDING":
                pass
        elif row.get("source") not in ("TDCC_ARCHIVE","TAIFEX"):continue
        # Exclude 383 MOPS and 711 TPEx already parsed at stage; select by latest CK
        if row["source"] in ("TPEx","MOPS"):
            n="v097_TPEX_LEGACY_RSTA3104_V1_CK_%02d.json"%lane if row["source"]=="TPEx" else "v097_MOPS_HTML_MATRIX_QA_V1_CK_%02d.json"%lane
            v=match(api,c,n)
            old=load_json(api,v["id"])["done"] if v else {}
            ispass=(old.get(fid,{}).get("status") or "").endswith("PASS_PIT_PENDING")
            if row["source"]=="TPEx":
                b=match(api,c,"v097_LEGACY_TPEX_MOPS_V2_TPEx_CK_%02d.json"%lane)
            else:
                b=match(api,c,"v097_LEGACY_TPEX_MOPS_V2_MOPS_CK_%02d.json"%lane)
            v2=load_json(api,b["id"])["done"] if b else {}
            if ispass or v2.get(fid,{}).get("state")=="LEGACY_PARSED_STAGED_PIT_PENDING":continue
        if fid in candidates:raise RuntimeError("SAME_ID_MULTIPLE_CATEGORIES")
        candidates[fid]={"fid":fid,"source":row.get("source"),"path":row.get("path"),
            "expected_sha":fm.get(fid,{}).get("sha256"),"kind":kind}
 if len(candidates)!=39:raise RuntimeError("EXPECTED_39_UNRESOLVED_GOT_"+str(len(candidates)))
 records=[];state=Counter();sources=Counter()
 for fid,item in candidates.items():
    r=dict(item)
    try:
        meta=call(lambda:api.files().get(fileId=fid,fields="name,size,md5Checksum"))
        size=int(meta.get("size") or 0)
        if not 0<size<=32*1024*1024:raise ValueError("EXCEPTION_READ_SIZE_INVALID")
        raw=call(lambda:api.files().get_media(fileId=fid))
        if len(raw)!=size:raise ValueError("SOURCE_BYTES_CHANGED")
        if meta.get("md5Checksum") and hashlib.md5(raw).hexdigest()!=meta["md5Checksum"]:raise ValueError("DRIVE_MD5_CONFLICT")
        r["sha256"]=sha(raw)
        if item.get("expected_sha") and item["expected_sha"]!=r["sha256"]:raise ValueError("PRIOR_SOURCE_SHA_CHANGED")
        r["bytes"]=len(raw)
        fmt,details=detect(raw,meta["name"])
        r.update(source_format=fmt,actual_format_facts=details)
        if item["source"]=="TAIFEX" and ("TimeAndSales" in meta["name"]):
            r.update(state="OUT_OF_SCOPE_TICK_DATA_USER_EXCLUDED",next="PRESERVE_AS_NONMARKET_AUDIT_NOT_STOCK_GOLD")
        elif fmt=="ZIP":
            r.update(state="ARCHIVE_CRC_PASS_DATASET_PROVENANCE_PENDING",next="CHECK_MANIFEST_INTERNAL_SOURCE_DATE_AND_EXISTING_OFFICIAL_COPIES")
        elif fmt=="JSON":
            r.update(state="JSON_STRUCTURE_PASS_DATASET_AND_DATE_PENDING",next="VERIFY_OFFICIAL_SOURCE_DATASET_SCHEMA_AND_ASOF")
        elif fmt=="HTML":
            r.update(state="HTML_CONTENT_PRESENT_DATASET_SEMANTICS_PENDING",next="VERIFY_ON_OFFICIAL_HISTORY_OR_REPARSE")
        else:
            r.update(state="SPECIAL_FORMAT_SOURCE_REVIEW",next="CHECK_ORIGINAL_API_RESPONSE_HEADER_AND_OFFICIAL_SOURCE")
    except Exception as exc:
        r.update(state="RAW_CONTENT_INTEGRITY_HOLD",error=type(exc).__name__+":"+str(exc)[:170],
           next="OFFICIAL_REREQUEST_IF_BYTES_INVALID")
    state[r["state"]]+=1;sources[r["source"]]+=1;records.append(r)
 report={"schema":"v097_remaining_39_content_census_1","run":RUN,
   "total":len(records),"by_state":dict(state),"by_source":dict(sources),
   "no_original_deleted":True,"formal_bronze_promoted":0,"rows":records}
 put_once(api,q,"v097_REMAINING_39_CONTENT_QA_"+RUN+".json",report)
 print("REMAINING_39_CONTENT_SUMMARY="+json.dumps(report,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
