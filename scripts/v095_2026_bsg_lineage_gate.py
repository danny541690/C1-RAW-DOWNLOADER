#!/usr/bin/env python3
"""Per-accepted-partition B/S/G bidirectional hash and row trace audit.
Runs only after candidate source producer finishes. Does not assert historical PIT.
"""
import collections, hashlib, io, json, os, pathlib, sys
import pyarrow.parquet as pq
from scripts.v095_2026_annual_consolidated import service
ROOT=pathlib.Path("v095_2026_price_incremental")
def digest(data):return hashlib.sha256(data).hexdigest()
def audit(s,item):
    ids={k:item[k+"_id"] for k in ("bronze","silver","gold")}
    sha={k:item[k+"_sha256"] for k in ids}
    blobs={k:s.files().get_media(fileId=v).execute() for k,v in ids.items()}
    for k,v in blobs.items():
        if digest(v)!=sha[k]:raise ValueError("REMOTE_SHA_MISMATCH_"+k)
    silver=pq.read_table(io.BytesIO(blobs["silver"]))
    gold=pq.read_table(io.BytesIO(blobs["gold"]))
    if silver.num_rows!=item["rows"] or gold.num_rows!=item["gold_rows"]:raise ValueError("ROW_COUNT_MISMATCH")
    for table,cols in ((silver,("bronze_file_id","bronze_sha256")),
                       (gold,("bronze_file_id","bronze_sha256","silver_file_id","silver_sha256"))):
        if not set(cols).issubset(table.column_names):raise ValueError("LINEAGE_COLUMN_MISSING")
        for col in cols:
            expected=ids[col.split("_")[0]] if col.endswith("_file_id") else sha[col.split("_")[0]]
            if set(table[col].to_pylist())!={expected}:raise ValueError("UPSTREAM_LINEAGE_SHA_OR_ID_MISMATCH_"+col)
    sk={(x,y) for x,y in zip(silver["stock_id"].to_pylist(),silver["trade_date"].to_pylist())}
    gk={(x,y) for x,y in zip(gold["stock_id"].to_pylist(),gold["trade_date"].to_pylist())}
    if len(sk)!=silver.num_rows or len(gk)!=gold.num_rows or not gk.issubset(sk):
        raise ValueError("GOLD_SILVER_REVERSE_STOCK_ROW_MAPPING_FAILED")
    return {"source":item["source"],"date":item["date"],"silver_rows":silver.num_rows,"gold_rows":gold.num_rows,
            "forward_gold_silver_bronze_sha":"PASS","reverse_bronze_silver_gold_key_subset":"PASS",
            "historical_pit":"NOT_CERTIFIED"}
def main():
    p=ROOT/"result.json"
    if not p.exists():raise SystemExit("SOURCE_BATCH_RESULT_MISSING")
    data=json.loads(p.read_text())
    s=service();done=[];fail=[]
    for item in data.get("completed",[]):
        try:done.append(audit(s,item))
        except Exception as exc:fail.append({"source":item["source"],"date":item["date"],"error":type(exc).__name__+":"+str(exc)[:150]})
    report={"run_id":os.getenv("GITHUB_RUN_ID"),"source":data.get("active_source"),"accepted_partition_checks":len(done),
      "lineage_failures":fail,"source_day_failures":len(data.get("failed",[])),
      "historical_PIT_certified":False,"whole_year_certified":False,"passed":not fail}
    (ROOT/"lineage_receipt.json").write_text(json.dumps({"summary":report,"partitions":done},ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    return 0 if not fail else 2
if __name__=="__main__":sys.exit(main())
