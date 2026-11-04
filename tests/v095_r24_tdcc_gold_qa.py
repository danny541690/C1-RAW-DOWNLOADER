"""R24: actual TDCC full-dataset QA Gold candidate + strict publish guard.
Unit meaning remains source-native. No investment signal released before
TDCC tier semantics, publication timestamp and TSE/OTC security master QA.
"""
import collections,decimal,hashlib,json,pathlib
import pyarrow as pa
import pyarrow.parquet as pq

SRC=pathlib.Path("r20_tdcc_full")
OUT=pathlib.Path("r24_tdcc_numeric_gold_candidate")
OUT.mkdir(exist_ok=True)
D=decimal.Decimal
def sha(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()
def n(v):return int(str(v).replace(",",""))
def derive():
    audit=json.loads((SRC/"report.json").read_text())
    if audit.get("status")!="PASS_FULL_BRONZE_SILVER_GOLD_QA_ONLY":raise ValueError("RAW_CANDIDATE_NOT_APPROVED")
    raw=SRC/"bronze.json";p=SRC/"silver_candidate.parquet"
    if sha(raw)!=audit["bronze_sha256"] or sha(p)!=audit["silver_sha256"]:raise ValueError("SOURCE_HASH_MISMATCH")
    rows=json.loads(raw.read_text(encoding="utf-8-sig"))
    if pq.read_metadata(p).num_rows!=len(rows):raise ValueError("SILVER_ROW_COUNT_MISMATCH")
    grouped=collections.defaultdict(dict)
    for row in rows:
        date=str(row.get("\ufeff資料日期",row.get("資料日期","")))
        stock=str(row["證券代號"])
        grade=n(row["持股分級"])
        if grade<1 or grade>17 or grade in grouped[(date,stock)]:raise ValueError("INVALID_OR_DUPLICATE_GRADE")
        grouped[(date,stock)][grade]=row
    result=[];counts=collections.Counter()
    for (date,stock),levels in grouped.items():
        if set(levels)!=set(range(1,18)):raise ValueError("INCOMPLETE_TIERS")
        holders=n(levels[17]["人數"]);shares=n(levels[17]["股數"])
        total_subholders=sum(n(levels[i]["人數"]) for i in range(1,17))
        total_subshares=sum(n(levels[i]["股數"]) for i in range(1,17))
        ratio_sum=sum(D(str(levels[i]["占集保庫存數比例%"]).replace(",","")) for i in range(1,17))
        holders_diff=total_subholders-holders
        shares_diff=total_subshares-shares
        ratio_warning=abs(ratio_sum-D("100"))>D(".08")
        warning=bool(holders_diff or shares_diff or ratio_warning)
        counts["group_warnings"]+=int(warning)
        counts["holder_or_share_diff"]+=int(bool(holders_diff or shares_diff))
        counts["share_diff"]+=int(shares_diff!=0)
        counts["ratio_warning"]+=int(ratio_warning)
        # This is a candidate arithmetic example, not a validated concentration threshold.
        ratio12to15=sum(D(str(levels[i]["占集保庫存數比例%"]).replace(",","")) for i in range(12,16))
        result.append({"source_date_raw":date,"security_id":stock,
          "total_holders_reported":holders,"total_shares_reported":shares,
          "level_12_15_reported_ratio_pct_QA_ONLY":str(ratio12to15),
          "sum_level_1_16_reported_ratio_pct":str(ratio_sum),
          "holder_difference":holders_diff,"share_difference":shares_diff,
          "ratio_warning":ratio_warning,"semantic_review_required":warning,
          "pit_verified":False,"security_master_verified":False,"numeric_semantics_verified":False,
          "investment_gold_approved":False})
    out=OUT/"tdcc_gold_qa_only.parquet"
    pq.write_table(pa.Table.from_pylist(result),out,compression="zstd")
    read=pq.read_table(out).to_pylist()
    if read!=result:raise AssertionError("QA_GOLD_PARQUET_READBACK")
    for r in read:
        if r["investment_gold_approved"] or r["pit_verified"] or r["security_master_verified"]:
            raise ValueError("GOLD_RELEASE_POLICY_VIOLATION")
    return {"schema":"JARVIS_R24_TDCC_GOLD_QA_ONLY","status":"PASS_CANDIDATE_ONLY",
      "source_rows":len(rows),"security_date_groups":len(result),
      "warning_counts":dict(counts),"source_bronze_sha256":sha(raw),
      "source_silver_sha256":sha(p),"gold_candidate_sha256":sha(out),
      "publication_timestamp":None,"security_master_validated":False,"release_approved":False}
def main():
    try:
        result=derive()
        print("R24_TDCC_QA_GROUPS="+str(result["security_date_groups"]))
        print("R24_TDCC_QA_WARNINGS="+json.dumps(result["warning_counts"]))
    except Exception as exc:
        result={"schema":"JARVIS_R24_TDCC_GOLD_QA_ONLY","status":"BLOCKED",
            "release_approved":False,"error":type(exc).__name__+":"+str(exc)}
        (OUT/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
        print("R24_TDCC_QA_STATUS=BLOCKED "+result["error"])
        raise
    (OUT/"report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print("R24_TDCC_QA_STATUS=PASS_CANDIDATE_ONLY")
    print("R24_RELEASE_APPROVED=false")
if __name__=="__main__":main()
