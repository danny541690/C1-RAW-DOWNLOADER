#!/usr/bin/env python3
"""JARVIS v0.97 deep source-native format inspection, bounded and release-safe.
Records metadata not confidential raw rows; never grants Silver/Gold.
Official spec transitions included as documented tests, NOT proof of source bytes.
"""
import csv,io,json,re,zipfile
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser
from scripts.v097_bronze_autopilot import digest
MAX_INPUT=55*1024*1024
MAX_MEMBERS=400
MAX_UNPACKED=100*1024*1024
MAX_MEMBER=20*1024*1024
MAX_ROWS=400000
OFFICIAL_CHANGE_DATES={
 "TWSE":[("2003-12-01","A05_COMMERCIAL_START"),("2019-04-30","A05_PLUS_INDEX"),
 ("2021-04-12","A05_20210412"),("2021-06-28","A05_20210628"),
 ("2022-01-24","A05_20220124"),("2023-01-16","A05_20230116"),
 ("2024-05-27","A05_20240527"),("2025-04-28","A05_20250428")],
 "TPEx":[("2003-08-01","LEGACY_DAILY"),("2007-01-02","HIST_2007_START"),
 ("2007-04-21","POST_HIST_20070420")],
 "MOPS":[("2010-05-01","XBRL_VOLUNTARY_START"),("2010-08-01","XBRL_MANDATORY_START"),
 ("2011-04-01","XBRL_SINGLE_TRACK"),("2013-04-01","IFRS_2013_Q1_REPORTING"),
 ("2018-10-01","IXBRL_PILOT"),("2019-04-01","IXBRL_SINGLE_TRACK")],
 "TDCC":[("2008-07-01","WEEKLY_PUBLIC_HISTORICAL_START")],
 "TAIFEX":[("2017-05-15","AFTER_HOURS_TRADING_START")],
 "NDC":[("2001-01-01","SIGNAL_REV_2001"),("2007-07-01","SIGNAL_REV_2007"),
 ("2013-07-01","SIGNAL_REV_2013"),("2018-07-01","SIGNAL_REV_2018"),
 ("2024-01-01","SIGNAL_REV_2024")],
 "FinMind":[]
}
OFFICIAL_DOCS={
 "TWSE":["https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8"],
 "TPEx":["https://www.tpex.org.tw/zh-tw/mainboard/trading/info/pricing.html",
         "https://www.tpex.org.tw/zh-tw/mainboard/trading/info/stock-pricing.html"],
 "MOPS":["https://wwwc.twse.com.tw/staticFiles/listed/manual/ff80808167ee6fdf0169dc2e70320ab3.pdf"],
 "TDCC":["https://original-www.tdcc.com.tw/portal/zh/smWeb/qryStock"],
 "TAIFEX":["https://www.taifex.com.tw/cht/3/dlFutDailyMarketView"],
 "NDC":["https://www.ndc.gov.tw/nc_336_2245"],
 "FinMind":["https://finmind.github.io/tutor/TaiwanMarket/Technical/"]
}
def version(source,day):
 if source not in OFFICIAL_CHANGE_DATES:raise ValueError("SOURCE")
 if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",day):return "UNDATED_REQUIRES_CONTENT_DATE"
 return next((key for boundary,key in reversed(OFFICIAL_CHANGE_DATES[source]) if day>=boundary),"EARLIER_VERSION_UNVERIFIED")
def signature(blob):
 if blob[:4]==b"PK\x03\x04":return "ZIP_OR_XLSX"
 if blob[:4]==b"%PDF":return "PDF"
 if blob[:4]==b"\xd0\xcf\x11\xe0":return "LEGACY_XLS"
 if blob.startswith(b"\x1f\x8b"):return "GZIP"
 sample=blob[:20000].lstrip()
 if sample[:1] in (b"{",b"["):return "JSON_CANDIDATE"
 if sample.startswith((b"<?xml",b"<xbrl",b"<html",b"<!DOCTYPE",b"<table")):return "XML_HTML_CANDIDATE"
 return "TEXT_CSV_OR_UNKNOWN"
