"""Combine cross-source Drive migration stress results without making blocked sources appear passed."""
import json,pathlib
root=pathlib.Path("v095_seven_drive_stress")
sources=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
rows=[]
for src in sources:
 f=root/src/"report.json"
 if not f.exists():rows.append({"source":src,"status":"MISSING_REPORT"});continue
 o=json.loads(f.read_text())
 rows.append(o)
ok=[x for x in rows if x.get("status","").startswith("PASS")]
report={"schema":"V095_SEVEN_SOURCE_PARALLEL_DRIVE_STRESS_REPORT_V1","source_count":7,
 "candidate_pass":len(ok),"blocked":len(rows)-len(ok),"results":rows,
 "parallel_max":3,"historic_all_seven_approved":False,
 "silver_numeric_normalization_approved":False,"gold_investment_approved":False,
 "all_source_sha_proven":False,"production_writes":False,
 "new_candidate_bytes":sum(x.get("candidate_bytes",0) for x in ok),
 "source_bytes":sum(x.get("raw_bytes",0) for x in ok),
 "max_source_elapsed_seconds":max((x.get("elapsed_seconds",0) for x in rows),default=0),
 "source_sum_elapsed_seconds":round(sum(x.get("elapsed_seconds",0) for x in rows),3)}
root.mkdir(exist_ok=True)
(root/"SEVEN_SOURCE_COMBINED_REPORT.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print("SEVEN_DRIVE_STRESS_COMBINED",json.dumps({k:v for k,v in report.items() if k!="results"},ensure_ascii=False),flush=True)
for x in rows:print("SOURCE_STATUS",x["source"],x["status"],x.get("error",""),flush=True)
if len(ok)<7:raise SystemExit(1)
