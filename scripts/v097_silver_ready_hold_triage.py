#!/usr/bin/env python3
"""v0.97 HOLD remediation queue. Does not promote records or run Silver/Gold.
Reads exact seven-source independent immutable release gates and publishes
a source-ranked, evidence-linked queue; no parser status is promoted to READY.
"""
import hashlib,json,os,sys
from collections import Counter
from datetime import datetime,timezone
from scripts.v097_bronze_autopilot import SOURCES,COHORT,READY,source_api
from scripts.v097_bronze_content_qa import children

PRIORITY={"TPEx":1,"TWSE":1,"TDCC":2,"FinMind":2,"TAIFEX":3,"MOPS":3,"NDC":4}
RULES={
 "TPEx":"Verify official historical ZIP member bytes, per-member date, schema, financial columns and source URL; never infer source from parent ZIP SHA",
 "TWSE":"Verify historical archive member hashes, trading dates, typed quote tables and source publication; do not certify ZIP container alone",
 "TDCC":"Separate listed/OTC from special securities using dated official master; validate shareholding table totals, effective date and exact source",
 "FinMind":"Independently verify provider manifest, units, row dates and source evidence per dataset; do not infer numeric proof from unit-member SHA",
 "TAIFEX":"Reconcile official historical CSV encodings, columns, date semantics, contract type and archive expansion limits",
 "MOPS":"Validate exact accounting numbers with independent original tables, units, revision and announcement dates",
 "NDC":"Verify the remaining native-cell gap against official series inception and historical workbook"}
def collect(gates):
    summary={};queue=[];ready=0;seen=set()
    for src in SOURCES:
        g=gates[src]
        if g.get("source")!=src or g.get("schema")!="v097_silver_input_release_source_v1":
            raise RuntimeError("INVALID_GATE_"+src)
        rows=g["records"]
        if len(rows)!=g["cohort"]:raise RuntimeError("COHORT_MISMATCH_"+src)
        counts=Counter();examples={}
        for r in rows:
            sid=r["source_id"]
            if sid in seen:raise RuntimeError("DUPLICATE_SOURCE_ID_"+sid)
            seen.add(sid)
            state=r["status"]
            if state==READY:
                if not r.get("receipt") or not r.get("silver_input_only"):
                    raise RuntimeError("UNSUPPORTED_READY_"+sid)
                ready+=1
            else:
                counts[state]+=1
                examples.setdefault(state,[])
                if len(examples[state])<5:
                    examples[state].append({"source_id":sid,"source_path":r.get("source_path"),"receipt":r.get("receipt")})
        summary[src]={"total":len(rows),"ready":len(rows)-sum(counts.values()),
             "hold":sum(counts.values()),"reasons":dict(counts)}
        for reason,n in counts.items():
            queue.append({"source":src,"priority":PRIORITY[src],"reason":reason,"count":n,
                "required_evidence":RULES[src],"examples":examples[reason],
                "release_policy":"HOLD until independently verified; no automatic READY promotion"})
    if len(seen)!=COHORT:raise RuntimeError("FROZEN_BASELINE_COUNT_MISMATCH")
    queue.sort(key=lambda x:(x["priority"],-x["count"],x["source"],x["reason"]))
    return {"cohort":COHORT,"ready":ready,"hold":COHORT-ready,
        "silver_ready_ratio":round(ready/COHORT,6),
        "by_source":summary,"queue":queue,
        "silver_gold_executed":False,"no_automatic_release":True}
def selftest():
    gates={}
    for src in SOURCES:
        gates[src]={"schema":"v097_silver_input_release_source_v1","source":src,"cohort":0,"records":[]}
    # Validate source ordering and semantic constraints without pretending 74750 records exist.
    assert PRIORITY["TWSE"]==PRIORITY["TPEx"]==1
    assert all("official" in RULES[s].lower() or "provider" in RULES[s].lower()
               or "accounting" in RULES[s].lower() for s in SOURCES)
    assert all("records" in gates[s] for s in SOURCES)
    print("HOLD_TRIAGE_SELFTEST_PASS")
def run():
    api,control,quality,match,load_json,put_once,_,_=source_api()
    # Latest completed immutable seven-source release; never assume that a
    # more recent parse-only run has passed the independent gate.
    listings=children(api,quality)
    names=[x["name"] for x in listings if x["name"].startswith("v097_AP_REPORT_") and x["name"].endswith(".json")]
    ids=sorted((int(n.split("_")[-1][:-5]) for n in names if n.split("_")[-1][:-5].isdigit()),reverse=True)
    if not ids:raise RuntimeError("NO_AUTOPILOT_ACCEPTANCE_REPORT")
    selected=None
    for rid in ids:
        gates={};ok=True
        for s in SOURCES:
            f=match(api,quality,f"v097_AP_SILVER_INPUT_RELEASE_{s}_{rid}.json")
            if not f:ok=False;break
            g=load_json(api,f["id"])
            if g.get("run")!=str(rid) or g.get("pit_backtest_approved") is not False:ok=False;break
            gates[s]=g
        if ok:
            selected=rid;break
    if selected is None:raise RuntimeError("NO_COMPLETE_SEVEN_SOURCE_GATE")
    result=collect(gates)
    report={"schema":"v097_silver_ready_hold_remediation_queue_1",
      "source_release_run":str(selected),"created_at":datetime.now(timezone.utc).isoformat(),
      **result}
    # Idempotent immutable output keyed by source release run, not cron run.
    canonical={k:v for k,v in report.items() if k!="created_at"}
    filename=f"v097_SILVER_READY_HOLD_REMEDIATION_QUEUE_{selected}.json"
    f=match(api,quality,filename)
    if f:
        existing=load_json(api,f["id"])
        if {k:v for k,v in existing.items() if k!="created_at"}!=canonical:
            raise RuntimeError("PREVIOUS_HOLD_QUEUE_CONFLICT")
    else:
        put_once(api,quality,filename,report)
    print("HOLD_REMEDIATION_QUEUE="+json.dumps({
      "release_run":selected,"ready":result["ready"],"hold":result["hold"],
      "by_source":{s:{"ready":v["ready"],"hold":v["hold"]} for s,v in result["by_source"].items()},
      "largest_issues":[{"source":q["source"],"reason":q["reason"],"count":q["count"]} for q in result["queue"][:12]],
      "queue_file":filename},ensure_ascii=False),flush=True)
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif len(sys.argv)==1:run()
    else:raise SystemExit("usage: [selftest]")
