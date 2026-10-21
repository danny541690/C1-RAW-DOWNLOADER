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
