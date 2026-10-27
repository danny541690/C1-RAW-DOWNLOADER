"""Offline routing candidate. Does not request, download, approve or close data."""
import datetime,calendar,re
TERMS='https://mopsfin.twse.com.tw/terms'
def plan_route(year,quarter,market,*,as_of,adoption=None,calendar_type='CALENDAR'):
 if type(year) is not int or not 2000<=year<=2026:raise ValueError('YEAR_OUTSIDE_REGISTER_SCOPE')
 if type(quarter) is not int or not 1<=quarter<=4:raise ValueError('INVALID_QUARTER')
 if market not in ['TWSE','TPEx','EMERGING','PUBLIC']:raise ValueError('UNKNOWN_MARKET')
 when=datetime.date.fromisoformat(as_of);month=quarter*3;end=datetime.date(year,month,calendar.monthrange(year,month)[1])
 result={'year':year,'quarter':quarter,'market':market,'reference':TERMS,'request_allowed':False,'certified':False,'gap_remains_open':True,'attempts_preserved':True,'route':None}
 if end>when:return dict(result,action='PERIOD_NOT_DUE')
 if calendar_type!='CALENDAR':return dict(result,action='CONFIRM_FISCAL_PERIOD')
 if market in ['EMERGING','PUBLIC'] and quarter not in [2,4]:return dict(result,action='VERIFY_REPORTING_QUARTER_APPLICABILITY')
 if adoption is not None:
  if not isinstance(adoption,dict) or adoption.get('approved') is not True or not adoption.get('reference') or not re.fullmatch('[0-9a-fA-F]{64}',str(adoption.get('sha256',''))) or type(adoption.get('year')) is not int or not 1900<=adoption['year']<=2026:
   raise ValueError('DOCUMENTED_ADOPTION_REQUIRED')
  if year<adoption['year']:return dict(result,action='PRE_ADOPTION_LEGACY_ROUTE_REQUIRED')
  return dict(result,action='COMPARE_CANARY_ONLY',route='https://mopsfin.twse.com.tw/compare/report',request_allowed=True)
 floor=2015 if market=='PUBLIC' else 2013
 if year<floor:return dict(result,action='LEGACY_ROUTE_RESEARCH_REQUIRED')
 return dict(result,action='VERIFY_COMPANY_ADOPTION_BEFORE_COMPARE')
