"""Validate the official early-2007 HTML report without changing original bytes."""
import datetime as dt,html,json,math,re
from lxml import html as lh
from scripts.v093_three_year_repair import actual_date,normdate

START='2007-01-02'
END='2007-04-20'
ENDPOINT='https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotesHis'

def clean(value):return re.sub(r'\s+','',html.unescape(re.sub('<[^>]+>',' ',str(value)))).strip()

def validate(raw,period):
 if not START<=period<=END:raise ValueError('TPEX_LEGACY_PERIOD_SCOPE')
 obj=json.loads(raw.decode('utf-8-sig'))
 if not isinstance(obj,dict):raise ValueError('TPEX_LEGACY_JSON_OBJECT_REQUIRED')
 if str(obj.get('stat','')).lower()!='ok':raise ValueError('TPEX_LEGACY_SOURCE_STATUS')
 payload=obj.get('html')
 if not isinstance(payload,str) or '<tr' not in payload.lower():raise ValueError('TPEX_LEGACY_HTML_MISSING')
 response_date=actual_date(obj)
 if response_date and response_date!=period:raise ValueError('TPEX_LEGACY_WRONG_RESPONSE_DATE')
 document=lh.fromstring(payload);trs=document.xpath('//tr');fields=None;header_at=None;code_index=None
 for index,tr in enumerate(trs):
  cells=[clean(cell.text_content()) for cell in tr.xpath('./th|./td')]
  for i,name in enumerate(cells):
   if name in ('代號','股票代號','證券代號'):
    fields=cells;code_index=i;header_at=index;break
  if fields:break
 if fields is None:raise ValueError('TPEX_LEGACY_CODE_HEADER_MISSING')
 title=' '.join(tr.text_content() for tr in trs[:header_at])
 dates=[]
 for match in re.finditer(r'(\d{2,4})\s*[/年]\s*(\d{1,2})\s*[/月]\s*(\d{1,2})',title):
  year,month,day=map(int,match.groups());year=year+1911 if year<1911 else year
  try:dates.append(dt.date(year,month,day).isoformat())
  except ValueError:raise ValueError('TPEX_LEGACY_TITLE_DATE_INVALID') from None
 if any(day!=period for day in dates):raise ValueError('TPEX_LEGACY_WRONG_TITLE_DATE')
 if not dates and not response_date:raise ValueError('TPEX_LEGACY_PAYLOAD_DATE_UNPROVEN')
 def column(names):
  return next((i for i,value in enumerate(fields) if any(value==name or value.startswith(name+'(') or value.startswith(name+'（') for name in names)),None)
 price_indexes=[column(names) for names in [('開盤','開盤價'),('最高','最高價'),('最低','最低價'),('收盤','收盤價')]]
 if None in price_indexes:raise ValueError('TPEX_LEGACY_OHLC_HEADERS_MISSING')
 volume=next((i for i,value in enumerate(fields) if value.startswith(('成交股數','成交量'))),None)
 amount=next((i for i,value in enumerate(fields) if value.startswith('成交金額')),None)
 if volume is None or amount is None:raise ValueError('TPEX_LEGACY_VOLUME_AMOUNT_HEADERS_MISSING')
 def number(value):
  text=clean(value).replace(',','')
  if text in ('','-','--','---','--.--'):return None
  value=float(text)
  if not math.isfinite(value):raise ValueError('TPEX_LEGACY_NONFINITE_NUMBER')
  return value
 codes=set();rows=0;price_checks=0;missing_price_rows=0
 for tr in trs[header_at+1:]:
  cells=[clean(cell.text_content()) for cell in tr.xpath('./th|./td')]
  if len(cells)<=code_index or not re.fullmatch('[1-9][0-9]{3}',cells[code_index]):continue
  if len(cells)!=len(fields):raise ValueError('TPEX_LEGACY_ROW_WIDTH')
  code=cells[code_index]
  if code in codes:raise ValueError('TPEX_LEGACY_DUPLICATE_CODE')
  codes.add(code);rows+=1;prices=[number(cells[i]) for i in price_indexes]
  if all(value is not None for value in prices):
   op,hi,lo,close=prices
   if min(prices)<=0 or not lo<=op<=hi or not lo<=close<=hi:raise ValueError('TPEX_LEGACY_OHLC_RELATIONSHIP')
   price_checks+=1
  else:missing_price_rows+=1
  for index in (volume,amount):
   value=number(cells[index])
   if value is None or value<0:raise ValueError('TPEX_LEGACY_VOLUME_OR_AMOUNT')
   if index==volume and '股數' in fields[index] and not any(unit in fields[index] for unit in ('千','仟')) and not value.is_integer():raise ValueError('TPEX_LEGACY_FRACTIONAL_SHARES')
 if len(codes)<300:raise ValueError('TPEX_LEGACY_MARKET_SCOPE_UNPROVEN')
 return dict(basic_verified=True,native=dict(period=period,rows=rows,codes=sorted(codes),fields=fields,price_relationship_rows_checked=price_checks,missing_price_rows=missing_price_rows,format='OFFICIAL_EARLY_2007_HTML_IN_JSON',period_evidence='TITLE_AND_JSON' if dates and response_date else 'TITLE' if dates else 'JSON_PAYLOAD_DATE'),units='AS_PUBLISHED_NO_CONVERSION',numeric_verified=False,pit_verified=False,full_acceptance=False)
