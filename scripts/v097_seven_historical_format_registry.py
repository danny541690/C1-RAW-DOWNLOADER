#!/usr/bin/env python3
"""v0.97 seven-official-source historical format/version registry.
Version windows are dataset-scoped and backed by linked official webpages.
An unavailable historical online endpoint is NEVER proof that Bronze is invalid.
Registry only guides read-only native parser checks; cannot release Silver.
"""
import json,sys
from datetime import date

OFFICIAL_VERSIONS={
 "TWSE":{
  "reference":[
   "https://www.twse.com.tw/zh/trading/historical/fmtqik.html",
   "https://www.twse.com.tw/zh/trading/historical/mi-index.html",
   "https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8",
   "https://openapi.twse.com.tw/"],
  "periods":[
   {"start":"2000-01","end":"2003-11","id":"TWSE_EARLY_MARKET_SUMMARY_NOT_STOCK_DAILY","format":"historical market aggregates/legacy sources; daily-stock archive proof not inferred"},
   {"start":"2003-12","end":"2004-01","id":"TWSE_COMMERCIAL_DAILY_PRODUCT_TRANSITION","format":"paid e-shop historical daily product, distinct from public closing-page availability"},
   {"start":"2004-02","end":"2021-03","id":"TWSE_CLOSING_PAGE_MIXED_TABLES","format":"mixed daily index / quotes / margin / market totals, HTML/CSV/JSON"},
   {"start":"2021-04","end":"9999-12","id":"TWSE_CLOSING_PAGE_AFTER_2021_FORMAT_REVISIONS","format":"mixed tables and commercial A05 layout revision, distinguish OpenAPI current snapshots"}
  ],
  "datasets":["STOCK_DAILY_OHLCV","MARKET_AGGREGATE","INDEX","VALUATION","MARGIN_FINANCING","INSTITUTIONAL","LENDING","FOREIGN_HOLDING"],
  "strict":["original SHA","member SHA","trading date","dataset-specific fields","trading scope","official origin","publication as-of"],
  "historical_warning":"TWSE 1990 market turnover start != 2004 per-security closing page start; A05 commercial format changed in 2021"},
 "TPEx":{
  "reference":[
   "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html",
   "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing/historical.html",
   "https://eshop.tpex.org.tw/zh/product/detail/BCDDCDFD315841EC011ED99B91DD528E",
   "https://www.tpex.org.tw/openapi/"],
  "periods":[
   {"start":"2000-01","end":"2003-07","id":"TPEX_PRE_PUBLIC_HISTORICAL_QUOTES","format":"independent archived origin required"},
   {"start":"2003-08","end":"2006-12","id":"TPEX_2003_2006_HISTORICAL_QUOTES","format":"legacy historical quotations HTML"},
   {"start":"2007-01","end":"2007-04","id":"TPEX_2007_EARLY_1","format":"dedicated 2007 Jan-Apr historical endpoint"},
   {"start":"2007-05","end":"2007-06","id":"TPEX_2007_MID","format":"transition before July later per-security view"},
   {"start":"2007-07","end":"9999-12","id":"TPEX_MODERN_QUOTE_DATASETS","format":"HTML/CSV/openapi and separate commercial TXT trade scopes"}
  ],
  "datasets":["STOCK_DAILY_OHLCV","MARKET_CAPITALIZATION","INDEX","MARGIN_FINANCING","LENDING","VALUATION","FOREIGN_HOLDING"],
  "strict":["original SHA","member manifest SHA","market category","trade date","ohlcv vs market cap","official origin"],
  "historical_warning":"commercial STKT1 vs STKT2 includes different after-hours scope; never equate market cap ranking with OHLCV"},
 "MOPS":{
  "reference":["https://www.twse.com.tw/rwd/IFRS/aboutIFRS","https://mopsfin.twse.com.tw/terms","https://www.twse.com.tw/rwd/XBRL/show"],
  "periods":[
   {"start":"2000-01","end":"2009-03","id":"MOPS_LEGACY_GAAP","format":"older financial HTML/filings, GAAP and publication timestamp"},
   {"start":"2009-04","end":"2012-12","id":"MOPS_XBRL_PRE_IFRS","format":"voluntary/mandatory XBRL transition; GAAP distinctions"},
   {"start":"2013-01","end":"2018-12","id":"MOPS_IFRS_XBRL","format":"IFRS 2013+ for listed/OTC, financial concepts & dimensions"},
   {"start":"2019-01","end":"9999-12","id":"MOPS_IFRS_IXBRL","format":"inline XBRL era and filing corrections"}
  ],
  "datasets":["MONTHLY_REVENUE","INCOME_STATEMENT","BALANCE_SHEET","CASH_FLOW","ANNOUNCEMENT","CORRECTION"],
  "strict":["company code and market as-of","period vs announced_at","GAAP/IFRS concepts","numeric decimals","unit scaling","amendment sequence","original official value"],
  "historical_warning":"IFRS adoption depends on reporting entity type; 2013 is a listed/OTC default, not universal"},
 "TDCC":{
  "reference":["https://www.tdcc.com.tw/portal/zh/smWeb/qryStock","https://data.gov.tw/dataset/11452"],
  "periods":[
   {"start":"2000-01","end":"2008-06","id":"TDCC_PRE_PUBLIC_HISTORICAL_SERVICE","format":"published historical page not demonstrated for period"},
   {"start":"2008-07","end":"9999-12","id":"TDCC_WEEKLY_DISTRIBUTION","format":"weekly last business day security-specific holder tier and percentage"}
  ],
  "datasets":["SHAREHOLDING_DISTRIBUTION","SECURITY_MASTER_ASOF","NON_ORDINARY_INSTRUMENT"],
  "strict":["source HTML/table","security code effective-dated class","shareholder bands","total shares","ratio denominator","weekly as-of"],
  "historical_warning":"public search retention is one year; old archive provenance must be proven independently"},
 "TAIFEX":{
  "reference":["https://www.taifex.com.tw/cht/3/futDailyMarketView","https://www.taifex.com.tw/cht/3/futDailyMarketReport","https://www.taifex.com.tw/cht/3/hisAppForm"],
  "periods":[
   {"start":"2000-01","end":"2017-04","id":"TAIFEX_DAY_SESSION_HISTORICAL","format":"CSV/ZIP separate contracts, trade date and contract expiration"},
   {"start":"2017-05","end":"9999-12","id":"TAIFEX_DAY_AND_AFTER_HOURS","format":"after-hours trading period attributed to next trade date"}
  ],
  "datasets":["FUTURES_DAILY","OPTIONS_DAILY","INSTITUTIONAL","LARGE_TRADER","FX_RATE","CONTRACT_META"],
  "strict":["CSV encoding","quote and tail delimiter","trade date vs expiry","unit contracts","session","contract identity","official source"],
  "historical_warning":"yearly archive ZIP; download page restricts daily date span to one month"},
 "NDC":{
  "reference":["https://www.ndc.gov.tw/nc_336_2245","https://www.ndc.gov.tw/nc_335_2237","https://www.ndc.gov.tw/nc_335_2235"],
  "periods":[
   {"start":"2000-01","end":"2000-12","id":"NDC_SIGNAL_PRE_2001_REVISION","format":"historical monthly signal cells and pre-2001 composition"},
   {"start":"2001-01","end":"2007-06","id":"NDC_SIGNAL_2001","format":"published 2001 methodology"},
   {"start":"2007-07","end":"2013-06","id":"NDC_SIGNAL_2007","format":"published 2007 methodology"},
   {"start":"2013-07","end":"2018-06","id":"NDC_SIGNAL_2013","format":"published 2013 methodology"},
   {"start":"2018-07","end":"2023-12","id":"NDC_SIGNAL_2018","format":"published 2018 methodology"},
   {"start":"2024-01","end":"9999-12","id":"NDC_SIGNAL_2024","format":"published 2024 methodology"}
  ],
  "datasets":["BUSINESS_SIGNAL","LEADING_INDEX","COINCIDENT_INDEX","LAGGING_INDEX","SERIES_COMPONENTS"],
  "strict":["workbook cell coordinate","published month","series effective date","original units","component version","documented gap"],
  "historical_warning":"series value revision != original publication PIT value"},
 "FinMind":{
  "reference":["https://github.com/FinMind/FinMind-MCP/blob/master/knowledge/datasets.md","https://finmind.github.io/WhatIsNew/"],
  "periods":[{"start":"2000-01","end":"9999-12","id":"FINMIND_DATASET_VERSIONED_API","format":"v4 dataset-specific JSON/ZIP raw unit and provider correction history"}],
  "datasets":["TaiwanStockPrice","TaiwanStockFinancialStatements","TaiwanStockInstitutionalInvestorsBuySell","TaiwanStockInfo"],
  "strict":["provider dataset ID","stock ID","row timestamp","units","revision version","member SHA","official match when feasible"],
  "historical_warning":"dataset availability differs by plan/data_id; provider corrections must not silently rewrite immutable Bronze"}
}

