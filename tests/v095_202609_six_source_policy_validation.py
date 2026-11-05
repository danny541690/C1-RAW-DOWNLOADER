import csv,json,pathlib,sys,collections
base=pathlib.Path("governance/v095")
rules=json.loads((base/"OFFICIAL_FIRST_FINMIND_FREE_FALLBACK_V1.json").read_text())
migration=json.loads((base/"202609_BRONZE_MIGRATION_RESUME_20261105.json").read_text())
contracts=list(csv.DictReader((base/"DATASET_CONTRACTS.csv").open()))
source=sys.argv[1]
inventory={x["source"]:x for x in migration["source_month_folders"]}
item=inventory[source]
assert rules["official"]["maximum_attempts_total"]==3
assert rules["finmind_free"]["never_auto_replace_official"]
assert len(item["files"])>0
assert all(int(x["bytes"])>0 for x in item["files"])
assert any(x["source_class_id"]==source for x in contracts)
report={"source":source,"period":"2026-09","observed_receipt_files":len(item["files"]),"policy_attempts":3,"finmind_fallback":"confirmed_gap_only","external_drive_sha_verified_in_this_run":False,"bronze_production_approved":False,"status":"FROZEN_RECEIPTS_RECHECKED_PENDING_FULL_BRONZE"}
out=pathlib.Path("v095_sept_qa");out.mkdir(exist_ok=True)
(out/(source+".json")).write_text(json.dumps(report,indent=2))
print(json.dumps(report))
