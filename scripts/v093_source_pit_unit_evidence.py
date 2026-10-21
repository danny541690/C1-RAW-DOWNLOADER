"""Fail-closed financial data release evidence checks.

A parsed number, a currency word, and a response date are not enough to
establish comparable unit, point-in-time availability or source agreement.
"""
import datetime,re
UNIT_FACTORS={"NTD":1,"NTD_THOUSANDS":1000,"NTD_MILLIONS":1000000,"NTD_100M":100000000}
def assess_evidence(source,stock_id,report_period,release_date,unit,comparison=None):
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
  for key in ("stock_id","report_period","metric","unit","source_sha256"):
   if not comparison.get(key):issues.append("COMPARISON_"+key.upper()+"_MISSING")
  if comparison.get("source")==source:issues.append("COMPARISON_NOT_INDEPENDENT")
  comparable=not any(x.startswith("COMPARISON_") for x in issues)
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
