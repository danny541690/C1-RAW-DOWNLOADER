"""R23 distinct GitHub job: restore full TDCC candidate artifact and verify lineage.
This is cross-job artifact handoff and restore, NOT cloud atomic CAS or production release.
"""
import hashlib,json,os,pathlib,zipfile
import pyarrow.parquet as pq

ROOT=pathlib.Path("r20_tdcc_full")
OUT=pathlib.Path("r23_restore_evidence")
OUT.mkdir(exist_ok=True)
def sha(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()
def main():
    result={"schema":"JARVIS_V095_R23_INDEPENDENT_JOB_RESTORE",
            "release_approved":False,"distributed_cas_verified":False,
            "status":"BLOCKED","source":"TDCC"}
    try:
        source=ROOT/"bronze.json"
        silver=ROOT/"silver_candidate.parquet"
        gold=ROOT/"gold_qa_only.json"
        prior=ROOT/"report.json"
        for p in [source,silver,gold,prior]:
            if not p.is_file():raise ValueError("RESTORE_ARTIFACT_MISSING:"+str(p))
        recorded=json.loads(prior.read_text())
        if recorded.get("status")!="PASS_FULL_BRONZE_SILVER_GOLD_QA_ONLY":
            raise ValueError("SOURCE_JOB_GATE_NOT_PASS")
        if sha(source)!=recorded["bronze_sha256"] or sha(silver)!=recorded["silver_sha256"]:
            raise ValueError("RESTORE_SHA_DIFFERS_FROM_SOURCE_JOB")
        rows=json.loads(source.read_text(encoding="utf-8-sig"))
        table=pq.read_table(silver)
        if len(rows)!=69887 or table.num_rows!=len(rows):
            raise ValueError("RESTORE_ROW_COUNT_MISMATCH")
        for i in (0,len(rows)//2,len(rows)-1):
            converted=json.loads(table["source_record_json"][i].as_py())
            if converted!=rows[i]:raise ValueError("RESTORE_SOURCE_CONTENT_MISMATCH:"+str(i))
        g=json.loads(gold.read_text())
        if g.get("release_approved") is not False or g.get("metric")!="structural_row_count_QA_ONLY":
            raise ValueError("RESTORE_GOLD_APPROVAL_OR_TYPE_MISMATCH")
        if g["value"]!=len(rows) or g["bronze_sha256"]!=sha(source) or g["silver_sha256"]!=sha(silver):
            raise ValueError("RESTORE_GOLD_LINEAGE_MISMATCH")
        result.update(status="PASS_CROSS_JOB_RESTORE_QA_ONLY",rows=len(rows),
                      bronze_sha256=sha(source),silver_sha256=sha(silver),
                      bronze_bytes=source.stat().st_size,silver_bytes=silver.stat().st_size,
                      pit_verified=False,investment_gold_approved=False)
    except Exception as e:
        result["error"]=type(e).__name__+":"+str(e)[:300]
    (OUT/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("R23_RESTORE_STATUS="+result["status"])
    print("R23_ROWS="+str(result.get("rows")))
    print("R23_DISTRIBUTED_CAS_VERIFIED=false")
    print("R23_RELEASE_APPROVED=false")
    if not result["status"].startswith("PASS"):raise SystemExit(1)
if __name__=="__main__":main()
