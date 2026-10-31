"""Official-first 2024-2026 raw audit and bounded gap repair.

Existing raw is immutable. Date evidence comes from payloads, never filenames.
ZIP CRC is storage integrity only; numeric/PIT/universe approval stays false.
"""
import argparse, calendar, collections, datetime as dt, hashlib, html, io, json
import os, re, time, urllib.error, urllib.parse, urllib.request, zipfile, csv
from pathlib import Path
from scripts.annual_actual_firstpass import Drive, service

ROOT = '1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'
REPORT_ROOT = '1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
PASS = 'THREE_YEAR_OFFICIAL_GAPS_20261019_R1'
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
DAILY = {
 'TWSE': [('prices_indices','rwd/zh/afterTrading/MI_INDEX',{'type':'ALLBUT0999'}),
 ('institutional','rwd/zh/fund/T86',{'selectType':'ALLBUT0999'}),
 ('margin','rwd/zh/marginTrading/MI_MARGN',{'selectType':'ALL'}),
 ('valuation','rwd/zh/afterTrading/BWIBBU_d',{'selectType':'ALL'}),
 ('lending','rwd/zh/marginTrading/TWT93U',{}),
 ('foreign_holdings','rwd/zh/fund/MI_QFIIS',{'selectType':'ALLBUT0999'})],
 'TPEx': [('prices','afterTrading/dailyQuotes',{}),
 ('institutional','insti/dailyTrade',{'type':'Daily','sect':'AL'}),
 ('margin','margin/balance',{}),('lending','margin/sbl',{}),
 ('foreign_holdings','insti/qfii',{}),('marketcap','afterTrading/dailyMarktVal',{}),
 ('valuation','afterTrading/peQryDate',{'cate':''}),('indices','afterTrading/indexSummary',{})]}
EVENTS = {'TWSE':[('ex_dividend','https://www.twse.com.tw/rwd/zh/exRight/TWT49U'),
 ('capital_reduction','https://www.twse.com.tw/exchangeReport/TWTAUU')],
 'TPEx':[(n,'https://www.tpex.org.tw/www/zh-tw/bulletin/'+p) for n,p in
 [('ex_dividend','exDailyQ'),('capital_reduction','revivt'),('par_value_change','pvChgRslt')]]}

def stamp(): return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(b): return hashlib.sha256(b).hexdigest()
def emit(x): print(json.dumps(x,ensure_ascii=False),flush=True)
def listing(d,p):
 out=[]; token=None
 while True:
  r=d.call(lambda:d.api.files().list(q="'"+p+"' in parents and trashed=false",fields='nextPageToken,files(id,name,mimeType,size)',pageSize=1000,pageToken=token))
  out.extend(r.get('files',[]));token=r.get('nextPageToken')
  if not token:return out
