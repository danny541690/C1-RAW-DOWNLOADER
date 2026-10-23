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
TICK_PAGES = ['dlFutPrevious30DaysSalesData', 'dlOptPrevious30DaysSalesData',
              'dlFutPrevious30DaysSpreadSalesData', 'dlFutPrevious30DaysSpreadOrdersReport', 'dlOptDailyDelta']
def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(b): return hashlib.sha256(b).hexdigest()
def encode(v): return json.dumps(v, ensure_ascii=False, sort_keys=True).encode()
def parse_date(v):
    v=str(v).strip()
    if re.fullmatch(r'20\d{6}',v):v=v[:4]+'/'+v[4:6]+'/'+v[6:]
    m = re.fullmatch(r'\s*(\d{3,4})[-/](\d{1,2})[-/](\d{1,2})(?:\s+.*)?', str(v))
    if not m: return None
    y, mo, day = map(int, m.groups())
    try: return dt.date(y + 1911 if y < 1911 else y, mo, day)
    except ValueError: return None

def csv_evidence(raw, start, end):
    if raw.lstrip().startswith((b'<', b'{', b'[')): raise ValueError('NOT_CSV_ERROR_OR_HTML')
    for encoding in ('utf-8-sig', 'cp950'):
        try: text = raw.decode(encoding); break
        except UnicodeDecodeError: pass
    else: raise ValueError('CSV_ENCODING')
    reader = csv.reader(io.StringIO(text)); header = next(reader, [])
    indexes = [i for i, k in enumerate(header) if any(x in k for x in ('日期', '年月日', 'Date', 'date'))]
    if not indexes: raise ValueError('CSV_DATE_HEADER_MISSING')
    count = 0; lo = None; hi = None; products = set(); sessions = set()
    contract = next((i for i, x in enumerate(header) if x.strip() in ('契約', '商品代號', '商品')), None)
    session = next((i for i, x in enumerate(header) if x.strip() == '交易時段'), None)
    for row in reader:
        if not any(x.strip() for x in row): continue
        dates = [parse_date(row[i]) for i in indexes if i < len(row)]
        dates = [x for x in dates if x]
        # Expiry dates may lie outside the request. Use the first date column
        # (trade/publication date), not the contract's expiry date.
        date = dates[0] if dates else None
        if not date: raise ValueError('CSV_ROW_DATE_MISSING')
        if not start <= date <= end: raise ValueError('RESPONSE_DATE_OUTSIDE_REQUEST:' + date.isoformat())
        lo = min(lo, date) if lo else date; hi = max(hi, date) if hi else date; count += 1
        if contract is not None and contract < len(row): products.add(row[contract].strip())
        if session is not None and session < len(row): sessions.add(row[session].strip())
    if not count: raise ValueError('EMPTY_NOT_PROOF_OF_NO_DATA')
    return dict(rows=count, content_period={'min': lo.isoformat(), 'max': hi.isoformat()},
                products=sorted(products), sessions=sorted(sessions), schema=header)

def validate(raw, job):
    kind = job['kind']; start = dt.date.fromisoformat(job['start']); end = dt.date.fromisoformat(job['end'])
    if kind == 'snapshot':
        rows = json.loads(raw.decode('utf-8-sig'))
        if not isinstance(rows, (list, dict)) or not rows: raise ValueError('EMPTY_OR_INVALID_API_RESPONSE')
        if isinstance(rows, dict) and any(k.lower() in ('error', 'errors') for k in rows): raise ValueError('API_ERROR')
        dates=[parse_date(v.get('Date','')) for v in rows if isinstance(v,dict)] if isinstance(rows,list) else []
        dates=[d.isoformat() for d in dates if d]
        return {'rows': len(rows), 'content_period': {'min':min(dates),'max':max(dates)} if dates else None, 'period_semantics': 'ACTUAL_SOURCE_DATE_ONLY_NO_HISTORICAL_PARAMETERS'}
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

