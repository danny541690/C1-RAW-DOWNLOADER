#!/usr/bin/env python3
"""JARVIS v0.97 G2/G3 versioned formal contract specification and promotion guard.

All seven-source dataset families are enumerated. A source-wide reference URL
is NOT a dataset-era attestation. Native layout specifications are candidates
until real official documentation, immutable source evidence, full-file validation,
primary-key semantics, PIT and scope are independently verified.
This module NEVER materializes Silver or Gold or modifies Bronze.
"""
import hashlib,json,re,sys
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_v3_contract_registry import CONTRACTS,UNITS,normalize,REGISTRY_VERSION
VERSION="v097_g2g3_formal_contract_v2_20261117"
SOURCES=tuple(OFFICIAL_VERSIONS)
PROVENANCE_REQUIRED=("official_dataset_url","official_spec_sha256",
                     "official_response_sha256","official_retrieved_at")
G2_PROOFS=("source_id_sha","dataset_identity","historical_era_effective",
           "native_layout_member_identity","official_layout_provenance")
G3_PROOFS=("required_native_fields","typed_all_rows","primary_key_verified",
           "raw_units_verified","null_policy_verified","calendar_session_verified",
           "revision_pit_verified","security_scope_verified")
HISTORIC_HOLDS={
 "TWSE":("ZIP_MEMBER_IDENTITY_ORIGIN_PIT_PENDING","A05_FORMAT_EDITION_MIXED_TABLES"),
 "TPEx":("RAW_RECEIPT_IS_NOT_MARKET_DATA","DATE_PARTITION_2024_VS_2026_CONFLICT",
         "2000_2007_HISTORIC_SOURCE_FORMAT"),
 "MOPS":("GAAP_PRE_IFRS_XBRL_IXBRL_ACCOUNTING_ERA",
         "FILING_AMENDMENT_PUBLICATION_PIT"),
 "TDCC":("TDCC_SPECIAL_SECURITY_5035_HISTORY_CLASSIFICATION",
         "TWO_ZIP_429_SHARES_20_PERCENT_DIFFERENCES_HOLD"),
 "TAIFEX":("CSV_BLANK_TAIL_VS_TRUE_WIDTH_SHIFT","DAY_VS_AFTER_HOURS_TRADE_DATE"),
 "NDC":("UNDOCUMENTED_ORIGINAL_CELL_MISSING_NOT_ZERO","SIGNAL_METHOD_REVISIONS"),
 "FinMind":("SOURCE_PIT_AND_PROVIDER_REVISION","ROW_PERIOD_CONFLICT")
}
KEY_SCHEMAS={
 "TWSE":{"STOCK_DAILY_OHLCV":("date","code"),
         "INDEX":("date","index_id"),"INSTITUTIONAL":("date","code","investor_type")},
 "TPEx":{"STOCK_DAILY_OHLCV":("date","code"),
         "INDEX":("date","index_id"),"MARKET_CAPITALIZATION":("date","code")},
 "MOPS":{"MONTHLY_REVENUE":("period","code"),
         "INCOME_STATEMENT":("period","code","statement_item","filing_revision"),
         "BALANCE_SHEET":("period","code","statement_item","filing_revision"),
         "CASH_FLOW":("period","code","statement_item","filing_revision")},
 "TDCC":{"SHAREHOLDING_DISTRIBUTION":("date","code","tier"),
         "SECURITY_MASTER_ASOF":("effective_date","code")},
 "TAIFEX":{"FUTURES_DAILY":("date","contract","expiration","session"),
           "OPTIONS_DAILY":("date","contract","expiration","strike","put_call","session")},
 "NDC":{"BUSINESS_SIGNAL":("period","series_id"),
        "LEADING_INDEX":("period","series_id"),"SERIES_COMPONENTS":("period","series_id","component_id")},
 "FinMind":{"TaiwanStockPrice":("date","code"),
            "TaiwanStockFinancialStatements":("period","code","statement_item")}
}
NATIVE_VARIANTS={
 "TDCC":{"SHAREHOLDING_DISTRIBUTION":[
   {"id":"TDCC_HTML_16_TIERS_1_TO_15_PLUS_TOTAL","format":"HTML",
    "table_rows":16,"total_ordinal":16,"metadata":["code","date"],
    "source_fixture":"1--oAGav1QBgijxyNgkM3NVR5JiJ5oAgC",
    "observed_source_run":"44117824116"},
   {"id":"TDCC_ARCHIVE_17_TIERS_WITH_ADJUSTMENT","format":"JSONL_ZIP",
    "table_rows":17,"adjustment_ordinal":16,"total_ordinal":17,
    "caution":"429 shares and 20 percent discrepancies remain HOLD"}]},
 "TAIFEX":{"FUTURES_DAILY":[
   {"id":"DAY_SESSION_LEGACY","format":"CSV_ZIP","date_rule":"official_trade_date"},
   {"id":"DAY_AND_AFTER_HOURS","format":"CSV_ZIP",
    "date_rule":"after_hours_volume_next_general_session"}]},
 "MOPS":{"INCOME_STATEMENT":[
   {"id":"GAAP","format":"HTML_XBRL"},
   {"id":"IFRS_XBRL","format":"XBRL"},
   {"id":"IFRS_IXBRL","format":"IXBRL"}]},
 "TWSE":{"STOCK_DAILY_OHLCV":[
   {"id":"A05_COMMERCIAL_NATIVE","format":"CSV_TXT","date_rule":"A05_OFFICIAL_EDITION"},
   {"id":"PUBLIC_DAILY_MIXED_TABLES","format":"HTML_CSV_JSON","date_rule":"SOURCE_PUBLIC_LAYOUT"}]}
}
def contract(source,dataset,era):
    if source not in OFFICIAL_VERSIONS:raise ValueError("UNKNOWN_SOURCE")
    official=OFFICIAL_VERSIONS[source]
    if dataset not in official["datasets"]:raise ValueError("UNKNOWN_DATASET")
    matches=[p for p in official["periods"] if p["id"]==era]
    if not matches:raise ValueError("UNKNOWN_ERA")
    required=CONTRACTS.get(source,{}).get(dataset)
    keys=KEY_SCHEMAS.get(source,{}).get(dataset)
    versions=NATIVE_VARIANTS.get(source,{}).get(dataset,[])
    return {"schema":VERSION,"source":source,"dataset":dataset,"historical_era":era,
       "edition_window":{k:matches[0][k] for k in ("start","end")},
       "era_is_dataset_verified":False,
       "field_spec_state":"CANDIDATE" if required else "MISSING_DATASET_FIELD_SPEC",
       "required_fields":required or {},"native_units_candidate":UNITS.get(source,{}),
       "candidate_primary_key":list(keys or []),
       "source_native_variants":versions,
       "official_source_reference_candidates":official["reference"],
       "source_specific_open_holds":list(HISTORIC_HOLDS[source]),
       "promotion_state":"NOT_CERTIFIED",
       "g2_proof_requirements":list(G2_PROOFS),"g3_proof_requirements":list(G3_PROOFS),
       "silver_gold_materialized":False}
