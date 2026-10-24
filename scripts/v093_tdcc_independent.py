"""Independent TDCC capture: official catalog snapshots and published weekly history."""
import argparse,datetime as dt,hashlib,http.cookiejar,json,os,re,time,urllib.request,urllib.parse,urllib.error
from html.parser import HTMLParser
ROOT='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'
REPORT='1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
SPEC='https://openapi.tdcc.com.tw/tdcc-opendata-api-docs'
QUERY='https://www.tdcc.com.tw/portal/zh/smWeb/qryStock'
REPAIR_REVISION='TDCC_HISTORY_RESTART_SUCCESS_RECEIPTS_V3'
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
class Tables(HTMLParser):
 def __init__(self):super().__init__();self.tables=[];self.table=None;self.row=None;self.cell=None
 def handle_starttag(self,t,a):
  if t=='table':self.table=[]
  elif t=='tr' and self.table is not None:self.row=[]
  elif t in ('td','th') and self.row is not None:self.cell=[]
 def handle_data(self,s):
  if self.cell is not None:self.cell.append(s)
 def handle_endtag(self,t):
  if t in ('td','th') and self.cell is not None:self.row.append(''.join(self.cell).strip());self.cell=None
  elif t=='tr' and self.row is not None:
   if self.row:self.table.append(self.row)
   self.row=None
  elif t=='table' and self.table is not None:self.tables.append(self.table);self.table=None

def dates_in_rows(rows):
 dates=[]
 for r in rows:
  for k,v in r.items():
   if not any(x in k for x in ('日期','年月','年度','date','Date')):continue
   s=str(v).strip();m=re.fullmatch(r'(\d{3,4})[-/]?(\d{2})(?:[-/]?(\d{2}))?',s)
   if not m:continue
   y=int(m[1]);y=y+1911 if y<1911 else y
   try:d=dt.date(y,int(m[2]),int(m[3] or 1))
   except ValueError:continue
   dates.append(d.isoformat())
 return dict(min=min(dates) if dates else None,max=max(dates) if dates else None)
def distribution_json(rows):
 if not rows:raise ValueError('EMPTY_NOT_PROOF_OF_NO_DATA')
 for r in rows:
  if not all(any(k.lstrip('\ufeff')==x for k in r) for x in ('資料日期','證券代號','持股分級','股數','人數')):raise ValueError('DISTRIBUTION_SCHEMA')
  for k,v in r.items():
   if k in ('股數','人數') and (not str(v).replace(',','').isdigit()):raise ValueError('DISTRIBUTION_NONNEGATIVE_INTEGER')
 return True

def validate_history(raw,date,code):
 s=raw.decode('utf-8-sig');p=Tables();p.feed(s)
 candidates=[t for t in p.tables if any(('持股分級' in ''.join(r) or '持股/單位數分級' in ''.join(r)) and '股數' in ''.join(r) for r in t)]
 if not candidates:raise ValueError('HISTORICAL_DISTRIBUTION_TABLE_MISSING')
 # Date must be in rendered result, not merely an echoed dropdown option.
 body=s[s.find('</form>')+7:]
 flat=re.sub('<[^>]*>',' ',body);digits=re.sub(r'\s','',flat)
 if not any(x in digits for x in (date,date[:4]+'/'+date[4:6]+'/'+date[6:],date[:4]+'年'+date[4:6]+'月'+date[6:],str(int(date[:4])-1911)+'年'+date[4:6]+'月'+date[6:])):raise ValueError('HISTORY_RESULT_DATE_NOT_CONFIRMED')
 if not re.search(r'證券代號[：:]\s*'+re.escape(code)+r'(?![0-9A-Za-z])',flat):raise ValueError('HISTORY_RESULT_CODE_NOT_CONFIRMED')
 rows=candidates[0]
 if len(rows)<10:raise ValueError('HISTORY_ROWS_INCOMPLETE')
 return len(rows)-1
def history_summary(date,codes,receipts):
 expected={date+'|'+code for code in codes}
 saved={key for key in expected if receipts.get(key,{}).get('status')=='SAVED_BASIC_VERIFIED'
        and receipts[key].get('file_id') and receipts[key].get('sha256')
        and receipts[key].get('remote_readback_hash_verified') is True}
 return dict(expected_candidates=len(expected),saved=len(saved),unresolved=len(expected-saved),
             candidate_set_complete=bool(expected) and expected==saved,
             historical_universe_complete=False)