def read(d,f): return d.call(lambda:d.api.files().get_media(fileId=f['id']))
def putj(d,p,n,x): d.put(p,n,(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode(),'application/json',overwrite=True)
def normdate(v):
 s=str(v).strip()
 m=re.fullmatch(r'(\d{3,4})[-/](\d{1,2})[-/](\d{1,2})',s) or re.fullmatch(r'(20\d{2})(\d{2})(\d{2})',s)
 if not m:return None
 y,mo,da=map(int,m.groups());y=y+1911 if y<1911 else y
 try:return dt.date(y,mo,da).isoformat()
 except ValueError:return None
def actual_date(obj):
 for k in ('date','Date','trade_date','tradeDate','reportDate'):
  found=normdate(obj.get(k,''))
  if found:return found
 return None
def category(name,source):
 name=name.rsplit('/',1)[-1]
 for cat,_,_ in DAILY.get(source,[]):
  if re.search(r'(?:^|_)'+re.escape(cat)+r'(?:_|\.)',name,re.I):return cat
 if source in ('TWSE','TPEx') and ('BULK' in name or 'HISTORICAL_CORRECTED' in name):
  return 'prices_indices' if source=='TWSE' else 'prices'
 for cat,_ in EVENTS.get(source,[]):
  if cat in name:return cat
 if source=='MOPS':
  m=re.search(r'revenue_(sii|otc).*?_(0|1)(?:_|\.)',name)
  if m:return 'revenue_'+m[1]+'_'+m[2]
  m=re.search(r'(?:MONTHLY_REVENUE_|revenue_)(sii|otc)',name)
  if m:return 'revenue_'+m[1]+'_0'
 return None
def tabular(obj):
 tables=obj.get('tables') or ([obj] if isinstance(obj.get('data'),list) else [])
 rows=[]; codes=set(); issues=0
 for t in tables:
  if not isinstance(t,dict):continue
  fields=t.get('fields',[]);data=t.get('data',[])
  for row in data:
   if not isinstance(row,list):continue
   if fields and len(row)!=len(fields):issues+=1
   rows.append(row)
  ix=next((i for i,f in enumerate(fields) if str(f).strip() in ('代號','股票代號','證券代號','公司代號')),None)
  if ix is not None:
   codes.update(str(row[ix]).strip().replace('="','').strip('"') for row in data if isinstance(row,list) and len(row)>ix and re.fullmatch(r'[1-9]\d{3}',str(row[ix]).strip()))
 return rows,codes,issues
def validate(raw,source,cat,period):
 if source=='MOPS' and cat.startswith('revenue_'):
  text=None
  # Older official HTML contains Big5 extension characters. Never discard bytes:
  # strict CP950 alone rejected otherwise readable tables as NO_REVENUE_TABLE.
  for enc in ('utf-8-sig','cp950','big5hkscs'):
   try:
    candidate=raw.decode(enc)
    if '<table' in candidate.lower():text=candidate;break
   except UnicodeDecodeError:pass
  if text is None:raise ValueError('REVENUE_ENCODING_OR_TABLE_UNPROVEN')
  y,m=map(int,period.split('-'));plain=html.unescape(re.sub('<[^>]+>',' ',text))
  if not re.search(str(y-1911)+r'\s*年\s*0?'+str(m)+r'\s*月',plain):raise ValueError('REVENUE_PERIOD_UNPROVEN')
  codes=set(re.findall(r'<td[^>]*>\s*([1-9]\d{3})\s*</td>',text,re.I))
  if not codes:raise ValueError('NO_COMPANY_ROWS')
  return {'rows':len(codes),'codes':sorted(codes),'period':period,'encoding':enc}
 try:obj=json.loads(raw.decode('utf-8-sig'))
 except (ValueError,UnicodeDecodeError):
  if len(period)!=10:raise ValueError('NON_JSON_PERIOD_REQUIRES_SEPARATE_VALIDATION')
  for enc in ('utf-8-sig','cp950'):
   try:
    text=raw.decode(enc)
    mt=re.search(r'(\d{3,4})[/年](\d{1,2})[/月](\d{1,2})',text[:600])
    if not mt or normdate('/'.join(mt.groups()))!=period:continue
    rows=list(csv.reader(io.StringIO(text)))
    hi=next(i for i,r in enumerate(rows) if any(f in r for f in ('代號','股票代號','證券代號')))
    fields=rows[hi];ix=next(i for i,f in enumerate(fields) if f in ('代號','股票代號','證券代號'))
    data=[r for r in rows[hi+1:] if len(r)>ix and re.fullmatch(r'[A-Za-z0-9]{4,12}',r[ix].strip())]
    if not data or any(len(r)!=len(fields) for r in data):raise ValueError('CSV_TABLE_WIDTH_OR_ROWS')
    codes={r[ix].strip() for r in data if re.fullmatch(r'[1-9]\d{3}',r[ix].strip())}
    if cat in ('prices','prices_indices') and len(codes)<300:raise ValueError('CSV_NOT_FULL_MARKET')
    return {'rows':len(data),'codes':sorted(codes),'period':period,'encoding':enc,'format':'OFFICIAL_CSV'}
   except (UnicodeDecodeError,StopIteration):continue
  raise ValueError('NON_JSON_OR_CSV_DATE_UNPROVEN')
 if not isinstance(obj,dict):raise ValueError('NOT_JSON_OBJECT')
 if str(obj.get('stat','')).lower()!='ok':raise ValueError('SOURCE_STATUS:'+str(obj.get('stat',''))[:100])
 rows,codes,issues=tabular(obj)
 if issues:raise ValueError('ROW_FIELD_WIDTH_MISMATCH')
 if len(period)==10:
  if actual_date(obj)!=period:raise ValueError('RESPONSE_DATE_MISMATCH:'+str(actual_date(obj)))
  if not rows:raise ValueError('EMPTY_RESPONSE_NOT_COVERAGE')
  if cat in ('prices','prices_indices') and len(codes)<300:raise ValueError('NOT_FULL_MARKET_PRICE_TABLE')
 else:
  # Event rows must carry dates; empty results are not proof of no events.
  if not rows:raise ValueError('EMPTY_EVENT_UNPROVEN')
  dates=[normdate(re.sub('<[^>]+>','',str(r[0])).strip()) for r in rows if r]
  if not dates or any(not v or v[:7]!=period for v in dates):raise ValueError('EVENT_PERIOD_UNPROVEN')
 return {'rows':len(rows),'codes':sorted(codes),'period':period}

def request_data(params):
 # JSON round-trips tuples into lists; retain repeated companyId parameters.
 if params is None:return None
 if hasattr(params,'items'):pairs=list(params.items())
 elif isinstance(params,(list,tuple)):
  if any(not isinstance(p,(list,tuple)) or len(p)!=2 for p in params):raise ValueError('INVALID_FORM_PARAMETER_PAIR')
  pairs=[tuple(p) for p in params]
 else:raise ValueError('INVALID_FORM_PARAMETERS')
 return urllib.parse.urlencode(pairs).encode()

def request(url,params=None):
 data=request_data(params)
 req=urllib.request.Request(url,data=data,headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'identity','Referer':'https://mopsfin.twse.com.tw/'})
 with urllib.request.urlopen(req,timeout=18) as r:
  raw=r.read(32000001)
  if len(raw)>32000000:raise ValueError('RESPONSE_LIMIT')
  return raw

