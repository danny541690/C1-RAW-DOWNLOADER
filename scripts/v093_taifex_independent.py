"""Stage 06: independent, resumable capture of official free TAIFEX data.

Native RAW is immutable. A verified transfer is not a numeric/PIT certification.
OpenAPI snapshots have no invented historical date arguments. Published CSV forms
and annual archives supply history; every receipt records the actual response range.
"""
import argparse, calendar, csv, datetime as dt, hashlib, html, http.cookiejar
import io, json, os, pathlib, re, time, urllib.error, urllib.parse, urllib.request, zipfile
from html.parser import HTMLParser
ROOT = '1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'
REPORT = '1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
SITE = 'https://www.taifex.com.tw'
SPEC = 'https://openapi.taifex.com.tw/swagger.json'
FLOOR = dt.date(2000, 1, 1)
TZ = dt.timezone(dt.timedelta(hours=8))
MAX_BYTES = 300_000_000
REPAIR_REVISION = 'TAIFEX_ROUTE_HEALTH_AND_DUE_TRANSPORT_RECOVERY_V8_2_20261025'
# These official aliases have 238 paired saved responses with identical SHA.
ROUTE_PAIRS = (('bargainOrderDown','dlBargainOrderDown'),
               ('largeTraderFutDown','dlLargeTraderFutDown'),
               ('largeTraderOptDown','dlLargeTraderOptDown'),
               ('productOrderDown','dlProductOrderDown'),
               ('singleOrderDown','dlSingleOrderDown'),
               ('combinationOrderDown','dlCombinationOrderDown'))
MAX_RETRY_CYCLES = 3
TICK_PAGES = ['dlFutPrevious30DaysSalesData', 'dlOptPrevious30DaysSalesData',
              'dlFutPrevious30DaysSpreadSalesData', 'dlFutPrevious30DaysSpreadOrdersReport', 'dlOptDailyDelta']
TERMINAL = {'SAVED_BASIC_VERIFIED', 'SKIPPED_SOURCE_EMPTY', 'SKIPPED_NOT_PUBLISHED'}
class OfficialEmpty(ValueError):
    """Valid native empty response; skip without certifying historical absence."""

def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def encode(v): return json.dumps(v, ensure_ascii=False, sort_keys=True).encode()
def parse_date(v):
    v=str(v).strip()
    v=re.sub(r'\s*([/-])\s*',r'\1',v)
    if re.fullmatch(r'(?:19|20)\d{6}',v):v=v[:4]+'/'+v[4:6]+'/'+v[6:]
    elif re.fullmatch(r'\d{7}',v):v=v[:3]+'/'+v[3:5]+'/'+v[5:]
    m = re.fullmatch(r'\s*(\d{3,4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+.*)?', str(v))
    if not m: return None
    y, mo, day = map(int, m.groups())
    try: return dt.date(y + 1911 if y < 1911 else y, mo, day)
    except ValueError: return None

def native_text(raw):
    for encoding in ('utf-8-sig', 'cp950'):
        try: return raw.decode(encoding)
        except UnicodeDecodeError: pass
    raise ValueError('CSV_ENCODING')

def reject_html(text):
    if not text.lstrip().startswith('<'):return
    # Exact official no-row alert, not a generic HTML/error page.
    if re.search(r'alert\(\s*[\"\']查無資料[\"\']\s*\)',text):
        raise OfficialEmpty('OFFICIAL_NO_DATA_ALERT_NOT_ABSENCE_CERTIFICATION')
    if '<title>Swagger UI</title>' in text:raise ValueError('API_ROUTE_RETURNS_SWAGGER_HTML')
    raise ValueError('NOT_CSV_ERROR_OR_HTML')

def csv_evidence(raw, start, end):
    text=native_text(raw)
    reject_html(text)
    if text.lstrip().startswith(('{','[')):raise ValueError('NOT_CSV_ERROR_OR_HTML')
    # Official annual futures exports contain a final DOS EOF record (0x1A).
    # Strip it only at EOF; malformed records within the file still fail.
    text=text.rstrip('\x1a \t\r\n')
    reader = csv.reader(io.StringIO(text)); header = next(reader, [])
    # Two official layouts do not repeat the publication/trade date on each row.
    if [v.strip() for v in header[:4]] == ['', '', '', '公布日期時間']:
        date=parse_date(header[4]) if len(header)==5 else None
        if not date or not start<=date<=end:raise ValueError('DELTA_PUBLICATION_DATE_OUTSIDE_REQUEST')
        schema=next(reader,[])
        if [v.strip() for v in schema]!=['商品','買賣權','到期月份(週別)','履約價格','Delta值','契約到期日']:
            raise ValueError('DELTA_SCHEMA_MISMATCH')
        count=0
        for row in reader:
            if not any(v.strip() for v in row):continue
            if len(row)!=6 or not row[0].strip() or row[1].strip() not in ('買權','賣權') or not parse_date(row[5]):
                raise ValueError('DELTA_ROW_INVALID')
            count+=1
        if not count:raise OfficialEmpty('EMPTY_DELTA_ROWS')
        return dict(rows=count,content_period={'min':date.isoformat(),'max':date.isoformat()},
                    schema=schema,period_semantics='OFFICIAL_PUBLICATION_TIMESTAMP_NOT_CONTRACT_EXPIRY')
    if header==['組合式序號','日期','契約數','交易時段']:
        schema=next(reader,[])
        if schema!=['組合式序號','子序號','契約','到期月份(週別)','履約價格','買/賣權','成交價格','成交數量']:
            raise ValueError('BLOCK_TRADE_SCHEMA_MISMATCH')
        groups=0;count=0;lo=None;hi=None;group=None;remaining=0;seen=set()
        for row in reader:
            if not any(v.strip() for v in row):continue
            if row[-1]=='':row=row[:-1]
            if len(row)==4:
                if remaining:raise ValueError('BLOCK_TRADE_LEGS_MISSING')
                date=parse_date(row[1])
                if not date or not start<=date<=end:raise ValueError('RESPONSE_DATE_OUTSIDE_REQUEST')
                if row[0] in seen or not re.fullmatch(r'C\d+',row[0]) or not row[2].isdigit() or int(row[2])<1:
                    raise ValueError('BLOCK_TRADE_GROUP_INVALID')
                group=row[0];seen.add(group);remaining=int(row[2]);groups+=1;leg=0
                lo=min(lo,date) if lo else date;hi=max(hi,date) if hi else date
            elif len(row)==8 and remaining and row[0]==group and row[1]==str(leg+1) and row[2].strip():
                remaining-=1;leg+=1;count+=1
            else:raise ValueError('BLOCK_TRADE_LEG_INVALID')
        if remaining:raise ValueError('BLOCK_TRADE_LEGS_MISSING')
        if not count:raise OfficialEmpty('EMPTY_BLOCK_TRADE_ROWS')
        return dict(rows=count,groups=groups,content_period={'min':lo.isoformat(),'max':hi.isoformat()},
                    schema=header,leg_schema=schema,period_semantics='TRADE_GROUP_DATE_INHERITED_BY_MATCHING_LEGS')
    indexes = [i for i, k in enumerate(header) if any(x in k for x in ('日期', '年月日', 'Date', 'date'))]
    if not indexes: raise ValueError('CSV_DATE_HEADER_MISSING')
    count = 0; lo = None; hi = None; products = set(); sessions = set(); footnotes=[]
    large_trader=(header[:5]==['日期','商品(契約)','商品名稱(契約名稱)','到期月份(週別)','交易人類別'] or header[:6]==['日期','商品(契約)','商品名稱(契約名稱)','買賣權','到期月份(週別)','交易人類別'])
    contract = next((i for i, x in enumerate(header) if x.strip() in ('契約', '商品代號', '商品')), None)
    session = next((i for i, x in enumerate(header) if x.strip() == '交易時段'), None)
    for row in reader:
        if not any(x.strip() for x in row): continue
        if large_trader and len(row)==1 and row[0].startswith(('月份類別格式:', '交易人類別格式：', '-表當日收盤後', '備註一：666666為所有週到期契約合計', '備註二：交易人類別格式：', '備註三："-"表當日收盤後')):
            footnotes.append(row[0]);continue
        if footnotes:raise ValueError('CSV_DATA_AFTER_FOOTNOTE')
        # Expiry dates may lie outside the request. Use the first date column
        # (trade/publication date), not the contract's expiry date.
        date = parse_date(row[indexes[0]]) if indexes[0]<len(row) else None
        if not date: raise ValueError('CSV_ROW_DATE_MISSING')
        if not start <= date <= end: raise ValueError('RESPONSE_DATE_OUTSIDE_REQUEST:' + date.isoformat())
        lo = min(lo, date) if lo else date; hi = max(hi, date) if hi else date; count += 1
        if contract is not None and contract < len(row): products.add(row[contract].strip())
        if session is not None and session < len(row): sessions.add(row[session].strip())
    if not count: raise OfficialEmpty('EMPTY_NOT_PROOF_OF_NO_DATA')
    return dict(rows=count, content_period={'min': lo.isoformat(), 'max': hi.isoformat()},
                products=sorted(products), sessions=sorted(sessions), schema=header,footnotes=footnotes)