def norm(s):
 return re.sub(r"[ \t\r\n\u3000（）()]+","",str(s)).lower()
def dataset(source,cols):
 t="|".join(norm(x) for x in cols)
 def anyof(*a):return any(x in t for x in a)
 if source=="MOPS":
  if anyof("ix:nonfraction","contextref","unitref"):return "XBRL_FACT"
  if anyof("營收","營業收入"):return "MONTHLY_REVENUE_OR_INCOME"
  if anyof("資產","負債"):return "BALANCE_SHEET"
 if source=="TDCC" and anyof("持股分級","佔集保庫存比例","股數","人數"):return "HOLDER_DISTRIBUTION"
 if source=="NDC" and anyof("景氣","領先指標","同時指標"):return "ECONOMIC_SIGNAL"
 if source=="FinMind" and anyof("trading_volume","trading_money","close","stock_id"):return "FINMIND_PRICE"
 if source=="TAIFEX" and anyof("到期月份","未沖銷","契約","交易日期"):return "DERIVATIVE_CONTRACT"
 if anyof("市值佰萬元","發行股數") and anyof("排名","市值"):return "MARKET_CAP"
 if anyof("融資","融券","資餘額"):return "MARGIN_FINANCING"
 if anyof("收盤價","收盤") and anyof("成交股數","成交量") and anyof("代號","股票代號","證券代號"):return "DAILY_OHLCV_CANDIDATE"
 if anyof("借券"):return "LENDING"
 if anyof("外資","投信","自營商"):return "INSTITUTIONAL"
 if anyof("指數","收盤指數"):return "INDEX"
 return "UNKNOWN_DATASET_NEEDS_VERSIONED_TEMPLATE"
