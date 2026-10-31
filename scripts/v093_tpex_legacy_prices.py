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
 return validate_html(payload,period,'OFFICIAL_EARLY_2007_HTML_IN_JSON',response_date)

def validate_archived(raw,period):
 if not '2003-08-01'<=period<='2006-12-31':raise ValueError('TPEX_ARCHIVED_PERIOD_SCOPE')
 text=None
 for codec in ('utf-8-sig','cp950','big5hkscs'):
  try:text=raw.decode(codec);break
  except UnicodeDecodeError:pass
 if text is None:raise ValueError('TPEX_ARCHIVED_ENCODING_UNPROVEN')
 return validate_html(text,period,'OFFICIAL_ARCHIVED_STATIC_HTML')

def validate_html(payload,period,format_name,response_date=None):
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
 # Oracle Reports repeats a compact ROC date under the explicit 資料日期
 # label on every page. Ignore generation timestamps; bind all report dates.
 for value in re.findall(r'資料日期\s*[:：]\s*(\d{6,8})(?!\d)',document.text_content()):
  year=int(value[:-4]);year=year+1911 if len(value)<8 else year
  try:dates.append(dt.date(year,int(value[-4:-2]),int(value[-2:])).isoformat())
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
 def number(value,price=False):
  text=clean(value).replace(',','')
  if price:text=re.sub(r'^[♁☉]','',text)
  if text in ('','-','--','---','--.--'):return None
  value=float(text)
  if not math.isfinite(value):raise ValueError('TPEX_LEGACY_NONFINITE_NUMBER')
  return value
 codes=set();rows=0;price_checks=0;missing_price_rows=0;zero_quote_rows=0;marked_price_cells=0;unquoted_ohl_rows=0
 for tr in trs[header_at+1:]:
  cells=[clean(cell.text_content()) for cell in tr.xpath('./th|./td')]
  if len(cells)<=code_index or not re.fullmatch('[1-9][0-9]{3}',cells[code_index]):continue
  if len(cells)!=len(fields):raise ValueError('TPEX_LEGACY_ROW_WIDTH')
  if '\ufffd' in ''.join(cells):raise ValueError('TPEX_LEGACY_SOURCE_REPLACEMENT_CHARACTER')
  code=cells[code_index]
  if code in codes:raise ValueError('TPEX_LEGACY_DUPLICATE_CODE')
  codes.add(code);rows+=1;prices=[number(cells[i],True) for i in price_indexes]
  marked_price_cells+=sum(cells[i].startswith(('♁','☉')) for i in price_indexes)
  if prices==[0.0]*4 and column(('漲跌',)) is not None and cells[column(('漲跌',))]=='---':
   prices=[None]*4;zero_quote_rows+=1
  elif format_name=='OFFICIAL_ARCHIVED_STATIC_HTML' and all(cells[i]=='.00' for i in price_indexes[:3]) and column(('漲跌',)) is not None and cells[column(('漲跌',))]=='0':
   if prices[3] is not None and prices[3]<0:raise ValueError('TPEX_LEGACY_NEGATIVE_CLOSE')
   # The observed Oracle report has no O/H/L quote in these rows, even when
   # a closing field or small trade exists. Preserve it; do not certify OHLC.
   prices[:3]=[None]*3;unquoted_ohl_rows+=1
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
 return dict(basic_verified=True,native=dict(period=period,rows=rows,codes=sorted(codes),fields=fields,price_relationship_rows_checked=price_checks,missing_price_rows=missing_price_rows,zero_quote_rows=zero_quote_rows,unquoted_open_high_low_rows=unquoted_ohl_rows,marked_price_cells=marked_price_cells,format=format_name,period_evidence='TITLE_AND_JSON' if dates and response_date else 'TITLE' if dates else 'JSON_PAYLOAD_DATE'),units='AS_PUBLISHED_NO_CONVERSION',numeric_verified=False,pit_verified=False,full_acceptance=False)
