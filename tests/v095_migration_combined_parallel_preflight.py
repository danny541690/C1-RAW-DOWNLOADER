"""ONE combined pre-copy/pre-transform preflight + bounded local parallel benchmark.
Inputs are REAL data from same isolated Github run (R20/R24/R27).
NO Drive writes, NO live source concurrency test, NO production release.
"""
import concurrent.futures,collections,datetime,hashlib,json,os,pathlib,tempfile,time,statistics,shutil
import pyarrow as pa
import pyarrow.parquet as pq
ROOT=pathlib.Path("v095_migration_single_preflight")
ROOT.mkdir(exist_ok=True)
SRC=pathlib.Path("r20_tdcc_full/bronze.json")
AUDIT=pathlib.Path("r20_tdcc_full/report.json")
SILVER=pathlib.Path("r20_tdcc_full/silver_candidate.parquet")
R24=pathlib.Path("r24_tdcc_numeric_gold_candidate/report.json")
R27=pathlib.Path("r27_official_security_master/R27_current_master_join_report.json")
def digest(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()
def ledger_copy(src,dst,expected,ledger):
    """Simulated independent object copy. Never replace if different."""
    if dst.exists():
        if digest(dst)==expected:
            ledger.append("ALREADY_VERIFIED_SKIP")
            return "SKIP"
        ledger.append("DEST_CONFLICT_QUARANTINE")
        return "CONFLICT"
    tmp=dst.with_suffix(dst.suffix+".incomplete")
    if tmp.exists():tmp.unlink()
    with src.open("rb") as a,tmp.open("wb") as b:
        shutil.copyfileobj(a,b,1024*1024)
    if digest(tmp)!=expected:
        tmp.unlink()
        raise RuntimeError("STAGING_SHA_MISMATCH")
    os.replace(tmp,dst)
    if digest(dst)!=expected:raise RuntimeError("DEST_READBACK_SHA_MISMATCH")
    ledger.append("NEW_COPY_VERIFIED")
    return "COPY"
def synthetic_archive_checks():
    from v095_v093_migration_preflight import mkzip,verify_bytes
    valid=mkzip([("market_data.csv","date,price\n2026-10-01,10")])
    manifest=mkzip([("manifest.json",'{"all_market_complete":false,"units":[]}')])
    s1=verify_bytes(valid,2026,"TWSE","2026-10",hashlib.sha256(valid).hexdigest())
    s2=verify_bytes(manifest,2026,"MOPS","2026-10",hashlib.sha256(manifest).hexdigest())
    if s1["status"]!="PASS_COPY_PREFLIGHT_ONLY" or s2["status"]!="QUARANTINE_MANIFEST_ONLY":
        raise RuntimeError("ARCHIVE_CLASSIFICATION_FAILED")
    return {"real_archive_fixture_verified":False,
      "synthetic_valid_archive":s1["status"],
      "synthetic_manifest_only":s2["status"]}
def transform_qa():
    audit=json.loads(AUDIT.read_text())
    r24=json.loads(R24.read_text())
    r27=json.loads(R27.read_text())
    if audit.get("full_bronze_verified") is not True:raise RuntimeError("BRONZE_FULL_BLOCKED")
    if digest(SRC)!=audit["bronze_sha256"] or digest(SILVER)!=audit["silver_sha256"]:
        raise RuntimeError("SOURCE_HASH_MISMATCH")
    count=pq.read_metadata(SILVER).num_rows
    if count!=audit["source_rows"] or r24["security_date_groups"]<1:raise RuntimeError("SILVER_COUNT_MISMATCH")
    if r27["current_market_snapshot_join_pass"] is not True:raise RuntimeError("MARKET_MASTER_MISSING")
    # Test actual Parquet *structural* partition path without allocating Gold.
    table=pq.read_table(SILVER,columns=["source","source_row_number","source_sha256"])
    if table.num_rows!=count:raise RuntimeError("PARTITION_SOURCE_COUNT_DRIFT")
    with tempfile.TemporaryDirectory() as temp:
        tmp=pathlib.Path(temp)
        pq.write_to_dataset(table,root_path=str(tmp/"silver"),partition_cols=["source"],compression="zstd")
        back=pq.read_table(tmp/"silver").select(table.column_names)
        if back.num_rows!=count:raise RuntimeError("PARQUET_PARTITION_COUNT_DRIFT")
        if set(back["source"].to_pylist())!={"TDCC"}:raise RuntimeError("PARQUET_SOURCE_DRIFT")
    return {"tdcc_source_rows":count,"tdcc_qa_groups":r24["security_date_groups"],
     "tdcc_semantic_warning_groups":r24["warning_counts"].get("group_warnings"),
     "silver_structural_parquet_repartition":"PASS_ISOLATED",
     "real_numeric_pit_verified":False,"gold_approved":False}
def task(blob):
    return hashlib.sha256(blob).hexdigest()
def bench(chunks,workers):
    times=[]
    expected=[task(x) for x in chunks]
    for repetition in range(2):
        start=time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            observed=list(ex.map(task,chunks))
        elapsed=time.perf_counter()-start
        if observed!=expected:raise RuntimeError("HASH_BENCHMARK_DIVERGED")
        times.append(elapsed)
    return {"local_workers":workers,"seconds_runs":[round(x,5) for x in times],
        "median_seconds":round(statistics.median(times),5),"errors":0}
def main():
    required=[SRC,AUDIT,SILVER,R24,R27]
    for p in required:
        if not p.exists():raise RuntimeError("MISSING_REAL_INPUT:"+str(p))
    audited=transform_qa()
    # Benchmarks local file hashing: NOT equivalent to real Drive API transfer.
    data=SRC.read_bytes()
    chunks=[data[i:i+1024*1024] for i in range(0,len(data),1024*1024)]
    benchmarks=[bench(chunks,n) for n in (1,2,4,8)]
    measured={r["local_workers"]:r["median_seconds"] for r in benchmarks}
    base=measured[1]
    # Staged pilot cap: 4 global workers, 1 writer per source/dataset.
    # 8 is BENCHMARK ONLY, not admitted to actual API work.
    selected=4 if measured[4]<=base*1.10 else (2 if measured[2]<=base*1.10 else 1)
    with tempfile.TemporaryDirectory() as temp:
        src=pathlib.Path(temp)/"original.bin"
        dst=pathlib.Path(temp)/"staged.bin"
        src.write_bytes(data[:4096])
        h=digest(src)
        ledger=[]
        a=ledger_copy(src,dst,h,ledger)
        b=ledger_copy(src,dst,h,ledger)
        dst.write_bytes(b"DIFFERENT")
        c=ledger_copy(src,dst,h,ledger)
        if (a,b,c)!=("COPY","SKIP","CONFLICT"):raise RuntimeError("RESTART_OR_CONFLICT_GATE_FAILED")
        if digest(src)!=h:raise RuntimeError("SOURCE_MODIFIED")
    archive=synthetic_archive_checks()
    report={
      "schema":"JARVIS_V095_MIGRATION_COMBINED_PREFLIGHT_V1",
      "generated_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
      "raw_sha256":digest(SRC),"raw_size_bytes":len(data),
      "archive_fixture":archive,"real_data_parquet_qa":audited,
      "local_hash_benchmark":{"benchmark_type":"LOCAL_IN_MEMORY_SHA256_ONLY",
        "chunks":len(chunks),"bytes_each_max":1048576,
        "trials_per_setting":2,"results":benchmarks,
        "caveat":"NOT Google Drive API, no live network throughput, no API quotas tested"},
      "recommended_trial_policy":{
         "migration_global_workers":selected,
         "initial_drive_read_concurrency":2,
         "initial_drive_copy_concurrency":1,
         "initial_source_writers_per_dataset":1,
         "parallel_shards_only_distinct_dataset_month":True,
         "independent_release_publisher":1,
         "network_parallel_8_enabled":False,
         "decision":"PROVISIONAL_SUBJECT_TO_REAL_API_BENCHMARK_QUOTA_AND_ERRORS"},
      "isolated_copy_resume_conflict":{"copy":"PASS","idempotent_skip":"PASS",
        "same_name_different_hash_blocked":"PASS","source_unchanged":"PASS"},
      "required_before_bulk_copy":[
         "COMPLETE_2000_2026_PAGINATED_SOURCE_INVENTORY",
         "SOURCE_AND_DEST_FULL_BYTE_SHA_AND_ZIP_CHECK",
         "PROVEN_PER_DATASET_AVAILABLE_DATES_AND_PUBLISHED_AT",
         "REAL_DRIVE_API_CONCURRENCY_LATENCY_429_ERROR_BENCHMARK",
         "DRIVE_WRITE_CREDENTIALS_QUOTA_AND_SINGLE_WRITER_LEASE",
         "FULL_SOURCE_SPECIFIC_TYPED_PARQUET_NUMERIC_PIT_TRANSFORM",
         "PERSISTENT_CHECKPOINT_AND_ISSUE_REPAIR_LEDGER",
         "RESTORE_TEST_AND_OFFICIAL_GOLD_ADMISSION"],
      "bulk_copy_approved":False,"production_release_approved":False}
    (ROOT/"COMBINED_PRECOPY_PRETRANSFORM_GATE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("COMBINED_PREFLIGHT_LOCAL_BENCH="+json.dumps(measured))
    print("COMBINED_PREFLIGHT_TRIAL_WORKERS="+str(selected))
    print("COMBINED_PREFLIGHT_REAL_DATA_PARQUET_ROWS="+str(audited["tdcc_source_rows"]))
    print("COMBINED_PREFLIGHT_BULK_COPY_APPROVED=false")
if __name__=="__main__":main()