class TableCounter(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.tables=0;self.rows=0;self.cells=0;self.ix_facts=0
 def handle_starttag(self,tag,attrs):
  if tag=="table":self.tables+=1
  if tag=="tr":self.rows+=1
  if tag in ("td","th"):self.cells+=1
  if tag in ("ix:nonfraction","ix:nonnumeric"):self.ix_facts+=1
def analyze_json(source,blob):
 try:o=json.loads(blob.decode("utf-8-sig"))
 except (ValueError,UnicodeError):return {"kind":"JSON_INVALID","parsed":False}
 t=[];dates=[];bad_widths=0;num_rows=0
 if isinstance(o,dict):
  dates=[str(o[x])[:24] for x in ("date","Date","資料日期","公告日期","申報日期") if x in o]
  if isinstance(o.get("tables"),list):t=[x for x in o["tables"] if isinstance(x,dict)]
  elif isinstance(o.get("fields"),list):t=[o]
  elif isinstance(o.get("data"),list) and o["data"] and isinstance(o["data"][0],dict):
   t=[{"fields":list(o["data"][0]),"data":o["data"]}]
 elif isinstance(o,list) and o and isinstance(o[0],dict):t=[{"fields":list(o[0]),"data":o}]
 fingerprints=Counter();schemas=[]
 for x in t[:80]:
  fields=x.get("fields",[])
  rows=x.get("data",[])
  if not isinstance(fields,list) or not isinstance(rows,list):bad_widths+=1;continue
  ds=dataset(source,fields);fingerprints[ds]+=1
  sizes=Counter(len(v) if isinstance(v,(list,dict)) else -1 for v in rows[:MAX_ROWS])
  bad_widths+=sum(n for size,n in sizes.items() if size!=len(fields))
  num_rows+=len(rows)
  if len(schemas)<12:schemas.append({"dataset":ds,"cols":len(fields),"rows":len(rows),
      "schema_fingerprint":digest("|".join(norm(f) for f in fields).encode()),
      "fields":[str(f)[:45] for f in fields[:15]],"widths":dict(sizes)})
 return {"kind":"JSON","parsed":True,"table_count":len(t),"row_count":num_rows,
         "dates":dates[:5],"dataset_counts":dict(fingerprints),
         "row_width_conflicts":bad_widths,"schemas":schemas,
         "requires_published_at_evidence":True}
def analyze_text(source,blob):
 codec=None
 for enc in ("utf-8-sig","cp950","big5"):
  try:s=blob.decode(enc);codec=enc;break
  except UnicodeError:pass
 if codec is None:return {"kind":"BINARY_OR_UNKNOWN","parsed":False}
 tag=TableCounter()
 if re.search(r"<(?:html|table|xbrl|ix:nonfraction)\b",s[:4096],re.I):
  tag.feed(s[:2000000])
  return {"kind":"HTML_XML","encoding":codec,"tables":tag.tables,"rows":tag.rows,
          "cells":tag.cells,"ixbrl_numeric_facts":tag.ix_facts,
          "has_xbrl_context":bool(re.search(r"contextRef|contextref",s,re.I)),
          "needs_taxonomy_unit_and_pit":source=="MOPS"}
 lines=[z for z in s.splitlines() if z.strip()]
 if not lines:return {"kind":"EMPTY_TEXT","parsed":False}
 delim=max((",","\t",";"),key=lambda x:lines[0].count(x))
 try:
  rows=csv.reader(io.StringIO(s),delimiter=delim)
  header=next(rows,[])
  widths=Counter();sample=[];count=0
  for row in rows:
   if not any(z.strip() for z in row):continue
   count+=1;widths[len(row)]+=1
   if len(sample)<5 and len(row)!=len(header):sample.append({"line":count+1,"width":len(row),
     "text_excerpt":str(row[0])[:38]})
   if count>=MAX_ROWS:break
  return {"kind":"CSV_OR_TEXT","encoding":codec,"separator":repr(delim),
          "header_fields":[str(z)[:50] for z in header[:25]],
          "header_width":len(header),"row_count_scanned":count,
          "row_width_histogram":dict(widths),"anomaly_samples":sample,
          "dataset":dataset(source,header),"data_cap_reached":count>=MAX_ROWS}
 except csv.Error:return {"kind":"CSV_ERROR","encoding":codec}
def analyze(source,name,blob,day=None,depth=0):
 if source not in OFFICIAL_CHANGE_DATES:raise ValueError("SOURCE")
 base={"source":source,"member":name[:145],"sha256":digest(blob),
   "bytes":len(blob),"signature":signature(blob),
   "official_format_version_hint":version(source,day or ""),
   "official_spec_urls":OFFICIAL_DOCS[source],
   "source_provenance_verified":False,"published_at_verified":False,
   "third_party_values_checked":False,"silver_ready_promoted":False}
 if len(blob)>MAX_INPUT:return {**base,"status":"HOLD_SIZE_LIMIT"}
 if depth>3:return {**base,"status":"HOLD_ARCHIVE_NESTING_LIMIT"}
 if signature(blob)=="ZIP_OR_XLSX":
  if not zipfile.is_zipfile(io.BytesIO(blob)):return {**base,"status":"HOLD_NOT_VALID_ZIP"}
  with zipfile.ZipFile(io.BytesIO(blob)) as z:
   infos=[x for x in z.infolist() if not x.is_dir()]
   if len(infos)>MAX_MEMBERS:return {**base,"status":"HOLD_MEMBER_LIMIT"}
   names={x.filename for x in infos}
   if "xl/workbook.xml" in names and "[Content_Types].xml" in names:
    return {**base,"status":"XLSX_NATIVE_WORKBOOK_CELL_EXTRACTION_PENDING",
      "workbook_members":len(infos),"workbook_xml_sha256":digest(z.read("xl/workbook.xml")),
      "worksheet_count":sum(x.startswith("xl/worksheets/") and x.endswith(".xml") for x in names),
      "silver_ready_promoted":False}
   members=[];unpacked=0
   for entry in infos:
    if entry.filename.startswith("/") or ".." in entry.filename.replace("\\","/").split("/"):
     return {**base,"status":"HOLD_UNSAFE_PATH"}
    if entry.flag_bits & 1 or entry.file_size>MAX_MEMBER:return {**base,"status":"HOLD_ENCRYPTED_OR_LARGE_MEMBER"}
    unpacked+=entry.file_size
    if unpacked>MAX_UNPACKED:return {**base,"status":"HOLD_ZIP_BOMB_BOUND"}
    raw=z.read(entry)
    child=analyze(source,entry.filename,raw,day,depth+1)
    members.append({"name":entry.filename[:120],"sha256":child["sha256"],"format":child["signature"],
        "dataset":child.get("dataset"),"detail":child.get("detail",{})})
  return {**base,"status":"ZIP_MEMBER_DEPTH_COMPLETE_ORIGIN_PENDING",
          "member_count":len(members),"members":members[:120]}
 detail=analyze_json(source,blob) if signature(blob)=="JSON_CANDIDATE" else analyze_text(source,blob)
 return {**base,"status":"DEEP_FORMAT_CLASSIFIED_ORIGIN_PENDING" if detail.get("parsed",True) else "HOLD_PARSE_INCOMPLETE",
         "dataset":detail.get("dataset"),"detail":detail}
def selftest():
 assert version("TWSE","2021-04-11")!=version("TWSE","2021-04-12")
 assert version("TWSE","2024-05-26")!=version("TWSE","2024-05-27")
 assert version("MOPS","2018-09-30")!=version("MOPS","2018-10-01")
 assert version("TAIFEX","2017-05-14")!=version("TAIFEX","2017-05-15")
 sample=json.dumps({"date":"2026-11-13","tables":[{"fields":["代號","收盤","成交股數"],"data":[["2330","100","300"]]}]},ensure_ascii=False).encode()
 for src in OFFICIAL_CHANGE_DATES:
  r=analyze(src,"data.raw",sample,"2026-11-13")
  assert r["detail"]["table_count"]==1 and r["silver_ready_promoted"] is False
  assert r["source_provenance_verified"] is False
 assert dataset("TPEx",["排名","股票代號","收盤價","發行股數","市值(佰萬元)"])=="MARKET_CAP"
 assert dataset("TWSE",["代號","收盤","成交股數"])=="DAILY_OHLCV_CANDIDATE"
 assert dataset("MOPS",["公司代號","營業收入"])=="MONTHLY_REVENUE_OR_INCOME"
 assert dataset("TDCC",["持股分級","人數","股數"])=="HOLDER_DISTRIBUTION"
 assert analyze("TAIFEX","test.csv",b"date,contract,volume\n20261113,TX,100\n")["detail"]["row_width_histogram"]=={3:1}
 z=io.BytesIO()
 with zipfile.ZipFile(z,"w") as a:a.writestr("market.raw",sample)
 assert analyze("TWSE","x.zip",z.getvalue())["member_count"]==1
 xlsx=io.BytesIO()
 with zipfile.ZipFile(xlsx,"w") as wb:
  wb.writestr("[Content_Types].xml",b"<Types/>")
  wb.writestr("xl/workbook.xml",b"<workbook/>")
  wb.writestr("xl/worksheets/sheet1.xml",b"<worksheet/>")
 out=analyze("NDC","history.xlsx",xlsx.getvalue())
 assert out["status"]=="XLSX_NATIVE_WORKBOOK_CELL_EXTRACTION_PENDING"
 assert out["worksheet_count"]==1
 assert analyze("TWSE","nested.zip",z.getvalue(),depth=4)["status"]=="HOLD_ARCHIVE_NESTING_LIMIT"
 print("SEVEN_DEEP_FORMAT_TEST_PASS")
if __name__=="__main__":selftest()