API_CSV_SCHEMAS = {'DailyForeignExchangeRates': ['日期', '美元_新台幣(匯率)', '人民幣_新台幣(匯率)', '歐元_美元(匯率)', '美元_日幣(匯率)', '英鎊_美元(匯率)', '澳幣_美元(匯率)', '美元_港幣(匯率)', '美元_人民幣(匯率)', '美元_南非幣(匯率)', '紐幣_美元(匯率)'], 'DailyMarketReportOpt': ['日期', '契約', '到期月份(週別)', '履約價', '買賣權', '開盤價', '最高價', '最低價', '最後成交價', '成交量', '結算價', '未沖銷契約量', '最後最佳買價', '最後最佳賣價', '歷史最高價', '歷史最低價', '是否因訊息面暫停交易', '交易時段'], 'MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate': ['日期', '商品名稱', '身份別', '多方交易口數', '多方交易契約金額(千元)', '空方交易口數', '空方交易契約金額(千元)', '多空交易口數淨額', '多空交易契約金額淨額(千元)', '多方未平倉口數', '多方未平倉契約金額(千元)', '空方未平倉口數', '空方未平倉契約金額(千元)', '多空未平倉口數淨額', '多空未平倉契約金額淨額(千元)']}

API_CSV_SCHEMAS['DailyMarketReportFut'] = ['日期', '契約代號', '到期月份(週別)', '開盤價', '最高價', '最低價', '最後成交價', '漲跌價', '漲跌%', '合計成交量', '結算價', '未沖銷契約數', '最後最佳買價', '最後最佳賣價', '歷史最高價', '歷史最低價', '是否因訊息面暫停交易', '交易時段', '價差對單式委託成交量']

# Official government catalogue resources, live-probed 2026-10-25.
# Latest-only resources: never use them to reconstruct a missed capture day.
OFFICIAL_CSV_MIRRORS = {
    'AcceptableCollateralGovernmentBonds': 'https://data.gov.tw/dataset/11351',
    'IndexFuturesAndOptionsMargining': 'https://data.gov.tw/dataset/11604',
    'DailyOptionsDelta': 'https://data.gov.tw/dataset/11321',
    'CCP_CMLists': 'https://data.gov.tw/dataset/170552',
    'SSFRefferedOpeningPrice': 'https://data.gov.tw/dataset/136666',
    'SSFRefferedOpeningPriceAh': 'https://data.gov.tw/dataset/157963',
    'productsExemptedAH': 'https://data.gov.tw/dataset/170553',
}
API_CSV_SCHEMAS.update({
    'AcceptableCollateralGovernmentBonds': ['日期','公債代號','公債名稱','交易幣別'],
    'IndexFuturesAndOptionsMargining': ['商品別','結算保證金','維持保證金','原始保證金','日期'],
    'CCP_CMLists': ['結算會員中文名稱','結算會員類別','日期'],
    'DailyOptionsDelta': ['契約','買賣權','到期月份(週別)','履約價格','Delta值','契約到期日'],
    'SSFRefferedOpeningPrice': ['日期','股票代號','商品名稱','商品契約代號','月份','開盤參考價'],
    'SSFRefferedOpeningPriceAh': ['日期','股票代號','商品名稱','商品代號','月份','開盤參考價'],
    'productsExemptedAH': ['中文簡稱','商品契約代號','是否為盤後交易時段豁免代為沖銷商品','日期'],
})

def official_csv_mirror(job,today):
    parsed=urllib.parse.urlparse(job.get('url',''))
    route=parsed.path.removeprefix('/v1/')
    if (job.get('kind')!='snapshot' or job.get('start')!=today.isoformat()
            or job.get('end')!=today.isoformat() or job.get('fields')
            or parsed.scheme!='https' or parsed.netloc!='openapi.taifex.com.tw'
            or parsed.path!='/v1/'+route or parsed.query or route not in OFFICIAL_CSV_MIRRORS):
        return None
    return dict(job,url=SITE+'/data_gov/taifex_open_data.asp?data_name='+route,
                official_catalog_url=OFFICIAL_CSV_MIRRORS[route],
                latest_only=True,historical_reconstruction=False)

def api_csv_evidence(raw,job):
    parsed=urllib.parse.urlparse(job.get('url',''))
    route=parsed.path.removeprefix('/v1/')
    if parsed.scheme!='https' or parsed.hostname!='openapi.taifex.com.tw' or parsed.path!='/v1/'+route:
        raise ValueError('UNRECOGNIZED_API_CSV_ROUTE')
    rows=list(csv.reader(io.StringIO(native_text(raw))))
    if route not in API_CSV_SCHEMAS:raise ValueError('UNRECOGNIZED_API_CSV_ROUTE')
    if not rows or rows[0]!=API_CSV_SCHEMAS[route]:raise ValueError('API_CSV_SCHEMA_MISMATCH')
    for row in rows[1:]:
        if not any(v.strip() for v in row):continue
        if len(row)!=len(rows[0]):raise ValueError('API_CSV_ROW_WIDTH')
    if route=='DailyOptionsDelta':
        from decimal import Decimal, InvalidOperation
        seen=set()
        for row in rows[1:]:
            if not any(v.strip() for v in row):continue
            try:
                strike=Decimal(row[3]);delta=Decimal(row[4])
            except InvalidOperation:raise ValueError('DELTA_INVALID_NUMBER')
            if (not row[0].strip() or row[1] not in ('買權','賣權')
                    or not re.fullmatch(r'20\d{2}(?:0[1-9]|1[0-2])(?:[WF][1-5])?',row[2])
                    or not strike.is_finite() or strike<=0 or not delta.is_finite()
                    or not (-1<=delta<=1) or not parse_date(row[5])):
                raise ValueError('DELTA_INVALID_NATIVE_ROW')
            key=tuple(row[:4])
            if key in seen:raise ValueError('DELTA_DUPLICATE_CONTRACT')
            seen.add(key)
        if not seen:raise OfficialEmpty('EMPTY_DELTA_SNAPSHOT')
        # Expiry is not the publication/trade date. This resource omits that date.
        return dict(native_format='csv',rows=len(seen),schema=rows[0],content_period=None,
                    period_semantics='UNDATED_LATEST_SNAPSHOT_CAPTURE_ONLY_NOT_EXPIRY_DATE',
                    publication_date_verified=False,numeric_verified=False,pit_verified=False)
    # No historical arguments: use actual source dates, never capture day as data day.
    ev=csv_evidence(raw,FLOOR,dt.date.fromisoformat(job['end']))
    ev.update(native_format='csv',period_semantics='ACTUAL_SOURCE_DATE_ONLY_NO_HISTORICAL_PARAMETERS',
              numeric_verified=False,pit_verified=False)
    return ev

