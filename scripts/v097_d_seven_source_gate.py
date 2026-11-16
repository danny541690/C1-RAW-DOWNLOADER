#!/usr/bin/env python3
"""Seven-source D-level incremental evidence gate: never promote on format alone.

Inputs are immutable A receipts, B/C native V2 checkpoints, original per-source
Silver-input release, and optional externally attested numerical comparison
record (independent official + independent provider; verified hashes/values).
A provider URL or manifest self-assertion is never independently verified data.
Write new D decision checkpoint, not prior original Bronze or Silver release.
"""
import json,os,sys,re
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from scripts.v097_bronze_autopilot import source_api,SOURCES,READY,COHORT

VERSION="v097-d-three-way-gate-1"
BATCH=max(1,min(300,int(os.getenv("D_BATCH","120"))))
NUMERIC_FIELDS={
 "TWSE":("open","high","low","close","volume","amount"),
 "TPEx":("open","high","low","close","volume","amount"),
 "MOPS":("account_value",),
 "TDCC":("holders","shares","percentage"),
 "TAIFEX":("settlement","volume","open_interest"),
 "NDC":("value",),
 "FinMind":("value",)
}
EVIDENCE_REQUIRED=("dataset","business_key","as_of","original_sha256",
                   "official_source_uri","official_retrieved_at",
                   "official_payload_sha256","third_party_source_uri",
                   "third_party_retrieved_at","third_party_payload_sha256",
                   "metric","original_value","official_value","third_party_value",
                   "unit","publication_pit_as_of")
def good_hash(h):return bool(re.fullmatch("[a-f0-9]{64}",str(h or "")))
def dec(v):
 try:
  v=Decimal(str(v))
  return v if v.is_finite() else None
 except (InvalidOperation,ValueError,TypeError):return None
def independently_attested(row,e):
 if not isinstance(e,dict) or any(k not in e for k in EVIDENCE_REQUIRED):
  return False,"MISSING_TRIPLE_NUMERIC_EVIDENCE"
 if any(not good_hash(e[k]) for k in ("original_sha256","official_payload_sha256","third_party_payload_sha256")):
  return False,"INVALID_EVIDENCE_HASH"
 if e["original_sha256"]!=row["sha"]:return False,"SOURCE_SHA_MISMATCH"
 if not e.get("official_fetch_receipt_id") or not e.get("third_party_fetch_receipt_id"):
  return False,"MISSING_INDEPENDENT_FETCH_RECEIPTS"
 if not e.get("original_extracted_value_receipt_id"):
  return False,"MISSING_ORIGINAL_VALUE_EXTRACTION_RECEIPT"
 if not e.get("publisher_host_verified") or not e.get("third_party_host_verified"):
  return False,"UNVERIFIED_PUBLISHER_DOMAINS"
 if not e.get("stock_market_asof_verified") or not e.get("dataset_field_version_verified"):
  return False,"DATASET_OR_SECURITY_ASOF_NOT_VERIFIED"
 if not e.get("publication_pit_verified"):return False,"PUBLICATION_PIT_NOT_VERIFIED"
 if len({e["official_source_uri"],e["third_party_source_uri"]})!=2:
  return False,"INDEPENDENT_SOURCES_NOT_DISTINCT"
 if not e.get("same_business_key_verified") or not e.get("same_units_verified"):
  return False,"KEY_OR_UNIT_NOT_PROVEN"
 if e["metric"] not in NUMERIC_FIELDS[row["source"]]:
  return False,"UNKNOWN_SOURCE_NATIVE_METRIC"
 values=[dec(e[k]) for k in ("original_value","official_value","third_party_value")]
 if any(x is None for x in values):return False,"INVALID_DECIMAL"
 if values[0]!=values[1] or values[0]!=values[2]:
  return False,"TRIPLE_NUMERIC_MISMATCH"
 return True,"TRIPLE_NUMERIC_EVIDENCE_MATCHED"