def period(source,ym):
 if source not in OFFICIAL_VERSIONS:raise ValueError("UNKNOWN_SOURCE")
 if not isinstance(ym,str) or len(ym)!=7 or ym[4]!="-":raise ValueError("BAD_YYYY_MM")
 try:
  y,m=map(int,ym.split("-"))
  if y<2000 or not 1<=m<=12:raise ValueError()
 except ValueError:raise ValueError("INVALID_YYYY_MM")
 for v in OFFICIAL_VERSIONS[source]["periods"]:
  if v["start"]<=ym<=v["end"]:return dict(v)
 raise ValueError("NO_HISTORICAL_PERIOD")
def selftest():
 expected={"TWSE":4,"TPEx":5,"MOPS":4,"TDCC":2,"TAIFEX":2,"NDC":6,"FinMind":1}
 assert {x:len(y["periods"]) for x,y in OFFICIAL_VERSIONS.items()}==expected
 for source,cfg in OFFICIAL_VERSIONS.items():
  assert len(cfg["reference"])>=2 and cfg["datasets"] and cfg["strict"]
  months=[]
  for yr in range(2000,2027):
   for mo in range(1,13):
    ym=f"{yr:04d}-{mo:02d}"
    assert sum(a["start"]<=ym<=a["end"] for a in cfg["periods"])==1,(source,ym)
    months.append(period(source,ym)["id"])
  assert months
 assert period("MOPS","2012-12")["id"]!="MOPS_IFRS_XBRL"
 assert period("MOPS","2013-01")["id"]=="MOPS_IFRS_XBRL"
 assert period("NDC","2018-06")["id"]!=period("NDC","2018-07")["id"]
 assert period("TAIFEX","2017-04")["id"]!=period("TAIFEX","2017-05")["id"]
 print("SEVEN_HISTORICAL_SOURCE_VERSION_REGISTRY_PASS")
if __name__=="__main__":
 if sys.argv[1:]==["selftest"]:selftest()
 elif len(sys.argv)==3:print(json.dumps(period(sys.argv[1],sys.argv[2]),ensure_ascii=False))
 else:raise SystemExit("usage: selftest | SOURCE YYYY-MM")
