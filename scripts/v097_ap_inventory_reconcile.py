#!/usr/bin/env python3
"""Reconcile frozen 82,273 inventory by exact source Drive file ID.
Read-only, auditable; do not conflate 74750 byte-PASS and 7489 exceptions.
"""
import os,json
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_first_pipeline import service,common,match,load_json,put_once
RUN=os.getenv("GITHUB_RUN_ID","manual")
BASE="v097_BRONZE_74750_BASELINE_ROWS_43604879456.json"
ERRORS="v097_FINAL_OPEN_ISSUES_20261113_V1_RECORDS_43603534092.json"
def main():
 api=service();manifests,control,quality,_=common(api)
 b=match(api,quality,BASE);e=match(api,quality,ERRORS)
 if not b or not e:raise RuntimeError("MISSING_FROZEN_BASELINE_OR_EXCEPTION_REPORT")
 baseline=load_json(api,b["id"])["rows"]
 errs=load_json(api,e["id"])["records"]
 bset={r["source_id"] for r in baseline};eset={r["file_id"] for r in errs}
 if len(bset)!=74750 or len(eset)!=7489:
  raise RuntimeError("BASELINE_OR_EXCEPTION_ID_COLLISION")
 audit={}
 for ln in range(12):
  f=match(api,manifests,"v097_BF_AUDIT_LANE_%02d.json"%ln)
  if not f:raise RuntimeError("FROZEN_AUDIT_LANE_MISSING:"+str(ln))
  data=load_json(api,f["id"])
  for row in data["items"]:
   fid=row["file_id"]
   if fid in audit:raise RuntimeError("AUDIT_DUPLICATE_SOURCE_ID:"+fid)
   audit[fid]={"source":row.get("source"),"source_path":row.get("path"),
      "raw_status":row.get("raw_status"),"prior_status":row.get("prior_status"),
      "expected_sha256":row.get("expected_sha256")}
 inv=set(audit)
 if len(inv)!=82273:raise RuntimeError("AUDIT_NOT_82273:"+str(len(inv)))
 missing=sorted(inv-(bset|eset))
 outside=sorted((bset|eset)-inv)
 overlap=sorted(bset&eset)
 info=[{"source_id":fid,**audit[fid]} for fid in missing]
 states=Counter(x["raw_status"] for x in info)
 sources=Counter(x["source"] for x in info)
 result={"schema":"v097_ap_82273_reconcile_1","run_id":RUN,
  "utc":datetime.now(timezone.utc).isoformat(),
  "frozen_inventory":len(inv),"base_qa_pass":len(bset),
  "exception_files":len(eset),"baseline_exception_overlap":len(overlap),
  "unaccounted_file_ids":len(missing),"outside_82273":len(outside),
  "unaccounted_by_status":dict(states),"unaccounted_by_source":dict(sources),
  "unaccounted_records":info,"outside_ids":outside,"overlap_ids":overlap,
  "no_mutation":True,
  "ready_not_inferred":True}
 put_once(api,quality,"v097_AP_INVENTORY_RECONCILE_%s.json"%RUN,result)
 print("AP_RECONCILE="+json.dumps({k:v for k,v in result.items()
    if k not in ("unaccounted_records","outside_ids","overlap_ids")},ensure_ascii=False),flush=True)
 if len(missing)!=34 or outside or overlap:
  print("WARNING_UNEXPECTED_SET_ACCOUNTING check report",flush=True)
if __name__=="__main__":main()