def decision(row,old_release,probe,evidence=None):
 if old_release.get("source_id")!=row["source_id"] or old_release.get("source_sha256")!=row["sha"]:
  raise RuntimeError("FORMAL_GATE_SOURCE_SHA_CONFLICT")
 if old_release.get("status")==READY:
  return {"status":"READY_PRESERVED_EXISTING","newly_ready":False,
          "basis":"EXISTING_IMMUTABLE_FORMAL_SILVER_INPUT_GATE"}
 if not probe or probe.get("source_id")!=row["source_id"]:
  return {"status":"HOLD_NO_SOURCE_NATIVE_V2_EVIDENCE","newly_ready":False}
 if probe.get("bronze_sha256")!=row["sha"] or not probe.get("input_bytes_sha_checked"):
  return {"status":"HOLD_ORIGINAL_SHA_NOT_PROVEN","newly_ready":False}
 status=str(probe.get("status",""))
 if status.startswith(("HOLD_","RETRY_")):
  return {"status":"HOLD_SOURCE_NATIVE_SEMANTIC","reason":status,"newly_ready":False}
 if not evidence:return {"status":"HOLD_THREE_WAY_NUMERIC_NOT_INDEPENDENTLY_PROVEN",
                         "source_native_status":status,"newly_ready":False}
 passed,reason=independently_attested(row,evidence)
 if not passed:return {"status":"HOLD_"+reason,"newly_ready":False}
 if not evidence.get("all_rows_verified") or not evidence.get("all_fields_verified"):
  return {"status":"HOLD_PARTIAL_TRIPLE_PROOF_NOT_ENOUGH","newly_ready":False}
 # D stage candidate only; authoritative original Silver input gate remains
 # unchanged until a dedicated signed, policy-reviewed release consumes it.
 return {"status":"D_CANDIDATE_FULL_THREE_WAY_ATTESTED",
         "newly_ready":False,"candidate_for_official_release":True,
         "evidence_receipts":[evidence["official_fetch_receipt_id"],
             evidence["third_party_fetch_receipt_id"],
             evidence["original_extracted_value_receipt_id"]]}
