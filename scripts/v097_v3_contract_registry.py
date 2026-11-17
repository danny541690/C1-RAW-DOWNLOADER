#!/usr/bin/env python3
"""V3 seven-source source-native, era-aware schema contract *candidates*.
Verified official references are links; aliases alone can NEVER certify release.
Raw unit metadata retained; nothing normalized and nothing materialized.
"""
import re,sys
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS

REGISTRY_VERSION="v097_v3_contract_candidates_20261117_r1"
# Proposed minimum keys. They are NOT authority to certify a complete file.
CONTRACTS={
 "TWSE":{"STOCK_DAILY_OHLCV":{
   "date":["日期","交易日期","date","trade_date"],
   "code":["證券代號","股票代號","股票代碼"],
   "open":["開盤價","開盤"],
   "high":["最高價","最高"],
   "low":["最低價","最低"],
   "close":["收盤價","收盤"],
   "volume":["成交股數","成交量"]}},
 "TPEx":{"STOCK_DAILY_OHLCV":{
   "date":["日期","交易日期","date"],
   "code":["代號","證券代號","股票代號","股票代碼"],
   "open":["開盤","開盤價"],"high":["最高","最高價"],
   "low":["最低","最低價"],"close":["收盤","收盤價"],
   "volume":["成交股數"]}},
 "MOPS":{"MONTHLY_REVENUE":{
   "code":["公司代號","證券代號","股票代號","stock_id"],
   "period":["營收月份","年月","資料年月","month"],
   "revenue":["當月營收","營業收入","營收","revenue"]}},
 "TDCC":{"SHAREHOLDING_DISTRIBUTION":{
   "code":["證券代號","股票代號","證券代碼","StockNo"],
   "date":["資料日期","資料年月日","查詢日期","date"],
   "tier":["持股分級","持股級距","持股/單位數分級"],
   "holders":["人數","持有人數"],
   "shares":["股數","持有股數","股數/單位數"],
   "percent":["占集保庫存數比例","占集保庫存數比例 (%)","占集保庫存數比例(%)","比例","持股比例"]}},
 "TAIFEX":{"FUTURES_DAILY":{
   "date":["日期","交易日期","date"],
   "contract":["契約","契約名稱","商品代號"],
   "expiration":["到期月份(週別)","到期月份","契約月份"],
   "volume":["成交量","成交口數"]}},
 "NDC":{"BUSINESS_SIGNAL":{
   "period":["年月","月份","資料年月","month","period"],
   "value":["景氣對策信號","景氣對策信號綜合判斷分數","分數","value"]}},
 "FinMind":{"TaiwanStockPrice":{
   "date":["date"],"code":["stock_id"],"open":["open"],
   "high":["max"],"low":["min"],"close":["close"],
   "volume":["Trading_Volume"],"amount":["Trading_money"]}}
}
UNITS={
 "TWSE":{"close":"TWD","volume":"shares"},
 "TPEx":{"close":"TWD","volume":"shares"},
 "MOPS":{"revenue":"original_reporting_unit_to_verify"},
 "TDCC":{"shares":"shares","percent":"percent"},
 "TAIFEX":{"volume":"contracts"},
 "NDC":{"value":"series_specific"},
 "FinMind":{"close":"TWD","volume":"shares"}
}
def normalize(s):return re.sub(r"[\s_\u3000（）()]+","",str(s)).lower()
def infer(src,headers,era=None,dataset_hint=None,metadata=None):
    if src not in CONTRACTS:raise ValueError("INVALID_SOURCE")
    if not isinstance(headers,list) or not headers:
        return {"status":"HEADER_NOT_OBSERVED","registry":REGISTRY_VERSION}
    observed={normalize(s):str(s) for s in headers}
    candidates=[]
    for dataset,required in CONTRACTS[src].items():
        fields={};missing=[]
        for key,aliases in required.items():
            value=next((observed[normalize(x)] for x in aliases if normalize(x) in observed),None)
            if value is None and src=="TDCC" and key in ("code","date") and metadata and metadata.get("source")=="TDCC_HTML_BODY":
                proof=metadata.get(key)
                if isinstance(proof,dict) and proof.get("validated") is True and proof.get("value"):
                    value="@PAGE_METADATA:"+key
            if value is None:missing.append(key)
            else:fields[key]=value
        if len(set(fields.values()))!=len(fields):missing.append("DUPLICATE_FIELD_CLAIM")
        candidates.append({"dataset":dataset,"mapped":fields,"missing":missing,
                           "required_total":len(required)})
    candidates.sort(key=lambda x:(len(x["missing"]),-len(x["mapped"])))
    top=candidates[0]
    allowed_eras={x["id"] for x in OFFICIAL_VERSIONS[src]["periods"]}
    era_ok=bool(era and era in allowed_eras)
    if not era_ok:
        status="HISTORICAL_EDITION_UNCERTIFIED"
    elif not top["missing"]:
        status="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED"
    else:
        status="INCOMPLETE_HEADER_CONTRACT"
    return {"status":status,"source":src,"era":era,"era_registered":era_ok,
            "dataset_candidate":top["dataset"],"observed_fields":top["mapped"],
            "missing_required":top["missing"],"units":UNITS[src],
            "registry":REGISTRY_VERSION,
            "official_references":OFFICIAL_VERSIONS[src]["reference"],
            "source_dataset_hint":dataset_hint,
            "metadata_proof_used":bool(src=="TDCC" and metadata and any(str(v).startswith("@PAGE_METADATA:") for v in top["mapped"].values())),
            "source_native_typed_and_row_verified":False,
            "official_layout_attested_for_this_file":False,
            "silver_schema_ready":False}
def selftest():
    assert len(CONTRACTS)==7
    assert normalize("交易 日期") == normalize("交易日期")
    assert normalize("Trading Volume") == normalize("Trading_Volume")
    assert normalize("證券\t代號") == normalize("證券代號")
    for src in CONTRACTS:
        assert len(OFFICIAL_VERSIONS[src]["reference"])>=1
    q=infer("FinMind",["date","stock_id","open","max","min","close","Trading_Volume","Trading_money"],
            OFFICIAL_VERSIONS["FinMind"]["periods"][0]["id"])
    assert q["status"]=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED"
    assert q["silver_schema_ready"] is False
    x=infer("TDCC",["StockNo","持股分級"],OFFICIAL_VERSIONS["TDCC"]["periods"][-1]["id"])
    assert x["missing_required"] and x["status"]=="INCOMPLETE_HEADER_CONTRACT"
    row=["序","持股/單位數分級","人數","股數/單位數","占集保庫存數比例 (%)"]
    meta={"source":"TDCC_HTML_BODY","code":{"value":"4609","validated":True},
          "date":{"value":"2025-11-28","validated":True}}
    era=OFFICIAL_VERSIONS["TDCC"]["periods"][-1]["id"]
    valid=infer("TDCC",row,era,metadata=meta)
    assert valid["status"]=="COMPLETE_HEADER_CANDIDATE_UNCERTIFIED"
    assert valid["metadata_proof_used"] and valid["silver_schema_ready"] is False
    assert infer("TDCC",row,era)["status"]=="INCOMPLETE_HEADER_CONTRACT"
    assert infer("TDCC",row,era,metadata={**meta,"date":{"value":"2025-11-28","validated":False}})["status"]=="INCOMPLETE_HEADER_CONTRACT"
    print("V3_SEVEN_SOURCE_CONTRACT_REGISTRY_SELFTEST_PASS")
if __name__=="__main__":
    if sys.argv[1:]==["selftest"]:selftest()
    else:raise SystemExit("selftest")
