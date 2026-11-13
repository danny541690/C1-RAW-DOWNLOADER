#!/usr/bin/env python3
"""JARVIS v0.97 full original anomaly ledger reconciliation.
Join 6358 V4 exceptions and 1131 residual by immutable original Drive file ID;
record all unresolved IDs, stage receipts, parser reason and admission state.
A pass in a legacy parser is NOT market Bronze. No data files are altered.
"""
import os,json
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once
from scripts.v097_v4_exception_evidence_upload import frozen_rows
from scripts.v097_bf_residual_1131 import relevant
RUN=os.getenv("GITHUB_RUN_ID","manual")
PREFIX="v097_FINAL_OPEN_ISSUES_20261113_V1"
def ck(api,folder,key):
    f=match(api,folder,key)
    return load_json(api,f["id"]) if f else {"done":{}}
def main():
    api=service();m,c,q,_=common(api)
    allrows={};population=Counter();detail=Counter()
    for lane in range(6):
        fr=frozen_rows(api,q,lane)
        stage=ck(api,c,"v097_V4_EXCEPTIONS_STAGED_V1_CK_%02d.json"%lane)["done"]
        for row in fr:
            fid=row["file_id"]
            if fid in allrows:raise RuntimeError("V4_DUPLICATE")
            category=row.get("category","UNKNOWN")
            copy=stage.get(fid,{})
            a={"file_id":fid,"source_group":"V4","category":category,
               "source_path":row.get("source_path"),
               "original_error":row.get("prior_error"),
               "source_sha256":copy.get("source_sha256"),
               "quarantine_copy":copy.get("status","UNVERIFIED"),
               "quarantine_id":copy.get("dest_id"),
               "formal_market_bronze_certified":False}
            if category=="CONTROL_METADATA":
                a.update(current_bucket="CONTROL_ONLY_EXCLUDE_FROM_MARKET_COUNT",
                    next_action="KEEP_CONTROL_PROVENANCE; NOT_FINANCIAL_MARKET_DATA")
            elif category=="TDCC_IDENTITY":
                a.update(current_bucket="TDCC_SPECIAL_CODES_NOT_STOCK_BRONZE",
                    next_action="RETAIN_TDCC_SPECIAL_SECURITY_SIDECAR; 3 LIVE OFFICIAL SPOT MATCHES; HISTORICAL CATEGORY PENDING")
            elif category=="TRANSIENT_RETRY":
                a.update(current_bucket="V4_BASIC_QA_PASS_BRONZE_RELEASE_PENDING",
                    next_action="VERIFY_PER_FILE_OFFICIAL_LINEAGE_AND_MARKET_BRONZE_RELEASE_GATE")
            else:
                a.update(current_bucket="V4_UNCLASSIFIED_PROVENANCE_REVIEW",
                    next_action="RESOLVE_ORIGINAL_DATASET_AND_PERIOD; OFFICIAL REDOWNLOAD IF DAMAGED")
            allrows[fid]=a;population["V4"]+=1
    if population["V4"]!=6358:raise RuntimeError("V4_EXPECTED_6358")
    residual_ids=set();overlap=0
    for lane in range(6):
        fmt=ck(api,c,"v097_BF_RESIDUAL_FORMAT_V1_CK_%02d.json"%lane)["done"]
        t1=ck(api,c,"v097_TPEX_LEGACY_RSTA3104_V1_CK_%02d.json"%lane)["done"]
        m1=ck(api,c,"v097_MOPS_HTML_MATRIX_QA_V1_CK_%02d.json"%lane)["done"]
        v2t=ck(api,c,"v097_LEGACY_TPEX_MOPS_V2_TPEx_CK_%02d.json"%lane)["done"]
        v2m=ck(api,c,"v097_LEGACY_TPEX_MOPS_V2_MOPS_CK_%02d.json"%lane)["done"]
        fmtcopy=ck(api,c,"v097_FORMAT_SALVAGE_HOLD_V3_CK_%02d.json"%lane)["done"]
        other=ck(api,c,"v097_NONHTML_RESIDUAL_HOLD_V1_CK_%02d.json"%lane)["done"]
        for row,category,_ in relevant(api,m,c,lane):
            fid=row["file_id"]
            if fid in residual_ids:raise RuntimeError("RESIDUAL_DUPLICATE")
            residual_ids.add(fid)
            src=row.get("source","UNKNOWN")
            b=fmt.get(fid,{})
            a={"file_id":fid,"source_group":"RESIDUAL_1131",
               "source":src,"category":category,
               "source_path":row.get("path"),"source_period":row.get("month"),
               "source_filename":row.get("file_name"),
               "original_qa_status":row.get("prior_status"),
               "format_qa_state":b.get("state","NOT_CHECKED"),
               "format_source_sha256":b.get("sha256"),
               "v097_copy_state":(fmtcopy.get(fid) or other.get(fid) or {}).get("status","STAGE_NOT_PROVED"),
               "formal_market_bronze_certified":False}
            if src=="TPEx":
                v=t1.get(fid,{})
                w=v2t.get(fid,{})
                if w.get("state")=="LEGACY_PARSED_STAGED_PIT_PENDING" or v.get("status")=="TPEX_RSTA3104_PARSE_QA_PASS_PIT_PENDING":
                    a.update(current_bucket="TPEX_PARSED_PIT_AND_MARKET_MASTER_PENDING",
                        staged_dest_id=w.get("dest_id") or v.get("parsed_dest_id"),
                        next_action="OFFICIAL SOURCE/DATE COMPARISON, LISTED OTC HISTORICAL MASTER, THEN RAW BRONZE QA")
                else:
                    a.update(current_bucket="TPEX_NOT_PARSED",
                        parser_error=w.get("error") or v.get("error"),
                        next_action="REPAIR_OR_OFFICIAL_REDOWNLOAD_OLD_PRICE_REPORT")
            elif src=="MOPS":
                v=m1.get(fid,{})
                w=v2m.get(fid,{})
                if v.get("status")=="MOPS_MATRIX_QA_PASS_STAGED_PIT_PENDING" or w.get("state")=="LEGACY_PARSED_STAGED_PIT_PENDING":
                    a.update(current_bucket="MOPS_PARSED_PIT_AND_FINANCIAL_SEMANTICS_PENDING",
                        staged_dest_id=w.get("dest_id") or v.get("parsed_dest_id"),
                        next_action="VERIFY FIRST OFFICIAL PUBLICATION, REVENUE ACCOUNTS/UNITS AND HISTORICAL MARKET MASTER")
                elif "THREE_YEAR_OFFICIAL_GAPS" in str(row.get("file_name") or ""):
                    a.update(current_bucket="MOPS_IFRS_STAGED_SEPARATE_GROUP_MAPPING_PENDING",
                        parser_error=w.get("error"),next_action="VERIFY 3 IFRS GROUP COLUMN MAP, CASHFLOW ACCOUNTS AND DISCLOSURE TIME")
                else:
                    a.update(current_bucket="MOPS_NOT_PARSED",
                        parser_error=w.get("error"),
                        next_action="REVIEW_ENCODING/ROW_SHAPE; OFFICIAL REREQUEST IF NOT FIXABLE")
            elif src=="TDCC":
                a.update(current_bucket="TDCC_FIVE_RESIDUAL_SEMANTICS_PENDING",
                    next_action="CHECK FIVE TDCC HISTORICAL TABLES AGAINST OFFICIAL DATE/SECURITY CODE")
            else:
                a.update(current_bucket="OTHER_27_SOURCE_OR_STRUCTURE_PENDING",
                    next_action="PER_FILE SOURCE/DATASET TYPE, INTEGRITY, DATE, OFFICIAL IF NEEDED")
            if fid in allrows:
                overlap+=1
                allrows[fid]["residual"]=a
                allrows[fid]["current_bucket"]+="__PLUS_RESIDUAL"
            else:allrows[fid]=a
    if len(residual_ids)!=1131:raise RuntimeError("RESIDUAL_EXPECTED_1131:"+str(len(residual_ids)))
    counts=Counter(v["current_bucket"] for v in allrows.values())
    samples=defaultdict(list)
    for fid,item in allrows.items():
        if len(samples[item["current_bucket"]])<10:
            samples[item["current_bucket"]].append({k:item.get(k) for k in
             ("file_id","source","source_period","source_filename","source_path","parser_error","category","next_action")})
    report={"schema":"v097_open_issues_reconciliation_1","run":RUN,
      "at":datetime.now(timezone.utc).isoformat(),"v4_total":6358,
      "residual_total":1131,"overlap_file_ids":overlap,
      "unique_anomaly_files":len(allrows),"by_bucket":dict(counts),
      "samples":dict(samples),
      "market_bronze_promotion_proven_by_this_run":0,
      "note":"Counts statuses by source file, not days. Full market Bronze, Silver and Gold gates separate. 3 IFRS exception formats may have separate staged artifacts.",
      "records":list(allrows.values())}
    put_once(api,q,PREFIX+"_RECORDS_"+RUN+".json",report)
    small={k:v for k,v in report.items() if k!="records"}
    put_once(api,q,PREFIX+"_SUMMARY_"+RUN+".json",small)
    print("OPEN_ISSUES_SUMMARY="+json.dumps(small,ensure_ascii=False),flush=True)
if __name__=="__main__":main()
