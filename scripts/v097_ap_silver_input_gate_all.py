#!/usr/bin/env python3
"""JARVIS v0.97 per-source Bronze -> Silver INPUT attestations.

Read-only immutable Bronze. Reuses exact frozen v3 byte QA, current content QA
receipts and checkpoint. NEVER certifies PIT/backtest or runs Silver/Gold.
READY is per dataset, not a blanket parser-pass upgrade.
"""
import os,re,json,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import source_api,adapter_version,SOURCES,READY
from scripts.v097_ap_silver_input_gate import verify_ndc
RUN=os.getenv("GITHUB_RUN_ID","manual")
GATE="bronze-silver-seven-sources-v1"
def sha(x):return bool(re.fullmatch(r"[a-f0-9]{64}",str(x or "")))
def verdict(src,row,d,ck):
    """One immutable source+destination hash+receipt and typed source gate."""
    if ck.get("adapter_version")!=adapter_version(src) or d.get("adapter_version")!=adapter_version(src):
        return "RECHECK_PENDING"
    if d.get("source_id")!=row["source_id"] or d.get("destination_id")!=row["dest_id"]:
        return "HOLD_RECEIPT_FILE_ID"
    if not sha(row.get("sha")) or d.get("source_sha256")!=row["sha"] or d.get("dest_sha256")!=row["sha"]:
        return "HOLD_ORIGINAL_DESTINATION_SHA"
    if d.get("source_path")!=row["source_path"] or ck.get("status")!=d.get("status"):
        return "HOLD_RECEIPT_PATH_OR_CHECKPOINT"
    path=row["source_path"]
    period=str(row["year"])+"-"+str(row["month"])
    if not path.startswith(str(row["year"])+"/"+src+"/"+period+"/"):
        return "HOLD_SOURCE_NAMESPACE"
    status=d.get("status","")
    if src=="NDC":
        return verify_ndc(row,d,ck)
    if src=="TWSE":
        # Only the dated TWSE mixed official tables that passed full row-width
        # and key numeric text checks in current content adapter.
        dates=d.get("dates",[])
        m=re.search(r"/TWSE_BULK_(\d{4}-\d\d-\d\d)\.json$",path)
        if (status=="CONTENT_PARSED_ORIGIN_PIT_HOLD"
            and d.get("dataset")=="twse_mixed_index_and_stock_quotes"
            and m and dates and all(x==m.group(1) for x in dates)):
            return READY
        return "HOLD_TWSE_DATASET_OR_ARCHIVE_ADAPTER"
    if src=="TPEx":
        dates=d.get("dates",[])
        if (status=="CONTENT_PARSED_ORIGIN_PIT_HOLD"
            and d.get("dataset")=="tpex_quotes_and_optional_sections"
            and path.lower().endswith(".json")
            and dates and all(x[:7]==period for x in dates)
            and ("HISTORICAL_CORRECTED" in path or re.search(r"/\d{4}-\d\d-\d\d_",path))):
            return READY
        return "HOLD_TPEX_HISTORICAL_DATASET_OR_PROVENANCE"
    if src=="TDCC":
        m=re.search(r"/distribution_(\d{8})_(\d{4})_[a-f0-9]{64}\.html$",path)
        if (status=="TDCC_HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING"
            and d.get("dataset")=="holdings"
            and d.get("table_qa")=="HTML_DISTRIBUTION_TOTALS_MATCH"
            and m and d.get("content_security_id")==m.group(2)
            and m.group(1)[:6]==period.replace("-","")):
            return READY
        return "HOLD_TDCC_SOURCE_CLASS_TOTAL_OR_DATES"
    if src=="TAIFEX":
        h=d.get("header",[])
        if (status=="TAIFEX_CSV_ENCODING_WIDTH_PASS_DATE_PIT_HOLD"
            and d.get("date_evidence") is True and d.get("rows_checked",0)>0
            and d.get("missing_date_rows")==0 and d.get("codec") in ("cp950","big5","utf-8-sig")
            and path.lower().endswith(".csv")
            and isinstance(h,list) and len(h)>=3
            and any("日期" in str(col) or str(col) in ("Date","交易日") for col in h)
            and any(any(k in str(col) for k in ("商品","契約","買方","賣方","成交","未平倉","口數")) for col in h)):
            return READY
        return "HOLD_TAIFEX_DATASET_NUMERIC_OR_PERIOD"
    if src=="MOPS":
        # Current receipt is ONLY HTML parser shape, without an exact-match
        # independent financial value ledger. Leave on HOLD.
        return "HOLD_MOPS_EXACT_FINANCIAL_NUMERIC_EVIDENCE"
    if src=="FinMind":
        if (status=="FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD"
            and d.get("unit_count",0)>0 and d.get("rows_checked",0)>0
            and d.get("members_verified",0)>=2
            and d.get("units_missing_source_numeric_or_pit_proof")==0
            and d.get("manifest_numeric_verified") is True):
            return READY
        return "HOLD_FINMIND_PROVIDER_OR_DATASET_PROOF"
    return "HOLD_UNSUPPORTED_SOURCE"