def validate(raw, job):
    kind = job['kind']; start = dt.date.fromisoformat(job['start']); end = dt.date.fromisoformat(job['end'])
    if kind == 'snapshot':
        text=native_text(raw);reject_html(text)
        if not text.lstrip().startswith(('{','[')):return api_csv_evidence(raw,job)
        rows = json.loads(text)
        if rows == []: raise OfficialEmpty('EMPTY_NATIVE_JSON_ARRAY_NOT_HISTORICAL_ABSENCE_PROOF')
        if not isinstance(rows, (list, dict)) or not rows: raise ValueError('EMPTY_OR_INVALID_API_RESPONSE')
        if isinstance(rows, dict) and any(k.lower() in ('error', 'errors') for k in rows): raise ValueError('API_ERROR')
        dates=[parse_date(v.get('Date','')) for v in rows if isinstance(v,dict)] if isinstance(rows,list) else []
        dates=[d.isoformat() for d in dates if d]
        return {'native_format':'json','rows': len(rows), 'content_period': {'min':min(dates),'max':max(dates)} if dates else None, 'period_semantics': 'ACTUAL_SOURCE_DATE_ONLY_NO_HISTORICAL_PARAMETERS'}
    if kind in ('annual', 'tick'):
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            members = z.infolist()
            if not members or any(m.flag_bits & 1 or m.file_size > 1_000_000_000 for m in members): raise ValueError('ZIP_MEMBER_LIMIT_OR_ENCRYPTED')
            if sum(m.file_size for m in members) > 1_500_000_000: raise ValueError('ZIP_EXPANSION_LIMIT')
            out = {'members': [m.filename for m in members], 'zip_crc_verified': True}
            rows = 0; low = None; high = None; products = set(); sessions = set()
            for m in members:
                if m.is_dir(): continue
                if kind == 'annual':
                    if not m.filename.lower().endswith('.csv'): raise ValueError('ANNUAL_UNEXPECTED_MEMBER')
                    ev = csv_evidence(z.read(m), start, end)
                    rows += ev['rows']; low = min(low, ev['content_period']['min']) if low else ev['content_period']['min']
                    high = max(high, ev['content_period']['max']) if high else ev['content_period']['max']
                    products.update(ev['products']); sessions.update(ev['sessions'])
                else:
                    # Read all members to check CRC, while bounding memory.
                    with z.open(m) as stream:
                        first = stream.read(8192)
                        if not first: raise ValueError('EMPTY_TICK_MEMBER')
                        first_text = first.decode('cp950', errors='replace')
                        dates = re.findall(r'(?<!\d)(20\d{2})[/-]?(\d{2})[/-]?(\d{2})(?!\d)', first_text)
                        expected = start.strftime('%Y%m%d')
                        if not any(''.join(v) == expected for v in dates): raise ValueError('TICK_CONTENT_DATE_NOT_CONFIRMED')
                        while stream.read(1024 * 1024): pass
            if kind == 'annual': out.update(rows=rows, content_period={'min': low, 'max': high}, products=sorted(products), sessions=sorted(sessions))
            else: out.update(content_period={'min': start.isoformat(), 'max': end.isoformat()}, numeric_verified=False)
            return out
    return csv_evidence(raw, start, end)

class FormParser(HTMLParser):
    def __init__(self): super().__init__(); self.forms=[]; self.current=None; self.select=None
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='form': self.current={'action':a.get('action',''), 'fields':{}, 'options':{}}
        elif self.current is not None:
            if tag=='input' and a.get('name') and a.get('type') not in ('button','submit'):
                self.current['fields'][a['name']]=a.get('value','')
            elif tag=='select' and a.get('name'):
                self.select=a['name']; self.current['options'][self.select]=[]
            elif tag=='option' and self.select and a.get('value') is not None:
                self.current['options'][self.select].append(a['value'])
    def handle_endtag(self, tag):
        if tag=='form' and self.current is not None: self.forms.append(self.current); self.current=None; self.select=None
        elif tag=='select': self.select=None

def forms_from_page(page, name):
    text=re.sub(r'<!--.*?-->', '', page.decode('utf-8-sig'), flags=re.S)
    p=FormParser(); p.feed(text)
    actions=re.findall(r"attr\(\s*['\"]action['\"]\s*,\s*['\"]([^'\"]+)['\"]", text)
    actions=[x for x in actions if re.fullmatch(r'[A-Za-z0-9]+Down',x)]
    result=[]
    for f in p.forms:
        if not {'queryStartDate','queryEndDate'} <= f['fields'].keys(): continue
        action=actions[-1] if actions else f['action']
        if not re.fullmatch('[A-Za-z0-9]+Down', action): continue
        if action in ('futDataDown','optDataDown','dlOptDataDown'): continue
        fields=f['fields'].copy()
        for key, options in f['options'].items():
            all_value=next((x for x in ('all','ALL','') if x in options), None)
            if all_value is None:
                # Selecting just the first product would silently truncate scope.
                fields[key]=options
            else: fields[key]=all_value
        for key in list(fields):
            if isinstance(fields[key], list): break
        else:
            if 'down_type' in fields: fields['down_type']='1'
            result.append({'name':name, 'action':action, 'fields':fields,
                'first':(parse_date(fields.get('firstDate','')) or FLOOR).isoformat(),
                'last':(parse_date(fields.get('lastDate','')) or dt.datetime.now(TZ).date()).isoformat(),
                'boundary_confirmed':bool(parse_date(fields.get('firstDate',''))),
                'source_page':SITE+'/cht/3/'+name})
    return result

def months_desc(latest, first):
    point=latest.replace(day=1)
    while point <= latest and point.replace(day=calendar.monthrange(point.year,point.month)[1]) >= first:
        yield max(first, point), min(latest, point.replace(day=calendar.monthrange(point.year,point.month)[1]))
        point=(point-dt.timedelta(days=1)).replace(day=1)

def make_job(key, url, kind, start, end, fields=None):
    return dict(key=key, url=url, kind=kind, start=start.isoformat(), end=end.isoformat(), fields=fields)

def transient_error(error):
    return bool(re.search(r'HTTP Error (?:502|503|504|520)\b',error) or
                error.startswith(('TimeoutError:', 'URLError:', 'ConnectionError:')))

def alias_job(job):
    parts=job.get('key','').split('|')
    if len(parts)<3 or parts[0]!='HISTORY' or job.get('kind')!='csv':return None
    for pair in ROUTE_PAIRS:
        if parts[1] not in pair:continue
        action=pair[1] if parts[1]==pair[0] else pair[0]
        if job.get('url')!=SITE+'/cht/3/'+parts[1]:return None
        parts[1]=action
        return dict(job,key='|'.join(parts),url=SITE+'/cht/3/'+action)
    return None

def same_query(a,b):
    # UI-only blank fields do not change the all-products request.
    clean=lambda fields:{k:v for k,v in (fields or {}).items() if v!=''}
    return (a.get('kind'),a.get('start'),a.get('end'),clean(a.get('fields'))) == \
           (b.get('kind'),b.get('start'),b.get('end'),clean(b.get('fields')))

def migrate_repairs(state):
    if state.get('repair_revision')==REPAIR_REVISION:return
    for entry in state.get('receipts',{}).values():
        if entry.get('status') in TERMINAL:continue
        # Parser migrations must not repeatedly reset transport/unknown failures.
        mirror=official_csv_mirror(entry.get('request',{}),dt.datetime.now(TZ).date())
        if not mirror and 'CSV_ROW_DATE_MISSING' not in entry.get('error',''):continue
        if mirror and 'API_ROUTE_RETURNS_SWAGGER_HTML' not in entry.get('error',''):continue
        entry['prior_attempts']=entry.get('attempts',0)
        entry['prior_error']=entry.get('error')
        entry.update(attempts=0, retry_after_epoch=0, repair_revision=REPAIR_REVISION)
    for name,day in list(state.get('tick_page_attempted_dates',{}).items()):
        if state.get('tick_page_success_dates',{}).get(name)!=day:
            state['tick_page_attempted_dates'].pop(name,None)
    state.update(repair_revision=REPAIR_REVISION)
    state.pop('resume_after_epoch',None)

def reconcile_interrupted_intents(state):
    # Called only after this workflow concurrency group has obtained its writer slot.
    for entry in state.get('receipts',{}).values():
        if entry.get('status')!='REQUEST_INTENT':continue
        entry.update(status='UNRESOLVED',error='TimeoutError:PREVIOUS_REQUEST_INTENT_UNCONFIRMED',
                     interrupted_request=True)

