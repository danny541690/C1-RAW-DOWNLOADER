"""Bounded read-only native staging sanity checks; never certifies source values."""
import collections,datetime,math,re
IDENTIFIERS={"股票代號","證券代號","代號","公司代號","stock_id","Code","StockCode","SecuritiesCompanyCode"}
def audit(rows,period):
 counts=collections.Counter();keys=set();issues=[]
 for r in rows:
  counts["rows"]+=1
  try:
   day=datetime.date.fromisoformat(r["date"])
   if day.isoformat()!=r["date"] or r["date"][:7]!=period:raise ValueError("wrong period")
  except (KeyError,TypeError,ValueError):
   counts["invalid_date"]+=1
  if not re.fullmatch(r"[0-9A-Za-z]{4,8}",str(r.get("stock_id",""))):counts["invalid_stock_id"]+=1
  val=r.get("numeric_unscaled")
  if isinstance(val,bool) or not isinstance(val,(int,float)) or not math.isfinite(val):counts["nonfinite_numeric"]+=1
  field=str(r.get("native_field","")).split("__col_")[0]
  if field in IDENTIFIERS:counts["identifier_as_numeric"]+=1
  if any(r.get(k) is not False for k in ("unit_verified","numeric_verified","pit_verified")):counts["premature_verification"]+=1
  if r.get("status")!="STAGING_UNMAPPED":counts["premature_publication"]+=1
  key=tuple(r.get(k) for k in ("source","native_archive","native_member","native_table","row_index","date","stock_id","native_field"))
  if key in keys:counts["duplicate_lineage_key"]+=1
  else:keys.add(key)
 return {"rows":counts["rows"],"invalid_date":counts["invalid_date"],"invalid_stock_id":counts["invalid_stock_id"],"nonfinite_numeric":counts["nonfinite_numeric"],"identifier_as_numeric":counts["identifier_as_numeric"],"premature_verification":counts["premature_verification"],"premature_publication":counts["premature_publication"],"duplicate_lineage_key":counts["duplicate_lineage_key"],"certified":False}
