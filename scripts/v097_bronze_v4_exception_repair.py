#!/usr/bin/env python3
"""v0.97 V3 exception-only triage and bounded repair.
Keeps v0.93 immutable. Never changes the original V3 copy/QA checkpoints.
A successful repaired copy is counted ONLY after independent source+destination SHA QA.
Official download requires a verified source/dataset/period mapping; this script does not guess URLs.
"""
import os, json, re, hashlib
from collections import Counter
from datetime import datetime, timezone
from scripts.v097_bronze_first_pipeline import common, match, load_json, put_once, upsert, service
from scripts.v097_bronze_first_batch_v3 import ck_name, copy_one, qa_one, verify_identity

RUN=os.getenv("GITHUB_RUN_ID","manual")
LANES=range(6)
RETRY_CAP=int(os.getenv("BF_REPAIR_RETRY_CAP","15"))
TRANSIENT=("HttpError","Timeout","ConnectionError","SSLError","OSError","429","500","502","503","504","RateLimit")
CODE_MAP={
    "CONTROL_SIDECAR_NOT_MARKET_RAW":"CONTROL_METADATA",
    "SOURCE_PATH_PERIOD_NOT_GROUNDED":"IDENTITY_PATH",
    "TDCC_SYMBOL_DATE_NOT_EVIDENCED":"TDCC_IDENTITY",
    "TDCC_FILENAME_DATE_MISMATCH":"TEMPORAL",
    "ORIGINAL_FILENAME_CHANGED":"SOURCE_IDENTITY_CHANGED",
    "SOURCE_EMPTY_OR_TOO_LARGE":"STORAGE_OR_LIMIT",
    "SOURCE_SIZE_CHANGED":"STORAGE_CHANGED",
    "SOURCE_MD5_CHANGED":"STORAGE_CHANGED",
    "SOURCE_HASH_CHANGED":"STORAGE_CHANGED",
    "RAW_STRUCTURE_DID_NOT_PASS":"CONTENT_STRUCTURE",
    "DESTINATION_SHA_OR_SIZE_MISMATCH":"DESTINATION_INTEGRITY",
}
def timestamp():return datetime.now(timezone.utc).isoformat()
def classify(err):
    e=str(err or "")
    name=e.split(":",1)[-1].split(":",1)[0]
    if any(k.lower() in e.lower() for k in TRANSIENT):return "TRANSIENT_RETRY"
    for k,v in CODE_MAP.items():
        if k in e:return v
    return "UNCLASSIFIED_REVIEW"
def audit_lookup(api,manifest,copy_lane):
    result={}
    for lane in range(copy_lane,12,6):
        af=match(api,manifest,"v097_BF_AUDIT_LANE_%02d.json"%lane)
        if not af:raise RuntimeError("MISSING_AUDIT_LANE_%d"%lane)
        for row in load_json(api,af["id"])["items"]:
            result[row["file_id"]]=row
    return result
def rescue_lookup(api,control,copy_lane):
    done={}
    for lane in range(copy_lane,12,6):
        f=match(api,control,"v097_BF_RAW_RESCUE_V1_CK_%02d.json"%lane)
        if f:
            done.update(load_json(api,f["id"]).get("done",{}))
    return done
def candidate(row,rescued):
    if row.get("raw_status")=="A_PASS_CANDIDATE_R2_BYTES":return row
    p=rescued.get(row["file_id"],{})
    if row.get("raw_status")=="RAW_UNKNOWN_NO_R2_RECEIPT" and p.get("state")=="RAW_RESCUED_BASIC_CANDIDATE" and p.get("sha256") and p.get("bytes"):
        r=dict(row)
        r.update(expected_sha256=p["sha256"],size_bytes=p["bytes"],raw_status="A_PASS_CANDIDATE_RESCUE_BYTES",prior_status="RAW_RESCUED_BASIC_CANDIDATE")
        return r
    return None
def load_progress(api,control,lane):
    name="v097_BF_REPAIR_V4_CK_%02d.json"%lane
    f=match(api,control,name)
    d=load_json(api,f["id"]) if f else {"schema":"v097_bf_repair_v4_checkpoint_1","lane":lane,"repaired":{}}
    if d["schema"]!="v097_bf_repair_v4_checkpoint_1" or d["lane"]!=lane:raise RuntimeError("BAD_REPAIR_CHECKPOINT")
    return name,d
