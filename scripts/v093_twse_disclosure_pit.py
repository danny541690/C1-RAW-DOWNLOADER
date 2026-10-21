"""Taiwan MOPS/TWSE dated disclosure evidence, not automatic PIT approval."""
import datetime,re
def roc_compact_date(value):
 s=str(value or "").strip()
 m=re.fullmatch(r"(\d{3})(\d{2})(\d{2})",s)
 if not m:return None
 try:return datetime.date(int(m[1])+1911,int(m[2]),int(m[3])).isoformat()
 except ValueError:return None
def roc_compact_month(value):
 s=str(value or "").strip()
 m=re.fullmatch(r"(\d{3})(\d{2})",s)
 if not m:return None
 y,mo=int(m[1])+1911,int(m[2])
 return f"{y:04d}-{mo:02d}" if 1<=mo<=12 else None
def disclosure_evidence(row,target_month):
 period=roc_compact_month(row.get("資料年月"))
 published=roc_compact_date(row.get("出表日期"))
 issues=[]
 if not period:issues.append("DATA_MONTH_MISSING_OR_INVALID")
 if not published:issues.append("REPORT_DATE_MISSING_OR_INVALID")
 if period and period!=target_month:issues.append("DATA_MONTH_DIFFERENT_FROM_TARGET")
 if published and published[:7]>target_month:issues.append("DISCLOSURE_AFTER_TARGET_MONTH")
 return {"data_month":period,"report_date":published,"target_month":target_month,"pit_eligible_for_target_month":False if issues else None,"issues":issues,"certified":False}

def audit_disclosure_rows(rows,target_month):
 """Count every row; never infer market-available date from archive folder."""
 import collections
 c=collections.Counter();dates=collections.Counter();periods=collections.Counter()
 for row in rows:
  c["total_rows"]+=1
  if not isinstance(row,dict):
   c["non_dict_rows"]+=1;continue
  e=disclosure_evidence(row,target_month)
  if e["data_month"]:periods[e["data_month"]]+=1
  if e["report_date"]:dates[e["report_date"]]+=1
  for issue in e["issues"]:c[issue]+=1
  if not e["issues"]:c["no_detected_month_mismatch_but_pit_unverified"]+=1
 return {"counts":dict(c),"data_month_counts":dict(periods.most_common(12)),
         "report_date_counts":dict(dates.most_common(12)),
         "certified":False,"pit_verified":False}
