"""Dated official ESB evidence. Routes retained RAW; never approves release."""
import datetime,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse,parse_qs
FIELDS=['日期','成交股數','成交金額(元)','成交最高','成交最低','成交均價','筆數']*1+['成交股數','成交金額(元)','成交最高','成交最低','成交均價','筆數']
def load_evidence(directory):
 directory=Path(directory); manifest=json.loads((directory/'manifest.json').read_text()); result={}
 for entry in manifest['inputs']:
  name=entry['file'];code=entry['code'];month=entry['month']
  if Path(name).name!=name or not re.fullmatch(r'[0-9]{4}',code):raise ValueError('ESB_UNSAFE_INPUT')
  datetime.date.fromisoformat(month+'-01')
  u=urlparse(entry['url']);q=parse_qs(u.query)
  if u.scheme!='https' or u.netloc!='www.tpex.org.tw' or u.path!='/www/zh-tw/emerging/historical' or q.get('code')!=[code] or q.get('date')!=[month.replace('-','/')+'/01'] or q.get('type')!=['Monthly']:raise ValueError('ESB_SOURCE_SCOPE')
  b=(directory/name).read_bytes();digest=hashlib.sha256(b).hexdigest()
  if digest!=entry['sha256']:raise ValueError('ESB_SHA_MISMATCH')
  obj=json.loads(b);t=obj['tables'][0];y,m=map(int,month.split('-'));roc=f'{y-1911}年{m:02d}月'
  if obj.get('stat')!='ok' or obj.get('date')!=month.replace('-','')+'01' or t.get('title')!='興櫃個股歷史行情' or t.get('date')!=roc or not t.get('subtitle','').startswith(roc+' '+code+' ') or t.get('fields')!=FIELDS or t.get('totalCount')!=len(t['data']):raise ValueError('ESB_CONTENT_SCOPE')
  for row in t['data']:
   if len(row)!=13:raise ValueError('ESB_ROW_WIDTH')
   a,b,c=map(int,row[0].split('/'));date=datetime.date(a+1911,b,c).isoformat()
   if date[:7]!=month:raise ValueError('ESB_ROW_PERIOD')
   key=(date,code)
   if key in result:raise ValueError('ESB_DUPLICATE_KEY')
   vals=[Decimal(str(v).replace(',','')) for v in row[1:]]
   if any(not v.is_finite() or v<0 for v in vals):raise ValueError('ESB_INVALID_NUMBER')
   result[key]=dict(native_row=row,official_sha256=digest,official_url=entry['url'],market='TPEx_ESB',scope='RETAINED_RAW_ONLY_NOT_RELEASED')
 return result

def compare_row(row,evidence):
 r=evidence['native_row'];num=lambda x:Decimal(str(x).replace(',',''))
 # Outside-system trades require a separate aggregation contract.
 if any(num(v)!=0 for v in r[7:]):raise ValueError('ESB_OUTSIDE_SYSTEM_CONTRACT_REQUIRED')
 checks={k:num(row[k])==num(r[i]) for k,i in [('max',3),('min',4),('Trading_Volume',1),('Trading_money',2)]}
 if not all(checks.values()):raise ValueError('ESB_OFFICIAL_VALUE_MISMATCH')
 return dict(date=row['date'],code=row['stock_id'],official_sha256=evidence['official_sha256'],comparisons=checks,scope='RETAINED_RAW_ONLY_NOT_RELEASED',open_semantics='PREVIOUS_AVERAGE_NOT_OPENING_TRADE',open_value_verified=False,close_value_verified=False,pit_verified=False)
