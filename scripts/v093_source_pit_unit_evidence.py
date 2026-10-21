"""Fail-closed financial data release evidence checks.

A parsed number, a currency word, and a response date are not enough to
establish comparable unit, point-in-time availability or source agreement.
"""
import datetime,re
UNIT_FACTORS={"NTD":1,"NTD_THOUSANDS":1000,"NTD_MILLIONS":1000000,"NTD_100M":100000000}
def assess_evidence(source,stock_id,report_period,release_date,unit,comparison=None,*,metric=None):
 issues=[]
 if not re.fullmatch(r"[1-9][0-9]{3}",str(stock_id or "")):issues.append("STOCK_ID_NOT_PROVEN")
 try:
  y,m=map(int,str(report_period).split("-"))
  assert 2000<=y<=2100 and 1<=m<=12
  period=f"{y:04d}-{m:02d}"
 except (ValueError,AssertionError,AttributeError):
  period=None;issues.append("REPORT_PERIOD_NOT_PROVEN")
 try:
  pub=datetime.date.fromisoformat(str(release_date))
 except (ValueError,TypeError):
  pub=None;issues.append("PUBLICATION_DATE_NOT_PROVEN")
 if pub and period and pub.strftime("%Y-%m")<period:issues.append("PUBLICATION_PRECEDES_REPORT_PERIOD")
 if unit not in UNIT_FACTORS:issues.append("UNIT_NOT_PROVEN")
 comparable=False
 if comparison is not None:
  # Both sources must identify the same company, reported period, semantic
  # field, and original unit; value agreement alone is not proof.
  for key in ("source","stock_id","report_period","metric","unit","source_sha256"):
   if not comparison.get(key):issues.append("COMPARISON_"+key.upper()+"_MISSING")
  if comparison.get("source")==source:issues.append("COMPARISON_NOT_INDEPENDENT")
  if not metric:issues.append("COMPARISON_PRIMARY_METRIC_MISSING")
  for key,expected in (("stock_id",str(stock_id)),("report_period",period),("metric",metric),("unit",unit)):
   if comparison.get(key)!=expected:issues.append("COMPARISON_"+key.upper()+"_MISMATCH")
  if not re.fullmatch(r"[0-9a-fA-F]{64}",str(comparison.get("source_sha256",""))):
   issues.append("COMPARISON_SOURCE_SHA256_INVALID")
  comparable=not issues
 return {"source":source,"pit_evidence_complete":pub is not None and period is not None and "PUBLICATION_PRECEDES_REPORT_PERIOD" not in issues,"unit_evidence_complete":unit in UNIT_FACTORS,"cross_source_metadata_comparable":comparable,"verified":False,"issues":issues}
def mops_html_evidence(html):
 """Inspect HTML for hints, not claims of official report identity or PIT."""
 from scripts.v093_standard_r2 import classify_mops_html
 x=classify_mops_html(html)
 x["has_stock_id_evidence"]=bool(re.search(r"(?:公司代號|股票代號|證券代號)\s*[:：]?\s*[1-9]\d{3}\b",html))
 x["has_publication_timestamp_evidence"]=bool(re.search(r"(?:公告日期|公告時間|發布日期|發布時間)\s*[:：]?\s*(?:20\d{2}|1\d{2})[/.-]",html))
 x["has_report_period_evidence"]=bool(re.search(r"(?:報表年度|報表期間|資料年月|民國)\s*[:：]?\s*(?:20\d{2}|1\d{2})",html))
 x["pit_verified"]=False;x["certified"]=False
 return x

