"""JARVIS 2026-09 Bronze admission: governance evidence only, never source-byte proof.
Runs in Actions; writes explicit per-source release blockers.
"""
import csv,json,pathlib,collections
G=pathlib.Path("governance/v095")
d=json.loads((G/"202609_BRONZE_GATE_STATUS_20261105.json").read_text())
flags=json.loads((G/"PHASE1_FLAGS.json").read_text())
with (G/"DATASET_CONTRACTS.csv").open(newline="") as f:
 rows=list(csv.DictReader(f))
by=collections.Counter(r["source_class_id"] for r in rows)
six=["TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC"]
issues={}
for name in six:
 a=[]
 if not by[name]:a.append("NO_DATASET_CONTRACTS")
 if not d["source_checks"].get(name):a.append("NO_SOURCE_EVIDENCE")
 if not d["source_universe_certified"]:a.append("UNVERIFIED_COMPLETE_SOURCE_DATASET_UNIVERSE")
 if name=="TWSE" and d["source_checks"][name]["sha256_matches"]!=122:a.append("SOURCE_MANIFEST_SHA_FAILURE")
 if name=="TPEx" and d["source_checks"][name]["remaining_primary_missing"]!=0:a.append("PRIMARY_DAILY_MISSING")
 if name=="TDCC" and d["source_checks"][name]["duplicate_composite_keys"]!=0:a.append("TDCC_DUPLICATE_DATE_STOCK_TIER_KEYS")
 if name=="NDC" and not d["source_checks"][name]["official_11509_xlsx_present"]:a.append("NDC_11509_OFFICIAL_ATTACHMENT_MISSING")
 if name=="TAIFEX" and len(d["source_checks"][name].get("exact_duplicate_alias_pairs_verified",[]))<3:a.append("TAIFEX_ALIAS_SHA_EVIDENCE_MISSING")
 if name in ("MOPS","TDCC","NDC","TAIFEX"):a.append("DATASET_SPECIFIC_PRODUCTION_PIT_OR_NATIVE_LINEAGE_PENDING")
 issues[name]=a
blocked=any(issues.values()) or not flags.get("RELEASE_APPROVED",False)
report={"schema":"JARVIS_202609_BRONZE_GOVERNANCE_ADMISSION_V1",
        "classification":"NOT_A_SOURCE_BYTE_READBACK_TEST",
        "contract_rows":len(rows),"per_source_candidate_contracts":dict(by),
        "bronze_full_month_status":"BLOCKED" if blocked else "PENDING_MANUAL_PRODUCTION_EVIDENCE",
        "silver_full_month_allowed":False,
        "candidate_silver_dry_run_allowed":True,
        "finmind_required_by_verified_defects":False,
        "source_issues":issues,
        "notes":"GitHub contract and receipt checks cannot independently read private Drive bytes. Never use this result to approve monthly Bronze."}
out=pathlib.Path("v095_202609_bronze_admission");out.mkdir(exist_ok=True)
(out/"gate.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
if len(rows)<30 or set(by)!=set(six):raise SystemExit("candidate contracts absent")
if flags.get("RELEASE_APPROVED") or flags.get("BULK_COPY_APPROVED"):raise SystemExit("dangerous auto release flags")
