"""Second-stage official calendar checks and bounded re-query of proven empty RAW.

Unavailable calendars, unproved legacy routes and uncertain requests stay open.
Neither a weekday nor absence from an annual holiday table proves trading.
"""
import argparse,collections,copy,datetime as dt,hashlib,html,json,os,re,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_state_pages import unpack,SCHEMA
from scripts.v093_source_rate import reserve
from scripts.v093_source_executor import Executor,ApplicabilityUnproven
from scripts.v093_source_adapters import NativeAdapter,RAW_ROOT
from scripts.v093_admission_runtime import load_release
from scripts.v093_problem_recovery import load_rows,PLAN as ORIGINAL_PLAN

PLAN='config/v093_official_followup_20261031.json'
NAMESPACE='official-followup-20261031-v2'
HOSTS={'TWSE':{'www.twse.com.tw'},'TPEx':{'www.tpex.org.tw','hist.tpex.org.tw'}}

def sha(raw):return hashlib.sha256(raw).hexdigest()

def read_pin(store,commit):
 if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('FOLLOWUP_PIN')
 if store.git('cat-file','-e',commit+':state.json',check=False).returncode:store.git('fetch','--no-tags','--no-write-fetch-head','origin',commit)
 raw=store.git('show',commit+':state.json').stdout;obj=json.loads(raw)
 return unpack(raw,lambda name:store.git('show',commit+':'+name).stdout) if obj.get('schema')==SCHEMA else obj

def calendar(raw,year,url):
 obj=json.loads(raw.decode('utf-8-sig'))
 if obj.get('stat')!='ok' or not isinstance(obj.get('data'),list) or not obj['data']:raise ValueError('CALENDAR_SCHEMA')
 scopes=[]
 if str(obj.get('queryYear','')).isdigit():
  value=int(obj['queryYear']);scopes.append(value+1911 if value<1911 else value)
 if re.fullmatch(r'20\d{6}',str(obj.get('date',''))):scopes.append(int(obj['date'][:4]))
 title=re.search(r'(\d{3,4})\s*年',obj.get('title',''))
 if title:
  value=int(title[1]);scopes.append(value+1911 if value<1911 else value)
 if not scopes or any(y!=year for y in scopes):raise ValueError('CALENDAR_REQUESTED_YEAR_UNPROVEN')
 closed=[];opened=[];unknown=[]
 for row in obj['data']:
  if not isinstance(row,list) or len(row)<2:raise ValueError('CALENDAR_ROW')
  day=dt.date.fromisoformat(str(row[0]));label=html.unescape(re.sub('<[^>]+>',' ',str(row[1])));description=html.unescape(re.sub('<[^>]+>',' ',' '.join(map(str,row[2:]))))
  if day.year!=year:raise ValueError('CALENDAR_ROW_YEAR_MISMATCH')
  # Last/new trading dates must take precedence over holiday words in notes.
  if any(s in label for s in ('開始交易','最後交易','開始買賣','最後買賣')):opened.append(day.isoformat())
  elif any(s in label+' '+description for s in ('休市','放假','市場無交易','不交易')):closed.append(day.isoformat())
  else:unknown.append(day.isoformat())
 if set(closed)&set(opened):raise ValueError('CALENDAR_CONFLICTING_DATE')
 return dict(year=year,url=url,raw_sha256=sha(raw),closed=sorted(set(closed)),opened=sorted(set(opened)),unclassified=sorted(set(unknown)),annual_table_is_not_complete_emergency_calendar=True)

def request(source,url):
 def allowed(value):
  parsed=urllib.parse.urlsplit(value)
  return parsed.scheme=='https' and parsed.hostname in HOSTS[source] and not parsed.username and not parsed.password
 if not allowed(url):raise ValueError('OFFICIAL_METADATA_HOST')
 class Redirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,req,fp,code,message,headers,newurl):
   if not allowed(newurl):raise ValueError('OFFICIAL_METADATA_REDIRECT')
   return super().redirect_request(req,fp,code,message,headers,newurl)
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 JARVIS official-source verification','Accept-Encoding':'identity'})
 with urllib.request.build_opener(Redirect()).open(req,timeout=25) as response:raw=response.read(200001)
 if len(raw)>200000:raise ValueError('OFFICIAL_METADATA_SIZE_LIMIT')
 return raw