def migrate_history(state):
 if state.get('history_completion_revision')==REPAIR_REVISION:return False
 state.setdefault('history_checkpoint_backups',[]).append(dict(revision=state.get('history_completion_revision'),completed_dates=state.get('completed_dates',[]),visited_dates=state.get('visited_dates',[]),captured_utc=stamp()))
 state.update(completed_dates=[],visited_dates=[],history_date_results={},history_completion_revision=REPAIR_REVISION,status='RESTART_NEWEST_OFFICIAL_DATE')
 return True

class Worker:
 def __init__(self,minutes):
  from scripts.annual_actual_firstpass import Drive,service
  self.d=Drive(service());self.d.direct_readback=True
  self.ctrl=self.d.folder(REPORT,'TDCC_INDEPENDENT_STAGE05')
  raw=self.d.read(self.ctrl,'CURSOR.json');self.state=json.loads(raw) if raw else {'revision':'TDCC_INDEPENDENT_V1','receipts':{},'history_receipts':{},'history_date_index':0,'history_code_index':0}
  self.state.setdefault('history_receipts',{})
  self.until=time.monotonic()+minutes*60;self.started=stamp();self.requests=0;self.saved=0;self.skipped=0;self.folders={}
  self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def save(self):
  self.state.update(updated_utc=stamp(),sources=['TDCC'],finmind_enabled=False,coverage_certified=False,numeric_verified=False,pit_verified=False)
  
  history=self.state.get('history_receipts',{})
  if self.state.get('history_receipt_date'):
   self.d.put(self.ctrl,'HISTORY_'+self.state['history_receipt_date']+'.json',json.dumps(history,ensure_ascii=False).encode(),'application/json',overwrite=True)
  cursor={k:v for k,v in self.state.items() if k!='history_receipts'}
  self.d.put(self.ctrl,'CURSOR.json',json.dumps(cursor,ensure_ascii=False).encode(),'application/json',overwrite=True)
 def request(self,url,data=None):
  host=urllib.parse.urlparse(url).hostname
  if host not in ('www.tdcc.com.tw','openapi.tdcc.com.tw'):raise ValueError('NON_OFFICIAL_SOURCE')
  time.sleep(1)
  self.requests+=1
  req=urllib.request.Request(url,data=data,headers={'User-Agent':'Mozilla/5.0 JARVIS-TDCC/1.0','Accept':'application/json,text/html','Referer':QUERY})
  with self.opener.open(req,timeout=22) as r:
   b=r.read(80000001)
  if len(b)>80000000:raise ValueError('RESPONSE_LIMIT')
  return b
 def target(self,month):
  if month not in self.folders:self.folders[month]=self.d.folder(self.d.folder(self.d.folder(ROOT,month[:4]),'TDCC'),month)
  return self.folders[month]
 def persist(self,raw,label,month,ext):
  name=label+'_'+sha(raw)+'.'+ext;parent=self.target(month)
  self.d.put(parent,name,raw,'application/json' if ext=='json' else 'text/html',overwrite=False)
  f=self.d.find(parent,name)
  readback=self.d.call(lambda:self.d.api.files().get_media(fileId=f['id']))
  if sha(readback)!=sha(raw):raise ValueError('TDCC_REMOTE_READBACK_SHA_MISMATCH')
  self.saved+=1
  return dict(file_id=f['id'],sha256=sha(raw),bytes=len(raw),remote_readback_hash_verified=True)
 def process(self,key,url,label,kind='json',date=None,code=None):
  bucket=self.state['history_receipts'] if date else self.state['receipts'];old=bucket.get(key,{})
  if old.get('status')=='SAVED_BASIC_VERIFIED':self.skipped+=1;return True
  if old.get('repair_revision')!=REPAIR_REVISION:
   old=dict(old,prior_error=old.get('error'),prior_attempts=old.get('attempts'),attempts=0,repair_revision=REPAIR_REVISION)
  if old.get('attempts',0)>=3:self.skipped+=1;return True
  start=time.monotonic()
  for attempt in range(old.get('attempts',0),3):
   if time.monotonic()>self.until-35 or time.monotonic()-start>65:return False
   e=dict(old,status='REQUEST_INTENT',attempts=attempt+1,url=url,date=date,code=code,title=label);bucket[key]=e;self.save()
   raw=None
   try:
    if date:
     page=self.request(QUERY).decode('utf-8-sig')
     fields=dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"',page))
     fields.update(scaDate=date,sqlMethod='StockNo',stockNo=code,stockName='')
     raw=self.request(QUERY,urllib.parse.urlencode(fields).encode());count=validate_history(raw,date,code)
     month=date[:4]+'-'+date[4:6];period={'min':date,'max':date}
    else:
     raw=self.request(url);rows=json.loads(raw.decode('utf-8-sig'))
     if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('NOT_NATIVE_ROW_ARRAY')
     if not rows:raise ValueError('EMPTY_NOT_PROOF_OF_NO_DATA')
     if url.endswith('/1-5'):distribution_json(rows)
     count=len(rows);period=dates_in_rows(rows)
     month=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime('%Y-%m')
     if url.endswith('/1-5'):
      self.state['bulk_distribution_date']=period.get('max','')
      self.state['distribution_codes']=sorted({str(r.get('證券代號','')).strip() for r in rows if re.fullmatch('[0-9A-Za-z]{4,8}',str(r.get('證券代號','')).strip())})
    evidence=self.persist(raw,label,month,'html' if date else 'json')
    e.pop('error',None)
    e.update(evidence,status='SAVED_BASIC_VERIFIED',rows=count,content_period=period,captured_utc=stamp(),period_semantics='SOURCE_RESPONSE_RANGE_NOT_REQUESTED_MONTH',numeric_verified=False,pit_verified=False)
    bucket[key]=e;self.save();print(json.dumps({'key':key,'status':e['status'],'rows':count,'range':period}),flush=True);return True
   except Exception as exc:
    
    if raw is not None:
     qname='UNRESOLVED_'+sha(raw)+'.raw'
     self.d.put(self.ctrl,qname,raw,'application/octet-stream',overwrite=False)
     e['quarantine_file']=qname;e['response_sha256']=sha(raw)
    e.update(error_class='SOURCE_EMPTY_UNCONFIRMED' if 'EMPTY_NOT_PROOF' in str(exc) else ('SOURCE_BACKOFF' if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429) else 'DOWNLOAD_OR_PARSER_ERROR'),status='UNRESOLVED',error=type(exc).__name__+':'+str(exc)[:220]);bucket[key]=e;self.save()
    if isinstance(exc,urllib.error.HTTPError) and exc.code in (403,429):
     self.state['resume_after_epoch']=time.time()+900;self.save();return False
    if isinstance(exc,ValueError):e['attempts']=3;bucket[key]=e;self.save();return True
  return True
 def run(self):
  if self.state.get('resume_after_epoch',0)>time.time():return
  # Probe catalogs once per day; endpoint receipts deduplicate successful snapshots.
  today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat()
  spec=json.loads(self.request(SPEC));self.d.put(self.ctrl,'OPENAPI_SPEC_'+sha(json.dumps(spec,sort_keys=True).encode())+'.json',json.dumps(spec,ensure_ascii=False).encode(),'application/json',overwrite=False)
  page=self.request(QUERY);text=page.decode('utf-8-sig');dates=sorted(set(re.findall(r'<option\s+value="(20\d{6})"',text)),reverse=True)
  dates=[d for d in dates if '20000101'<=d<=today.replace('-','')]
  self.state['availability']={'weekly_distribution_dates':dates,'earliest':min(dates) if dates else None,'latest':max(dates) if dates else None,'official_retention':'ONE_YEAR_FOR_WEEKLY_DISTRIBUTION','requested_floor':'2000-01-01','outside_retention':'NOT_AVAILABLE_THROUGH_THIS_OFFICIAL_QUERY_NOT_DOWNLOADED','other_endpoints':'NO_DATE_PARAMETERS_IN_OPENAPI_CAPTURE_ALL_RETURNED_ROWS_AND_REPORT_ACTUAL_RANGE','checked_utc':stamp()}
  self.d.put(self.ctrl,'DATE_OPTIONS_'+sha(page)+'.html',page,'text/html',overwrite=False);self.save()
  priority=['/v1/opendata/1-5','/v1/opendata/1-1','/v1/opendata/1-4']
  paths=sorted(spec['paths'],key=lambda p:(priority.index(p) if p in priority else 9,p))
  for path in paths:
   if time.monotonic()>self.until-40:break
   if not re.fullmatch('/v1/opendata/[0-9]+-[0-9]+(?:-[0-9]+)?',path):continue
   title=spec['paths'][path].get('get',{}).get('summary',path)
   if not self.process(today+'|'+path,'https://openapi.tdcc.com.tw'+path,path.rsplit('/',1)[-1]):break
  else:self.state['snapshot_catalog_completed_date']=today
  # Weekly jobs are bounded by the source's real date menu, never manufactured dates.
  codes=self.state.get('distribution_codes',[])
  if not codes:
   receipts=[r for k,r in self.state['receipts'].items() if k.endswith('/1-5') and r.get('file_id') and r.get('status')=='SAVED_BASIC_VERIFIED']
   if receipts:
    saved=max(receipts,key=lambda r:r.get('captured_utc',''))
    native=self.d.call(lambda:self.d.api.files().get_media(fileId=saved['file_id']))
    if sha(native)!=saved['sha256']:raise ValueError('UNIVERSE_RAW_HASH_MISMATCH')
    native=json.loads(native.decode('utf-8-sig'))
    codes=sorted({str(r.get('證券代號','')).strip() for r in native if re.fullmatch('[0-9A-Za-z]{4,8}',str(r.get('證券代號','')).strip())})
    self.state.update(distribution_codes=codes,completed_dates=[],universe_padding_migration='STRIP_SOURCE_PADDING_V2');self.save()
  if not codes:raise ValueError('NO_HISTORICAL_CANDIDATES_NOT_COMPLETE')
  if migrate_history(self.state):self.save()
  for date in dates:
   if time.time()<self.state.get('resume_after_epoch',0):break
   if date in self.state.get('visited_dates',[]):continue
   if date==str(self.state.get('bulk_distribution_date','')).replace('-',''):
    self.state.setdefault('visited_dates',[]).append(date)
    self.state.setdefault('history_date_results',{})[date]=dict(status='BULK_SNAPSHOT_SAVED',historical_universe_complete=False)
    self.save();continue
   if self.state.get('history_receipt_date')!=date:
    self.state['history_receipt_date']=date
    previous=self.d.read(self.ctrl,'HISTORY_'+date+'.json')
    self.state['history_receipts']=json.loads(previous) if previous else {}
   ordered=sorted(codes,key=lambda c:(c not in ('2330','2317','0050'),c))
   for code in ordered:
    if time.monotonic()>self.until-45:break
    self.state.update(active_date=date,active_code=code,status='HISTORICAL_DOWNLOAD')
    if not self.process(date+'|'+code,QUERY,'distribution_'+date+'_'+code,'html',date,code):break
   else:
    summary=history_summary(date,codes,self.state['history_receipts'])
    self.state.setdefault('history_date_results',{})[date]=summary
    self.state.setdefault('visited_dates',[]).append(date)
    if summary['candidate_set_complete']:self.state.setdefault('completed_dates',[]).append(date)
    self.save();continue
   break
  else:self.state['status']='AVAILABLE_HISTORY_VISITED_WITH_UNRESOLVED_ITEMS'
  self.save()
  report=dict(status=self.state.get('status','CATALOG_CAPTURE'),active_date=self.state.get('active_date'),active_code=self.state.get('active_code'),availability=self.state.get('availability'),source_requests_this_run=self.requests,saved_this_run=self.saved,skipped_this_run=self.skipped,snapshot_saved=sum(r.get('status')=='SAVED_BASIC_VERIFIED' for r in self.state['receipts'].values()),history_saved=sum(r.get('saved',0) for date,r in self.state.get('history_date_results',{}).items() if date!=self.state.get('history_receipt_date'))+sum(r.get('status')=='SAVED_BASIC_VERIFIED' for r in self.state['history_receipts'].values()),history_saved_scope='RECONCILED_DATE_RECEIPTS_ONLY',pending_history_dates=[d for d,r in self.state.get('history_date_results',{}).items() if r.get('unresolved',0)],unresolved=sum(r.get('status')!='SAVED_BASIC_VERIFIED' for b in ('receipts','history_receipts') for r in self.state[b].values()),scope='ALL_OFFICIAL_OPENAPI_DATASETS_PLUS_WEEKLY_CURRENT_DISTRIBUTION_SECURITY_CANDIDATES',historical_universe_complete=False,coverage_certified=False,numeric_verified=False,pit_verified=False,started_utc=self.started,updated_utc=stamp(),run_id=os.environ.get('GITHUB_RUN_ID'))
  self.d.put(self.ctrl,'STATUS.json',json.dumps(report,ensure_ascii=False).encode(),'application/json',overwrite=True);print(json.dumps(report,ensure_ascii=False),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=45);a=p.parse_args()
 if not 1<=a.minutes<=50:raise ValueError('INVALID_RUNTIME')
 Worker(a.minutes).run()
if __name__=='__main__':main()
