#!/usr/bin/env python3
"""JARVIS v0.97 unified seven-source parser gap inventory and safe source-specific triage.

Reads the LATEST COMPLETE immutable seven-source release set and per-source Bronze
checkpoints. Reports verifiable blockers, adapter plans, evidence and ownership.
Never rewrites Bronze, changes formal READY, or runs Silver/Gold. Each source has
its own parser; shared orchestrator merges status and validation contracts only.
"""
import json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,COHORT,READY,source_api
from scripts.v097_bronze_content_qa import children

RULES={
 "TWSE":{"adapter":"TWSE versioned JSON/HTML/ZIP and per-member official provenance",
   "formats":["ZIP member .raw JSON","daily mixed tables","historical OHLCV","lending","foreign holding","index"],
   "blockers":["HOLD_TWSE_DATASET_OR_ARCHIVE_ADAPTER","HOLD_UNKNOWN_JSON_DATASET","HOLD_UNRECOGNIZED_EXTENSION"],
   "fix":"B+C raw-bytes format fingerprints, manifest SHA, typed tables and historical official/third-party value cross-check"},
 "TPEx":{"adapter":"TPEx market-cap/quotes/margin/lending/index and 2003-2007 historical variants",
   "formats":["ZIP member .raw JSON","listed OTC quote tables","market capitalization","financing","lending"],
   "blockers":["HOLD_TPEX_HISTORICAL_DATASET_OR_PROVENANCE","HOLD_CONTENT_PERIOD_CONFLICT"],
   "fix":"Separate market cap from OHLCV, official historical schema/date, manifest SHA, external published price evidence"},
 "MOPS":{"adapter":"MOPS HTML financial matrix and statement revision/PIT classifier",
   "formats":["HTML financial matrices","monthly revenue","filing revisions","older structured tables"],
   "blockers":["HOLD_MOPS_EXACT_FINANCIAL_NUMERIC_EVIDENCE"],
   "fix":"Per-company accounting period, column labels and units, official independent financial figures and announcement timestamps"},
 "TDCC":{"adapter":"TDCC security type as-of master and shareholding distribution table",
   "formats":["HTML distribution","historical security identity","special instruments","ZIP"],
   "blockers":["HOLD_TDCC_SOURCE_CLASS_TOTAL_OR_DATES"],
   "fix":"As-of official historical security master, class restrictions, sum/ratio reconciliation, 3-way structural evidence"},
 "TAIFEX":{"adapter":"TAIFEX versioned CP950/Big5/UTF8 historical futures CSV",
   "formats":["CSV quoting","trailing delimiter","contract month","ZIP archive","date columns"],
   "blockers":["HOLD_TAIFEX_DATASET_NUMERIC_OR_PERIOD"],
   "fix":"Versioned encoding/schema and width repair rules; trade-date vs contract-month and official contract comparison"},
 "NDC":{"adapter":"NDC historical Excel native cell and published economic time series",
   "formats":["XLS/XLSX native-cell extraction","publication date","historical series gaps"],
   "blockers":["HOLD_NDC_UNDOCUMENTED_CELL_GAP"],
   "fix":"Resolve specific native-cell gap via official original worksheet, series inception or documented NA"},
 "FinMind":{"adapter":"FinMind dataset-specific JSON/ZIP unit manifest and provider PIT",
   "formats":["ZIP raw units","daily-stock datasets","field units","date semantics"],
   "blockers":["HOLD_FINMIND_PROVIDER_OR_DATASET_PROOF","HOLD_FINMIND_ROW_PERIOD_CONFLICT"],
   "fix":"Provider version/API provenance, per-unit SHA and row period, financial units, paid entitlement independent of proof"}
}
def inspect(gates):
 if set(gates)!=set(SOURCES):raise RuntimeError("SEVEN_SOURCE_GATES_REQUIRED")
 overview={};cohort=0;ready=0;ids=set()
 for src in SOURCES:
  gate=gates[src]
  if gate.get("source")!=src or gate.get("schema")!="v097_silver_input_release_source_v1":
   raise RuntimeError("INVALID_GATE:"+src)
  rows=gate.get("records",[])
  if len(rows)!=gate.get("cohort"):raise RuntimeError("GATE_COHORT_MISMATCH:"+src)
  counts=Counter()
  samples={}
  for r in rows:
   sid=r["source_id"]
   if sid in ids:raise RuntimeError("CROSS_SOURCE_DUPLICATE_ID:"+sid)
   ids.add(sid)
   status=r["status"]
   if status==READY and (not r.get("silver_input_only") or not r.get("receipt")):
    raise RuntimeError("GATE_UNSUPPORTED_READY:"+sid)
   counts[status]+=1
   if status!=READY and len(samples.setdefault(status,[]))<3:
    samples[status].append({"source_id":sid,"path":r.get("source_path"),"receipt":r.get("receipt")})
  n=len(rows);r=counts[READY];cohort+=n;ready+=r
  overview[src]={"total":n,"ready":r,"hold":n-r,
   "formal_status_counts":dict(counts),
   "largest_blockers":[{"code":k,"count":v,"examples":samples.get(k,[])}
     for k,v in sorted(counts.items(),key=lambda x:-x[1]) if k!=READY][:12],
   "adapter_plan":RULES[src],"parser_stage":"PARSER_SPECIFIC_REMEDIATION_REQUIRED" if r<n else "SOURCE_GATE_COMPLETE",
   "silver_gold_executed":False}
 if cohort!=COHORT:raise RuntimeError("FROZEN_COHORT_MISMATCH")
 return {"cohort":cohort,"ready":ready,"hold":cohort-ready,
         "ready_ratio":round(ready/cohort,6),"by_source":overview,
         "silver_gold_executed":False,"no_automatic_promotion":True}