def catalog():
    output=[]
    for source,settings in OFFICIAL_VERSIONS.items():
        for dataset in settings["datasets"]:
            for p in settings["periods"]:
                output.append(contract(source,dataset,p["id"]))
    return output
def _sha(v):return bool(isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v))
def review(source,dataset,era,evidence):
    """Conservative formal G2/G3 evaluation. Verified only after complete attestation.
    This is a review verdict, not authorization for a Silver release job.
    """
    spec=contract(source,dataset,era)
    missing=[]
    if not isinstance(evidence,dict):evidence={}
    sid=evidence.get("source_id")
    raw=evidence.get("bronze_sha256")
    if not sid or not _sha(raw) or evidence.get("destination_sha256")!=raw:
        missing.append("G0_SOURCE_AND_DEST_SHA")
    if evidence.get("dataset")!=dataset or evidence.get("source")!=source or evidence.get("historical_era")!=era:
        missing.append("G2_DATASET_ERA_IDENTITY")
    if not evidence.get("historical_asof_within_effective_window"):
        missing.append("G2_ERA_EFFECTIVE_DATE")
    if not evidence.get("native_member_sha_match"):
        missing.append("G2_MEMBER_LINEAGE")
    off=evidence.get("official_provenance",{})
    if not isinstance(off,dict):off={}
    if not off.get("official_dataset_url") or not _sha(off.get("official_spec_sha256")) or not _sha(off.get("official_response_sha256")) or not off.get("official_retrieved_at"):
        missing.append("G2_OFFICIAL_LAYOUT_PROVENANCE")
    if not off.get("dataset_era_binding_verified"):
        missing.append("G2_OFFICIAL_DATASET_ERA_BINDING")
    if not spec["required_fields"]:
        missing.append("G3_DATASET_FIELD_SPEC_MISSING")
    if not spec["candidate_primary_key"]:
        missing.append("G3_DATASET_PRIMARY_KEY_SPEC_MISSING")
    if not evidence.get("full_native_required_fields_verified"):
        missing.append("G3_REQUIRED_NATIVE_FIELDS")
    if not evidence.get("all_native_rows_typed"):
        missing.append("G3_ALL_ROWS_TYPED")
    if not evidence.get("source_native_primary_key_verified"):
        missing.append("G3_SOURCE_KEY_SEMANTICS")
    if not evidence.get("original_units_verified"):
        missing.append("G3_RAW_UNIT_SEMANTICS")
    if not evidence.get("native_null_policy_verified"):
        missing.append("G3_NULL_POLICY")
    if not evidence.get("calendar_and_session_verified"):
        missing.append("G3_DATE_AND_SESSION")
    if not evidence.get("publication_pit_and_revisions_verified"):
        missing.append("G3_PIT_AND_REVISIONS")
    if not evidence.get("historical_stock_scope_verified"):
        missing.append("G3_HISTORICAL_SECURITY_SCOPE")
    if evidence.get("unresolved_error_count",1)!=0:
        missing.append("UNRESOLVED_ERROR_LEDGER")
    if not evidence.get("independent_qa_reviewed"):
        missing.append("INDEPENDENT_QA_REVIEW")
    g2_blocks=[x for x in missing if x.startswith("G0_") or x.startswith("G2_")]
    g3_blocks=[x for x in missing if x.startswith("G3_")]
    # Even all review predicates being true must not silently release files.
    return {"schema":VERSION,"source":source,"dataset":dataset,"era":era,
        "g2_contract_verified":not g2_blocks,
        "g3_contract_verified":not g3_blocks and not g2_blocks and
                               "UNRESOLVED_ERROR_LEDGER" not in missing and
                               "INDEPENDENT_QA_REVIEW" not in missing,
        "missing_proofs":missing,
        "release_state":"REVIEW_ELIGIBLE_NOT_RELEASED" if not missing else "HOLD_EVIDENCE_INCOMPLETE",
        "silver_schema_ready":False,"silver_materialized":False,"gold_materialized":False}
