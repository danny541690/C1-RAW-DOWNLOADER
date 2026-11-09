#!/usr/bin/env python3
"""Local v0.96 P0 manifest audit. No Google Drive writes or external downloads."""
import collections,hashlib,json,pathlib
OUT=pathlib.Path("v096_run")
def check(manifest,report):
 rows=manifest["rows"]
 if manifest.get("schema")!="JARVIS_V096_P0_SOURCE_MANIFEST_V1":
  raise ValueError("V096_MANIFEST_SCHEMA")
 ids=[r["original_drive_file_id"] for r in rows]
 if len(ids)!=len(set(ids)):raise ValueError("V096_DUPLICATED_ORIGINAL_ID")
 issues=[]
 for row in rows:
  if row.get("raw_v096_storage")!="REFERENCE_ORIGINAL_ID_ONLY" or row.get("source_sha256") is not None:
   raise ValueError("V096_UNPROVEN_NATIVE_SHA_OR_IMMUTABILITY")
  if row.get("historical_pit_verified") is not False:
   raise ValueError("V096_PIT_FALSE_POSITIVE")
  if row.get("original_file_deleted") or row.get("market_data_rewritten"):
   raise ValueError("V096_SOURCE_MUTATION_UNSAFE")
  if row["month_folder"][:4] not in ("2025","2026"):
   raise ValueError("V096_YEAR_SCOPE")
  if not isinstance(row["size_bytes"],int) or row["size_bytes"]<0:
   raise ValueError("V096_BYTES_BAD")
  if row["source_format"]=="OTHER":issues.append({"file":row["original_drive_file_id"],"kind":"ADAPTER_REQUIRED"})
 for field in ("silver_partitions_created","gold_indicators_created","official_downloads"):
  if report[field]!=0:raise ValueError("V096_P0_SCOPE_OVERCLAIM:"+field)
 if report["legacy_files_indexed"]!=len(rows):raise ValueError("V096_MANIFEST_ROW_COUNT")
 if not all(report.get(k) is False for k in ("v095_mutated","v093_mutated","PIT_certified","full_source_completeness_certified")):
  raise ValueError("V096_UNVERIFIED_COMPLETENESS")
 return {"status":"PASS_METADATA_INDEX_ONLY","rows_indexed":len(rows),
   "distinct_original_ids":len(ids),"unmapped_format_count":len(issues),
   "source_counts":dict(collections.Counter(r["source"] for r in rows)),
   "notes":["raw source SHA not yet verified","folder pages may be partial",
            "no Parquet conversion certified","no historical PIT proof"]}
def run():
 manifest=json.loads((OUT/"manifest.json").read_text())
 report=json.loads((OUT/"inventory_report.json").read_text())
 result=check(manifest,report)
 (OUT/"audit_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":run()
