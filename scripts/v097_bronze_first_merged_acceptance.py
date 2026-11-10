#!/usr/bin/env python3
"""Merged Bronze-first release gate: deterministic tests + live read-only receipt cross-audit.

This script never touches Silver or Gold and never modifies original/bronze market bytes.
The live report only describes evidence; failed or missing QA cannot be marked passed.
"""
import os,re,json,hashlib,io,zipfile
from collections import Counter,defaultdict
from scripts.v097_bronze_first_batch_v3 import verify_identity,receipt_name
from scripts.v097_bronze_first_pipeline import classify,raw_integrity,service,common,match,load_json,save

RUN=os.environ.get("GITHUB_RUN_ID","manual")
EXPECTED_INVENTORY=82273
STATES={"COPY_MATCHED_PENDING_INDEPENDENT_QA","COPY_EXCEPTION"}
QA_PASS="BRONZE_BYTE_PROVENANCE_AND_PATH_PASS"

def offline_tests():
 checks=[]
 def yes(name,condition):
  assert condition,name
  checks.append(name)
 valid={"source":"TWSE","year":"2024","month":"2024-06",
        "path":"2024/TWSE/2024-06/TWSE_BULK_2024-06-12.json",
        "file_name":"TWSE_BULK_2024-06-12.json"}
 yes("source_date_path",verify_identity(valid) is None)
 for label,record in [
  ("wrong_source",{**valid,"path":"2024/TPEx/2024-06/foo.json"}),
  ("wrong_month",{**valid,"path":"2024/TWSE/2024-05/foo.json"}),
  ("control_sidecar",{**valid,"file_name":"2024-01-31_HISTORICAL_CORRECTED_R3.json.receipt.json"}),
  ("control_manifest",{**valid,"file_name":"SOURCE.manifest.json"}),
  ("TDCC_unverified_stock",{"source":"TDCC","year":"2025","month":"2025-11",
     "path":"2025/TDCC/2025-11/distribution_20251107_YJR4_x.html",
     "file_name":"distribution_20251107_YJR4_x.html","prior_status":"TDCC_TABLE_NUMERIC_PENDING"})]:
  try:verify_identity(record)
  except RuntimeError:checks.append("blocks_"+label)
  else:raise AssertionError("unsafe_original_allowed:"+label)
 yes("zip_crc",raw_integrity(_validzip(),"native.zip")=="RAW_STRUCTURE_PASS")
 yes("bad_zip_blocked",raw_integrity(b"PK\x03\x04bad","native.zip")!="RAW_STRUCTURE_PASS")
 yes("empty_rejected",raw_integrity(b"","example.json")!="RAW_STRUCTURE_PASS")
 yes("stable_receipt_names",receipt_name("COPY",0,["foo","bar"])==receipt_name("COPY",0,["foo","bar"]))
 r={"file_id":"1","source":"TWSE","path":"2024/TWSE/2024-06/good.json","size_bytes":4}
 good={"file_id":"1","source":"TWSE","path":r["path"],"sha256":"a"*64,"bytes":4,"status":"JSON_ROWS_PARSED_PIT_PENDING"}
 yes("R2_raw_basic_candidate_not_pit_certification",classify(r,good)[0]=="A_PASS_CANDIDATE_R2_BYTES")
 yes("R2_missing_not_pass",classify(r,None)[0]!="A_PASS_CANDIDATE_R2_BYTES")
 yes("R2_hash_conflict_block",classify(r,{**good,"sha256":"invalid"})[0]!="A_PASS_CANDIDATE_R2_BYTES")
 print("MERGED_BRONZE_OFFLINE_PASS",len(checks),json.dumps(checks))
 return checks

def _validzip():
 b=io.BytesIO()
 with zipfile.ZipFile(b,"w") as z:z.writestr("member.txt","ok")
 return b.getvalue()