def latest_complete(api,quality,match,load_json):
 listing=children(api,quality)
 ids=[]
 for f in listing:
  n=f["name"]
  if n.startswith("v097_AP_REPORT_") and n.endswith(".json"):
   try:ids.append(int(n[len("v097_AP_REPORT_"):-5]))
   except ValueError:pass
 for rid in sorted(set(ids),reverse=True):
  gates={};valid=True
  for src in SOURCES:
   f=match(api,quality,"v097_AP_SILVER_INPUT_RELEASE_"+src+"_"+str(rid)+".json")
   if not f:valid=False;break
   body=load_json(api,f["id"])
   if str(body.get("run"))!=str(rid) or body.get("pit_backtest_approved") is not False:
    valid=False;break
   gates[src]=body
  if valid:return str(rid),gates
 raise RuntimeError("NO_COMPLETE_SEVEN_SOURCE_FORMAL_RELEASE")
def run(source="all"):
 if source!="all" and source not in SOURCES:raise RuntimeError("INVALID_SOURCE")
 api,control,quality,match,load_json,put_once,upsert,call=source_api()
 rid,gates=latest_complete(api,quality,match,load_json)
 report=inspect(gates)
 # Classify actual source-native adapter checkpoint statuses, distinct from the
 # formal coarse Silver release gate. Missing checkpoint remains a hard failure.
 from scripts.v097_seven_source_specific_resolvers import triage
 for src in SOURCES:
  file=match(api,control,"v097_AP_CHECKPOINT_"+src+".json")
  if not file:raise RuntimeError("MISSING_SOURCE_ADAPTER_CHECKPOINT:"+src)
  checkpoint=load_json(api,file["id"])
  actual=checkpoint.get("done")
  if not isinstance(actual,dict):raise RuntimeError("BAD_SOURCE_ADAPTER_CHECKPOINT:"+src)
  expected=report["by_source"][src]["total"]
  if len(actual)>expected:raise RuntimeError("SOURCE_ADAPTER_EXCEEDS_COHORT:"+src)
  raw_status=Counter(str(v.get("status","MISSING_STATUS")) for v in actual.values())
  source_specific=[]
  for status,count in raw_status.most_common():
   guidance=triage(src,status)
   source_specific.append({"parser_status":status,"count":count,
     "resolver":guidance["resolver"],"required_release_evidence":guidance["required_release_evidence"],
     "silver_ready_promoted":False})
  report["by_source"][src]["checkpoint_parsed"]=len(actual)
  report["by_source"][src]["adapter_status_reasons"]=source_specific
  report["by_source"][src]["checkpoint_not_examined"]=expected-len(actual)
 summary={"schema":"v097_seven_parser_remediation_inventory_v1",
   "source_release_run":rid,"generated_at":datetime.now(timezone.utc).isoformat(),
   "scope":source,"cohort":report["cohort"],"ready":report["ready"],"hold":report["hold"],
   "ready_ratio":report["ready_ratio"],
   "by_source":{s:report["by_source"][s] for s in (SOURCES if source=="all" else (source,))},
   "silver_gold_executed":False,"no_automatic_promotion":True}
 # Run-specific immutable reports avoid cross-run file overwrites.
 out_name="v097_SEVEN_SOURCE_PARSER_TRIAGE_"+rid+"_"+os.getenv("GITHUB_RUN_ID","manual")+"_"+source+".json"
 if os.getenv("GITHUB_RUN_ID"):put_once(api,quality,out_name,summary)
 print("SEVEN_PARSER_TRIAGE="+json.dumps({"release_run":rid,"source":source,
   "ready":report["ready"],"hold":report["hold"],
   "sources":{s:{"ready":v["ready"],"hold":v["hold"],
     "top_reasons":[{"code":x["code"],"count":x["count"]} for x in v["largest_blockers"][:4]]}
      for s,v in summary["by_source"].items()},
   "report_file":out_name},ensure_ascii=False),flush=True)
def selftest():
 assert len(RULES)==len(SOURCES)==7
 assert "NDC" in RULES and "FinMind" in RULES
 gates={s:{"source":s,"schema":"v097_silver_input_release_source_v1","cohort":0,"records":[]} for s in SOURCES}
 try:inspect(gates)
 except RuntimeError as e:assert "FROZEN_COHORT_MISMATCH" in str(e)
 else:raise AssertionError("must reject invented empty cohort")
 assert all("adapter" in RULES[s] and "fix" in RULES[s] for s in SOURCES)
 from scripts.v097_seven_source_specific_resolvers import triage
 assert all(triage(s,"HOLD_UNKNOWN_JSON_DATASET")["source"]==s for s in SOURCES)
 print("SEVEN_SOURCE_PARSER_COORDINATION_SELFTEST_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)<=2:run(sys.argv[1] if len(sys.argv)>1 else "all")
 else:raise SystemExit("usage: [selftest|all|SOURCE]")
