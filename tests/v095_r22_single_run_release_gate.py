"""R22 single-run live-source quality and release report, fail closed by design.
Consumes source artifacts from the SAME GitHub Runner, keeps RAW immutable,
checks TDCC total-tier semantics and MOPS revenue units. Never publishes.
"""
import collections,datetime,hashlib,json,pathlib,decimal
import pyarrow.parquet as pq

ROOT=pathlib.Path("r22_combined")
ROOT.mkdir(exist_ok=True)
def load(path):
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
def sha(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def validate_tdcc():
    source=pathlib.Path("r20_tdcc_full")
    result=load(source/"report.json")
    if result["status"]!="PASS_FULL_BRONZE_SILVER_GOLD_QA_ONLY":return {"status":"BLOCKED","reason":result.get("error","TDCC_SOURCE_UNAVAILABLE")}
    raw=source/"bronze.json"
    if sha(raw)!=result["bronze_sha256"]:raise AssertionError("TDCC_SOURCE_SHA")
    rows=load(raw);silver=pq.read_table(source/"silver_candidate.parquet")
    if silver.num_rows!=len(rows):raise AssertionError("TDCC_SILVER_COUNT")
    fields={"證券代號","持股分級","人數","股數","占集保庫存數比例%"}
    if not fields.issubset(rows[0]):raise AssertionError("TDCC_REQUIRED_FIELDS")
    grouped=collections.defaultdict(dict)
    for r in rows:
        code=str(r["證券代號"]).strip() # only trim padding, preserve leading zeros and suffixes
        if not code:raise AssertionError("TDCC_EMPTY_SECURITY_ID")
        grade=int(r["持股分級"])
        period=str(r.get("\ufeff資料日期",r.get("資料日期","")))
        if grade in grouped[(period,code)]:raise AssertionError("TDCC_DUPLICATE_TIER")
        grouped[(period,code)][grade]=r
    missing=sum(set(group)!=set(range(1,18)) for group in grouped.values())
    if missing:raise AssertionError("TDCC_MISSING_TIER_GROUPS")
    discrepancy=0;share_discrepancy=0;ratio_warnings=0
    flagged_groups=[]
    for (period,code),levels in grouped.items():
        holders=sum(int(levels[i]["人數"].replace(",","")) for i in range(1,17))
        shares=sum(int(levels[i]["股數"].replace(",","")) for i in range(1,17))
        total_holders=int(levels[17]["人數"].replace(",",""))
        total_shares=int(levels[17]["股數"].replace(",",""))
        count_diff=(holders!=total_holders or shares!=total_shares)
        if count_diff:discrepancy+=1
        if shares!=total_shares:share_discrepancy+=1
        pct=sum(decimal.Decimal(str(levels[i]["占集保庫存數比例%"]).replace(",","")) for i in range(1,17))
        ratio_warning=abs(pct-decimal.Decimal("100"))>decimal.Decimal(".08")
        if ratio_warning:ratio_warnings+=1
        if count_diff or ratio_warning:
            flagged_groups.append({"observation_date":period,"security_id":code,
                "holders_sum_16_tiers":holders,"holders_reported_total":total_holders,
                "shares_sum_16_tiers":shares,"shares_reported_total":total_shares,
                "sum_share_percent_16_tiers":str(pct),
                "ratio_uses_tdcc_inventory_not_issued_shares":True,
                "share_total_discrepancy":shares!=total_shares,
                "ratio_warning":ratio_warning,
                "official_semantics_certified":False})
    detail_path=ROOT/"TDCC_NATIVE_GROUP_WARNINGS.json"
    detail_path.write_text(json.dumps({"schema":"JARVIS_R22_TDCC_WARNING_GROUPS_V2",
        "source_sha256":sha(raw),"total_groups":len(grouped),
        "flagged_groups":flagged_groups,
        "requires_official_weekly_inventory_denominator_and_security_type":True,
        "security_code_normalization":"TRIM_OUTER_WHITESPACE_ONLY_KEEP_LEADING_ZEROS",
        "formal_pit_verified":False},ensure_ascii=False,indent=2))
    return {"status":"PASS_WITH_SEMANTIC_WARNINGS","records":len(rows),"groups":len(grouped),
        "discrepant_groups":discrepancy,"share_discrepant_groups":share_discrepancy,
        "ratio_warning_groups":ratio_warnings,"warning_group_details":str(detail_path),
        "warning_group_detail_count":len(flagged_groups),
        "sha256":sha(raw),"full_source":True,
        "pit_verified":False,"investment_gold_approved":False}
def validate_mops_ndc():
    report=load("r19_live_candidates/report.json")
    results={}
    for item in report["results"]:
        source=item["source"]
        if item["status"]!="PASS_LOCAL_THREE_LAYER_QA_ONLY":
            results[source]={"status":"BLOCKED","reason":item.get("error","API_OR_SCHEMA_FAILURE")}
            continue
        folder=pathlib.Path("r19_live_candidates")/source
        silver=folder/"silver_sample.parquet"
        row=pq.read_table(silver).to_pylist()
        if len(row)!=1:raise AssertionError(source+"_ONE_ROW_PARQUET_READBACK")
        gold=load(folder/"gold_qa_only.json")
        if gold["source_sha256"]!=item["bronze_sha256"] or gold["silver_sha256"]!=sha(silver):
            raise AssertionError(source+"_LINEAGE")
        if source=="MOPS":
            revenue=decimal.Decimal(row[0]["revenue_thousand_ntd"])
            expected=decimal.Decimal(gold["metrics"]["value"])
            if revenue/decimal.Decimal(100000)!=expected:
                raise AssertionError("MOPS_100M_NTD_UNIT_CONVERSION")
        results[source]={"status":"PASS_CANDIDATE_ONLY","records":len(row),"sha256":sha(silver),
             "pit_verified":False,"investment_gold_approved":False}
    return results
def main():
    legacy=load("r17_live_source_connectivity.json")
    live={x["source"]:x for x in legacy["results"]}
    r18=load("r18_live_recovery_report.json")
    recovery={x["source"]:x for x in r18["source_results"]}
    tdcc=validate_tdcc()
    candidates=validate_mops_ndc()
    sources={}
    for s in ("TWSE","TPEx","TAIFEX","FinMind"):
        item=live.get(s,{})
        sources[s]={"status":"API_SAMPLE_PASS" if item.get("data_verified") else "BLOCKED",
            "numeric_verified":False,"pit_verified":False,"complete_three_layer":False}
    sources["TDCC"]=tdcc
    for s in ("MOPS","NDC"):
        info=candidates.get(s,{"status":"BLOCKED"})
        sources[s]=dict(info)
        key="MOPS_REVENUE" if s=="MOPS" else "NDC_XLSX"
        sources[s]["live_download_verified"]=recovery.get(key,{}).get("valid_data",False)
    report={"schema":"JARVIS_V095_R22_SINGLE_RUN_GATE","release_approved":False,
         "release_reason":"NUMERIC_PIT_7SOURCES_AND_DRIVE_DISTRIBUTED_RELEASE_UNVERIFIED",
         "sources":sources,"seven_sources_present":len(sources)==7,
         "tdcc_warnings_not_auto_corruption":True,
         "cross_runner_drive_atomic_cas_verified":False,
         "live_daily_and_historical_parallel_verified":False,
         "two_market_sessions_verified":False,
         "independent_production_restore_verified":False}
    path=ROOT/"R22_RELEASE_GATE.json"
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("R22_SOURCE_STATUS "+json.dumps({k:v["status"] for k,v in sources.items()},ensure_ascii=False))
    print("R22_TDCC_ROWS",tdcc.get("records"),"GROUPS",tdcc.get("groups"),
        "DISCREPANCIES",tdcc.get("discrepant_groups"),"RATIO_WARNINGS",tdcc.get("ratio_warning_groups"))
    print("R22_RELEASE_APPROVED=false")
    # Integration run must actually fail if a previously healthy live source is unavailable.
    missing=[s for s,v in sources.items() if v["status"]=="BLOCKED"]
    if missing:raise SystemExit("R22_SOURCE_BLOCKED "+",".join(missing))
if __name__=="__main__":main()