def mops_revenue_header_evidence(html):
 """Extract report period, table export date and explicit monetary unit.
 Export date is NOT a company-specific first-publication timestamp.
 """
 from html.parser import HTMLParser
 class Text(HTMLParser):
  def __init__(self):super().__init__();self.parts=[]
  def handle_data(self,data):
   t=data.strip()
   if t:self.parts.append(t)
 p=Text();p.feed(html)
 header=" ".join(p.parts[:100])
 period_match=re.search(r"(?:上市|上櫃)公司\s*(\d{2,3})年\s*(\d{1,2})月份",header)
 export_match=re.search(r"出表日期\s*[:：]\s*(\d{2,3})/(\d{1,2})/(\d{1,2})",header)
 unit_match=re.search(r"單位\s*[:：]\s*(千元|仟元|元|百萬元|億元)",header)
 def roc_date(m):
  if not m:return None
  try:return datetime.date(int(m.group(1))+1911,int(m.group(2)),int(m.group(3))).isoformat()
  except ValueError:return None
 period=None
 if period_match:
  y,mo=int(period_match.group(1))+1911,int(period_match.group(2))
  if 2000<=y<=2100 and 1<=mo<=12:period=f"{y:04d}-{mo:02d}"
 unit=unit_match.group(1) if unit_match else None
 unit_code={"千元":"NTD_THOUSANDS","仟元":"NTD_THOUSANDS","元":"NTD","百萬元":"NTD_MILLIONS","億元":"NTD_100M"}.get(unit)
 return {"report_period":period,"export_date":roc_date(export_match),
         "export_date_is_publication_date":False,"publication_date":None,
         "unit_label":unit,"unit_code":unit_code,"unit_evidence_complete":unit_code is not None,
         "pit_verified":False,"certified":False}

def mops_revenue_table_probe(html):
 """Read-only table-row extraction, retaining positional columns and raw text."""
 from html.parser import HTMLParser
 class Probe(HTMLParser):
  def __init__(self):
   super().__init__();self.rows=[];self.row=None;self.cell=None;self.depth=0
  def handle_starttag(self,tag,attrs):
   if tag=="tr":self.row=[]
   if tag in ("td","th") and self.row is not None:self.cell=[]
  def handle_data(self,data):
   if self.cell is not None:self.cell.append(data)
  def handle_endtag(self,tag):
   if tag in ("td","th") and self.cell is not None and self.row is not None:
    self.row.append(" ".join("".join(self.cell).split()));self.cell=None
   if tag=="tr" and self.row is not None:
    if self.row:self.rows.append(self.row)
    self.row=None
 p=Probe();p.feed(html)
 symbols=[];headers=[];seen=set();active_header=None;revenue=[];rejected=0
 metadata=mops_revenue_header_evidence(html)
 for row in p.rows:
  if row and row[0]=="公司代號" and "當月營收" in row:
   active_header=row
  elif active_header and row and re.fullmatch(r"[1-9][0-9]{3}",row[0]):
   # Only the explicitly headed company column identifies a stock. Four-digit
   # revenue values elsewhere in a row are never security identifiers.
   from decimal import Decimal,InvalidOperation
   index=active_header.index("當月營收")
   try:
    raw_value=row[index]
    if not re.fullmatch(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?",raw_value):raise ValueError("INVALID_REVENUE")
    value=Decimal(raw_value.replace(",",""))
    if not metadata["report_period"] or not metadata["unit_code"]:raise ValueError("MISSING_HEADER_METADATA")
    factor=Decimal(UNIT_FACTORS[metadata["unit_code"]])
    revenue.append({"stock_id":row[0],"report_period":metadata["report_period"],
     "metric":"當月營收","raw_value":raw_value,"unit":metadata["unit_code"],
     "value_100m_ntd":str(value*factor/Decimal(100000000)),
     "publication_date":None,"pit_verified":False,"numeric_verified":False,"certified":False})
   except (IndexError,InvalidOperation,ValueError):rejected+=1
  for i,cell in enumerate(row):
   if active_header and i==0 and re.fullmatch(r"[1-9][0-9]{3}",cell):
    key=(cell,i)
    if key not in seen:
     seen.add(key);symbols.append({"stock_id":cell,"column":i,"sample":row[:12]})
   if "公司代號" in cell or "當月營收" in cell:
    if len(headers)<8:headers.append(row[:18])
 return {"html_rows":len(p.rows),"distinct_symbol_column_pairs":len(seen),
         "symbol_samples":symbols[:8],"header_samples":headers,
         "revenue_candidates":len(revenue),"rejected_revenue_rows":rejected,
         "revenue_candidate_samples":revenue[:8],"candidate_status":"STAGING_NOT_APPROVED",
         "certified":False,"pit_verified":False}
