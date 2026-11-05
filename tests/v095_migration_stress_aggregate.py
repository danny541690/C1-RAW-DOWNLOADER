"""Aggregate 3 disjoint real Drive shards and seven-source migration readiness."""
import json,pathlib
root=pathlib.Path("v095_migration_stress")
results=[]
for i in range(3):
 p=root/f"shard_{i}"/"report.json"
 if not p.is_file():raise SystemExit("MISSING_SHARD_ARTIFACT:"+str(i))
 results.append(json.loads(p.read_text()))
files=[r for s in results for r in s["per_file"]]
ids=[r["source_file"] for r in files]
if len(files)!=23 or len(set(ids))!=23:raise SystemExit("DUPLICATE_OR_INCOMPLETE_SHARDS")
totals={k:sum(s[k] for s in results) for k in ["passed","failed","created","skipped","source_bytes","parquet_bytes"]}
statuses={src:{"historical_sha_manifest":"VERIFIED" if src=="TDCC" else "BLOCKED_NOT_YET_PINNED",
  "historical_drive_candidate_migrated_files":23 if src=="TDCC" else 0,
  "silver_normalized":False,"gold_investment_pit_verified":False}
 for src in ("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")}
report={"schema":"V095_3WAY_REAL_DRIVE_COMBINED_ACCEPTANCE_V1",
 "run_approved":all(s["status"]=="PASS" for s in results) and totals["passed"]==23,
 "sources":statuses,"source_count":7,"source_historical_migration_complete_count":1,
 "historical_samples_migrated":totals["passed"],"totals":totals,
 "worker_sum_seconds":round(sum(s["elapsed_seconds"] for s in results),3),
 "worker_max_seconds":round(max(s["elapsed_seconds"] for s in results),3),
 "drive_production_writes":False,"bronze_production_approved":False,
 "silver_production_approved":False,"gold_production_approved":False,
 "historical_2000_2026_coverage_complete":False,"shards":results}
out=root/"COMBINED_REPORT.json";out.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print("MIGRATION_STRESS_AGGREGATE",json.dumps({k:v for k,v in report.items() if k!="shards"},ensure_ascii=False),flush=True)
if not report["run_approved"]:raise SystemExit(1)
