"""Consolidate 7 source probe, recovered routes, 3-source Parquet and v093 TDCC Drive pilot.
PASS for a probe is not approval for historical migration or PIT/Gold.
"""
import json,datetime,hashlib,pathlib
OUT=pathlib.Path("v095_seven_source_audit");OUT.mkdir(exist_ok=True)
def load(p):
 try:return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
 except (FileNotFoundError,ValueError):return None
probe=load("r17_live_source_connectivity.json") or {}
recover=load("r18_live_recovery_report.json") or {}
converted=load("r19_live_candidates/report.json") or {}
tdcc=load("v095_real_drive_transfer/report.json") or {}
sources=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
p={x["source"]:x for x in probe.get("results",[])}
r={x["source"].split("_")[0]:x for x in recover.get("source_results",[])}
c={x["source"]:x for x in converted.get("results",[])}
items=[]
for src in sources:
 pp=p.get(src,{})
 rr=r.get(src,{})
 cc=c.get(src,{})
 pr=pp.get("status","NOT_RUN")
 passed=pp.get("data_verified") is True or rr.get("valid_data") is True or cc.get("status","").startswith("PASS")
 if src=="TDCC":
  count=tdcc.get("pass_count",0)
  historical="PASS_CANDIDATE_23_PINNED_FILE_SAMPLES" if count==23 and tdcc.get("fail_count")==0 else "BLOCKED_TDCC_CANDIDATE"
 else:
  count=0
  historical="BLOCKED_NO_SOURCE_SPECIFIC_PINNED_V093_DRIVE_SHA_MANIFEST"
 item={"source":src,"probe_status":pr,"probe_data_verified":pp.get("data_verified",False),
       "route_status":rr.get("status","NOT_RUN"),"local_parquet_status":cc.get("status","NOT_RUN"),
       "live_sample_available":passed,"v093_to_v095_drive_migrated_count":count,
       "v093_historical_migration":historical,"historical_pit_approved":False,
       "production_bronze_approved":False,"production_silver_approved":False,
       "gold_approved":False}
 items.append(item)
report={"schema":"JARVIS_V095_SEVEN_SOURCE_SINGLE_RUN_V1",
 "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "source_count":len(items),"source_results":items,
 "historical_migrated_candidates":sum(x["v093_to_v095_drive_migrated_count"] for x in items),
 "historical_migration_sources_proven":sum(x["v093_to_v095_drive_migrated_count"]>0 for x in items),
 "live_sample_sources_responding":sum(x["live_sample_available"] for x in items),
 "historical_coverage_2000_2026_verified":False,"production_bulk_approved":False,
 "gold_approved":False,"status":"PASS_SCOPED_WITH_BLOCKERS" if len(items)==7 and tdcc.get("pass_count")==23 and tdcc.get("fail_count")==0 else "BLOCKED"}
(OUT/"SEVEN_SOURCE_SINGLE_RUN_REPORT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
for x in items:print("SEVEN_SOURCE",x["source"],x["probe_status"],x["local_parquet_status"],x["v093_historical_migration"],flush=True)
print("SEVEN_SOURCE_SUMMARY",json.dumps({k:v for k,v in report.items() if k!="source_results"},ensure_ascii=False),flush=True)
if report["status"]=="BLOCKED":raise SystemExit(1)