class Worker:
    def __init__(self, minutes):
        from scripts.annual_actual_firstpass import Drive,service
        self.d=Drive(service()); self.d.direct_readback=True
        self.ctrl=self.d.folder(REPORT, 'TAIFEX_INDEPENDENT_STAGE06')
        raw=self.d.read(self.ctrl,'CURSOR.json')
        self.state=json.loads(raw) if raw else {'revision':'TAIFEX_INDEPENDENT_V1','receipts':{},'catalog':{},'tick_jobs':{}}
        self.until=time.monotonic()+minutes*60; self.today=dt.datetime.now(TZ).date()
        self.started=stamp(); self.saved=0; self.requests=0; self.folders={}
        self.state['status']='RUNNING_INDEPENDENT_CAPTURE'
        self.state.pop('last_error',None)
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def live(self): return time.monotonic()<self.until-100 and time.time()>=self.state.get('resume_after_epoch',0)
    def save(self):
        self.state.update(updated_utc=stamp(), run_id=os.environ.get('GITHUB_RUN_ID'), source='TAIFEX',
            finmind_enabled=False, coverage_certified=False, numeric_verified=False, pit_verified=False)
        self.d.put(self.ctrl,'CURSOR.json',encode(self.state),'application/json',overwrite=True)
        receipts=self.state['receipts']; periods=[v.get('content_period') for v in receipts.values() if v.get('status')=='SAVED_BASIC_VERIFIED' and v.get('content_period')]
        report={k:v for k,v in self.state.items() if k not in ('receipts','catalog','tick_jobs')}
        report.update(started_utc=self.started, saved_this_run=self.saved, source_requests_this_run=self.requests,
            saved_total=sum(v.get('status')=='SAVED_BASIC_VERIFIED' for v in receipts.values()),
            unresolved=sum(v.get('status')=='UNRESOLVED' for v in receipts.values()),
            actual_saved_range={'min':min(v['min'] for v in periods) if periods else None,'max':max(v['max'] for v in periods) if periods else None},
            requested_range={'min':'2000-01-01','max':self.today.isoformat()},
            historical_forms=len(self.state['catalog']), tick_files_discovered=len(self.state['tick_jobs']))
        self.d.put(self.ctrl,'STATUS.json',encode(report),'application/json',overwrite=True)
    def request(self,url,fields=None,timeout=45):
        if urllib.parse.urlparse(url).hostname not in ('www.taifex.com.tw','openapi.taifex.com.tw'): raise ValueError('NON_OFFICIAL_HOST')
        time.sleep(0.5); self.requests+=1
        data=urllib.parse.urlencode(fields).encode() if fields is not None else None
        req=urllib.request.Request(url,data=data,headers={'User-Agent':'Mozilla/5.0 JARVIS-TAIFEX/1.0', 'Referer':SITE+'/cht/3/futDailyMarketView'})
        with self.opener.open(req, timeout=timeout) as r:
            if urllib.parse.urlparse(r.geturl()).hostname not in ('www.taifex.com.tw','openapi.taifex.com.tw'): raise ValueError('NON_OFFICIAL_REDIRECT')
            raw=r.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('RESPONSE_SIZE_LIMIT_UNRESOLVED')
        return raw
    def evidence(self,name,raw):
        self.d.put(self.ctrl,name+'_'+digest(raw)+'.raw',raw,overwrite=False)
    def process(self,job):
        key=job['key']; old=self.state['receipts'].get(key,{})
        if old.get('status')=='SAVED_BASIC_VERIFIED': return True
        if old.get('attempts',0)>=3: return True
        if not self.live(): return False
        self.state['active_unit']={k:v for k,v in job.items() if k!='fields'}
        entry=dict(old,status='REQUEST_INTENT', attempts=old.get('attempts',0)+1, request=job, updated_utc=stamp())
        self.state['receipts'][key]=entry; self.save()
        raw=None
        try:
            raw=self.request(job['url'], job.get('fields')); ev=validate(raw,job)
            year=job['start'][:4]; period='_ANNUAL' if job['kind']=='annual' else job['start'][:7]
            cache_key=year+'/'+period
            if cache_key not in self.folders:
                self.folders[cache_key]=self.d.folder(self.d.folder(self.d.folder(ROOT,year),'TAIFEX'),period)
            parent=self.folders[cache_key]; extension='zip' if job['kind'] in ('tick','annual') else ('json' if job['kind']=='snapshot' else 'csv')
            name=re.sub('[^a-zA-Z0-9_-]','_',key)+'_'+digest(raw)+'.'+extension
            self.d.put(parent,name,raw,overwrite=False); file=self.d.find(parent,name)
            entry.update(ev,status='SAVED_BASIC_VERIFIED',file_id=file['id'],sha256=digest(raw),bytes=len(raw),
                         remote_readback_hash_verified=True,captured_utc=stamp(),numeric_verified=False,pit_verified=False)
            self.saved+=1
            if job['url'].endswith('/DailyMarketReportFut') and ev.get('content_period'):
                self.state['latest_trading_date']=ev['content_period']['max']
            print(json.dumps({'key':key,'status':entry['status'],'bytes':len(raw),'range':ev.get('content_period')}),flush=True)
        except Exception as exc:
            entry.update(status='UNRESOLVED',error=type(exc).__name__+':'+str(exc)[:220])
            if raw is not None:
                self.evidence('UNRESOLVED',raw); entry['response_sha256']=digest(raw)
            if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429): self.state['resume_after_epoch']=time.time()+900
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
            except Exception as exc:self.state.setdefault('discovery_errors',{})[name]=str(exc)[:200]
            done[name]=marker;self.save()
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
            if form['boundary_confirmed']:
                rolling=dt.date(latest.year-3,latest.month,min(latest.day,calendar.monthrange(latest.year-3,latest.month)[1]))
                first=max(first,rolling);last=latest
            for start,end in months_desc(last,first):
                fields=dict(form['fields'],queryStartDate=start.strftime('%Y/%m/%d'),queryEndDate=end.strftime('%Y/%m/%d'))
                key='HISTORY|'+action+'|'+start.strftime('%Y-%m')
                if end==last:key+='|'+end.isoformat()
                jobs.append(make_job(key,SITE+'/cht/3/'+action,'csv',start,end,fields))
        return sorted(jobs,key=lambda j:(j['end'],j['key'].startswith('MARKET'),j['key']),reverse=True)
    def discover_more(self,limit=4):
        completed=self.state.setdefault('discovery_done',[])
        for name in [n for n in self.state.get('discovery_pages',[]) if n not in completed][:limit]:
            if not self.live():return
            try:
                raw=self.page(name); forms=forms_from_page(raw,name)
                for f in forms:self.state['catalog'][f['action']]=f
                if not forms:self.state.setdefault('non_date_forms',[]).append(name)
                completed.append(name)
            except Exception as exc:
                self.state.setdefault('discovery_errors',{})[name]=str(exc)[:200]
                self.state.setdefault('discovery_attempts',{})[name]=self.state.get('discovery_attempts',{}).get(name,0)+1
                if self.state['discovery_attempts'][name]>=3:completed.append(name)
                if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):raise
            self.save()
    def run(self):
        if not self.live():return
        try:
            self.discover()
            # Preserve data through reachable official APIs before slower website probes.
            priority=['/DailyMarketReportFut','/DailyMarketReportOpt','/PutCallRatio','/DailyOptionsDelta']
            self.batch([make_job('API|'+self.today.isoformat()+'|'+p,'https://openapi.taifex.com.tw/v1'+p,'snapshot',self.today,self.today) for p in priority if p in self.state['api_paths']],4)
            while self.live():
                before=self.requests
                ticks=sorted(self.state['tick_jobs'].values(),key=lambda j:(j['end'],j['key']),reverse=True)
                self.batch(ticks,6)
                api=[make_job('API|'+self.today.isoformat()+'|'+p,'https://openapi.taifex.com.tw/v1'+p,'snapshot',self.today,self.today) for p in self.state['api_paths']]
                self.batch(api,12)
                self.refresh_tick_catalog()
                self.discover_more(4)
                self.batch(self.history_jobs(),24)
                if self.requests==before:break
            self.state['status']='CHECKPOINTED_CONTINUE_NEXT_WAKE' if self.live() else 'TIME_BUDGET_OR_BACKOFF_CHECKPOINT'
        except Exception as exc:
            self.state.update(status='BOOTSTRAP_OR_DISCOVERY_ERROR',last_error=type(exc).__name__+':'+str(exc)[:300])
            if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):self.state['resume_after_epoch']=time.time()+900
            raise
        finally:self.save()
    def batch(self,jobs,limit):
        count=0
        for j in jobs:
            old=self.state['receipts'].get(j['key'],{})
            if old.get('status')=='SAVED_BASIC_VERIFIED' or old.get('attempts',0)>=3:continue
            if not self.process(j):break
            count+=1
            if count>=limit:break

def main():
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=45);a=p.parse_args()
    if not 1<=a.minutes<=50:raise ValueError('INVALID_RUNTIME')
    Worker(a.minutes).run()
if __name__=='__main__':main()