def selftest():
    c=catalog()
    expected=sum(len(z["datasets"])*len(z["periods"]) for z in OFFICIAL_VERSIONS.values())
    assert len(c)==expected and len({(v["source"],v["dataset"],v["historical_era"]) for v in c})==expected
    assert len({v["source"] for v in c})==7
    assert all(v["promotion_state"]=="NOT_CERTIFIED" and not v["silver_gold_materialized"] for v in c)
    era=OFFICIAL_VERSIONS["TDCC"]["periods"][-1]["id"]
    spec=contract("TDCC","SHAREHOLDING_DISTRIBUTION",era)
    assert len(spec["source_native_variants"])==2
    assert {v["table_rows"] for v in spec["source_native_variants"]}=={16,17}
    no=review("TDCC","SHAREHOLDING_DISTRIBUTION",era,{})
    assert not no["g2_contract_verified"] and not no["g3_contract_verified"] and not no["silver_schema_ready"]
    proof={"source_id":"x","bronze_sha256":"a"*64,"destination_sha256":"a"*64,
           "source":"TDCC","dataset":"SHAREHOLDING_DISTRIBUTION","historical_era":era,
           "historical_asof_within_effective_window":True,
           "native_member_sha_match":True,
           "official_provenance":{"official_dataset_url":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
                "official_spec_sha256":"b"*64,"official_response_sha256":"c"*64,
                "official_retrieved_at":"2026-11-17T00:00:00Z",
                "dataset_era_binding_verified":True},
           "full_native_required_fields_verified":True,"all_native_rows_typed":True,
           "source_native_primary_key_verified":True,"original_units_verified":True,
           "native_null_policy_verified":True,"calendar_and_session_verified":True,
           "publication_pit_and_revisions_verified":True,"historical_stock_scope_verified":True,
           "unresolved_error_count":0,"independent_qa_reviewed":True}
    yes=review("TDCC","SHAREHOLDING_DISTRIBUTION",era,proof)
    assert yes["g2_contract_verified"] and yes["g3_contract_verified"]
    assert yes["release_state"]=="REVIEW_ELIGIBLE_NOT_RELEASED" and not yes["silver_schema_ready"]
    proof["publication_pit_and_revisions_verified"]=False
    assert not review("TDCC","SHAREHOLDING_DISTRIBUTION",era,proof)["g3_contract_verified"]
    assert contract("MOPS","INCOME_STATEMENT",OFFICIAL_VERSIONS["MOPS"]["periods"][-1]["id"])["candidate_primary_key"]
    print("G2G3_FORMAL_SEVEN_SOURCE_CONTRACT_CATALOG_TEST_PASS",len(c))
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    elif sys.argv[1:]==["catalog"]:
        print(json.dumps({"schema":VERSION,"contracts":catalog()},ensure_ascii=False))
    else:raise SystemExit("selftest|catalog")
