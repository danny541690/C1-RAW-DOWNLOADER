#!/usr/bin/env python3
"""Reconcile official source fields/formats with the v0.95 2026 native contract registry.

Authoritative docs are linked for audits, but these mappings do not prove that
all historical endpoint vintages are accessible. Data-source date, source
publication timestamp and processing timestamp are strictly separate.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
CONTRACTS=ROOT/"governance/v095/DATASET_CONTRACTS.csv"
OUTPUT=pathlib.Path("v095_official_schema_reconciliation")
OFFICIAL={
"TWSE":{"document":"https://data.gov.tw/dataset/11672",
 "official_fields":["日期","成交股數","成交金額","成交筆數","發行量加權股價指數","漲跌點數"],
 "formats":["json","csv"],"time_field":"trade_date","release_verified":False,
 "notes":"Historical FMTQIK market aggregate is not individual stock OHLCV; R.O.C. dates may need conversion"},
"TPEx":{"document":"https://www.tpex.org.tw/openapi/swagger.json",
 "official_fields":["日期","證券代號","收盤價","成交股數"],
 "formats":["json","csv"],"time_field":"trade_date","release_verified":False,
 "notes":"OTC original stock-history API JSON tables date must equal query month; stock samples cannot prove full market coverage"},
"MOPS":{"document":"https://mops.twse.com.tw/mops/web/t21sc03",
 "official_fields":["公司代號","公司名稱","當月營收","上月營收","去年當月營收"],
 "formats":["html_cp950"],"time_field":"report_month","release_verified":False,
 "notes":"Legacy t21sc03_N_M.html versus _0.html; NTD1000 -> 億元 divide 100000; report month is NOT submitted_at"},
"TDCC":{"document":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
 "official_fields":["資料日期","證券代號","持股分級","人數","股數","占集保庫存數比例%"],
 "formats":["json","csv"],"time_field":"weekly_snapshot_date","release_verified":False,
 "notes":"Official fields and source dates belong to CSV/JSON tables. v0.95 JSONL legacy partition is internal archive serialization, not an official wire format. Weekly last-business-day inventory, start 2008-07; portal 1-year retention."},
"TAIFEX":{"document":"https://www.taifex.com.tw/cht/3/futDailyMarketView",
 "official_fields":["日期","契約代號","到期月份(週別)","開盤價","最高價","最低價","最後成交價","合計成交量","結算價","未沖銷契約數","交易時段"],
 "formats":["csv"],"time_field":"trade_date","release_verified":False,
 "notes":"Native yearly ZIP of CSV, monthly max one month; night-session transaction belongs to its specified trade date; 2015-17 date-only pass != numeric valid"},
"NDC":{"document":"https://www.stat.gov.tw/News_NoticeCalendar_Content_temp.aspx?MetaI_D=257&n=3717&year=2026",
 "official_fields":["觀察月份","景氣指標值","景氣對策信號"],
 "formats":["xlsx"],"time_field":"observation_month","release_verified":False,
 "notes":"Original source ZIP contains XLSX current/revised series; observation month != press release date, original historical vintage/PIT unverified"}
}
def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with CONTRACTS.open(newline="",encoding="utf-8-sig") as f:rows=list(csv.DictReader(f))
    required={"dataset_id","source_class_id","raw_format","native_unit","standard_unit","primary_keys",
       "schema_version","published_at_rule","revision_rule","market_scope","effective_start","status"}
    if not rows or not required.issubset(rows[0]):raise ValueError("V095_CONTRACT_MISSING_MANDATORY_HEADERS")
    if len({x["dataset_id"] for x in rows})!=len(rows):raise ValueError("CONTRACT_DUPLICATE_DATASET_ID")
    if set(x["source_class_id"] for x in rows)!=set(OFFICIAL):raise ValueError("SIX_SOURCE_CONTRACT_SCOPE_INCOMPLETE")
    counts=collections.Counter()
    issues=[];matches=[]
    for x in rows:
        source=x["source_class_id"];rule=OFFICIAL[source]
        counts[source]+=1
        issue=[]
        if x["raw_format"] not in rule["formats"]:
            if source=="TDCC" and x["raw_format"]=="jsonl_legacy_partition":
                issue.append("INTERNAL_JSONL_IS_NOT_OFFICIAL_NATIVE_WIRE_FORMAT_REQUIRE_ORIGINAL_SOURCE_SHA_AND_FIELD_MAP")
            else:
                issue.append("RAW_FORMAT_CONTRACT_DIFFERS_FROM_OFFICIAL_REFERENCE")
        if x["native_unit"] in ("NTD","NTD1000") and x["standard_unit"]!="億元":
            issue.append("MONETARY_UNIT_NOT_CONVERTED_TO_YI")
        if x["standard_unit"]=="億元" and x["native_unit"]=="NTD1000":
            unit_divisor=100000
        elif x["standard_unit"]=="億元" and x["native_unit"]=="NTD":
            unit_divisor=100000000
        else:unit_divisor=None
        if source=="MOPS" and ("report_month" not in x["primary_keys"]):
            issue.append("MOPS_PRIMARY_KEY_MISSING_REPORT_MONTH")
        if source=="TDCC" and "weekly_snapshot_date" not in x["primary_keys"]:
            issue.append("TDCC_WEEKLY_DATE_NOT_KEYED")
        if source=="NDC" and "observation_month" not in x["primary_keys"]:
            issue.append("NDC_OBSERVATION_MONTH_NOT_KEYED")
        if x["published_at_rule"] in ("official_source_release_time","published_after_report_month",
                                       "weekly_snapshot_release","official_2026-10-29_release"):
            release_status="RULE_ONLY_SOURCE_TIMESTAMP_NOT_PROVEN"
        else:release_status="REVIEW_PUBLICATION_RULE"
        if x["status"] not in ("CANDIDATE_NEEDS_SCHEMA_AND_PIT_VALIDATION","READY","DISABLED"):
            issue.append("UNKNOWN_CONTRACT_READINESS")
        if x["status"]=="READY":issue.append("READY_REQUIRES_PIT_EVIDENCE_CHECK")
        entry={"dataset_id":x["dataset_id"],"source":source,"actual_contract_format":x["raw_format"],
          "official_compatible_formats":rule["formats"],"primary_keys":x["primary_keys"],
          "official_relevant_date":rule["time_field"],"native_unit":x["native_unit"],
          "target_unit":x["standard_unit"],"money_divisor":unit_divisor,
          "release_proof":release_status,"status":x["status"],"issues":issue}
        matches.append(entry)
        if issue:issues.append(entry)
    report={"schema":"JARVIS_V095_OFFICIAL_FORMAT_CONTRACT_DIFF_V1",
      "date":"2026-11-08","contract_rows_checked":len(rows),
      "source_contract_counts":dict(counts),"format_or_mapping_review_items":len(issues),
      "official_reference":OFFICIAL,"dataset_contract_results":matches,
      "not_recovered_by_format_check":["historical_release_timestamp","full_historical_market_holidays",
          "TDCC_pre_2008_source_nonexistence","MOPS_2000_2004_34_source_unverified"],
      "Bronze_download_can_continue_with_quarantine":True,
      "formal_pit_release_approved":False,"full_historical_release_dates_complete":False}
    output=OUTPUT/"official_vs_v095_contracts.json"
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"contracts":len(rows),"sources":dict(counts),"issues":len(issues),
        "PIT":False,"Bronze_candidate_download_allowed":True},ensure_ascii=False))
    return report
if __name__=="__main__":main()