def build(src,api,control,quality,match,load_json):
    input_file=match(api,quality,"v097_AP_INPUT_"+src+".json")
    if not input_file:raise RuntimeError("NO_FROZEN_INPUT:"+src)
    rows=load_json(api,input_file["id"])["rows"]
    if len(rows)!=len({x["source_id"] for x in rows}):
        raise RuntimeError("INPUT_FILE_ID_COLLISION:"+src)
    f=match(api,control,"v097_AP_CHECKPOINT_"+src+".json")
    done=load_json(api,f["id"])["done"] if f else {}
    if set(done)-{r["source_id"] for r in rows}:
        raise RuntimeError("CHECKPOINT_ORPHAN_ID:"+src)
    cache={};results=[];counts=Counter()
    for row in rows:
        sid=row["source_id"];ck=done.get(sid,{})
        receipt=ck.get("receipt")
        if not ck:state="NOT_EXAMINED"
        elif ck.get("adapter_version")!=adapter_version(src):state="RECHECK_PENDING"
        elif not receipt:state="HOLD_MISSING_CONTENT_RECEIPT"
        else:
            if receipt not in cache:
                rf=match(api,quality,receipt)
                if not rf:raise RuntimeError("MISSING_IMMUTABLE_RECEIPT:"+receipt)
                body=load_json(api,rf["id"])
                items=body.get("rows",[])
                if body.get("source")!=src or body.get("adapter_version")!=adapter_version(src):
                    raise RuntimeError("RECEIPT_SOURCE_VERSION_MISMATCH:"+receipt)
                if len(items)!=len({x.get("source_id") for x in items}):
                    raise RuntimeError("RECEIPT_DUPLICATE_IDS:"+receipt)
                cache[receipt]={x["source_id"]:x for x in items}
            detail=cache[receipt].get(sid)
            state=verdict(src,row,detail,ck) if detail else "HOLD_RECEIPT_ROW_MISSING"
        counts[state]+=1
        results.append({"source_id":sid,"destination_id":row["dest_id"],
            "source_sha256":row["sha"],"source_path":row["source_path"],
            "source":src,"status":state,"adapter_version":adapter_version(src),
            "gate_version":GATE,"receipt":receipt,
            "silver_input_only":state==READY,
            "pit_ready_for_backtest":False,
            "official_live_recheck":False,
            "remaining_downstream_checks":["numeric_semantics","publication_pit","historical_security_master"]})
    return {"schema":"v097_silver_input_release_source_v1","run":RUN,
        "at":datetime.now(timezone.utc).isoformat(),"source":src,
        "gate_version":GATE,"adapter_version":adapter_version(src),
        "cohort":len(rows),"counts":dict(counts),"records":results,
        "ready_for_silver_input":counts[READY],
        "pit_backtest_approved":False,"silver_gold_executed":False}
def selftest():
    row={"source_id":"i","dest_id":"j","sha":"a"*64,"year":"2024","month":"10",
         "source_path":"2024/TWSE/2024-10/TWSE_BULK_2024-10-25.json"}
    ck={"adapter_version":adapter_version("TWSE"),"status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"}
    d={"source_id":"i","destination_id":"j","source_sha256":"a"*64,"dest_sha256":"a"*64,
       "adapter_version":adapter_version("TWSE"),"source_path":row["source_path"],
       "status":ck["status"],"dataset":"twse_mixed_index_and_stock_quotes","dates":["2024-10-25"]}
    assert verdict("TWSE",row,d,ck)==READY
    assert verdict("TWSE",row,{**d,"dest_sha256":"b"*64},ck)=="HOLD_ORIGINAL_DESTINATION_SHA"
    assert verdict("TWSE",row,{**d,"dates":["2026-10-25"]},ck)!="BRONZE_READY_FOR_SILVER"
    t={**row,"source_path":"2025/TDCC/2025-10/distribution_20251031_8042_"+("a"*64)+".html",
       "year":"2025","month":"10"}
    x={**d,"source_path":t["source_path"],"status":"TDCC_HTML_CODE_CONSISTENT_OFFICIAL_PROVENANCE_AND_ASOF_MASTER_PENDING",
       "dataset":"holdings","table_qa":"HTML_DISTRIBUTION_TOTALS_MATCH","content_security_id":"8042",
       "adapter_version":adapter_version("TDCC")}
    z={"adapter_version":adapter_version("TDCC"),"status":x["status"]}
    assert verdict("TDCC",t,x,z)==READY
    assert verdict("TDCC",t,{**x,"table_qa":"FAILED"},z)!=READY
    assert verdict("MOPS",{**row,"source_path":"2024/MOPS/2024-10/MOPS_MONTHLY_REVENUE_sii_2024-10.html"},
      {**d,"source_path":"2024/MOPS/2024-10/MOPS_MONTHLY_REVENUE_sii_2024-10.html",
       "adapter_version":adapter_version("MOPS")},{"adapter_version":adapter_version("MOPS"),
       "status":d["status"]})!=READY
    print("SEVEN_SOURCE_GATE_SELFTEST_PASS")
def main():
    if len(sys.argv)>1 and sys.argv[1]=="selftest":return selftest()
    src=os.environ.get("BRONZE_SOURCE") or (sys.argv[1] if len(sys.argv)>1 else None)
    if src not in SOURCES:raise SystemExit("BRONZE_SOURCE_REQUIRED")
    api,control,quality,match,load_json,put_once,_,_=source_api()
    out=build(src,api,control,quality,match,load_json)
    put_once(api,quality,"v097_AP_SILVER_INPUT_RELEASE_"+src+"_"+RUN+".json",out)
    print("SILVER_INPUT_SOURCE_RELEASE="+json.dumps({k:v for k,v in out.items() if k!="records"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
