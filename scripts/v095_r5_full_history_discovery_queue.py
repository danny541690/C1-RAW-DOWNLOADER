"""Create a 2000–2026 dataset-month *discovery* queue, not downloads or approval.
Every date remains UNKNOWN until officially documented source availability is measured.
"""
import csv,json,datetime as dt,pathlib,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCES={"TWSE","TPEx","MOPS","TDCC","TAIFEX","NDC"}
def months(start,end):
 a=dt.date.fromisoformat(start+"-01"); b=dt.date.fromisoformat(end+"-01")
 while (a.year,a.month)<=(b.year,b.month):
  yield a.strftime("%Y-%m")
  a=dt.date(a.year+int(a.month==12),a.month%12+1,1)
def plan():
 cfg=json.loads((ROOT/"config/v095_single_repo_fast_backfill_r2.json").read_text())
 rule=json.loads((ROOT/"config/v095_data_validity_system_rules.json").read_text())
 official=json.loads((ROOT/"config/v095_r8_official_source_semantics_20261107.json").read_text())
 begin=cfg["date_window"]["start"];end=cfg["date_window"]["end"]
 products=[{"dataset_id":x["dataset_id"],"source":x["source"]} for x in rule["sources"] if x["source"] in SOURCES]
 assert len(products)==7 and {x["source"] for x in products}==SOURCES
 m=list(months(begin,end));assert len(m)==323
 rows=[]
 for ds in products:
  for month in m:
   key=f'{ds["source"]}|{ds["dataset_id"]}|{month}'
   status="UNVERIFIED_HISTORY_DISCOVERY"
   reason="OFFICIAL_DATASET_EARLIEST_DATE_AND_MONTH_APPLICABILITY_NOT_VERIFIED"
   if ds["dataset_id"]=="TDCC_WEEKLY_OWNERSHIP" and month<"2008-07":
    status="OUTSIDE_THIS_TDCC_HISTORICAL_SERIES"
    reason="OFFICIAL_TDCC_SERIES_CONSTRUCTED_FROM_2008_07_NOT_A_DOWNLOAD_ERROR"
   elif ds["dataset_id"]=="TPEX_DAILY_MARKET" and month<"2003-08":
    status="LEGACY_TPEX_FORMAT_DISCOVERY_REQUIRED"
    reason="OTC_CURRENT_BULK_ARCHIVE_BEGINS_2003_08_CHECK_DIFFERENT_HISTORIC_DATASETS"
   rows.append({"task_id":hashlib.sha256(key.encode()).hexdigest()[:24],"source":ds["source"],
     "dataset_id":ds["dataset_id"],"month":month,
     "status":status,"official_expected_count":"UNKNOWN",
     "download_allowed":False,"silver_allowed":False,"gold_pit_allowed":False,
     "reason":reason,
     "priority":"PILOT_2026_09_11" if month>="2026-09" else "HISTORICAL_DISCOVERY"})
 assert len({r["task_id"] for r in rows})==len(rows)
 tdcc_pre=sum(r["status"]=="OUTSIDE_THIS_TDCC_HISTORICAL_SERIES" for r in rows)
 tpex_legacy=sum(r["status"]=="LEGACY_TPEX_FORMAT_DISCOVERY_REQUIRED" for r in rows)
 assert tdcc_pre==102 and tpex_legacy==43
 return rows,{"schema":"JARVIS_V095_R5_2000_2026_HISTORY_DISCOVERY_V1","start":begin,"end":end,
   "calendar_months":len(m),"source_count":6,"dataset_count":len(products),
   "candidate_dataset_months":len(rows),
   "official_start_constraints":{"tdcc_pre_2008_07_outside_series":tdcc_pre,
     "tpex_pre_2003_08_legacy_format_lookup":tpex_legacy},
   "official_semantic_document_count":len(official["source_documents"]),
   "verified_expected_dataset_months":0,
   "download_tasks_released":0,"production_gate":"BLOCKED",
   "reason":"An inventory is not a real download or official availability check."}
def main():
 rows,summary=plan();out=ROOT/"r5_history_discovery";out.mkdir(exist_ok=True)
 with (out/"queue.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
 print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()