def check_live():
 api=service()
 m,c,q,bronze=common(api)
 audit=Counter()
 missing_audit=[]
 for lane in range(12):
  f=match(api,m,"v097_BF_AUDIT_LANE_%02d.json"%lane)
  if not f:missing_audit.append(lane);continue
  d=load_json(api,f["id"])
  if d.get("lane")!=lane or sum(d.get("counts",{}).values())!=len(d.get("items",[])):
   raise RuntimeError("AUDIT_MANIFEST_CONSERVATION_FAILURE:"+str(lane))
  audit.update(d["counts"])
 copy=Counter();qa=Counter();wrong=[];missing_qa=[];nonqualifying=[];unique_ids=set()
 checkpoint_files=[]
 for lane in range(6):
  fc=match(api,c,"v097_BF_V3_COPY_CK_%02d.json"%lane)
  fq=match(api,c,"v097_BF_V3_QA_CK_%02d.json"%lane)
  cp=load_json(api,fc["id"]) if fc else {"done":{}}
  qp=load_json(api,fq["id"]) if fq else {"done":{}}
  if fc:checkpoint_files.append(fc["id"])
  if fq:checkpoint_files.append(fq["id"])
  if cp.get("lane",lane)!=lane or qp.get("lane",lane)!=lane:
   raise RuntimeError("LANE_CHECKPOINT_CONFLICT")
  cdone=cp.get("done",{})
  qdone=qp.get("done",{})
  for fid,row in cdone.items():
   if fid in unique_ids:raise RuntimeError("DUPLICATE_FILE_ID_ACROSS_LANES")
   unique_ids.add(fid)
   state=row.get("state","NO_STATE");copy[state]+=1
   if state not in STATES:raise RuntimeError("UNKNOWN_COPY_STATE:"+state)
   path=str(row.get("dest_path") or "")
   if state=="COPY_MATCHED_PENDING_INDEPENDENT_QA":
    if not row.get("dest_id") or not re.fullmatch("[0-9a-f]{64}",row.get("sha") or ""):
     wrong.append({"file_id":fid,"reason":"MISSING_COPY_ID_OR_HASH"})
    if path.lower().endswith((".receipt.json",".manifest.json",".checkpoint.json")):
     nonqualifying.append({"file_id":fid,"reason":"CONTROL_SIDECAR_WAS_COPIED","path":path})
    if not re.search(r"/(?:19|20)\d{2}/(?:0[1-9]|1[0-2])/",path):
     wrong.append({"file_id":fid,"reason":"BAD_DEST_YEAR_MONTH"})
    if fid not in qdone:missing_qa.append(fid)
  for fid,row in qdone.items():
   if fid not in cdone:raise RuntimeError("ORPHAN_QA_WITHOUT_COPY:"+fid)
   state=row.get("state","NO_STATE");qa[state]+=1
   if state==QA_PASS and cdone[fid].get("state")!="COPY_MATCHED_PENDING_INDEPENDENT_QA":
    raise RuntimeError("QA_PASS_WITHOUT_COPIED_MATCH:"+fid)
 eligible=audit.get("A_PASS_CANDIDATE_R2_BYTES",0)
 if not missing_audit and sum(audit.values())!=EXPECTED_INVENTORY:
  raise RuntimeError("82K_CANDIDATE_RECONCILIATION_FAILED")
 if len(unique_ids)>eligible:raise RuntimeError("MIGRATED_MORE_THAN_APPROVED")
 if sum(qa.values())>copy.get("COPY_MATCHED_PENDING_INDEPENDENT_QA",0):
  raise RuntimeError("QA_GREATER_THAN_COPIED")
 decision="BRONZE_NOT_CERTIFIED"
 blockers=[]
 if missing_audit:blockers.append("MISSING_AUDIT_LANES")
 if missing_qa:blockers.append("INCOMPLETE_DESTINATION_QA")
 if nonqualifying:blockers.append("CONTROL_SIDECAR_PRESENT_IN_BRONZE")
 if wrong:blockers.append("COPY_RECEIPT_ID_HASH_OR_PATH_ANOMALY")
 if audit.get("RAW_UNKNOWN_NO_R2_RECEIPT",0):blockers.append("V093_RAW_RECEIPTS_MISSING")
 if audit.get("RAW_REVIEW_QUARANTINED",0):blockers.append("V093_RAW_EXCEPTIONS_UNRESOLVED")
 if eligible>len(unique_ids):blockers.append("BRONZE_COPY_INCOMPLETE")
 blockers.extend(["XQ_IMPORT_PENDING","FINMIND_699_PENDING","SOURCE_CALENDAR_COVERAGE_UNCERTIFIED"])
 report={"schema":"v097_bronze_first_merged_acceptance_1","run_id":RUN,
 "inventory_expected":EXPECTED_INVENTORY,"audit_counts":dict(audit),
 "audit_missing_lanes":missing_audit,"copy_counts":dict(copy),"qa_counts":dict(qa),
 "unique_copy_attempted":len(unique_ids),"copy_eligible":eligible,
 "copy_remaining":max(0,eligible-len(unique_ids)),
 "qa_missing_count":len(missing_qa),"wrong_copy_receipts_count":len(wrong),
 "suspected_control_sidecars_count":len(nonqualifying),
 "control_sidecar_samples":nonqualifying[:20],"bad_copy_samples":wrong[:20],
 "blockers":blockers,"decision":decision,
 "silver_gold_not_executed":True,
 "note":"Merged tests are one read-only inspection; not historic market coverage release or Silver/Gold QA"}
 save(api,q,"v097_BF_MERGED_ACCEPTANCE_%s.json"%RUN,report)
 print("BRONZE_MERGED_ACCEPTANCE",json.dumps(report,ensure_ascii=False),flush=True)
 return report

if __name__=="__main__":
 checks=offline_tests()
 if os.getenv("BF_ACCEPTANCE_LIVE","0")=="1":check_live()
