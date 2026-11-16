#!/usr/bin/env python3
"""Seven source-specific error resolver contracts for JARVIS v0.97.
Strict triage only: source-native parsing + evidence gates, not READY promotion.
For each original parser status, prescribe exact follow-up evidence.
"""
import json,sys
from collections import Counter
from scripts.v097_bronze_autopilot import SOURCES,parse_taifex_csv,parse_ndc_native,parse_finmind_unit_archive,parse_json,check_table

SOURCE_RULES={
 "TWSE":{
   "formats":(".zip",".raw",".json",".csv",".html"),
   "roles":{"ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"ZIP_BC_CONTENT_AND_MANIFEST",
            "HOLD_UNKNOWN_JSON_DATASET":"TWSE_TABLE_TITLE_AND_FIELD_FINGERPRINT",
            "HOLD_CONTENT_PERIOD_CONFLICT":"TWSE_TRADE_DATE_VS_PUBLICATION_DATE",
            "HOLD_UNRECOGNIZED_EXTENSION":"TWSE_MAGIC_BYTES_AND_RAW_JSON"},
   "final":"EXACT_OFFICIAL_DATASET_ID_DATE_STOCK_VALUES_ORIGIN"},
 "TPEx":{
   "formats":(".zip",".raw",".json",".csv",".html"),
   "roles":{"ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"ZIP_BC_CONTENT_AND_MANIFEST",
            "HOLD_UNKNOWN_JSON_DATASET":"TPEX_OHLCV_MARKETCAP_INDEX_MARGIN_DISTINCT",
            "HOLD_CONTENT_PERIOD_CONFLICT":"TPEX_HISTORICAL_TRADE_DATE_EFFECTIVE_PERIOD",
            "HOLD_UNRECOGNIZED_EXTENSION":"TPEX_MAGIC_BYTES_AND_RAW_JSON"},
   "final":"OFFICIAL_HISTORICAL_MARKET_CODE_DATE_PRICE_SOURCE"},
 "MOPS":{
   "formats":(".html",".htm",".json",".csv",".pdf"),
   "roles":{"MOPS_MATRIX_RECEIPT_AND_PIT_HOLD":"MOPS_MATRIX_COMPANY_PERIOD_ANNOUNCEMENT",
            "ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"MOPS_ARCHIVE_SOURCE_RECEIPT",
            "HOLD_UNKNOWN_JSON_DATASET":"MOPS_ANNOUNCEMENT_AND_FINANCE_SCHEMA",
            "HOLD_HTML_SOURCE_ADAPTER":"MOPS_VARYING_TABLE_HEADER_AND_ACCOUNTING_UNIT"},
   "final":"EXACT_COMPANY_ACCOUNTING_FIGURES_UNITS_FILING_ASOF"},
 "TDCC":{
   "formats":(".html",".htm",".zip",".json"),
   "roles":{"TDCC_HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING":"TDCC_ASOF_SECURITY_CLASS",
            "TDCC_HOLD_DISTRIBUTION_TABLE_QA":"TDCC_SHAREHOLDER_BANDS_RECONCILIATION",
            "HOLD_DATE_EVIDENCE":"TDCC_WEEKLY_RELEASE_DATE_VS_SECURITY_ASOF",
            "HOLD_UNKNOWN_JSON_DATASET":"TDCC_DATASET_IDENTITY",
            "ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"TDCC_ARCHIVE_TYPED_MEMBER"},
   "final":"OFFICIAL_HISTORICAL_STOCK_ID_SHARE_BANDS_TOTAL_ASOF"},
 "TAIFEX":{
   "formats":(".csv",".zip",".json"),
   "roles":{"HOLD_TAIFEX_CSV_WIDTH":"TAIFEX_ENCODING_TRAILING_DELIMITER_QUOTING",
            "HOLD_DATE_EVIDENCE":"TAIFEX_TRADE_DATE_SEPARATE_CONTRACT_MONTH",
            "HOLD_TAIFEX_MONTH_CONFLICT":"TAIFEX_CONTRACT_MONTH_VS_TRADE_DAY",
            "HOLD_ZIP_EXPANSION_LIMIT":"TAIFEX_BOUNDED_ARCHIVE_PARTITION",
            "ZIP_MEMBERS_AUDITED_ORIGIN_HOLD":"TAIFEX_OFFICIAL_MEMBER_SCHEMA"},
   "final":"OFFICIAL_CONTRACT_TYPE_TRADE_DATE_VOLUME_OPEN_INTEREST"},
 "NDC":{
   "formats":(".xlsx",".xls",".json",".csv"),
   "roles":{"HOLD_NDC_UNDOCUMENTED_CELL_GAP":"NDC_SERIES_INCEPTION_AND_ORIGINAL_CELL",
            "HOLD_NDC_CELL_MISSING_OR_INVALID":"NDC_OFFICIAL_SERIES_MISSING_VALUE",
            "HOLD_NDC_SOURCE_ARCHIVE_PROOF":"NDC_ORIGINAL_WORKBOOK_AND_SHEET",
            "HOLD_NDC_CONTENT_MONTH_CONFLICT":"NDC_STAT_MONTH_VS_PUBLICATION_DATE"},
   "final":"NDC_PUBLISHED_NATIVE_SERIES_CELLS_OR_EXPLICIT_EVIDENCED_GAP"},
 "FinMind":{
   "formats":(".zip",".raw",".json",".jsonl"),
   "roles":{"HOLD_FINMIND_MEMBER_NAME":"FINMIND_UNIT_ID_PATH_RULE",
            "HOLD_FINMIND_ROW_PERIOD_CONFLICT":"FINMIND_ROW_TRADE_PERIOD_VS_EXPORT_PERIOD",
            "HOLD_FINMIND_MANIFEST_IDENTITY":"FINMIND_PROVIDER_ID_AND_DATASET",
            "HOLD_FINMIND_RAW_JSON_INVALID":"FINMIND_DATASET_SCHEMA_VERSION",
            "FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD":"FINMIND_PROVIDER_ORIGIN_NUMERIC_PIT"},
   "final":"PROVIDER_DATASET_VERSION_UNIT_DATE_INDEPENDENT_VALUES"}
}
FALLBACK={
 "TWSE":"TWSE_DATASET_PROVENANCE_REVIEW","TPEx":"TPEX_HISTORICAL_SCHEMA_REVIEW",
 "MOPS":"MOPS_ACCOUNTING_ANNOUNCEMENT_REVIEW","TDCC":"TDCC_SECURITY_ASOF_REVIEW",
 "TAIFEX":"TAIFEX_CONTRACT_DATE_REVIEW","NDC":"NDC_SERIES_CELL_REVIEW",
 "FinMind":"FINMIND_PROVIDER_PERIOD_REVIEW"}
def triage(source,parser_status,detail=None):
 if source not in SOURCE_RULES:raise ValueError("UNKNOWN_SOURCE")
 rules=SOURCE_RULES[source]
 if not isinstance(parser_status,str):raise TypeError("PARSER_STATUS_REQUIRED")
 if parser_status.startswith("RECHECK_") or parser_status.startswith("HOLD_DRIVE_"):
  task="RETRY_SOURCE_READ_MAX_3_WITH_CHECKPOINT"
 elif parser_status.startswith("HOLD_ORIGINAL") or parser_status.startswith("HOLD_RECEIPT"):
  task="SHA_AND_IMMUTABLE_ORIGINAL_RECEIPT_RECONCILE"
 else:task=rules["roles"].get(parser_status,FALLBACK[source])
 return {"source":source,"parser_status":parser_status,"resolver":task,
         "formats":rules["formats"],"required_release_evidence":rules["final"],
         "status":"HOLD_EVIDENCE_REQUIRED","silver_ready_promoted":False}
def selftest():
 assert set(SOURCE_RULES)==set(SOURCES)
 for src in SOURCES:
  assert SOURCE_RULES[src]["roles"]
  for problem,method in SOURCE_RULES[src]["roles"].items():
   t=triage(src,problem)
   assert t["resolver"]==method and not t["silver_ready_promoted"]
 assert triage("TAIFEX","HOLD_TAIFEX_CSV_WIDTH")["resolver"]=="TAIFEX_ENCODING_TRAILING_DELIMITER_QUOTING"
 assert triage("NDC","HOLD_NDC_UNDOCUMENTED_CELL_GAP")["resolver"]=="NDC_SERIES_INCEPTION_AND_ORIGINAL_CELL"
 assert triage("MOPS","MOPS_MATRIX_RECEIPT_AND_PIT_HOLD")["resolver"]=="MOPS_MATRIX_COMPANY_PERIOD_ANNOUNCEMENT"
 assert triage("TDCC","TDCC_HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING")["resolver"]=="TDCC_ASOF_SECURITY_CLASS"
 # Parser-native checks: numeric schema, actual official date types, no bogus auto promotion.
 assert check_table(["代號","收盤價"],[["2330","100"]])=="OK"
 assert parse_taifex_csv("交易日期,商品,成交口數\n20261116,TX,123\n".encode(),"2026-11")["status"]=="TAIFEX_CSV_ENCODING_WIDTH_PASS_DATE_PIT_HOLD"
 assert parse_taifex_csv("交易日期,商品,成交口數\n20261116,TX,123,99\n".encode(),"2026-11")["status"]=="HOLD_TAIFEX_CSV_WIDTH"
 print("SEVEN_SOURCE_SPECIFIC_RESOLVER_CONTRACTS_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==3:print(json.dumps(triage(sys.argv[1],sys.argv[2]),ensure_ascii=False))
 else:raise SystemExit("usage: selftest | SOURCE PARSER_STATUS")