def metadata(root,source,logical,url,state,store,checkpoint):
 """Persist source request intent before each public metadata GET, max four."""
 cache_key=sha(url.encode());cached=state.setdefault('tasks',{}).get(cache_key)
 if cached and cached.get('status')=='RESPONSE_SAVED':return cached
 c=Coordinator(GitCAS(root),source,ttl=600);key='FOLLOWUP_METADATA|'+logical
 _,shared=c.store.read(source);old=(shared or {}).get('tasks',{}).get(key)
 if (shared or {}).get('hold') or (shared or {}).get('cooldown_until',0)>c.clock():return dict(status='SOURCE_DEFERRED')
 count=state.setdefault('metadata_attempts',{}).get(logical,0)
 if count>=4:return dict(status='REQUEST_LIMIT')
 if old and old.get('followup_metadata')!=NAMESPACE:raise ValueError('METADATA_TASK_COLLISION')
 if old and old.get('owner') and old.get('expires',0)>c.clock():return dict(status='LEASE_DEFERRED')
 def seed(s):
  previous=s['tasks'].get(key,{})
  attempts=max(count,previous.get('attempts',0))
  s['tasks'][key]=dict(definition=dict(source=source,key=key,period=logical[:4]+'-01-01' if logical[:4].isdigit() else '2026-10-31',slot='DESC'),status='READY',attempts=attempts,fence=previous.get('fence',0),owner=None,followup_metadata=NAMESPACE)
 c.update(seed)
 _,shared=c.store.read(source);ticket=c.claim('DESC',NAMESPACE,exclude=set(shared['tasks'])-{key})
 if not ticket:return dict(status='REQUEST_LIMIT_OR_DEFERRED')
 result=None
 try:
  reserve(c,ticket,cost=1,limit=30,window=60,spacing=2);c.begin_request(ticket)
  raw=request(source,url);text=None;encoding=None
  for codec in ('utf-8','cp950','big5hkscs'):
   try:text=raw.decode(codec);encoding=codec;break
   except UnicodeDecodeError:pass
  if text is None:raise ValueError('OFFICIAL_METADATA_ENCODING')
  result=dict(status='RESPONSE_SAVED',url=url,raw_sha256=sha(raw),text=text,encoding=encoding,source=source)
 except Exception as exc:
  result=dict(status='REVIEW_REQUIRED',url=url,error=type(exc).__name__,http_status=getattr(exc,'code',None))
  if getattr(exc,'code',None) in (429,503):
   try:delay=max(60,float(exc.headers.get('Retry-After','60')))
   except (ValueError,TypeError,AttributeError):delay=60
   c.update(lambda s:s.update(cooldown_until=max(s.get('cooldown_until',0),c.clock()+delay)))
 finally:
  _,shared=c.store.read(source);current=shared['tasks'][key]
  state['metadata_attempts'][logical]=max(count,current['attempts']);state['tasks'][cache_key]=result or dict(status='INTERRUPTED')
  checkpoint()
  def complete(s):
   task=s['tasks'].get(key)
   if task and task.get('followup_metadata')==NAMESPACE and task.get('owner')==NAMESPACE:del s['tasks'][key]
  c.update(complete)
 return state['tasks'][cache_key]

def discover(text,url):
 """Collect only links actually present in official HTML; never invent an API."""
 scripts=[];forms=[];apis=[]
 for value in re.findall(r'<script[^>]+src=["\']([^"\']+)',text,re.I):
  link=urllib.parse.urljoin(url,html.unescape(value));p=urllib.parse.urlsplit(link)
  if p.scheme=='https' and p.hostname in HOSTS['TPEx']:scripts.append(link)
 for value in re.findall(r'<form[^>]+action=["\']([^"\']+)',text,re.I):forms.append(urllib.parse.urljoin(url,html.unescape(value)))
 for value in re.findall(r'["\']([^"\']*(?:/www/|/Hist/)[^"\'\s<>]*)["\']',text):
  link=urllib.parse.urljoin(url,html.unescape(value));p=urllib.parse.urlsplit(link)
  if p.scheme=='https' and p.hostname in HOSTS['TPEx']:apis.append(link)
 return dict(scripts=sorted(set(scripts)),forms=sorted(set(forms)),observed_routes=sorted(set(apis)),route_verified_for_download=False)

