#!/usr/bin/env python3
"""JARVIS v0.97 independent fail-closed Bronze -> Silver INPUT release gate.

Not a PIT/backtest certification and not a Silver conversion. This version
supports only NDC native Excel cell extracts with immutable SHA and a prior
Drive source-archive readback verification receipt. Other sources HOLD until
their own independent source-specific gates are implemented.
"""
import json,os,re
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import source_api,adapter_version,COHORT,SOURCES,READY
RUN=os.getenv("GITHUB_RUN_ID","manual")
RULE_VERSION="bronze-silver-input-ndc-v1"
RELEASE_FILE="v097_AP_SILVER_INPUT_RELEASE_NDC.json"
def verify_ndc(row,detail,ck):
    """Return evidence-based decision. Parser shape alone cannot grant READY."""
    if ck.get("adapter_version")!=adapter_version("NDC"):
        return "HOLD_STALE_PARSER_VERSION"
    if detail.get("source_id")!=row["source_id"] or detail.get("destination_id")!=row["dest_id"]:
        return "HOLD_RECEIPT_ID_CONFLICT"
    if (detail.get("source_sha256")!=row["sha"] or detail.get("dest_sha256")!=row["sha"]):
        return "HOLD_RECEIPT_SHA_CONFLICT"
    if detail.get("source_path")!=row["source_path"]:
        return "HOLD_RECEIPT_PATH_CONFLICT"
    if detail.get("adapter_version")!=adapter_version("NDC"):
        return "HOLD_RECEIPT_PARSER_VERSION"
    if detail.get("status")!="NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD":
        return "HOLD_NDC_SEMANTIC_NOT_PASSED"
    if detail.get("dataset")!="business_cycle" or detail.get("period")!=row["year"]+"-"+row["month"]:
        return "HOLD_NDC_DATASET_PERIOD"
    if not detail.get("archive_readback_proof_recorded"):
        return "HOLD_NDC_ORIGINAL_ARCHIVE_READBACK"
    if not re.fullmatch("[a-f0-9]{64}",str(detail.get("archive_sha256",""))):
        return "HOLD_NDC_ORIGINAL_ARCHIVE_SHA"
    if not isinstance(detail.get("tables"),int) or detail["tables"]<1:
        return "HOLD_NDC_TABLES"
    if not isinstance(detail.get("cells"),int) or detail["cells"]<1:
        return "HOLD_NDC_CELLS"
    if not isinstance(detail.get("numeric_cells"),int) or detail["numeric_cells"]<1:
        return "HOLD_NDC_NO_NUMERIC_CELLS"
    if not isinstance(detail.get("documented_gaps"),int) or detail["documented_gaps"]<0:
        return "HOLD_NDC_GAP_LEDGER"
    if detail["numeric_cells"]+detail["documented_gaps"]>detail["cells"]:
        return "HOLD_NDC_CELL_ACCOUNTING"
    # Numeric and coverage independent certifications still needed downstream.
    # Bronze input readiness merely permits lossless transformation into Silver.
    return READY