def run(src):
 if src not in SOURCES:raise RuntimeError("SOURCE_REQUIRED")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 inf=match(api,quality,"v097_AP_INPUT_"+src+".json")
 nf=match(api,control,"v097_SEVEN_FORMAT_V2_CK_"+src+".json")
 if not inf or not nf:raise RuntimeError("FROZEN_INPUT_OR_V2_CHECKPOINT_MISSING")
 rows=load_json(api,inf["id"])["rows"]
 byid={r["source_id"]:r for r in rows}
 native=load_json(api,nf["id"])["done"]
 # Full formal release gate for the same frozen cohort from the LAST COMPLETE
 # seven-source published set, never mix arbitrary unpaired source runs.
 from scripts.v097_seven_parser_triage import latest_complete
 rid,gates=latest_complete(api,quality,match,load_json)
 gate={r["source_id"]:r for r in gates[src]["records"]}
 if set(gate)!=set(byid):raise RuntimeError("COHORT_FORMAL_VS_INPUT_MISMATCH")
 # Locate externally retrieved one-row witnesses for C -> D traceability.
 # These reports are partial by design and never satisfy all-file release.
 witness_by_id={}
 if src in ("TWSE","TPEx"):
  from scripts.v097_bronze_content_qa import children
  prefix="v097_INDEPENDENT_CLOSE_WITNESS_"+src+"_"
  candidates=[x for x in children(api,quality) if x["name"].startswith(prefix) and x["name"].endswith(".json")]
  if candidates:
   latest=max(candidates,key=lambda x:int(re.search(r"_([0-9]+)[.]json$",x["name"]).group(1)))
   witness_report=load_json(api,latest["id"])
   for item in witness_report.get("records",[]):
    if item.get("source_id") and item.get("status")=="THREE_WAY_DAILY_CLOSE_MATCHED_SAMPLE":
     witness_by_id[item["source_id"]]={"source_report":latest["name"],
       "stock_id":item["stock_id"],"trade_date":item["trade_date"],
       "original_sha256":item.get("original_sha256"),
       "official_response_sha256":item.get("official_fetch",{}).get("response_sha256"),
       "third_party_response_sha256":item.get("finmind_fetch",{}).get("response_sha256")}
 evidence_file=match(api,quality,"v097_INDEPENDENT_TRIPLE_NUMERIC_EVIDENCE_"+src+".json")
 attest=load_json(api,evidence_file["id"]).get("by_source_id",{}) if evidence_file else {}
 name="v097_D_THREE_WAY_GATE_CK_"+src+".json"
 previous=match(api,control,name)
 ck=load_json(api,previous["id"]) if previous else {
  "schema":"v097_d_three_way_gate_checkpoint","source":src,"version":VERSION,"done":{}}
 if ck.get("version")!=VERSION:raise RuntimeError("D_VERSION_CONFLICT")
 if set(ck["done"])-set(byid):raise RuntimeError("D_CHECKPOINT_ORPHAN")
 # Existing READY must not be reprocessed; however tally for accurate reporting.
 # New witness evidence can arrive after the corresponding D row was gated.
 # Recheck only newly proven sample IDs; never replay all already accepted rows.
 refreshed=[byid[sid] for sid in witness_by_id if sid in ck["done"] and
   ck["done"][sid].get("status")=="HOLD_THREE_WAY_NUMERIC_NOT_INDEPENDENTLY_PROVEN"]
 new_rows=[r for r in rows if r["source_id"] not in ck["done"] and
          (r["source_id"] in native or gate[r["source_id"]]["status"]==READY)]
 pending=refreshed[:min(10,BATCH//4)]+new_rows[:BATCH-len(refreshed[:min(10,BATCH//4)])]
 new={}
 for row in pending:
  sid=row["source_id"]
  result=decision({**row,"source":src},gate[sid],native.get(sid),attest.get(sid))
  if sid in witness_by_id and result["status"]=="HOLD_THREE_WAY_NUMERIC_NOT_INDEPENDENTLY_PROVEN":
   result={**result,"status":"HOLD_PARTIAL_THREE_WAY_WITNESS_FULL_FILE_PENDING",
     "matched_sample":witness_by_id[sid],
     "newly_ready":False}
  new[sid]=result
 ck["done"].update(new)
 ck["last_run"]=os.getenv("GITHUB_RUN_ID","manual")
 ck["source_release_run"]=rid
 if new:upsert(api,control,name,ck)
 totals=Counter(v["status"] for v in ck["done"].values())
 print("D_SEVEN_SOURCE_TRIAGE="+json.dumps({"source":src,
    "cohort":len(rows),"native_available":len(native),"d_checked":len(ck["done"]),
    "this_batch":len(new),"rechecked_evidence":len(refreshed[:min(10,BATCH//4)]),"existing_ready":sum(x["status"]==READY for x in gate.values()),
    "newly_promoted":0,"d_status_counts":dict(totals),
    "formal_release_source_run":rid},ensure_ascii=False),flush=True)

def selftest():
 row={"source_id":"x","source":"TWSE","sha":"a"*64}
 old={"source_id":"x","source_sha256":"a"*64,"status":"HOLD"}
 native={"source_id":"x","bronze_sha256":"a"*64,"input_bytes_sha_checked":True,
         "status":"CONTENT_PARSED_ORIGIN_PIT_HOLD"}
 assert decision(row,{**old,"status":READY},native)["status"]=="READY_PRESERVED_EXISTING"
 assert decision(row,old,native)["status"]=="HOLD_THREE_WAY_NUMERIC_NOT_INDEPENDENTLY_PROVEN"
 assert decision(row,old,{**native,"status":"HOLD_UNKNOWN_DATASET"})["status"]=="HOLD_SOURCE_NATIVE_SEMANTIC"
 assert not independently_attested(row,{"official_value":"100","third_party_value":"100"})[0]
 assert set(NUMERIC_FIELDS)==set(SOURCES)
 assert decision(row,old,native)["newly_ready"] is False
 print("D_SEVEN_SOURCE_INDEPENDENT_GATE_NEGATIVE_TESTS_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==2:run(sys.argv[1])
 else:raise SystemExit("usage: selftest | SOURCE")
