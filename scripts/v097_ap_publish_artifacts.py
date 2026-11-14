#!/usr/bin/env python3
"""JARVIS v0.97 partial/full Bronze evidence publisher.
Does not invent Silver READY, and never edits original Bronze or Silver/Gold.
Emits seven sharded file-QA ledgers, an exception register, READY manifest,
adapter rulebook, and an honest partial/final acceptance decision.
"""
import os,json,hashlib
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,COHORT,READY,adapter_version,source_api
RUN=os.environ.get("GITHUB_RUN_ID","manual")
def decision(status,version_ok):
 if not version_ok:return "RECHECK_PENDING"
 if status==READY:return "READY"
 if status.startswith("EXCLUDED_"):return "EXCLUDED"
 return "HOLD"
def run():
 api,control,quality,match,load_json,put_once,_,_=source_api()
 totals=Counter();per_source={};ledger_files=[];ex=[];ready_rows=[]
 for src in SOURCES:
  inp=match(api,quality,"v097_AP_INPUT_"+src+".json")
  if not inp:raise RuntimeError("INPUT_NOT_INITIALIZED_"+src)
  rows=load_json(api,inp["id"])["rows"]
  cf=match(api,control,"v097_AP_CHECKPOINT_"+src+".json")
  done=load_json(api,cf["id"])["done"] if cf else {}
  source_ids={r["source_id"] for r in rows}
  if len(source_ids)!=len(rows) or set(done)-source_ids:
   raise RuntimeError("SOURCE_LEDGER_ID_DUPLICATE_OR_ORPHAN_"+src)
  ledger=[];counts=Counter();outstanding=0
  for r in rows:
   fid=r["source_id"];rec=done.get(fid,{})
   state=rec.get("status","NOT_EXAMINED")
   good_version=rec.get("adapter_version")==adapter_version(src)
   mode=decision(state,good_version) if rec else "NOT_EXAMINED"
   out={"source_id":fid,"destination_id":r.get("dest_id"),
    "source_sha256":r.get("sha"),"source":src,
    "source_path":r.get("source_path"),"state":state,
    "disposition":mode,"adapter_version":rec.get("adapter_version"),
    "receipt":rec.get("receipt"),"retries":rec.get("retries",0)}
   ledger.append(out);counts[mode]+=1
   if mode=="READY":
    if not out["receipt"] or not out["source_sha256"]:
     raise RuntimeError("READY_MISSING_RECEIPT_"+fid)
    ready_rows.append(out)
   elif mode=="HOLD":ex.append(out)
   elif mode in ("RECHECK_PENDING","NOT_EXAMINED"):
    outstanding+=1
  name="BRONZE_FILE_QA_LEDGER_%s_%s.json"%(src,RUN)
  put_once(api,quality,name,{"schema":"v097_bronze_file_qa_ledger_1",
      "run":RUN,"source":src,"adapter_version":adapter_version(src),
      "rows":ledger,"counts":dict(counts)})
  ledger_files.append(name)
  per_source[src]={"total":len(rows),"counts":dict(counts),"outstanding":outstanding,
    "ledger":name}
  totals.update(counts)
 if sum(totals.values())!=COHORT:raise RuntimeError("FINAL_74750_ACCOUNTING_FAILURE")
 rulebook={"schema":"v097_adapter_rulebook_1","run":RUN,
  "source_adapters":{
    "TWSE":"Official table/price JSON; historical source and publication proof still required",
    "TPEx":"OTC multi-table JSON and historical Big5; date and stock class as-of master held where missing",
    "MOPS":"Revenue/IFRS HTML accounting; native units and announcement PIT must be preserved",
    "TDCC":"Official holdings HTML numeric identity; special security vs ordinary stock and provenance separated",
    "TAIFEX":"Futures/options contract trading day vs overnight, archive and price semantics",
    "NDC":"Extracted source Excel native cells; Excel serial date and source SHA; revisions/PIT held",
    "FinMind":"Manifest-unit .raw JSON with per-member SHA/rows; official gap and historical availability held"},
  "ready_rule":"Requires authenticated source/dataset evidence, semantic QA and immutable SHA receipt",
  "recheck_rule":"Only requeue source adapter version changed or transient retry under cap",
  "pit_rule":"Do not use prior-period values before actual publication; Silver PIT gate mandatory",
  "formal_release_not_inferred_from_parser_shape":True}
 put_once(api,quality,"BRONZE_SOURCE_ADAPTER_RULEBOOK_%s.json"%RUN,rulebook)
 put_once(api,quality,"BRONZE_EXCEPTION_REGISTER_%s.json"%RUN,
  {"schema":"v097_bronze_exception_register_1","run":RUN,"hold_records":ex,
   "hold_count":len(ex),"not_final_without_independent_proof":True})
 put_once(api,quality,"BRONZE_READY_FOR_SILVER_MANIFEST_%s.json"%RUN,
  {"schema":"v097_bronze_ready_manifest_1","run":RUN,
   "ready_records":ready_rows,"ready_count":len(ready_rows),
   "silver_gold_executed":False,"ready_status_not_inferred":True})
 final={"schema":"v097_bronze_final_acceptance_1","run":RUN,
   "at":datetime.now(timezone.utc).isoformat(),"cohort":COHORT,
   "by_source":per_source,"dispositions":dict(totals),
   "ready":totals["READY"],"hold_provisional":totals["HOLD"],
   "excluded":totals["EXCLUDED"],"not_examined":totals["NOT_EXAMINED"],
   "recheck_pending":totals["RECHECK_PENDING"],
   "ledger_files":ledger_files,"total_unique":sum(totals.values()),
   "official_source_release_approved":False,
   "decision":"NOT_COMPLETE" if totals["NOT_EXAMINED"] or totals["RECHECK_PENDING"]
      else ("AWAITING_SOURCE_AND_SEMANTIC_CLEARANCE" if totals["HOLD"] else "EVIDENCE_GATE_COMPLETE"),
   "silver_gold_executed":False,"no_raw_modification":True}
 put_once(api,quality,"BRONZE_FINAL_ACCEPTANCE_%s.json"%RUN,final)
 print("BRONZE_ACCEPTANCE_ARTIFACTS="+json.dumps({k:v for k,v in final.items() if k not in ("by_source","ledger_files")},ensure_ascii=False),flush=True)
def selftest():
 assert decision("BRONZE_READY_FOR_SILVER",True)=="READY"
 assert decision("HOLD_SOURCE",True)=="HOLD"
 assert decision("BRONZE_READY_FOR_SILVER",False)=="RECHECK_PENDING"
 print("BRONZE_ARTIFACTS_SELFTEST_PASS")
if __name__=="__main__":
 import sys
 selftest() if len(sys.argv)>1 and sys.argv[1]=="selftest" else run()