def build(api,control,quality,match,load_json):
    f=match(api,quality,"v097_AP_INPUT_NDC.json")
    if not f:raise RuntimeError("MISSING_NDC_FROZEN_INPUT")
    rows=load_json(api,f["id"])["rows"]
    if len(rows)!=320 or len({r["source_id"] for r in rows})!=320:
        raise RuntimeError("INVALID_NDC_320_COHORT")
    cf=match(api,control,"v097_AP_CHECKPOINT_NDC.json")
    if not cf:raise RuntimeError("NO_NDC_CHECKPOINT")
    checkpoint=load_json(api,cf["id"])["done"]
    result=[];counts=Counter();receipts={}
    for row in rows:
        sid=row["source_id"]
        ck=checkpoint.get(sid)
        if not ck:
            status="NOT_EXAMINED";evidence=""
        elif ck.get("adapter_version")!=adapter_version("NDC"):
            status="RECHECK_PENDING";evidence=ck.get("receipt","")
        else:
            evidence=ck.get("receipt","")
            if not evidence:status="HOLD_MISSING_RECEIPT"
            else:
                if evidence not in receipts:
                    rf=match(api,quality,evidence)
                    if not rf:raise RuntimeError("CHECKPOINT_WITHOUT_IMMUTABLE_RECEIPT:"+evidence)
                    record=load_json(api,rf["id"])
                    if record.get("source")!="NDC" or record.get("adapter_version")!=adapter_version("NDC"):
                        raise RuntimeError("RECEIPT_SOURCE_VERSION_CONFLICT:"+evidence)
                    ritems=record.get("rows",[])
                    if len(ritems)!=len({x.get("source_id") for x in ritems}):
                        raise RuntimeError("RECEIPT_DUPLICATE_IDS:"+evidence)
                    receipts[evidence]={x["source_id"]:x for x in ritems}
                detail=receipts[evidence].get(sid)
                if not detail:
                    status="HOLD_RECEIPT_MISSING_FILE"
                elif ck.get("status")!=detail.get("status"):
                    status="HOLD_CHECKPOINT_RECEIPT_CONFLICT"
                else:status=verify_ndc(row,detail,ck)
        counts[status]+=1
        result.append({"source_id":sid,"destination_id":row["dest_id"],
          "source_sha256":row["sha"],"source_path":row["source_path"],
          "adapter_version":adapter_version("NDC"),"gate_version":RULE_VERSION,
          "status":status,"receipt":evidence,
          "pit_ready_for_backtest":False,
          "silver_input_only":status==READY})
    return {"schema":"v097_silver_input_release_ndc_v1","run":RUN,
      "at":datetime.now(timezone.utc).isoformat(),"gate_version":RULE_VERSION,
      "source":"NDC","cohort":len(rows),"counts":dict(counts),
      "release_approved_for_silver_input":counts[READY]>0,
      "pit_backtest_approved":False,
      "silver_gold_executed":False,"records":result}
def selftest():
 row={"source_id":"a","dest_id":"b","sha":"f"*64,"source_path":"2021/NDC/2021-04/test.json","year":"2021","month":"04"}
 ck={"adapter_version":adapter_version("NDC")}
 detail={"source_id":"a","destination_id":"b","source_sha256":"f"*64,"dest_sha256":"f"*64,
 "source_path":row["source_path"],"adapter_version":adapter_version("NDC"),
 "status":"NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD",
 "dataset":"business_cycle","period":"2021-04","archive_readback_proof_recorded":True,
 "archive_sha256":"a"*64,"tables":5,"cells":34,"numeric_cells":33,"documented_gaps":0}
 assert verify_ndc(row,detail,ck)==READY
 assert verify_ndc(row,{**detail,"archive_readback_proof_recorded":False},ck)=="HOLD_NDC_ORIGINAL_ARCHIVE_READBACK"
 assert verify_ndc(row,{**detail,"dest_sha256":"0"*64},ck)=="HOLD_RECEIPT_SHA_CONFLICT"
 assert verify_ndc(row,{**detail,"status":"HOLD_NDC_UNDOCUMENTED_CELL_GAP"},ck)=="HOLD_NDC_SEMANTIC_NOT_PASSED"
 print("NDC_SILVER_INPUT_GATE_SELFTEST_PASS")
def main():
 import sys
 if len(sys.argv)>1 and sys.argv[1]=="selftest":return selftest()
 api,control,quality,match,load_json,put_once,_,_=source_api()
 report=build(api,control,quality,match,load_json)
 put_once(api,quality,"v097_AP_SILVER_INPUT_RELEASE_NDC_"+RUN+".json",report)
 # Last-run pointer is immutable-run named, not a mutable global release.
 print("NDC_SILVER_INPUT_GATE_RESULT="+json.dumps({
  k:v for k,v in report.items() if k!="records"},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