def run_calendars(root,config):
 store=GitCAS(root,'jarvis-source-preflight/'+NAMESPACE+'-metadata');revision,state=store.read('TWSE');state=state or dict(source='TWSE',tasks={},calendars={})
 def checkpoint():
  nonlocal revision
  if not store.cas('TWSE',revision,state):raise ValueError('CALENDAR_CHECKPOINT_CONFLICT')
  revision,_=store.read('TWSE')
 started=time.monotonic()
 for year in range(2000,2027):
  if str(year) in state['calendars']:continue
  if time.monotonic()-started>900:break
  for params in ({'response':'json','queryYear':year},{'response':'json','queryYear':year-1911},{'response':'json','date':str(year)+'0101'}):
   url='https://www.twse.com.tw/rwd/zh/holidaySchedule/holidaySchedule?'+urllib.parse.urlencode(params)
   result=metadata(root,'TWSE',str(year)+'|calendar',url,state,store,checkpoint)
   if result.get('status')!='RESPONSE_SAVED':continue
   try:proof=calendar(result['text'].encode(),year,url)
   except (ValueError,KeyError,TypeError):continue
   proof['raw_sha256']=result['raw_sha256'];state['calendars'][str(year)]=proof;checkpoint();break
  time.sleep(2)
 state['checked_at']=dt.datetime.now(dt.timezone.utc).isoformat();checkpoint()
 Path('results').mkdir(exist_ok=True);Path('results/official-calendars.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(verified_years=sorted(state['calendars']),metadata_attempts=state.get('metadata_attempts'),calendar_state_commit=revision)),flush=True)

def classify(prior,calendars,config):
 if prior.get('status')!='REVIEW_REQUIRED' or prior.get('reason')!='OFFICIAL_EMPTY_UNCONFIRMED':return None
 definition=prior['definition'];source=definition['source'];period=definition['period'];date=dt.date.fromisoformat(period)
 if source=='TPEx' and period>='2001-01-01' and date.weekday()==5:
  return dict(reason='NATIONAL_STOCK_MARKET_SATURDAY_CLOSED',url=config['national_weekend_evidence'],date=period)
 proof=calendars.get(period[:4])
 if proof and period in proof['closed']:
  return dict(reason='OFFICIAL_ANNUAL_NONTRADING_DATE',date=period,url=proof['url'],raw_sha256=proof['raw_sha256'],calendar_year=proof['year'])
 return None

def eligible(task,prior,calendars):
 source=task['definition']['source'];period=task['definition']['period'];case=task.get('execution_contract') or {}
 if prior.get('status')!='REVIEW_REQUIRED' or prior.get('reason')!='OFFICIAL_EMPTY_UNCONFIRMED' or prior['attempts']>=4:return False
 # A proved calendar allows a bounded query, not a claim that every unlisted
 # weekday traded. Emergency closures can still return an unresolved empty.
 if period[:4] not in calendars or dt.date.fromisoformat(period).weekday()>=5:return False
 if case.get('mode')=='RETAINED':
  if not case.get('reference') or prior.get('raw_sha256')!=case.get('sha256'):return False
 elif case.get('mode')=='MISSING':
  proof=prior.get('rejected_evidence') or {}
  if case.get('reference') or proof.get('readback_verified') is not True or proof.get('accepted_as_raw') is not False or proof.get('raw_sha256')!=prior.get('raw_sha256'):return False
 else:return False
 return source=='TWSE' and period>='2004-02-11' or source=='TPEx' and period>='2007-04-21'

class EmptyQueryAdapter(NativeAdapter):
 def read(self,reference):
  proof=self.case.get('repair_evidence') or {};evidence=proof.get('rejected_evidence') or {}
  if reference==proof.get('reference') and evidence.get('readback_verified') is True and evidence.get('raw_sha256')==proof.get('sha256'):
   from scripts.v093_problem_recovery import RecheckAdapter
   reader=object.__new__(RecheckAdapter);reader.d=self.d;reader.rejected=evidence;reader.raw_cache={};return reader.read_rejected()
  return super().read(reference)
 def verify_repair_needed(self):
  proof=self.case['repair_evidence'];raw=self.read(proof['reference'])
  if sha(raw)!=proof['sha256']:raise ApplicabilityUnproven('FOLLOWUP_ORIGINAL_CHANGED')
  try:self.validate(raw)
  except ApplicabilityUnproven as exc:
   if str(exc)=='OFFICIAL_EMPTY_UNCONFIRMED' and proof.get('empty_response_requery') is True:return
   raise
  raise ApplicabilityUnproven('FOLLOWUP_EXISTING_VALID_OR_NOT_EMPTY')

def repair_row(task,prior,calendar_proof):
 row=copy.deepcopy(task);case=row['execution_contract']
 if case['mode']=='RETAINED':
  old_ref=case['reference'];old_sha=case['sha256']
  case.update(mode='REPAIR',reference=None,sha256=None,repair_evidence=dict(source=case['source'],key=case['key'],period=case['period'],reference=old_ref,sha256=old_sha,download_approved=True,reason='NATIVE_CONTENT_REJECTED',official_evidence_id='CALENDAR:'+calendar_proof['raw_sha256'],empty_response_requery=True,query_is_not_availability_proof=True,calendar_evidence=calendar_proof,rejected_evidence=task.get('rejected_evidence')))
 elif case['mode']!='MISSING':raise ValueError('FOLLOWUP_REPAIR_MODE')
 row.update(attempts=prior['attempts'],status='READY',check_only=False,owner=None,followup_repair=NAMESPACE)
 for field in ('save_intent','raw_reference','raw_sha256','reused_existing'):row.pop(field,None)
 return row

def requery(root,source,task,prior,calendar_proof,drive):
 c=Coordinator(GitCAS(root),source,ttl=600);key=task['definition']['key'];_,shared=c.store.read(source);existing=(shared or {}).get('tasks',{}).get(key)
 if existing and existing.get('followup_repair')!=NAMESPACE:raise ValueError('FOLLOWUP_TASK_COLLISION')
 if not existing:
  row=repair_row(task,prior,calendar_proof)
  def seed(s):
   if key in s['tasks']:raise ValueError('FOLLOWUP_TASK_COLLISION')
   s['tasks'][key]=row
  c.update(seed)
 _,shared=c.store.read(source);excluded=set(shared['tasks'])-{key};slot=task['definition']['slot'];ticket=c.recover(slot,NAMESPACE,exclude=excluded);recovering=bool(ticket)
 if not ticket:ticket=c.claim(slot,NAMESPACE,slot,exclude=excluded)
 if ticket:
  _,shared=c.store.read(source)
  try:
   adapter=EmptyQueryAdapter(c,drive,ticket,shared['tasks'][key]);executor=Executor(c,adapter)
   executor.resume_ticket(ticket) if recovering else executor.execute(ticket)
  except Exception as exc:
   _,shared=c.store.read(source)
   if shared['tasks'][key].get('owner')==NAMESPACE and shared['tasks'][key]['status']=='LEASED':c.error(ticket,'APPLICABILITY_HOLD','ADAPTER_BINDING',type(exc).__name__)
 _,shared=c.store.read(source);current=shared['tasks'][key];status=current['status']
 result=dict(prior,attempts=current['attempts'],followup_source_requests=current['attempts']-prior['attempts'],query_is_not_availability_proof=True)
 result['followup_terminal']=status in ('RAW_BASIC_VERIFIED','CONTENT_BLOCKED','APPLICABILITY_HOLD','SOURCE_HOLD','STORAGE_HOLD','BLOCKED')
 if result['followup_terminal']:result.update(status='RAW_BASIC_VERIFIED' if status=='RAW_BASIC_VERIFIED' else 'REVIEW_REQUIRED',reason=None if status=='RAW_BASIC_VERIFIED' else 'REQUERY_'+status)
 else:result['followup_pending_status']=status
 for name in ('raw_reference','raw_sha256','storage_receipt','error'):
  if name in current:result[name]=current[name]
 return result

def run_source(root,source,config):
 store=GitCAS(root,'jarvis-source-preflight/'+NAMESPACE);revision,state=store.read(source)
 if not state:
  baseline=read_pin(store,config['baseline_pins'][source])
  if baseline.get('source')!=source or len(baseline['tasks'])!=config['baseline_counts'][source]:raise ValueError('FOLLOWUP_BASELINE_SCOPE')
  state=dict(source=source,tasks=copy.deepcopy(baseline['tasks']),baseline_commit=config['baseline_pins'][source],phase='OFFICIAL_FOLLOWUP',source_requests=0)
 metadata_store=GitCAS(root,'jarvis-source-preflight/'+NAMESPACE+'-metadata');_,meta=metadata_store.read('TWSE');calendars=(meta or {}).get('calendars',{})
 def checkpoint():
  nonlocal revision
  state['counts']=dict(collections.Counter(t['status'] for t in state['tasks'].values()));state['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
  if not store.cas(source,revision,state):raise ValueError('FOLLOWUP_CHECKPOINT_CONFLICT')
  revision,_=store.read(source)
  summary=dict(baseline_held=len(state['tasks']),counts=state['counts'],state_commit=revision,phase=state['phase'],analysis_complete=state.get('analysis_complete',False),finished=state.get('finished',False),source_requests=state['source_requests'],full_acceptance=False,updated_at=state['updated_at'])
  Coordinator(GitCAS(root),source).update(lambda s:s.setdefault('problem_followup',{}).update({NAMESPACE:summary}))
  print(json.dumps(summary),flush=True)
 if source=='TPEx' and not state.get('discovery_done'):
  probe_revision,probe_state=metadata_store.read('TPEx');probe_state=probe_state or dict(source='TPEx',tasks={},metadata_attempts={})
  def probe_checkpoint():
   nonlocal probe_revision
   if not metadata_store.cas('TPEx',probe_revision,probe_state):raise ValueError('ROUTE_PROBE_CHECKPOINT_CONFLICT')
   probe_revision,_=metadata_store.read('TPEx')
  urls=list(config['tpex_official_pages']);seen=set();discovery=[]
  while urls and len(seen)<8:
   url=urls.pop(0)
   if url in seen:continue
   seen.add(url);result=metadata(root,source,'route-'+sha(url.encode())[:12],url,probe_state,metadata_store,probe_checkpoint)
   if result.get('status')=='RESPONSE_SAVED':
    found=discover(result['text'],url);discovery.append(dict(url=url,raw_sha256=result['raw_sha256'],**found));urls.extend(u for u in found['scripts'] if not any(x in u.lower() for x in ('jquery','bootstrap','gtag','analytics')))
   time.sleep(2)
  state.update(discovery_done=True,discovered_official_links=discovery);checkpoint()
 for key,prior in state['tasks'].items():
  proof=classify(prior,calendars,config)
  if proof:state['tasks'][key]=dict(prior,status='CONFIRMED_EXCEPTION',followup_evidence=proof,full_acceptance=False)
 state['analysis_complete']=True;checkpoint()
 rows=load_rows(store,json.loads((root/ORIGINAL_PLAN).read_text()),source);started=time.monotonic()
 from scripts.annual_actual_firstpass import Drive,service
 drive=Drive(service());more=False
 for task in rows:
  key=task['definition']['key'];prior=state['tasks'][key]
  if prior.get('followup_terminal'):continue
  if not prior.get('followup_pending_status') and not eligible(task,prior,calendars):continue
  if time.monotonic()-started>1500:more=True;break
  _,shared=Coordinator(GitCAS(root),source).store.read(source)
  if (shared or {}).get('hold'):more=True;break
  delay=max(0,(shared or {}).get('http_budget',{}).get('next_at',0)-time.time())
  if 0<delay<=5:time.sleep(delay)
  before=prior['attempts'];result=requery(root,source,task,prior,calendars[task['definition']['period'][:4]],drive)
  state['source_requests']+=result['attempts']-before;state['tasks'][key]=result;checkpoint()
  if result.get('followup_terminal'):
   def cleanup(s):
    current=s['tasks'].get(key)
    if current and current.get('followup_repair')==NAMESPACE and not current.get('owner'):del s['tasks'][key]
   Coordinator(GitCAS(root),source).update(cleanup)
  else:more=True;break
 state['finished']=not more;state['processing_pass_finished']=not more;state['still_open']=state['counts'].get('REVIEW_REQUIRED',0);state['all_issues_resolved']=state['still_open']==0;checkpoint()
 Path('results').mkdir(exist_ok=True);Path('results/official-followup.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',choices=('calendar','TWSE','TPEx'),required=True);args=parser.parse_args();root=Path.cwd();load_release(root);config=json.loads((root/PLAN).read_text())
 if config.get('enabled') is not True:print(json.dumps(dict(disabled=True,source_requests=0)));return
 if args.source=='calendar':run_calendars(root,config)
 else:run_source(root,args.source,config)
if __name__=='__main__':main()
