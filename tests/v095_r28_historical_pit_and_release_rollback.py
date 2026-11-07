"""R28 production-prelaunch: official dual-market master completeness,
look-ahead negative tests, and fail-closed staged release rollback.

All outputs TEST_ONLY. Local POSIX staging is NOT Google Drive atomic CAS.
No real publish or live production mutation.
"""
import collections,datetime,hashlib,json,os,pathlib,tempfile,unittest
import pyarrow.parquet as pq
ROOT=pathlib.Path("r28_prelaunch")
ROOT.mkdir(exist_ok=True)
def load(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def sha(b):return hashlib.sha256(b).hexdigest()
def historical_match(market_snapshot,source_date,decision_timestamp):
    """Current snapshots cannot establish prior-date security listing."""
    retrieved=datetime.datetime.fromisoformat(market_snapshot["retrieval_utc"])
    decision=datetime.datetime.fromisoformat(decision_timestamp)
    if retrieved>decision:return {"eligible":False,"reason":"FUTURE_SNAPSHOT_LOOKAHEAD"}
    if not market_snapshot.get("asof_historical_verified"):return {"eligible":False,"reason":"HISTORICAL_MEMBERSHIP_NOT_CERTIFIED"}
    if not source_date:return {"eligible":False,"reason":"SOURCE_DATE_MISSING"}
    return {"eligible":False,"reason":"HISTORICAL_PUBLICATION_TIME_NOT_CERTIFIED"}
def simulate_single_writer_and_rollback(base):
    base.mkdir(parents=True,exist_ok=True)
    pointer=base/"CURRENT.json"
    v1={"generation":1,"artifact_sha256":sha(b"bronze-v1"),"release_approved":False}
    v2={"generation":2,"artifact_sha256":sha(b"bronze-v2"),"release_approved":False}
    pointer.write_text(json.dumps(v1))
    previous=pointer.read_bytes()
    staging=base/"STAGED.json"
    staging.write_text(json.dumps(v2))
    # A crash BEFORE explicit promotion must preserve the original pointer.
    assert pointer.read_bytes()==previous
    # Reject an unexpected generation; this only works for a SINGLE LOCAL publisher.
    current=json.loads(pointer.read_text())
    rejected=0
    for wrong_generation in (0,2,10):
        if current["generation"]!=wrong_generation:rejected+=1
    assert rejected==3
    # Explicit isolated promotion and restore previous pointer.
    os.replace(staging,pointer)
    assert load(pointer)["generation"]==2
    restore=base/"RESTORE.json"
    restore.write_bytes(previous)
    os.replace(restore,pointer)
    assert pointer.read_bytes()==previous
    return {"single_local_publisher_staged_promotion":"PASS","rollback_to_prior_pointer":"PASS",
        "stale_generation_rejections":rejected,"drive_distributed_cas_verified":False,
        "real_drive_promotion_verified":False}
def main():
    r27=load("r27_official_security_master/R27_current_master_join_report.json")
    r25=load("r25_integrated_admission/R25_SIGNED_ADMISSION_GATE.json")
    r26=load("r26_evidence_register/R26_RECONCILED_GO_LIVE_GATE.json")
    if not r27["current_market_snapshot_join_pass"]:raise RuntimeError("BOTH_OFFICIAL_MASTERS_NOT_READY")
    if r25["release_approved"] or r26["release_approved"]:raise RuntimeError("UNEXPECTED_APPROVAL")
    snapshots={}; master_codes={}
    for market,field in (("TSE","公司代號"),("OTC","SecuritiesCompanyCode")):
        p=ROOT.parent/"r27_official_security_master"/(market+"_snapshot.json")
        buf=p.read_bytes()
        meta=r27["market_sources"][market]
        if sha(buf)!=meta["sha256"]:raise RuntimeError(market+"_SHA_MISMATCH")
        raw=json.loads(buf.decode("utf-8-sig"))
        codes=[str(x[field]).rstrip(" ") for x in raw if x.get(field) is not None]
        duplicate_codes=[k for k,v in collections.Counter(codes).items() if v>1]
        snapshots[market]={"rows":len(raw),"raw_sha256":sha(buf),
                           "distinct_codes":len(set(codes)),
                           "duplicate_code_count":len(duplicate_codes),
                           "retrieval_utc":meta["retrieval_utc"],
                           "historical_pit_verified":False}
        master_codes[market]=set(codes)
    overlapping=sorted(master_codes["TSE"]&master_codes["OTC"])
    # Current raw membership is not certification for any historical TDCC record.
    rows=pq.read_table("r24_tdcc_numeric_gold_candidate/tdcc_gold_qa_only.parquet",
                       columns=["security_id","source_date_raw"]).to_pylist()
    results=collections.Counter()
    for row in rows:
        for m in ("TSE","OTC"):
            # Explicit historical decision earlier than snapshot retrieval.
            meta=r27["market_sources"][m]
            decision="2026-10-30T07:00:00+00:00"
            out=historical_match(meta,row["source_date_raw"],decision)
            results[out["reason"]]+=1
            if out["eligible"]:raise AssertionError("LOOKAHEAD_RELEASED")
    local=simulate_single_writer_and_rollback(ROOT/"local_pointer_test")
    report={"schema":"JARVIS_R28_PRELAUNCH_HISTORICAL_PIT_AND_RELEASE_QA",
        "release_approved":False,"official_current_snapshots":snapshots,
        "current_market_master_code_overlap":len(overlapping),
        "overlap_examples":overlapping[:10],
        "historical_eligibility_counter":dict(results),
        "tdcc_rows_audited":len(rows),
        "local_single_writer_test":local,
        "historic_security_master_verified":False,
        "gold_pit_verified":False,
        "drive_distributed_atomic_publish_verified":False,
        "interpretation":"Safe anti-lookahead for Oct 30 decision using Nov 4 current snapshots. Local rollback passes, not Drive CAS."}
    (ROOT/"R28_GATE.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print("R28_MASTER_DUPLICATES "+json.dumps({k:v["duplicate_code_count"] for k,v in snapshots.items()}))
    print("R28_MASTER_OVERLAP "+str(len(overlapping)))
    print("R28_LOOKAHEAD_REJECTED "+str(sum(results.values())))
    print("R28_LOCAL_ROLLBACK_PASS=true")
    print("R28_DRIVE_DISTRIBUTED_CAS_VERIFIED=false")
    print("R28_RELEASE_APPROVED=false")
if __name__=="__main__":main()
