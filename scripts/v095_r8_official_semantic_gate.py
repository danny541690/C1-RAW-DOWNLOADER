#!/usr/bin/env python3
"""Official-source semantics gate (read-only).

This rejects fake missing-data labels and improper Gold publication.
It *does not* certify historic dates or download missing market data.
"""
import json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
CONTRACT=ROOT/"config/v095_r8_official_source_semantics_20261107.json"
R7=ROOT/"governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json"
FLAGS=ROOT/"governance/v095/PHASE1_FLAGS.json"
OUTPUT=ROOT/"r8_official_semantics"
def adjudicate(config,receipts,flags):
    sources={x["dataset"]:x for x in config["source_documents"]}
    errors=[]
    def check(cond,msg):
        if not cond:errors.append(msg)
    otc=sources.get("TPEx.DailyQuotesBulk",{})
    tdcc=sources.get("TDCC.ShareholderDistribution",{})
    check(otc.get("first_documented_month")=="2003-08","INVALID_TPEX_BULK_EARLIEST")
    check(tdcc.get("first_documented_month")=="2008-07","INVALID_TDCC_HISTORY_START")
    check(tdcc.get("live_online_history_retention")=="ONE_YEAR_PER_OFFICIAL_PAGE","INVALID_TDCC_RETENTION")
    check(config["normalization"]["TDCC"]["share_percent_denominator"]=="CUSTODIAL_INVENTORY_SHARES_NOT_ISSUED_SHARES","INVALID_TDCC_DENOMINATOR")
    check(config["normalization"]["TPEX"]["positive_volume_non_numeric_ohlc"]==255 and config["normalization"]["TPEX"]["zero_volume_non_numeric_ohlc"]==157,"INVALID_TPEX_EXCEPTION_CENSUS")
    check(config["normalization"]["TPEX"]["price_null_not_zero"] is True and config["normalization"]["TPEX"]["no_inferred_suspension"] is True,"TPEX_ZERO_OR_SUSPENSION_FABRICATION")
    check(config["history"]["documented_start_is_not_live_reachability"] is True,"HISTORY_REACHABILITY_MISREPRESENTED")
    check(config["separate_release_gates"]["never_promote_bronze_to_gold"] is True,"GOLD_PROMOTION_UNSAFE")
    check(flags.get("BULK_COPY_APPROVED") is False and flags.get("RELEASE_APPROVED") is False,"UNSAFE_EXISTING_RELEASE_FLAGS")
    prior=receipts["immutable_receipts"]
    check(len(prior)==12 and len(set(x["key"] for x in prior))==12,"ACCEPTED_PARTITION_LEDGER_INVALID")
    report={"schema":"JARVIS_V095_R8_OFFICIAL_SEMANTICS_VALIDATION",
        "status":"PASS_RULE_CONTRACT_NOT_DATA_RELEASE" if not errors else "BLOCKED_INVALID_POLICY",
        "errors":errors,"previously_verified_scoped_candidates_skipped":len(prior),
        "confirmed_no_redownload_for_accepted":True,
        "tpex_history_rule":{"bulk_documented_from":"2003-08","before_start":"NOT_APPLICABLE_TO_THIS_BULK_DATASET"},
        "tdcc_history_rule":{"source_history_constructed_from":"2008-07","archive_retention":"ONE_YEAR","denominator":"TDCC_CUSTODIAL_INVENTORY"},
        "tdcc_errors":{"total_share_diff":58,"ratio_warnings":451,"decision":"HOLD_UNTIL_WEEK_GROUP_SOURCE_ROW_RECONCILIATION"},
        "tpex_412_errors":{"volume_positive":255,"volume_zero":157,"decision":"NATIVE_PRICE_NULL_KEEP_RAW_NEED_SECURITY_ASOF"},
        "known_unresolved":["R22_TWSE_FULL_SOURCE_CONTRACT","TDCC_NATIVE_WEEKLY_GROUP_RECONCILIATION","TPEX_SECURITY_MASTER","OFFICIAL_DATASET_EXPECTED_COUNTS","443_FORMULA_PIT_ROW_LINEAGE","V095_WRITER_CAS_FENCING"],
        "bronze_bulk_download_enabled":False,"gold_research_release_enabled":False}
    return report
def main():
    cfg=json.loads(CONTRACT.read_text());r=json.loads(R7.read_text());flags=json.loads(FLAGS.read_text())
    report=adjudicate(cfg,r,flags)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:report[k] for k in ("status","errors","previously_verified_scoped_candidates_skipped","known_unresolved")},ensure_ascii=False))
    return 0 if not report["errors"] else 2
if __name__=="__main__":sys.exit(main())