def prepare_transport_retries(state,now=None):
    now=time.time() if now is None else now
    for entry in state.get('receipts',{}).values():
        if entry.get('status')!='UNRESOLVED' or not transient_error(entry.get('error','')):continue
        if entry.get('attempts',0)<3 or now<entry.get('retry_after_epoch',0):continue
        cycle=entry.get('transport_retry_cycle',1)
        if cycle>=MAX_RETRY_CYCLES:continue
        entry.setdefault('retry_history',[]).append(dict(cycle=cycle,attempts=entry['attempts'],error=entry.get('error'),at=stamp()))
        entry['lifetime_attempts']=max(entry.get('lifetime_attempts',0),sum(v['attempts'] for v in entry['retry_history']))
        entry.update(attempts=0,transport_retry_cycle=cycle+1)

def partition_jobs(jobs,direction):
    boundary='2013-01-01'
    result=[]
    for job in jobs:
        if job['start']<boundary<=job['end']:
            raise ValueError('PARTITION_CROSSING_JOB')
        if (job['end']<boundary)==(direction=='ASC'):result.append(job)
    return result

def import_history_catalog(state,peer):
    added=[]
    for action,form in peer.get('catalog',{}).items():
        if action in state.setdefault('catalog',{}):continue
        if not re.fullmatch(r'[A-Za-z0-9]+Down',action) or form.get('action')!=action:continue
        page=form.get('source_page','')
        if not re.fullmatch(re.escape(SITE)+r'/cht/3/[A-Za-z0-9]+',page):continue
        fields=form.get('fields')
        if not isinstance(fields,dict) or not {'queryStartDate','queryEndDate'}<=fields.keys():continue
        if any(not isinstance(k,str) or not isinstance(v,str) for k,v in fields.items()):continue
        try:first=dt.date.fromisoformat(form['first']);last=dt.date.fromisoformat(form['last'])
        except (KeyError,TypeError,ValueError):continue
        if first>last:continue
        state['catalog'][action]=dict(form,fields=dict(fields),catalog_imported_from_run=peer.get('run_id'))
        added.append(action)
    return added

def canonical_history_jobs(jobs,receipts):
    groups={}
    for job in jobs:
        alias=alias_job(job)
        route=min(job['url'],alias['url']) if alias else job['url']
        key=(job['kind'],job['start'],job['end'],route,
             json.dumps({k:v for k,v in (job.get('fields') or {}).items() if v!=''},sort_keys=True))
        prior=groups.get(key)
        rank=lambda j:(receipts.get(j['key'],{}).get('status')!='SAVED_BASIC_VERIFIED',
                       receipts.get(j['key'],{}).get('status') not in TERMINAL,
                       j['key'] not in receipts,j['key'])
        if prior is None or rank(job)<rank(prior):groups[key]=job
    return list(groups.values())

def snapshot_route_health(receipts):
    latest={};failures=[]
    for key,entry in receipts.items():
        job=entry.get('request',{})
        if job.get('kind')!='snapshot':continue
        route=job.get('url')
        if (entry.get('status')=='SAVED_BASIC_VERIFIED' and entry.get('remote_readback_hash_verified')
                and entry.get('file_id') and entry.get('sha256')):
            prior=latest.get(route)
            if prior is None or job.get('end','')>prior[1]['request'].get('end',''):
                latest[route]=(key,entry)
        elif entry.get('status')=='UNRESOLVED' and 'SWAGGER_HTML' in entry.get('error',''):
            failures.append((key,entry))
    interrupted={}
    for key,entry in receipts.items():
        job=entry.get('request',{})
        if not entry.get('interrupted_request') or job.get('kind')!='snapshot':continue
        saved=latest.get(job.get('url'))
        if saved and saved[1]['request'].get('end','')>job.get('end',''):
            interrupted[key]=dict(unit_id=saved[0],file_id=saved[1]['file_id'],sha256=saved[1]['sha256'],
                                  content_period=saved[1].get('content_period'),original_capture_recreated=False)
    no_capture=sorted({v['request']['url'] for _,v in failures}-set(latest))
    later={}
    for key,entry in failures:
        saved=latest.get(entry['request']['url'])
        if saved and saved[1]['request'].get('end','')>entry['request'].get('end',''):
            later[key]=dict(unit_id=saved[0],sha256=saved[1]['sha256'],file_id=saved[1]['file_id'],
                            original_capture_recreated=False)
    return dict(historical_swagger_failure_units=len(failures),
                swagger_failure_units_with_later_verified_capture=len(later),
                swagger_routes_without_any_verified_capture=no_capture,
                swagger_routes_without_any_verified_capture_count=len(no_capture),
                later_verified_captures=later,interrupted_capture_followups=interrupted,
                historical_capture_gaps_preserved=True)