class Audit:
 def __init__(self,year,repair):
  self.year=year;self.repair=repair;self.d=Drive(service());self.yroot=self.d.folder(ROOT,str(year))
  self.report=self.d.folder(REPORT_ROOT,PASS);self.ctrl=self.d.folder(self.report,str(year))
  self.report_ids={};self.circuit=collections.Counter();self.requests=collections.Counter();self.output=[]
  self.cover={};self.codes=set();self.audit=[];self.folders={};self.financial={};self.finmind_queue=[]
  self.started=time.monotonic()
 def folder(self,source,month):
  k=(source,month)
  if k not in self.folders:self.folders[k]=self.d.folder(self.d.folder(self.yroot,source),month)
  return self.folders[k]
 def accept(self,source,name,raw,meta,location,month):
  expected=meta.get('sha256') if isinstance(meta,dict) else None
  if expected and sha(raw)!=expected:raise ValueError('MANIFEST_HASH_MISMATCH')
  cat=category(meta.get('fulfills_name') or meta.get('name') or name,source)
  if not cat:
   if source=='MOPS':self.financial_payload(raw,name,location)
   return False
  period=meta.get('date') or meta.get('effective_date')
  if not period and source in DAILY and cat in [c for c,_,_ in DAILY[source]]:
   try:period=actual_date(json.loads(raw.decode('utf-8-sig')))
   except (ValueError,UnicodeDecodeError):pass
  if not period:period=month
  # File name/date metadata is only an expected contract; payload must prove it.
  named=re.findall(r'(?<!\d)(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)',name)
  if named and len(period)==10:
   claimed='-'.join(named[-1])
   if claimed!=period:raise ValueError('FILENAME_PAYLOAD_DATE_MISMATCH')
  if not period.startswith(month):raise ValueError('CROSS_MONTH_CONTENT')
  stats=validate(raw,source,cat,period);self.codes.update(stats['codes'])
  self.cover[(source,cat,period)]={'location':location,'sha256':sha(raw),'rows':stats['rows']}
  return True
 def financial_payload(self,raw,name,location):
  # Only aligned historical MOPS comparative statements count as partial numeric coverage.
  if not any(r in name for r in ('IncomeStatement','BalanceSheet','CashflowStatement')):return
  try:s=raw.decode('utf8')
  except UnicodeDecodeError:return
  ns=re.findall(r'name="reportName"\s+value="([^"]*)"',s)
  qs=re.findall(r'name="yearseason"\s+value="([^"]*)"',s)
  if not ns or not qs:return
  periods={re.sub(r'Q','',x) for x in qs}
  if len(periods)!=1:return
  per=next(iter(periods))
  if not re.fullmatch(str(self.year)+r'[1-4]',per):return
  report=next(r for r in ('IncomeStatement','BalanceSheet','CashflowStatement') if r in name)
  body=s.split('id="bodyTable"',1)[-1]
  body=body.split('<tbody>',1)[-1].split('</tbody>',1)[0]
  rows=[]
  for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',body,re.S):
   cells=[html.unescape(re.sub('<[^>]+>','',x)).strip() for x in re.findall(r'<td\b[^>]*>(.*?)</td>',tr,re.S)]
   if cells:rows.append(cells)
  if not rows or any(len(r)!=len(ns) for r in rows):return
  for i,n in enumerate(ns):
   code=n.split(' ')[0]
   if re.fullmatch(r'[1-9]\d{3}',code) and any(re.fullmatch(r'[-+]?[0-9,]+(?:\.[0-9]+)?',r[i]) for r in rows):
    self.financial[(code,report,per)]={'location':location,'sha256':sha(raw),'coverage':'PARTIAL_NUMERIC_CELLS_ONLY'}
 def scan(self,source,month):
  folder=self.folder(source,month);files=[f for f in listing(self.d,folder) if f['mimeType']!='application/vnd.google-apps.folder']
  receipts={}
  for f in files:
   if f['name'].endswith('.receipt.json'):
    try:receipts[f['name'][:-13]]=json.loads(read(self.d,f))
    except Exception:pass
  for f in files:
   name=f['name']
   if name.endswith('.receipt.json'):continue
   evidence={'source':source,'month':month,'file':name,'file_id':f['id'],'bytes':int(f.get('size',0)),'status':'UNASSESSED','accepted_units':0}
   try:
    if evidence['bytes']>350000000:raise ValueError('ARCHIVE_REQUIRES_SEPARATE_LARGE_FILE_PASS')
    b=read(self.d,f);evidence['sha256']=sha(b)
    if name.lower().endswith('.zip'):
     with zipfile.ZipFile(io.BytesIO(b)) as z:
      if sum(i.file_size for i in z.infolist())>1200000000:raise ValueError('UNCOMPRESSED_SIZE_LIMIT')
      bad=z.testzip()
      if bad:raise ValueError('ZIP_CRC:'+bad)
      evidence['zip_crc']='PASS';manifest={}
      for n in z.namelist():
       if n.endswith('manifest.json'):
        try:
         m=json.loads(z.read(n));units=m.get('units',[]) if isinstance(m,dict) else []
         for u in units:
          if isinstance(u,dict) and u.get('file'):manifest[u['file'].rsplit('/',1)[-1]]=u
        except Exception:pass
      failures=[]
      for n in z.namelist():
       if n.endswith('/') or n.endswith('manifest.json') or '/receipts/' in n or n.endswith('.receipt.json'):continue
       if not n.lower().endswith(('.raw','.json','.html','.csv')):continue
       raw=z.read(n);meta=manifest.get(n.rsplit('/',1)[-1],{})
       try:evidence['accepted_units']+=self.accept(source,n,raw,meta,name+':'+n,month)
       except Exception as e:
        failures.append({'member':n,'error':str(e)[:180]})
      evidence['content_holds']=failures;evidence['status']='STORAGE_VERIFIED_CONTENT_AUDITED'
    elif name.endswith(('.json','.html','.raw','.csv')):
     evidence['accepted_units']=int(self.accept(source,name,b,receipts.get(name,{}),name,month))
     evidence['status']='CONTENT_AUDITED'
    else:evidence['status']='NON_RAW_ATTACHMENT_NOT_PARSED'
   except Exception as e:evidence.update(status='AUDIT_HOLD',error=type(e).__name__+':'+str(e)[:200])
   self.audit.append(evidence)
  emit({'phase':'SCAN','year':self.year,'month':month,'source':source,'files':len(files),'verified_units':len(self.cover)})
 def calendar(self):
  url='https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?'+urllib.parse.urlencode({'response':'json','queryYear':self.year})
  info={'url':url,'year':self.year,'verified':False,'closed':[]}
  try:
   self.requests['TWSE']+=1;b=request(url);x=json.loads(b);rows=x.get('data') or []
   closed=[r[0] for r in rows if isinstance(r,list) and len(r)>1 and normdate(r[0]) and str(r[0]).startswith(str(self.year)) and not any(k in str(r[1]) for k in ('開始交易','最後交易'))]
   if not closed or len(rows)<8:raise ValueError('CALENDAR_YEAR_NOT_PROVEN')
   info.update(verified=True,closed=closed,sha256=sha(b));self.d.put(self.ctrl,'official_calendar.json',b,'application/json',overwrite=False)
  except Exception as e:info['error']=str(e)[:180]
  putj(self.d,self.ctrl,'calendar_validation.json',info);return set(info['closed'])
 def jobs(self,month,closed):
  y,m=map(int,month.split('-'));out=[]
  end=min(dt.date(y,m,calendar.monthrange(y,m)[1]),TODAY)
  for day in range(1,end.day+1):
   date=dt.date(y,m,day)
   if date.weekday()>4 or date.isoformat() in closed:continue
   for source,ds in DAILY.items():
    for cat,path,extra in ds:
     datearg=date.strftime('%Y%m%d') if source=='TWSE' else date.strftime('%Y/%m/%d')
     base='https://www.twse.com.tw/' if source=='TWSE' else 'https://www.tpex.org.tw/www/zh-tw/'
     url=base+path+'?'+urllib.parse.urlencode(dict(date=datearg,response='json',**extra))
     out.append({'source':source,'category':cat,'period':date.isoformat(),'url':url,'month':month})
  for source,events in EVENTS.items():
   fmt=lambda d:d.strftime('%Y%m%d') if source=='TWSE' else d.strftime('%Y/%m/%d')
   for cat,base in events:
    out.append({'source':source,'category':cat,'period':month,'month':month,'url':base+'?'+urllib.parse.urlencode({'startDate':fmt(dt.date(y,m,1)),'endDate':fmt(end),'response':'json'})})
  # Only complete previous revenue months are due; current month is NOT missing.
  if (y,m)<(TODAY.year,TODAY.month):
   for market in ('sii','otc'):
    for part in (0,1):
     out.append({'source':'MOPS','category':f'revenue_{market}_{part}','period':month,'month':month,'url':f'https://mopsov.twse.com.tw/nas/t21/{market}/t21sc03_{y-1911}_{m}_{part}.html'})
  return out
 def save(self,j,raw,stats):
  source=j['source'];folder=self.folder(source,j['month']);digest=sha(raw)
  ext='html' if source=='MOPS' and j['category'].startswith('revenue_') else 'json'
  name=f"{PASS}_{j['category']}_{j['period']}_{digest[:12]}.{ext}"
  receipt=dict(j,sha256=digest,bytes=len(raw),rows=stats.get('rows'),saved_at_utc=stamp(),validation='CONTENT_DATE_STRUCTURE_AND_REMOTE_SHA',numeric_verified=False,pit_verified=False,legacy_import=False)
  member=j['category']+'_'+j['period']+'.'+ext
  meta=dict(receipt,file=member,name=j['category']+'_'+j['period'])
  if len(j['period'])==10:meta['date']=j['period']
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
   z.writestr(member,raw);z.writestr('manifest.json',json.dumps({'source':source,'month':j['month'],'units':[meta]},ensure_ascii=False))
  archive=buf.getvalue()
  with zipfile.ZipFile(io.BytesIO(archive)) as z:
   if z.testzip():raise ValueError('NEW_ARCHIVE_CRC_FAILED')
  name=name.rsplit('.',1)[0]+'.zip'
  # Raw and receipt are committed atomically in one ZIP; original API bytes unchanged.
  self.d.put(folder,name,archive,'application/zip',overwrite=False)
  self.output.append(dict(receipt,file=name));self.codes.update(stats.get('codes',[]))
  self.cover[(source,j['category'],j['period'])]={'location':name+':'+member,'sha256':digest,'rows':stats.get('rows')}
  return name
 def repair_unit(self,j):
  e=dict(j,status='MISSING',attempts=0,numeric_verified=False,pit_verified=False)
  key=(j['source'],j['category'],j['period'])
  if key in self.cover:e.update(status='EXISTING_PAYLOAD_VERIFIED',evidence=self.cover[key]);return e
  if not self.repair:return e
  scope=(j['source'],j['category'])
  if self.circuit[scope]>=2:e['status']='SYSTEMIC_SOURCE_HOLD';return e
  if time.monotonic()-self.started>85*60:e['status']='TIME_BUDGET_DEFERRED';return e
  try:
   self.requests[j['source']]+=1;e['attempts']=1;raw=request(j['url'])
   stats=validate(raw,j['source'],j['category'],j['period'])
   e.update(status='REPAIRED_REMOTE_READBACK_VERIFIED',file=self.save(j,raw,stats),rows=stats['rows'])
   self.circuit[scope]=0
  except Exception as exc:
   error=type(exc).__name__+':'+str(exc)[:200]
   e.update(status='DEFERRED_GAP',error=error)
   # No-data on a holiday is a date-level ambiguity, not an endpoint outage.
   if not any(x in error for x in ('EMPTY_RESPONSE','EMPTY_EVENT','沒有符合條件','查無資料')):self.circuit[scope]+=1
  time.sleep(.3);return e
 def run(self):
  closed=self.calendar();months=[];alljobs=[]
  for m in range(1,13):
   if (self.year,m)>(TODAY.year,TODAY.month):continue
   month=f'{self.year}-{m:02d}'
   for source in ('TWSE','TPEx','MOPS'):self.scan(source,month)
   jobs=self.jobs(month,closed);results=[]
   for n,j in enumerate(jobs,1):
    e=self.repair_unit(j);results.append(e)
    if n%50==0:emit({'phase':'OFFICIAL_REPAIR','year':self.year,'month':month,'done':n,'total':len(jobs),'last':e['status']})
    if n%20==0:putj(self.d,self.ctrl,month+'_checkpoint.json',{'done':n,'total':len(jobs),'results':results})
   report={'year':self.year,'month':month,'expected_units':len(jobs),'counts':dict(collections.Counter(e['status'] for e in results)),'units':results,'all_market_complete':False,'numeric_verified':False,'pit_verified':False}
   putj(self.d,self.ctrl,month+'_result.json',report);months.append(report);alljobs.extend(results)
   putj(self.d,self.ctrl,'file_integrity_audit.json',self.audit)
   emit({'phase':'MONTH_SAVED','year':self.year,'month':month,'counts':report['counts']})
  # Explicit residual financial completeness queue, separate from daily table counts.
  financial=[]
  latestq=4 if self.year<TODAY.year else max(0,(TODAY.month-1)//3-1)
  # October has two fully published historical quarters; Q3 remains not-yet-due.
  if self.year==TODAY.year and TODAY.month>=10:latestq=2
  for q in range(1,latestq+1):
   per=str(self.year)+str(q)
   for report in ('IncomeStatement','BalanceSheet','CashflowStatement'):
    missing=[c for c in sorted(self.codes) if (c,report,per) not in self.financial]
    # Source failure circuit is shared across quarters to avoid repeated blocked requests.
    for k in range(0,len(missing),20):
     codes=missing[k:k+20];e={'source':'MOPS','report':report,'period':per,'codes':codes,'status':'MISSING_FINANCIAL_PARTIAL_NUMERICS','attempts':0}
     scope=('MOPS_FINANCIAL',report)
     if self.repair and self.circuit[scope]<2 and time.monotonic()-self.started<100*60:
      try:
       params=[('compareItem',report),('quarter','false'),('ylabel',{'CashflowStatement':'現金流量表(累計)','IncomeStatement':'綜合損益表(累計)','BalanceSheet':'資產負債表'}[report]),('ys',per),('revenue','false'),('bcodeAvg','false'),('companyAvg','false'),('qnumber','')]+[('companyId',c) for c in codes]
       self.requests['MOPS']+=1;e['attempts']=1;b=request('https://mopsfin.twse.com.tw/compare/report',params)
       before=set(self.financial);self.financial_payload(b,report+'_'+per,'new request')
       added=[c for c in codes if (c,report,per) in self.financial and (c,report,per) not in before]
       if not added:raise ValueError('NO_EXPLICIT_PERIOD_COMPANY_NUMERIC_COVERAGE')
       qmonth=f'{self.year}-{q*3:02d}';folder=self.folder('MOPS',qmonth);name=f'{PASS}_{report}_{per}_{sha(b)[:12]}.raw'
       self.d.put(folder,name,b,'text/html',overwrite=False)
       self.d.put(folder,name+'.receipt.json',json.dumps(dict(source='MOPS',report=report,period=per,requested_codes=codes,covered_codes=added,sha256=sha(b),bytes=len(b),numeric_verified=False,pit_verified=False,url='https://mopsfin.twse.com.tw/compare/report',params=params),ensure_ascii=False).encode(),'application/json',overwrite=False)
       e.update(status='FINANCIAL_PARTIAL_CELLS_SAVED',covered_codes=added,file=name);self.circuit[scope]=0
      except Exception as exc:self.circuit[scope]+=1;e.update(status='FINANCIAL_SOURCE_HOLD',error=str(exc)[:200])
     financial.append(e)
  putj(self.d,self.ctrl,'financial_gap_groups.json',financial)
  result={'pass':PASS,'year':self.year,'generated_utc':stamp(),'elapsed_seconds':round(time.monotonic()-self.started,2),'months_checked':len(months),'core_counts':dict(collections.Counter(e['status'] for e in alljobs)),'expected_core_units':len(alljobs),'source_requests':dict(self.requests),'new_core_files':len(self.output),'new_core_bytes':sum(x['bytes'] for x in self.output),'archives_and_files_audited':len(self.audit),'audit_file_holds':sum(e['status']=='AUDIT_HOLD' for e in self.audit),'financial_group_counts':dict(collections.Counter(e['status'] for e in financial)),'financial_company_universe_count':len(self.codes),'financial_universe_status':'PROVISIONAL_FOUR_DIGIT_IDS_NOT_APPROVED_ORDINARY_STOCK_UNIVERSE','full_market_complete':False,'numeric_verified':False,'pit_verified':False,'production_gate':'BLOCKED','report_folder_id':self.ctrl,'remaining_core_units':[e for e in alljobs if e['status'] not in ('EXISTING_PAYLOAD_VERIFIED','REPAIRED_REMOTE_READBACK_VERIFIED')],'finmind_status':'NOT_RUN_YET_OFFICIAL_AUDIT_MUST_FINISH_FIRST'}
  putj(self.d,self.ctrl,'year_summary.json',result);Path('run_reports').mkdir(exist_ok=True);Path(f'run_reports/{self.year}_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));emit({k:v for k,v in result.items() if k!='remaining_core_units'})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--year',required=True,type=int,choices=[2024,2025,2026]);p.add_argument('--repair',action='store_true');a=p.parse_args();Audit(a.year,a.repair).run()
