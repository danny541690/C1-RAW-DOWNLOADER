#!/usr/bin/env python3
"""Historical v0.93 2000-2026 evidence inventory baseline for JARVIS v0.97.

NO market-data completeness claims: a file/month folder is not one trading day.
Counts raw candidates separately from control/evidence and unknown formats.
Never modifies v0.93 files or invents availability from absent historical records.
"""
import csv
import io
import json
import os
from collections import Counter,defaultdict
from datetime import datetime,timezone
from scripts.v097_bronze_content_qa import service, children, folder, load_json, save

YEARS=range(2000,2027)
SOURCES=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
RUN=os.environ.get("GITHUB_RUN_ID","manual")
INVENTORY_RUN="42591232910"
CANDIDATE="CANDIDATE_RAW_UNVERIFIED"

def main():
    api=service()
    user=folder(api,"root","ChatGPT資料存取")
    root=folder(api,user,"JARVIS_C1_v097_LIFECYCLE")
    ctrl=folder(api,root,"00_SYSTEM_CONTROL")
    manifest=folder(api,ctrl,"03_RUN_MANIFESTS")
    release=folder(api,ctrl,"07_RELEASE_GATES")
    files=children(api,manifest)
    expected=["v097_inventory_%s_lane%d.json"%(INVENTORY_RUN,i) for i in range(6)]
    sources=Counter(); classes=Counter(); totals=defaultdict(Counter)
    per_year=Counter()
    unique_ids=set()
    dup_ids=0
    items=0
    inventory_errors=[]
    years_in_inventory=set()
    for i,name in enumerate(expected):
        matches=[f for f in files if f["name"]==name]
        if len(matches)!=1:raise RuntimeError("Inventory missing/ambiguous: "+name)
        data=load_json(api,matches[0]["id"])
        if data.get("run_id")!=INVENTORY_RUN or data.get("lane")!=i:
            raise RuntimeError("Inventory provenance mismatch: "+name)
        inventory_errors.extend(data.get("errors",[]))
        for row in data["files"]:
            items+=1
            fid=row.get("file_id")
            if not fid:raise RuntimeError("Inventory row lacks Drive ID")
            if fid in unique_ids:
                dup_ids+=1
            unique_ids.add(fid)
            src=row.get("source","UNKNOWN")
            cls=row.get("classification","UNKNOWN")
            year=str(row.get("year",""))
            month=row.get("month","")
            sources[src]+=1; classes[cls]+=1
            years_in_inventory.add(year)
            per_year[year]+=1
            if month and len(month)==7 and month[:4]==year and month[4]=="-":
                totals[(src,month)][cls]+=1
            else:
                totals[(src,year+"-UNCLASSIFIED")][cls]+=1
    rows=[]
    zero_months=0
    for src in SOURCES:
        for year in YEARS:
            for month in range(1,13):
                key="%04d-%02d"%(year,month)
                types=totals[(src,key)]
                n=sum(types.values())
                if not n:zero_months+=1
                rows.append({
                    "source":src,"year":year,"month":key,
                    "snapshot_file_count":n,
                    "raw_candidate_unverified_count":types[CANDIDATE],
                    "batch_evidence_review_count":types["BATCH_EVIDENCE_REVIEW"],
                    "format_review_count":types["FORMAT_REVIEW"],
                    "test_or_control_count":types["TEST_OR_CONTROL"],
                    "other_count":n-sum(types[k] for k in (
                        CANDIDATE,"BATCH_EVIDENCE_REVIEW","FORMAT_REVIEW","TEST_OR_CONTROL")),
                    "source_dataset_expected_count":"UNKNOWN",
                    "actual_trading_days_verified":"NO",
                    "completeness_label":"UNKNOWN_NOT_CERTIFIED",
                    "missing_interpretation":"ZERO_SNAPSHOT_FILES_IS_NOT_PROOF_OF_MISSING_OFFICIAL_DATA" if not n else "SOURCE_FILE_EXISTS_DATASET_NOT_VALIDATED"
                })
    fieldnames=list(rows[0])
    io_buffer=io.StringIO()
    writer=csv.DictWriter(io_buffer,fieldnames=fieldnames)
    writer.writeheader();writer.writerows(rows)
    result={
       "schema":"jarvis_v097_legacy_manifest_coverage_v1",
       "run_id":RUN,"timestamp_utc":datetime.now(timezone.utc).isoformat(),
       "legacy_inventory_run":INVENTORY_RUN,"inventory_files":len(expected),
       "legacy_items":items,"distinct_file_ids":len(unique_ids),
       "duplicated_ids_across_manifest_rows":dup_ids,
       "source_file_counts":dict(sources),"classification_counts":dict(classes),
       "years_found":sorted(years_in_inventory),
       "year_counts":dict(sorted(per_year.items())),
       "expected_source_month_cells":len(rows),
       "zero_file_month_cells":zero_months,
       "inventory_errors_count":len(inventory_errors),
       "data_completeness_verified":False,
       "market_expected_source_calendar_available":False,
       "warning":"Legacy file snapshot includes batch evidence, control/receipt and format review; counts are not trading-day or dataset coverage.",
       "required_followup":"Create source/dataset/date expected availability matrix with public official publication rules; compare actual records and post-fix snapshots."
    }
    save(api,release,"v097_LEGACY_SNAPSHOT_MATRIX_%s.csv"%RUN,io_buffer.getvalue(),"text/csv")
    save(api,release,"v097_LEGACY_SNAPSHOT_AUDIT_%s.json"%RUN,result)
    print("LEGACY_MANIFEST_AUDIT="+json.dumps(result,ensure_ascii=False))
if __name__=="__main__":main()