def triage_lane(api,lane):
    m,c,q,_=common(api)
    cf=match(api,c,ck_name("COPY",lane))
    if not cf:raise RuntimeError("MISSING_V3_COPY_CHECKPOINT")
    ck=load_json(api,cf["id"])
    exceptions={fid:v for fid,v in ck["done"].items() if v.get("state")=="COPY_EXCEPTION"}
    lookup=audit_lookup(api,m,lane);rescued=rescue_lookup(api,c,lane)
    name,progress=load_progress(api,c,lane)
    rows=[]; counts=Counter();retry_left=RETRY_CAP;new_pass=0
    for fid,detail in exceptions.items():
        cls=classify(detail.get("error"))
        prior=progress["repaired"].get(fid)
        row={"file_id":fid,"lane":lane,"prior_error":detail.get("error"),"category":cls,
             "source_path":detail.get("source_path"),"source_sha":detail.get("sha"),
             "original_state":"COPY_EXCEPTION","status":"NEEDS_SOURCE_OR_ADAPTER_REVIEW"}
        if prior and prior.get("state")=="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":
            row.update(status="REPAIR_ALREADY_VERIFIED",repaired_destination_id=prior.get("dest_id"))
        elif cls=="TRANSIENT_RETRY" and retry_left>0:
            original=lookup.get(fid)
            clean=candidate(original,rescued) if original else None
            retry_left-=1
            if clean:
                copied=copy_one(api,common(api)[3],clean,lane)
                if copied["state"]=="COPY_MATCHED_PENDING_INDEPENDENT_QA":
                    check=qa_one(api,fid,{"sha":copied["sha"],"state":copied["state"],
                        "dest_id":copied["destination_id"],"dest_path":copied["destination_path"],
                        "dest_folder_id":copied["destination_folder_id"]},lane)
                    if check["state"]=="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS":
                        row.update(status="REPAIR_QA_PASS",repaired_destination_id=copied["destination_id"],
                                   new_sha=check["sha"])
                        progress["repaired"][fid]={"state":check["state"],"sha":check["sha"],
                                                 "dest_id":copied["destination_id"],"run":RUN}
                        new_pass+=1
                    else:row.update(status="REPAIR_QA_FAILED",repair_error=check.get("error"))
                else:row.update(status="RETRY_FAILED",repair_error=copied.get("error"))
            else:row.update(status="RAW_EVIDENCE_NOT_AUTHORIZED")
        elif cls=="TRANSIENT_RETRY":
            row.update(status="TRANSIENT_DEFERRED_CAP")
        if row["status"]=="NEEDS_SOURCE_OR_ADAPTER_REVIEW":
            row["next_action"]="SOURCE_IDENTITY_OR_FORMAT_REVIEW; OFFICIAL_REDOWLOAD_ONLY_WITH_VERIFIED_DATASET_URL_PERIOD"
        counts[(cls,row["status"])]+=1
        rows.append(row)
    # Immutable per-run per-lane evidence first, then update only this NEW repair checkpoint.
    receipt="v097_BF_REPAIR_V4_%s_L%02d.json"%(RUN,lane)
    put_once(api,q,receipt,{"schema":"v097_bf_repair_v4_lane_1","run":RUN,"lane":lane,
                             "utc":timestamp(),"total_exceptions":len(exceptions),"rows":rows})
    upsert(api,c,name,progress)
    print("V4_LANE="+json.dumps({"lane":lane,"exceptions":len(exceptions),
         "new_independent_qa_pass":new_pass,"categories":{str(k):v for k,v in counts.items()},
         "receipt":receipt},ensure_ascii=False),flush=True)
def aggregate(api):
    m,c,q,_=common(api)
    rows=[]
    for lane in LANES:
        f=match(api,q,"v097_BF_REPAIR_V4_%s_L%02d.json"%(RUN,lane))
        if not f:raise RuntimeError("MISSING_REPAIR_V4_LANE_%d"%lane)
        rows.extend(load_json(api,f["id"])["rows"])
    cats=Counter(r["category"] for r in rows)
    statuses=Counter(r["status"] for r in rows)
    # A repaired case only passes after independent QA; old V3 counters are not modified.
    result={"schema":"v097_bf_repair_v4_consolidated_1","run":RUN,"utc":timestamp(),
      "copy_exception_original_count":len(rows),"by_category":dict(cats),"by_state":dict(statuses),
      "verified_repaired_this_run":statuses["REPAIR_QA_PASS"],
      "remaining_review":sum(v for k,v in statuses.items() if k not in ("REPAIR_QA_PASS","REPAIR_ALREADY_VERIFIED")),
      "official_downloads":0,
      "next":"VERIFY_OFFICIAL_DATASET_SOURCE_URL_AND_PERIOD_MAPPING; RUN_CONTENT_AND_SOURCE_CALENDAR_QA; REVALIDATE_REPAIRED_VERSIONS",
      "source_unchanged":True,"legacy_checkpoints_unchanged":True,
      "release_certified":False,
      "note":"Counts are frozen V3 COPY_EXCEPTION outcomes; not unique semantic errors or certified missing dataset-periods. No fictitious official retrieval."}
    put_once(api,q,"v097_BF_REPAIR_V4_SUMMARY_%s.json"%RUN,result)
    print("V4_SUMMARY="+json.dumps(result,ensure_ascii=False),flush=True)
def selftest():
    assert classify("HttpError: 429")=="TRANSIENT_RETRY"
    assert classify("RuntimeError:SOURCE_PATH_PERIOD_NOT_GROUNDED")=="IDENTITY_PATH"
    assert classify("RuntimeError:SOURCE_HASH_CHANGED")=="STORAGE_CHANGED"
    assert classify("RuntimeError:CONTROL_SIDECAR_NOT_MARKET_RAW")=="CONTROL_METADATA"
    print("V4_SELFTEST_PASS")
if __name__=="__main__":
    mode=os.getenv("BF_REPAIR_MODE","selftest")
    if mode=="selftest":selftest()
    elif mode=="lane":triage_lane(service(),int(os.environ["BF_REPAIR_LANE"]))
    elif mode=="aggregate":aggregate(service())
    else:raise SystemExit("UNKNOWN_MODE")
