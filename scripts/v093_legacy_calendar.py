"""Conservative reader for official archived HTML holiday tables."""
import datetime as dt,re
from lxml import html

def chinese_number(text):
 text=text.strip()
 if text.isdigit():return int(text)
 digits={'零':0,'〇':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
 if text.startswith('廿'):return 20+(chinese_number(text[1:]) if text[1:] else 0)
 if text.startswith('卅'):return 30+(chinese_number(text[1:]) if text[1:] else 0)
 total=0;current=0
 for char in text:
  if char in digits:current=digits[char]
  elif char in ('十','百'):total+=(current or 1)*(10 if char=='十' else 100);current=0
  else:raise ValueError('CALENDAR_CHINESE_NUMBER')
 return total+current

def parse(text,year,url):
 document=html.fromstring(text);rows=[]
 for tr in document.xpath('//tr'):
  rows.append([re.sub(r'\s+','',cell.text_content()) for cell in tr.xpath('./td|./th')])
 header=None;header_at=None
 for i,row in enumerate(rows):
  if '名稱' in row and '日期' in row:header=row;header_at=i;break
 if header is None:raise ValueError('LEGACY_CALENDAR_HEADERS_UNPROVEN')
 # A page title and a body heading must not disagree about the year.
 heading=' '.join(document.xpath('//title/text()|//h1//text()|//h2//text()|//h3//text()|//caption//text()'))+' '+' '.join(' '.join(row) for row in rows[:header_at])
 scopes=[]
 for value in re.findall(r'([0-9零〇一二三四五六七八九十百]{2,4})\s*年',heading):
  number=chinese_number(value);scopes.append(number if number>=1911 else number+1911)
 if not scopes or any(scope!=year for scope in scopes):raise ValueError('LEGACY_CALENDAR_YEAR_UNPROVEN')
 ni=header.index('名稱');di=header.index('日期');closed=set();opened=set();unknown=[]
 chars='0-9零〇一二三四五六七八九十廿卅'
 pattern=rf'([{chars}]{{1,3}})月([{chars}]{{1,3}})日'
 for row in rows[header_at+1:]:
  if len(row)!=len(header):continue # Merged/ambiguous rows are not inferred.
  label=row[ni];date_text=row[di];description=' '.join(row)
  pairs=re.findall(pattern,date_text);days=[]
  for month,day in pairs:days.append(dt.date(year,chinese_number(month),chinese_number(day)))
  if len(days)==2 and any(mark in date_text for mark in ('至','～','~')):
   if not 0<=(days[1]-days[0]).days<=15:raise ValueError('LEGACY_CALENDAR_RANGE')
   days=[days[0]+dt.timedelta(days=i) for i in range((days[1]-days[0]).days+1)]
  if not days:continue
  target=opened if any(value in label for value in ('開始交易','最後交易','開始買賣','最後買賣')) else closed if any(value in description for value in ('休市','放假','補假','市場無交易','不交易')) else None
  if target is None:unknown.extend(day.isoformat() for day in days)
  else:target.update(day.isoformat() for day in days)
 if not closed or closed&opened:raise ValueError('LEGACY_CALENDAR_DATES_UNPROVEN')
 return dict(year=year,url=url,closed=sorted(closed),opened=sorted(opened),unclassified=sorted(set(unknown)),format='OFFICIAL_ARCHIVED_HTML_CALENDAR',annual_table_is_not_complete_emergency_calendar=True)