class Worker:
    def __init__(self, minutes, direction='DESC', audit_round=1):
        from scripts.annual_actual_firstpass import Drive,service
        self.d=Drive(service()); self.d.direct_readback=True
        self.direction=direction
        self.audit_round=audit_round
        self.audit_revision=('REMOTE_RAW_SECOND_PASS_20261026' if audit_round==2 else 'REMOTE_RAW_AUDIT_V9')
        self.audited_this_run=0
        self.ctrl=self.d.folder(REPORT, 'TAIFEX_INDEPENDENT_STAGE06_ASC' if direction=='ASC' else 'TAIFEX_INDEPENDENT_STAGE06')
        raw=self.d.read(self.ctrl,'CURSOR.json')
        self.state=json.loads(raw) if raw else {'revision':'TAIFEX_INDEPENDENT_V1','receipts':{},'catalog':{},'tick_jobs':{}}
        if direction=='ASC':
            previous=self.d.read(self.d.folder(REPORT,'TAIFEX_INDEPENDENT_STAGE06'),'CURSOR.json')
            if previous:
                peer=json.loads(previous)
                added=import_history_catalog(self.state,peer)
                self.state['catalog_sync']=dict(from_run=peer.get('run_id'),added=added,total_forms=len(self.state['catalog']),checked_utc=stamp())
                for key,entry in peer.get('receipts',{}).items():
                    if entry.get('status')=='SAVED_BASIC_VERIFIED':
                        self.state['receipts'].setdefault(key,entry)
        self.recorded_repair_keys=frozenset(self.state.get('receipts',{}))
        self.state['repair_scope']='RECORDED_RECEIPTS_ONLY; SAVED_RAW_IMMUTABLE'
        self.state['direction']=direction
        self.state['partition_policy']='ASC:2000-01-01..2012-12-31; DESC:2013-01-01..LATEST; NO_OVERLAP'
        reconcile_interrupted_intents(self.state)
        migrate_repairs(self.state)
        self.until=time.monotonic()+minutes*60; self.today=dt.datetime.now(TZ).date()
        self.started=stamp(); self.saved=0; self.requests=0; self.folders={}
        self.peer_recovered=0; self.evidence_recovered=0; self._status_last=0
        self.state['status']='RUNNING_INDEPENDENT_CAPTURE'
        self.state['missing_data_policy']='DOWNLOAD_AVAILABLE; EMPTY_NOT_ABSENCE; MAX_3_ATTEMPTS_PER_CYCLE_MAX_3_TRANSIENT_CYCLES; CONTINUE_ASSIGNED_DIRECTION'
        self.state.pop('last_error',None)
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def live(self): return time.monotonic()<self.until-100
    def eligible(self,job):
        old=self.state['receipts'].get(job['key'],{})
        mirror=official_csv_mirror(job,getattr(self,'today',dt.datetime.now(TZ).date()))
        route=(mirror or job)['url'];host=urllib.parse.urlparse(route).hostname
        return (not old.get('integrity_hold') and old.get('status') not in TERMINAL and old.get('status')!='EXCLUDED_FUTURE_PUBLISHED_LINK'
                and old.get('attempts',0)<3 and time.time()>=old.get('retry_after_epoch',0)
                and time.time()>=self.state.get('route_backoff',{}).get(route,0)
                and time.time()>=self.state.get('source_backoff',{}).get(host,0))
    def save(self,force_status=False):
        self.state.update(updated_utc=stamp(), run_id=os.environ.get('GITHUB_RUN_ID'), source='TAIFEX',
            finmind_enabled=False, coverage_certified=False, numeric_verified=False, pit_verified=False)
        self.d.put(self.ctrl,'CURSOR.json',encode(self.state),'application/json',overwrite=True)
        if not force_status and time.monotonic()-getattr(self,'_status_last',0)<30:return
        receipts=self.state['receipts']; periods=[v.get('content_period') for v in receipts.values() if v.get('status')=='SAVED_BASIC_VERIFIED' and v.get('content_period') and v['content_period']['max']<=self.today.isoformat()]
        report={k:v for k,v in self.state.items() if k not in ('receipts','catalog','tick_jobs')}
        report.update(started_utc=self.started, saved_this_run=self.saved, source_requests_this_run=self.requests,
            saved_total=sum(v.get('status')=='SAVED_BASIC_VERIFIED' for v in receipts.values()),
            unresolved=sum(v.get('status')=='UNRESOLVED' for v in receipts.values()),
            skipped_unavailable=sum(v.get('status') in ('SKIPPED_SOURCE_EMPTY','SKIPPED_NOT_PUBLISHED') for v in receipts.values()),
            actual_saved_range={'min':min(v['min'] for v in periods) if periods else None,'max':max(v['max'] for v in periods) if periods else None},
            requested_range={'min':'2000-01-01','max':self.today.isoformat()},
            historical_forms=len(self.state['catalog']), tick_files_discovered=len(self.state['tick_jobs']))
        report['audit_round']=getattr(self,'audit_round',1)
        report['audited_this_run']=getattr(self,'audited_this_run',0)
        report['schedule_number']='6' if self.direction=='DESC' else '6-1'
        report['unresolved_error_counts']={}
        for entry in receipts.values():
            if entry.get('status')=='UNRESOLVED':
                error=entry.get('error','UNKNOWN').split(':',2)[:2];label=':'.join(error)
                report['unresolved_error_counts'][label]=report['unresolved_error_counts'].get(label,0)+1
        report['peer_receipts_recovered_this_run']=getattr(self,'peer_recovered',0)
        report['retained_evidence_recovered_this_run']=getattr(self,'evidence_recovered',0)
        report['unique_saved_files']=len({v.get('file_id') for v in receipts.values() if v.get('status')=='SAVED_BASIC_VERIFIED' and v.get('file_id')})
        assigned=[v for v in receipts.values() if v.get('request') and ((v['request'].get('end','')<'2013-01-01')==(self.direction=='ASC'))]
        report['assigned_saved_units']=sum(v.get('status')=='SAVED_BASIC_VERIFIED' for v in assigned)
        report['imported_or_outside_partition_saved_units']=report['saved_total']-report['assigned_saved_units']
        report['retry_cycles_exhausted_units']=sum(v.get('status')=='UNRESOLVED' and v.get('attempts',0)>=3 and v.get('transport_retry_cycle',1)>=MAX_RETRY_CYCLES for v in assigned)
        report['exhausted_units']=sum(v.get('status')=='UNRESOLVED' and v.get('attempts',0)>=3 for v in receipts.values())
        report['unresolved_api_route_count']=len({v.get('request',{}).get('url') for v in receipts.values() if v.get('status')=='UNRESOLVED' and 'SWAGGER_HTML' in v.get('error','')})
        report['snapshot_route_health']=snapshot_route_health(receipts)
        report['source_empty_units']=sum(v.get('status')=='SKIPPED_SOURCE_EMPTY' for v in receipts.values())
        report['unavailable_url_units']=sum(v.get('status')=='SKIPPED_NOT_PUBLISHED' for v in receipts.values())
        plan=self.history_jobs()
        report['planned_history_units']=len(plan)
        report['planned_history_unattempted_units']=sum(j['key'] not in receipts for j in plan)
        report['planned_history_saved_units']=sum(receipts.get(j['key'],{}).get('status')=='SAVED_BASIC_VERIFIED' for j in plan)
        report['planned_history_source_empty_units']=sum(receipts.get(j['key'],{}).get('status')=='SKIPPED_SOURCE_EMPTY' for j in plan)
        report['missed_snapshot_units']=sum(bool(v.get('status')=='UNRESOLVED' and v.get('interrupted_request') and v.get('request',{}).get('kind')=='snapshot' and v.get('request',{}).get('end','')<self.today.isoformat()) for v in receipts.values())
        self.d.put(self.ctrl,'STATUS.json',encode(report),'application/json',overwrite=True)
        self._status_last=time.monotonic()
        print('TAIFEX_LIVE_STATUS '+json.dumps({k:report.get(k) for k in ('run_id','direction','schedule_number','audit_round','status','saved_this_run','source_requests_this_run','audited_this_run','assigned_saved_units','unresolved','retry_cycles_exhausted_units','planned_history_units','planned_history_unattempted_units','raw_audit_summary','updated_utc')},ensure_ascii=False),flush=True)
    def request(self,url,fields=None,timeout=45):
        if urllib.parse.urlparse(url).hostname not in ('www.taifex.com.tw','openapi.taifex.com.tw'): raise ValueError('NON_OFFICIAL_HOST')
        if time.time()<self.state.get('source_backoff',{}).get(urllib.parse.urlparse(url).hostname,0):
            raise TimeoutError('SOURCE_COOLDOWN_ACTIVE')
        time.sleep(0.5); self.requests+=1
        data=urllib.parse.urlencode(fields).encode() if fields is not None else None
        req=urllib.request.Request(url,data=data,headers={'User-Agent':'Mozilla/5.0 JARVIS-TAIFEX/2.0', 'Accept':'application/json' if 'openapi.taifex.com.tw' in url else '*/*', 'Referer':SITE+'/cht/3/futDailyMarketView'})
        with self.opener.open(req, timeout=timeout) as r:
            if urllib.parse.urlparse(r.geturl()).hostname not in ('www.taifex.com.tw','openapi.taifex.com.tw'): raise ValueError('NON_OFFICIAL_REDIRECT')
            raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('RESPONSE_SIZE_LIMIT_UNRESOLVED')
        return raw
    def evidence(self,name,raw):
        self.d.put(self.ctrl,name+'_'+digest(raw)+'.raw',raw,overwrite=False)
    def persist_raw(self,job,raw,entry,ev):
        year=job['start'][:4];period='_ANNUAL' if job['kind']=='annual' else job['start'][:7]
        cache_key=year+'/'+period
        if cache_key not in self.folders:
            self.folders[cache_key]=self.d.folder(self.d.folder(self.d.folder(ROOT,year),'TAIFEX'),period)
        parent=self.folders[cache_key];extension='zip' if job['kind'] in ('tick','annual') else (ev.get('native_format','json') if job['kind']=='snapshot' else 'csv')
        name=re.sub('[^a-zA-Z0-9_-]','_',job['key'])+'_'+digest(raw)+'.'+extension
        self.d.put(parent,name,raw,overwrite=False);file=self.d.find(parent,name)
        entry.update(ev,status='SAVED_BASIC_VERIFIED',file_id=file['id'],sha256=digest(raw),bytes=len(raw),
            remote_readback_hash_verified=True,captured_utc=stamp(),numeric_verified=False,pit_verified=False,
            repair_revision=REPAIR_REVISION)
        entry.pop('error',None);entry.pop('retry_after_epoch',None)
        self.saved+=1
    def read_receipt_raw(self,entry):
        return self.d.call(lambda:self.d.api.files().get_media(fileId=entry['file_id']))
    def audit_saved(self, limit=24):
        """Resume immutable remote RAW checks; never treat a read outage as corruption."""
        checked=0
        items=sorted(self.state['receipts'].items(),key=lambda kv:(kv[1].get('request',{}).get('start',''),kv[0]),reverse=self.direction=='DESC')
        for key,entry in items:
            job=entry.get('request',{})
            if not self.live() or checked>=limit:break
            if entry.get('status')!='SAVED_BASIC_VERIFIED' or not job or entry.get('integrity_hold'):continue
            if job.get('kind')=='snapshot':
                if self.direction=='ASC':continue
            elif (job.get('end','')<'2013-01-01')!=(self.direction=='ASC'):continue
            signature=entry.get('sha256')
            prior=entry.get('raw_audit',{})
            if prior.get('revision')==getattr(self,'audit_revision','REMOTE_RAW_AUDIT_V9') and prior.get('sha256')==signature and prior.get('status')=='PASS_BASIC':continue
            if time.time()<prior.get('retry_after_epoch',0):continue
            checked+=1
            self.audited_this_run=getattr(self,'audited_this_run',0)+1
            audit=dict(revision=getattr(self,'audit_revision','REMOTE_RAW_AUDIT_V9'),sha256=signature,checked_utc=stamp(),run_id=os.environ.get('GITHUB_RUN_ID'))
            try:
                raw=self.read_receipt_raw(entry)
                if not signature or digest(raw)!=signature:raise ValueError('REMOTE_RAW_SHA_MISMATCH')
                ev=validate(raw,job)
                audit.update(status='PASS_BASIC',evidence=ev,numeric_verified=False,pit_verified=False)
            except Exception as exc:
                audit.update(status='READ_OR_CONTENT_CHECK_FAILED',error=type(exc).__name__+':'+str(exc)[:220],retry_after_epoch=time.time()+900)
                # A missing file may be recaptured by its original historical request.
                missing=(getattr(exc,'code',None) or getattr(getattr(exc,'resp',None),'status',None)) in (404,410)
                if missing:
                    entry['previous_saved_receipt']={k:v for k,v in entry.items() if k not in ('previous_saved_receipt','raw_audit')}
                    entry.update(status='UNRESOLVED',attempts=0,retry_after_epoch=0,error='AUDIT_REMOTE_FILE_MISSING')
                elif isinstance(exc,(ValueError,zipfile.BadZipFile,OfficialEmpty)):
                    entry['integrity_hold']=True
                    audit['status']='CONTENT_OR_SHA_HOLD_REQUIRES_REVIEW'
            if prior and prior.get('revision')!=audit['revision']:
                entry.setdefault('raw_audit_history',[]).append(dict(prior))
            entry['raw_audit']=audit
            self.state['raw_audit_last_unit']=key
            self.save()
        self.state['raw_audit_summary']={name:sum(e.get('raw_audit',{}).get('status')==name for e in self.state['receipts'].values()) for name in ('PASS_BASIC','READ_OR_CONTENT_CHECK_FAILED','CONTENT_OR_SHA_HOLD_REQUIRES_REVIEW')}

    def recover_existing(self):
        for key,old in list(self.state['receipts'].items()):
            if not self.live():return
            if old.get('status')!='UNRESOLVED':continue
            job=old.get('request',{})
            if not job:continue
            # ASC imports DESC successes; repair only the lane's assigned history.
            if job.get('kind')!='snapshot' and ((job['end']<'2013-01-01')!=(self.direction=='ASC')):continue
            if job.get('kind')=='snapshot' and self.direction=='ASC':continue
            if old.get('offline_recovery_revision')==REPAIR_REVISION:continue
            peer_job=alias_job(job)
            peer=self.state['receipts'].get(peer_job['key'],{}) if peer_job else {}
            has_peer=(peer.get('status')=='SAVED_BASIC_VERIFIED' and peer.get('remote_readback_hash_verified')
                      and peer.get('file_id') and same_query(job,peer.get('request',{})))
            # The unchanged Swagger validator cannot turn known HTML into data.
            if not has_peer and (not old.get('response_sha256') or 'API_ROUTE_RETURNS_SWAGGER_HTML' in old.get('error','')):continue
            entry=dict(old);entry['offline_recovery_revision']=REPAIR_REVISION
            try:
                if has_peer:
                    raw=self.read_receipt_raw(peer)
                    if digest(raw)!=peer['sha256']:raise ValueError('PEER_REMOTE_READBACK_SHA_MISMATCH')
                    ev=validate(raw,job)
                    entry.update(ev,status='SAVED_BASIC_VERIFIED',file_id=peer['file_id'],sha256=digest(raw),bytes=len(raw),
                        remote_readback_hash_verified=True,captured_utc=peer.get('captured_utc'),checked_utc=stamp(),
                        numeric_verified=False,pit_verified=False,repair_revision=REPAIR_REVISION,
                        recovered_from_verified_peer_receipt=peer_job['key'],
                        source_request=peer.get('source_request',peer['request']),prior_error=old.get('error'))
                    entry.pop('error',None);entry.pop('retry_after_epoch',None)
                    self.peer_recovered+=1
                elif old.get('response_sha256'):
                    raw=self.d.read(self.ctrl,'UNRESOLVED_'+old['response_sha256']+'.raw')
                    if raw is None:
                        entry.pop('offline_recovery_revision',None)
                        continue
                    if digest(raw)!=old['response_sha256']:raise ValueError('RETAINED_EVIDENCE_SHA_MISMATCH')
                    try:ev=validate(raw,job)
                    except OfficialEmpty as exc:
                        entry.update(status='SKIPPED_SOURCE_EMPTY',historical_absence_certified=False,
                            error='OfficialEmpty:'+str(exc),prior_error=old.get('error'))
                    except (ValueError,zipfile.BadZipFile) as exc:
                        entry.update(error=type(exc).__name__+':'+str(exc)[:220],prior_error=old.get('error'))
                        if 'API_ROUTE_RETURNS_SWAGGER_HTML' in str(exc):
                            self.state.setdefault('route_backoff',{})[job['url']]=max(time.time()+86400,self.state.get('route_backoff',{}).get(job['url'],0))
                    else:
                        self.persist_raw(job,raw,entry,ev);entry['recovered_from_saved_evidence']=True
                        self.evidence_recovered+=1
            except Exception as exc:
                entry['offline_recovery_error']=type(exc).__name__+':'+str(exc)[:220]
                # Integrity failures remain unresolved and must never trigger a new source overwrite.
                if 'SHA_MISMATCH' in str(exc):entry['integrity_hold']=True
                else:entry.pop('offline_recovery_revision',None)
            self.state['receipts'][key]=entry;self.save()
    def process(self,job):
        key=job['key']
        if hasattr(self,'recorded_repair_keys') and key not in self.recorded_repair_keys:return True
        old=self.state['receipts'].get(key,{})
        if old.get('status') in TERMINAL: return True
        if old.get('attempts',0)>=3: return True
        if not self.eligible(job):return True
        if not self.live(): return False
        self.state['active_unit']={k:v for k,v in job.items() if k!='fields'}
        entry=dict(old,status='REQUEST_INTENT', attempts=old.get('attempts',0)+1,
            lifetime_attempts=max(old.get('lifetime_attempts',0),old.get('attempts',0))+1,
            request=job, updated_utc=stamp())
        self.state['receipts'][key]=entry; self.save()
        raw=None
        try:
            # Recover rejected native RAW before spending another source request.
            if (not official_csv_mirror(job,getattr(self,'today',dt.datetime.now(TZ).date())) and old.get('response_sha256') and old.get('prior_error')
                    and old.get('evidence_revalidated_revision')!=REPAIR_REVISION):
                cached=self.d.read(self.ctrl,'UNRESOLVED_'+old['response_sha256']+'.raw')
                if cached is not None and digest(cached)==old['response_sha256']:
                    entry['evidence_revalidated_revision']=REPAIR_REVISION
                    try:ev=validate(cached,job)
                    except OfficialEmpty:
                        raw=cached;entry['recovered_from_saved_evidence']=True
                        raise
                    except ValueError as exc:
                        if 'API_ROUTE_RETURNS_SWAGGER_HTML' in str(exc):
                            raw=cached;raise
                    except zipfile.BadZipFile:pass
                    else:raw=cached;entry['recovered_from_saved_evidence']=True
            if raw is None:
                actual=alias_job(job) if transient_error(old.get('error','')) and entry['lifetime_attempts']%2==0 else None
                actual=actual or official_csv_mirror(job,getattr(self,'today',dt.datetime.now(TZ).date())) or job
                entry['source_request']=actual
                raw=self.request(actual['url'], actual.get('fields'));ev=validate(raw,job)
            self.persist_raw(job,raw,entry,ev)
            if job['url'].endswith('/DailyMarketReportFut') and ev.get('content_period'):
                self.state['latest_trading_date']=ev['content_period']['max']
            print(json.dumps({'key':key,'status':entry['status'],'bytes':len(raw),'range':ev.get('content_period')}),flush=True)
        except Exception as exc:
            entry.update(status='UNRESOLVED',error=type(exc).__name__+':'+str(exc)[:220],retry_after_epoch=time.time()+(60 if transient_error(type(exc).__name__+':'+str(exc)) else 900))
            if raw is not None:
                self.evidence('UNRESOLVED',raw); entry['response_sha256']=digest(raw)
            if isinstance(exc,OfficialEmpty):
                entry.update(status='SKIPPED_SOURCE_EMPTY', historical_absence_certified=False, skip_reason='VALID_NATIVE_RESPONSE_HAS_NO_ROWS_CONTINUE_OLDER_UNITS')
            elif isinstance(exc,urllib.error.HTTPError) and exc.code in (404,410):
                entry.update(status='SKIPPED_NOT_PUBLISHED', http_status=exc.code, historical_absence_certified=False, skip_reason='OFFICIAL_DOWNLOAD_URL_NOT_AVAILABLE_CONTINUE_OLDER_UNITS')
            if 'API_ROUTE_RETURNS_SWAGGER_HTML' in str(exc):
                self.state.setdefault('route_backoff',{})[job['url']]=time.time()+86400
            if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429,502,503,504,520):
                self.state.setdefault('source_backoff',{})[urllib.parse.urlparse(entry.get('source_request',job)['url']).hostname]=time.time()+(900 if exc.code in (403,429) else 60)
            print(json.dumps({'key':key,'status':entry['status'],'error':entry['error']}),flush=True)
        self.state['receipts'][key]=entry; self.save(); return self.live()
    def page(self,name):
        raw=self.request(SITE+'/cht/3/'+name,timeout=12)
        self.evidence('AVAILABILITY_'+name, raw)
        return raw
    def discover(self):
        # Catalogue was verified against real official downloads before deployment.
        # Its bounded refresh must never block accessible OpenAPI captures.
        seed=json.loads(pathlib.Path(__file__).with_name('taifex_verified_catalog.json').read_text())
        seed['tick_jobs']={}
        for directory,names in seed['published_files'].items():
            for name in names:
                match=re.search(r'(20\d{2})_?(\d{2})_?(\d{2})(?:_[A-Z])?\.(?:zip|csv)$',name)
                if not match:continue
                date=dt.date(*map(int,match.groups()))
                if not FLOOR<=date<=self.today:continue
                path=directory+'/'+name;key='TICK|'+path
                seed['tick_jobs'][key]=make_job(key,SITE+'/file/taifex/Dailydownload/'+path,'tick' if name.endswith('.zip') else 'csv',date,date)
        for key in ('api_paths','futures_annual_years','options_annual_years','latest_trading_date','discovery_pages'):
            self.state.setdefault(key,seed[key])
        self.state['tick_jobs']={k:v for k,v in self.state['tick_jobs'].items() if v['end']<=self.today.isoformat()}
        for receipt in self.state['receipts'].values():
            req=receipt.get('request',{})
            if req.get('kind')=='tick' and req.get('end','')>self.today.isoformat():
                receipt['capture_status_before_date_exclusion']=receipt['status']
                receipt['status']='EXCLUDED_FUTURE_PUBLISHED_LINK'
        for key in ('catalog','tick_jobs'):
            for k,v in seed[key].items():self.state[key].setdefault(k,v)
        self.state['availability']={'verified_catalog_utc':seed['verified_utc'],
            'futures_annual_years':self.state['futures_annual_years'],
            'options_annual_years':self.state['options_annual_years'],
            'institution_download_first':seed['catalog']['futContractsDateDown']['first'],
            'institution_download_last':seed['catalog']['futContractsDateDown']['last'],
            'ticks':'PUBLISHED_PREVIOUS_30_TRADING_DAY_LINKS_ONLY',
            'api_dataset_count':len(self.state['api_paths']),
            'api_history':'NO_HISTORICAL_ARGUMENTS; SOURCE_DATE_RECORDED',
            'unavailable_paid_history':'EXCLUDED_NOT_DOWNLOADED',
            'other_history':'PER_FORM_CONFIRMED_OR_EXPLICIT_UNCONFIRMED_BOUNDS'}
        self.evidence('VERIFIED_CATALOG',encode(seed))
        marker=self.today.isoformat()
        if self.state.get('bootstrap_date')!=marker:
            try:
                spec=self.request(SPEC,timeout=15);parsed=json.loads(spec.decode('utf-8-sig'))
                self.evidence('OPENAPI_SPEC',spec)
                self.state['api_paths']={p:v['get'].get('summary',p) for p,v in parsed['paths'].items()
                    if 'get' in v and not any(x.get('required') for x in v['get'].get('parameters',[]))}
            except Exception as exc:self.state['api_catalog_refresh_error']=str(exc)[:200]
            self.state['bootstrap_date']=marker
        self.save()
    def refresh_tick_catalog(self):
        done=self.state.setdefault('tick_page_attempted_dates',{})
        marker=self.today.isoformat()
        for name in TICK_PAGES:
            if done.get(name)==marker:continue
            retry=self.state.setdefault('tick_page_retry',{}).get(name,{})
            if retry.get('date')==marker and (retry.get('attempts',0)>=3 or time.time()<retry.get('after',0)):continue
            if time.time()<self.state.get('source_backoff',{}).get('www.taifex.com.tw',0):return
            if not self.live():return
            try:
                raw=self.page(name);text=html.unescape(raw.decode('utf-8-sig'))
                urls=set(re.findall(r'(https://www\.taifex\.com\.tw)?(/file/taifex/Dailydownload/[^\s\'\"<>]+\.(?:zip|csv))',text))
                for _,path in urls:
                    m=re.search(r'(20\d{2})_?(\d{2})_?(\d{2})(?:_[A-Z])?\.(?:zip|csv)$',path)
                    if not m:continue
                    date=dt.date(*map(int,m.groups()))
                    if not FLOOR<=date<=self.today:continue
                    key='TICK|'+path.split('/Dailydownload/',1)[-1]
                    self.state['tick_jobs'][key]=make_job(key,SITE+path,'tick' if path.endswith('.zip') else 'csv',date,date)
                self.state.setdefault('tick_page_success_dates',{})[name]=marker
                done[name]=marker
                self.state.get('discovery_errors',{}).pop(name,None)
                self.state.setdefault('tick_page_retry',{}).pop(name,None)
            except Exception as exc:
                self.state.setdefault('discovery_errors',{})[name]=str(exc)[:200]
                attempts=retry.get('attempts',0)+1 if retry.get('date')==marker else 1
                self.state.setdefault('tick_page_retry',{})[name]=dict(date=marker,attempts=attempts,after=time.time()+900)
            self.save()
            break
    def history_jobs(self):
        latest=min(self.today,dt.date.fromisoformat(self.state['latest_trading_date']))
        # Annual native archives reduce requests and include every product in each year.
        jobs=[]
        for label,action in [('futures','futDataDown'),('options','optDataDown')]:
            for start,end in months_desc(latest,dt.date(latest.year,1,1)):
                fields=dict(down_type='1', queryStartDate=start.strftime('%Y/%m/%d'),queryEndDate=end.strftime('%Y/%m/%d'),commodity_id='all',commodity_id2='')
                jobs.append(make_job('MARKET|'+label+'|'+start.strftime('%Y-%m')+'|'+end.isoformat() if end.month==latest.month else 'MARKET|'+label+'|'+start.strftime('%Y-%m'),SITE+'/cht/3/'+action,'csv',start,end,fields))
            for y in self.state[label+'_annual_years']:
                jobs.append(make_job('ANNUAL|'+label+'|'+str(y),SITE+'/cht/3/'+action,'annual',dt.date(y,1,1),dt.date(y,12,31),{'down_type':'2','his_year':str(y)}))
        for action,form in self.state['catalog'].items():
            first=max(FLOOR,dt.date.fromisoformat(form['first'])); last=min(latest,dt.date.fromisoformat(form['last']))
            for start,end in months_desc(last,first):
                fields=dict(form['fields'],queryStartDate=start.strftime('%Y/%m/%d'),queryEndDate=end.strftime('%Y/%m/%d'))
                key='HISTORY|'+action+'|'+start.strftime('%Y-%m')
                if end==last:key+='|'+end.isoformat()
                jobs.append(make_job(key,SITE+'/cht/3/'+action,'csv',start,end,fields))
        jobs=canonical_history_jobs(partition_jobs(jobs,self.direction),self.state.get('receipts',{}))
        return sorted(jobs,key=lambda j:(j['end'],j['key'].startswith('MARKET'),j['key']),reverse=self.direction=='DESC')
    def discover_more(self,limit=4):
        completed=self.state.setdefault('discovery_done',[])
        for name in [n for n in self.state.get('discovery_pages',[]) if n not in completed][:limit]:
            if not self.live():return
            try:
                raw=self.page(name); forms=forms_from_page(raw,name)
                for f in forms:self.state['catalog'][f['action']]=f
                if not forms:self.state.setdefault('non_date_forms',[]).append(name)
                completed.append(name)
                self.state.get('discovery_errors',{}).pop(name,None)
            except Exception as exc:
                self.state.setdefault('discovery_errors',{})[name]=str(exc)[:200]
                self.state.setdefault('discovery_attempts',{})[name]=self.state.get('discovery_attempts',{}).get(name,0)+1
                if self.state['discovery_attempts'][name]>=3:completed.append(name)
                if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):raise
            self.save()
    def wait_short_source_cooldown(self):
        # A transient 60s pause must not turn into a whole scheduled interval.
        # Long rate limits still checkpoint; never bypass or shorten host backoff.
        now=time.time()
        waits=[until-now for until in self.state.get('source_backoff',{}).values() if 0<until-now<=60]
        if not waits or not self.live():return False
        time.sleep(min(5,min(waits)))
        return True
    def retry_due_history(self):
        jobs=[]
        for entry in self.state['receipts'].values():
            job=entry.get('request',{})
            if (entry.get('status')=='UNRESOLVED' and transient_error(entry.get('error',''))
                    and job.get('kind') in ('csv','annual','tick') and job.get('end')
                    and ((job['end']<'2013-01-01')==(self.direction=='ASC'))
                    and self.eligible(job)):
                jobs.append(job)
        return sorted(jobs,key=lambda j:j['key'])
    def run(self):
        if not self.live():return
        try:
            self.state['audit_round']=getattr(self,'audit_round',1)
            self.discover()
            self.audit_saved()
            self.recover_existing()
            prepare_transport_retries(self.state)
            self.save()
            if self.direction=='ASC':
                while self.live():
                    before=(self.requests,self.saved)
                    self.batch(self.retry_due_history(),4)
                    history=self.history_jobs()
                    self.batch([j for j in history if j['kind']=='annual'],2)
                    self.batch(history,24)
                    if (self.requests,self.saved)==before:
                        if self.wait_short_source_cooldown():continue
                        break
                self.state['status']='ASC_CHECKPOINTED_WITH_OPEN_ITEMS'
                return
            # Preserve data through reachable official APIs before slower website probes.
            priority=['/CCP_CMLists','/DailyOptionsDelta','/SSFRefferedOpeningPrice','/SSFRefferedOpeningPriceAh','/productsExemptedAH','/DailyMarketReportFut','/DailyMarketReportOpt','/PutCallRatio']
            self.batch([make_job('API|'+self.today.isoformat()+'|'+p,'https://openapi.taifex.com.tw/v1'+p,'snapshot',self.today,self.today) for p in priority if p in self.state['api_paths']],8)
            while self.live():
                before=(self.requests,self.saved)
                self.batch(self.retry_due_history(),4)
                ticks=sorted(self.state['tick_jobs'].values(),key=lambda j:(j['end'],j['key']),reverse=True)
                self.batch(ticks,6)
                api=[make_job('API|'+self.today.isoformat()+'|'+p,'https://openapi.taifex.com.tw/v1'+p,'snapshot',self.today,self.today) for p in self.state['api_paths']]
                self.batch(api,12)
                self.refresh_tick_catalog()
                self.discover_more(4)
                history=self.history_jobs()
                # Annual archives cover every native product with fewer requests.
                # Recover their retained rejected ZIPs first; newest years first.
                self.batch([j for j in history if j['kind']=='annual'],2)
                self.batch(history,24)
                if (self.requests,self.saved)==before:
                    if self.wait_short_source_cooldown():continue
                    break
            self.state['status']='CHECKPOINTED_CONTINUE_NEXT_WAKE' if self.live() else 'TIME_BUDGET_OR_BACKOFF_CHECKPOINT'
        except Exception as exc:
            self.state.update(status='BOOTSTRAP_OR_DISCOVERY_ERROR',last_error=type(exc).__name__+':'+str(exc)[:300])
            if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):self.state['resume_after_epoch']=time.time()+900
            raise
        finally:
            self.save(force_status=True)
            self.publish_open_items()
    def publish_open_items(self):
        items=[]
        health=snapshot_route_health(self.state['receipts'])
        for key,entry in self.state['receipts'].items():
            if entry.get('status')=='SAVED_BASIC_VERIFIED' and not entry.get('integrity_hold') and entry.get('raw_audit',{}).get('status')!='READ_OR_CONTENT_CHECK_FAILED':continue
            error=entry.get('raw_audit',{}).get('error') or entry.get('error','')
            category=('MISSED_SNAPSHOT_CAPTURE_NOT_RECREATABLE' if entry.get('interrupted_request') and entry.get('request',{}).get('kind')=='snapshot' and entry.get('request',{}).get('end','')<self.today.isoformat() else
                      'INTEGRITY_HOLD' if entry.get('integrity_hold') else
                      'FUTURE_PUBLISHED_LINK_NOT_REQUESTED' if entry.get('status')=='EXCLUDED_FUTURE_PUBLISHED_LINK' else
                      'SOURCE_EMPTY_UNCONFIRMED' if entry.get('status')=='SKIPPED_SOURCE_EMPTY' else
                      'OFFICIAL_URL_UNAVAILABLE_NOT_ABSENCE' if entry.get('status')=='SKIPPED_NOT_PUBLISHED' else
                      'API_ROUTE_HTML' if 'SWAGGER_HTML' in error else
                      'TRANSIENT_TRANSPORT' if transient_error(error) else 'PARSER_OR_RESPONSE_REVIEW')
            items.append(dict(unit_id=key,category=category,status=entry.get('status'),error=error,
                attempts=entry.get('attempts',0),lifetime_attempts=entry.get('lifetime_attempts',entry.get('attempts',0)),
                retry_cycle=entry.get('transport_retry_cycle',1),retry_after_epoch=entry.get('retry_after_epoch'),
                request=entry.get('request'),sha256=entry.get('response_sha256'),
                later_verified_capture=health['later_verified_captures'].get(key) or health['interrupted_capture_followups'].get(key),
                original_capture_recreated=False,historical_absence_certified=False))
        self.d.put(self.ctrl,'OPEN_ITEMS.json',encode(dict(updated_utc=stamp(),run_id=os.environ.get('GITHUB_RUN_ID'),
            repair_revision=REPAIR_REVISION,items=items,coverage_certified=False,numeric_verified=False,pit_verified=False)),
            'application/json',overwrite=True)
    def batch(self,jobs,limit):
        count=0
        for j in jobs:
            if not self.eligible(j):continue
            if not self.process(j):break
            count+=1
            if count>=limit:break

def main():
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=45);p.add_argument('--direction',choices=['ASC','DESC'],default='DESC');p.add_argument('--audit-round',type=int,choices=[1,2],default=1);a=p.parse_args()
    if not 1<=a.minutes<=50:raise ValueError('INVALID_RUNTIME')
    Worker(a.minutes,a.direction,a.audit_round).run()
if __name__=='__main__':main()

