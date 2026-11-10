#!/usr/bin/env python3
"""v0.97 non-destructive reconciliation of existing 12 frozen R2 shards.

Reads ONLY prior manifests/receipts and issue-queue evidence. Does not download
source bytes, overwrite checkpoints, alter Bronze/Silver/Gold, or certify PIT.
"""
import json, os, re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from scripts.v097_bronze_content_qa import service,children,load_json,save
from scripts.v097_round2_verify import dirs,one

EXPECTED=82273
RUN=os.environ.get("GITHUB_RUN_ID","manual")
RECEIPT=re.compile(r"^v097_R2_(\d+)_(\d\d)_(\d\d)\.json$")
def now(): return datetime.now(timezone.utc).isoformat()

def classification(status):
    if not status: return "UNVERIFIED"
    if status.startswith("QUARANTINED_"):return "NG_EVIDENCE"
    if status.startswith("EXCEPTION_"):return "BLOCKED"
    if status in ("UNRESOLVED",):return "UNVERIFIED"
    # Structural parsing is only evidence for a stage; not dataset or PIT PASS.
    return "PARTIAL"

def lane(api,k):
    m,_,q=dirs(api)
    mf=one(api,m,"v097_R2_MANIFEST_%02d.json"%k)
    if not mf:raise RuntimeError("Missing frozen original manifest for lane %s"%k)
    d=load_json(api,mf["id"])
    if d.get("lane")!=k or d.get("schema")!="r2_manifest_1":
        raise RuntimeError("Unexpected frozen manifest schema")
    files=d["files"]
    ids={f["file_id"] for f in files}
    if len(ids)!=len(files):raise RuntimeError("Duplicate file IDs in manifest %d"%k)
    receipts=[]
    for f in children(api,q):
        match=RECEIPT.fullmatch(f["name"])
        if match and int(match.group(2))==k:
            receipts.append((int(match.group(1)),int(match.group(3)),f))
    receipts.sort()
    observed={}; conflicting=set(); unreadable=[]
    for _,_,f in receipts:
        try:
            r=load_json(api,f["id"])
            if r.get("schema")!="r2_receipt_1" or r.get("lane")!=k:raise ValueError("bad schema/lane")
            for item in r["results"]:
                fid=item.get("file_id")
                if fid not in ids:raise ValueError("receipt file outside frozen manifest")
                prior=observed.get(fid)
                if prior and prior.get("sha256") and item.get("sha256") and prior["sha256"]!=item["sha256"]:
                    conflicting.add(fid)
                observed[fid]=item
        except Exception as e:
            unreadable.append({"name":f["name"],"error":type(e).__name__})
    counts=Counter()
    by_source=defaultdict(Counter)
    for item in files:
        fid=item["file_id"]
        status="CONFLICT" if fid in conflicting else classification(observed.get(fid,{}).get("status"))
        counts[status]+=1
        by_source[item.get("source") or "UNKNOWN"][status]+=1
    if sum(counts.values())!=len(files):raise RuntimeError("Reconciliation arithmetic failed")
    result={
      "schema":"v097_reconciliation_lane_v1","run_id":RUN,"created_at":now(),"lane":k,
      "manifest_id":mf["id"],"manifest_files":len(files),"receipt_count":len(receipts),
      "receipt_covered_unique":len(observed),"receipt_unreadable":unreadable,
      "status_counts":dict(counts),"source_status":{s:dict(c) for s,c in by_source.items()},
      "R3_issue_queue_is_not_equivalent_to_confirmed_data_error":True,
      "classification_rules":{
        "UNVERIFIED":"no valid R2 receipt","PARTIAL":"a staged structural/parse result, PIT and numeric semantics not certified",
        "NG_EVIDENCE":"R2 quarantine evidence only; requires independent diagnosis before confirmed content NG",
        "BLOCKED":"technical parser/size/streaming limitation","CONFLICT":"same file ID has inconsistent SHA"},
      "full_dataset_pass_count_certified":0,
      "market_data_modified":False
    }
    save(api,q,"v097_RECON_%s_lane%02d.json"%(RUN,k),result)
    print("RECON_LANE",json.dumps({"lane":k,"total":len(files),"states":dict(counts),"receipts":len(receipts),"unreadable":len(unreadable)}),flush=True)

def aggregate(api):
    m,_,q=dirs(api)
    state=Counter(); source=defaultdict(Counter); rows=[]; missing=[]
    for k in range(12):
        f=one(api,q,"v097_RECON_%s_lane%02d.json"%(RUN,k))
        if not f:
            missing.append(k);continue
        d=load_json(api,f["id"])
        if d.get("run_id")!=RUN or d.get("lane")!=k:raise RuntimeError("Run mismatch")
        rows.append(d)
        state.update(d["status_counts"])
        for s,counts in d["source_status"].items():source[s].update(counts)
    total=sum(state.values())
    checks={"twelve_lanes_present":len(rows)==12,"total_matches_frozen_eligible":total==EXPECTED,
            "all_receipts_readable":not any(r["receipt_unreadable"] for r in rows),
            "no_sha_conflict":state.get("CONFLICT",0)==0}
    report={"schema":"v097_reconciliation_total_v1","run_id":RUN,"created_at":now(),
      "scope":"FROZEN_R2_MANIFEST_AND_EXISTING_R2_RECEIPTS_ONLY",
      "units":"unique candidate file IDs, NOT row counts or expected trading days",
      "eligible_expected":EXPECTED,"reconciled":total,"counts":dict(state),
      "by_source":{s:dict(c) for s,c in source.items()},
      "checks":checks,"missing_lanes":missing,
      "release_approved":False,"bulk_redownload_approved":False,
      "full_data_pass_certified":False,
      "decision":"RECONCILIATION_ONLY_NO_DATASET_RELEASE",
      "next":"Join latest R3 per-file repair/exception evidence using immutable file ID + SHA + code/rule versions; approve only affected stage for delta recheck"}
    save(api,q,"v097_RECON_%s_summary.json"%RUN,report)
    print("RECON_SUMMARY",json.dumps(report,ensure_ascii=False),flush=True)
    if not all(checks.values()):raise RuntimeError("Reconciliation incomplete; see immutable summary")

if __name__=="__main__":
    api=service()
    mode=os.environ.get("RECON_MODE","lane")
    if mode=="lane":
        k=int(os.environ["RECON_LANE"])
        if k<0 or k>=12:raise ValueError("bad lane")
        lane(api,k)
    elif mode=="aggregate": aggregate(api)
    else:raise ValueError("unknown mode")
