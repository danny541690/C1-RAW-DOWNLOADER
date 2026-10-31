"""Pinned held-task recovery; original archives and successful RAW stay immutable.

Rechecks use no source HTTP. A historical MOPS query is allowed only for a
previously missing domestic partition with an explicit 404 and remaining quota.
Every such request goes through the production coordinator and native executor.
"""
import argparse,collections,copy,datetime as dt,gzip,hashlib,json,re,time
from pathlib import Path
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_state_pages import unpack,SCHEMA
from scripts.v093_source_adapters import NativeAdapter,RAW_ROOT
from scripts.v093_source_executor import Executor
from scripts.v093_source_coordination import Coordinator
from scripts.v093_admission_runtime import load_release

PLAN='config/v093_problem_recovery_20261031.json'
TERMINAL={'RAW_BASIC_VERIFIED','CONFIRMED_EXCEPTION','REVIEW_REQUIRED'}

def digest(raw):return hashlib.sha256(raw).hexdigest()

def load_rows(store,plan,source):
 groups=[g for g in plan['archives'] if g['source']==source]
 commits=list(dict.fromkeys(g['commit'] for g in groups))
 for i in range(0,len(commits),40):
  missing=[sha for sha in commits[i:i+40] if store.git('cat-file','-e',sha+':state.json',check=False).returncode]
  if missing:store.git('fetch','--no-tags','--no-write-fetch-head','origin',*missing)
 rows=[]
 for group in groups:
  commit=group['commit']
  if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('RECOVERY_ARCHIVE_PIN')
  raw=store.git('show',commit+':state.json').stdout;obj=json.loads(raw)
  state=unpack(raw,lambda name:store.git('show',commit+':'+name).stdout) if obj.get('schema')==SCHEMA else obj
  if state.get('source')!=source or state.get('slot')!=group['slot']:raise ValueError('RECOVERY_ARCHIVE_SCOPE')
  for expected in group['held']:
   task=copy.deepcopy(state['tasks'][expected['key']]);definition=task['definition']
   actual=dict(key=definition['key'],status=task['status'],attempts=task['attempts'],period=definition['period'])
   if actual!=expected or definition['source']!=source or definition['slot']!=group['slot'] or task.get('owner'):raise ValueError('RECOVERY_BASELINE_CHANGED')
   task['recovery_archive']=dict(commit=commit,ref=group['ref']);rows.append(task)
 if len(rows)!=plan['baseline_source_counts'][source] or len({t['definition']['key'] for t in rows})!=len(rows):raise ValueError('RECOVERY_BASELINE_COUNT')
 return rows

def exception_evidence(task,plan,raw=None):
 case=task.get('execution_contract') or {};source=task['definition']['source'];period=task['definition']['period'];proofs=plan['official_evidence']
 if source=='TAIFEX':
  job=case.get('native_job') or {};endpoint=str(job.get('url','')).rsplit('/',1)[-1]
  if endpoint in ('dlLargeTraderFutDown','dlLargeTraderOptDown') and job.get('end','9999')<proofs['taifex_large_trader']['start']:
   if job.get('start','9999')>job['end'] or not job['start']<=period<=job['end']:raise ValueError('EXCEPTION_QUERY_PERIOD')
   return dict(reason='BEFORE_DATASET_START',**proofs['taifex_large_trader'])
 if source=='TWSE' and raw is not None and period<proofs['twse']['start']:
  obj=json.loads(raw.decode('utf-8-sig'))
  if obj.get('stat')=='查詢日期小於93年2月11日，請重新查詢!':return dict(reason='BEFORE_ENDPOINT_START',**proofs['twse'])
 if source=='TWSE' and raw is not None and period>=proofs['twse_weekends']['start'] and dt.date.fromisoformat(period).weekday()==5:
  obj=json.loads(raw.decode('utf-8-sig'))
  if '沒有符合條件的資料' in obj.get('stat',''):return dict(reason='OFFICIAL_SATURDAY_NONTRADING',date=period,**proofs['twse_weekends'])
 if source in ('TWSE','TPEx') and raw is not None and period in proofs['holidays_2026']['dates']:
  obj=json.loads(raw.decode('utf-8-sig'))
  empty=source=='TWSE' and '沒有符合條件的資料' in obj.get('stat','')
  if source=='TPEx':
   from scripts.v093_three_year_repair import actual_date,tabular
   empty=actual_date(obj)==period and not tabular(obj)[0]
  if empty:return dict(reason='OFFICIAL_NONTRADING_DATE',url=proofs['holidays_2026']['url'],date=period)
 return None

class RecheckAdapter(NativeAdapter):
 def __init__(self,drive,task,cache):
  self.rejected=task.get('rejected_evidence') or {};self.raw_cache=cache
  definition=task['definition'];super().__init__(None,drive,dict(source=definition['source'],key=definition['key']),task)
 def read(self,reference):
  evidence=self.rejected
  if reference==self.case.get('reference') and evidence.get('readback_verified') is True and evidence.get('raw_sha256')==self.case.get('sha256') and evidence.get('encoding')=='gzip':
   return self.read_rejected()
  return super().read(reference)
 def read_rejected(self):
  evidence=self.rejected
  if evidence.get('encoding')!='gzip' or evidence.get('readback_verified') is not True or evidence.get('accepted_as_raw') is not False:raise ValueError('RECOVERY_REJECTION_PROOF')
  fid=evidence['reference'];cache_key=(fid,evidence['stored_sha256'],evidence['raw_sha256'])
  if cache_key not in self.raw_cache:
   compressed=super().read(fid)
   if digest(compressed)!=evidence['stored_sha256']:raise ValueError('RECOVERY_REJECTED_STORED_SHA')
   import io
   with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:raw=stream.read(32_000_001)
   if len(raw)>32_000_000 or len(raw)!=evidence['raw_bytes'] or digest(raw)!=evidence['raw_sha256']:raise ValueError('RECOVERY_REJECTED_RAW_SHA')
   if len(self.raw_cache)>=64:self.raw_cache.clear()
   self.raw_cache[cache_key]=raw
  return self.raw_cache[cache_key]

def recheck(task,plan,drive,cache):
 definition=task['definition'];case=task.get('execution_contract') or {}
 result=dict(definition=definition,baseline_status=task['status'],attempts=task['attempts'],source_requests=0,raw_writes=0,archive=task['recovery_archive'],numeric_verified=False,pit_verified=False,full_acceptance=False)
 exception=exception_evidence(task,plan)
 if exception:return dict(result,status='CONFIRMED_EXCEPTION',evidence=exception)
 retained=case.get('mode')=='RETAINED'
 rejected=task.get('rejected_evidence') or {}
 if not retained and not rejected:return dict(result,status='REVIEW_REQUIRED',reason='HISTORICAL_ROUTE_OR_SOURCE_REVIEW')
 try:
  adapter=RecheckAdapter(drive,task,cache);raw=adapter.read(case['reference']) if retained else adapter.read_rejected()
  expected=case['sha256'] if retained else rejected['raw_sha256']
  if digest(raw)!=expected:raise ValueError('RECOVERY_RETAINED_SHA')
  if retained:result.update(raw_reference=case['reference'],raw_sha256=expected)
  else:result.update(rejected_evidence=rejected,raw_sha256=expected,accepted_as_raw=False)
  exception=exception_evidence(task,plan,raw)
  if exception:return dict(result,status='CONFIRMED_EXCEPTION',evidence=exception)
  stats=adapter.validate(raw)
  if stats.get('basic_verified') is not True:raise ValueError('RECOVERY_BASIC_QA_REQUIRED')
  if not retained:return dict(result,status='REVIEW_REQUIRED',reason='VALID_REJECTED_RAW_REQUIRES_PROMOTION',stats=stats)
  return dict(result,status='RAW_BASIC_VERIFIED',stats=stats,reused_existing=True,receipt_binding_revalidated=(task.get('error') or {}).get('phase')=='RECEIPT_BINDING')
 except Exception as exc:
  message=str(exc).split(':',1)[0]
  reason=message if re.fullmatch('[A-Z][A-Z0-9_]{2,80}',message) else type(exc).__name__
  return dict(result,status='REVIEW_REQUIRED',reason=reason,error_type=type(exc).__name__)

def historical_candidate(task):
 case=task.get('execution_contract') or {};category=case.get('category','');error=task.get('error') or {}
 if task['definition']['source']!='MOPS' or case.get('mode')!='MISSING' or error.get('code')!='HTTPError_404' or case.get('reference'):return None
 if not re.fullmatch('revenue_(sii|otc)_0',category) or not '2000-01'<=case['period']<='2009-12':return None
 market=category.split('_')[1];year,month=map(int,case['period'].split('-'))
 return f'https://mopsov.twse.com.tw/nas/t21/{market}/t21sc03_{year-1911}_{month}.html'

class HistoricalAdapter(NativeAdapter):
 def fetch(self):
  url=historical_candidate(self.recovery_task)
  if not url:raise ValueError('HISTORICAL_ROUTE_NOT_ADMITTED')
  return self.http(url)

class RecoveryPromotionAdapter(NativeAdapter):
 def read(self,reference):
  proof=self.case.get('promotion_evidence',{})
  if reference==proof.get('reference'):
   # Quarantine bytes are compressed; the formal RAW is the verified original.
   reader=object.__new__(RecheckAdapter);reader.rejected=proof['rejected_evidence'];reader.raw_cache={};reader.d=self.d
   return reader.read_rejected()
  return super().read(reference)

def promotion_task(task,evidence):
 row=copy.deepcopy(task);case=row['execution_contract'];rejected=evidence['rejected_evidence']
 if evidence.get('reason')!='VALID_REJECTED_RAW_REQUIRES_PROMOTION' or evidence.get('accepted_as_raw') is not False or evidence.get('raw_sha256')!=rejected['raw_sha256']:raise ValueError('RECOVERY_PROMOTION_PROOF')
 ref=rejected['reference'];sha=rejected['raw_sha256']
 proof=dict(source=case['source'],key=case['key'],period=case['period'],reference=ref,sha256=sha,verified_evidence_id='PINNED_RECHECK:'+task['recovery_archive']['commit']+':'+rejected['stored_sha256'],rejected_evidence=rejected)
 row['legacy_review']['provenance'].append(dict(source=case['source'],period=case['period'],status='REJECTED_EVIDENCE_RAW_REVALIDATED',raw_reference=ref,sha256=sha,encoding='gzip',stored_sha256=rejected['stored_sha256']))
 case.update(mode='PROMOTE',reference=None,sha256=None,promotion_evidence=proof)
 return row

def historical_query(task,production,drive,owner,promotion=None):
 """A query consumes one remaining logical attempt; never resets archived counts."""
 key=task['definition']['key'];_,state=production.store.read(production.source);existing=(state or {}).get('tasks',{}).get(key)
 if existing and existing.get('problem_recovery')!=owner:raise ValueError('RECOVERY_TASK_ALREADY_ACTIVE')
 if not existing:
  def seed(s):
   if key in s['tasks']:raise ValueError('RECOVERY_TASK_ALREADY_ACTIVE')
   row=promotion_task(task,promotion) if promotion else copy.deepcopy(task)
   row.update(status='READY',owner=None,fence=0,check_only=False,local_only=bool(promotion),problem_recovery=owner)
   for field in ('save_intent','raw_reference','raw_sha256','reused_existing'):row.pop(field,None)
   s['tasks'][key]=row
  production.update(seed)
 adapter_task=copy.deepcopy(task)
 def adapter(ticket):
  _,s=production.store.read(production.source);current=s['tasks'][key]
  adapter_class=RecoveryPromotionAdapter if promotion else HistoricalAdapter
  obj=adapter_class(production,drive,ticket,current);obj.recovery_task=adapter_task;return obj
 slot=task['definition']['slot'];ticket=production.recover(slot,owner,exclude=set((state or {}).get('tasks',{}))-{key})
 if not ticket:
  _,s=production.store.read(production.source)
  ticket=production.claim(slot,owner,slot,exclude=set(s['tasks'])-{key})
 try:
  if ticket:
   executor=Executor(production,adapter(ticket))
   _,s=production.store.read(production.source)
   if s['tasks'][key]['status']=='REQUEST_INTENT' and s['tasks'][key].get('save_intent'):executor.resume_ticket(ticket)
   else:executor.execute(ticket)
 except Exception:pass # Exact state and classified error below are durable.
 _,s=production.store.read(production.source);current=s['tasks'][key]
 result=dict(definition=task['definition'],baseline_status=task['status'],attempts=current['attempts'],source_requests=current['attempts']-task['attempts'],raw_writes=int(current['status']=='RAW_BASIC_VERIFIED'),status=current['status'],historical_route=historical_candidate(task),candidate_was_query_only=True,numeric_verified=False,pit_verified=False,full_acceptance=False,archive=task['recovery_archive'])
 for name in ('raw_reference','raw_sha256','storage_receipt','error','next_at'): 
  if name in current:result[name]=current[name]
 if promotion:result.update(local_promotion=True,materializations=current.get('materializations',0),rejected_evidence=promotion['rejected_evidence'])
 # Keep uncertain requests in the production state for executor reconciliation.
 result['terminal']=current['status'] in ('RAW_BASIC_VERIFIED','APPLICABILITY_HOLD','CONTENT_BLOCKED','BLOCKED','SOURCE_HOLD','STORAGE_HOLD')
 if promotion and not result['terminal']:result['pending_promotion']=promotion
 if result['terminal'] and current['status']!='RAW_BASIC_VERIFIED':result.update(status='REVIEW_REQUIRED',reason='HISTORICAL_QUERY_NOT_VERIFIED')
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',choices=('TWSE','TPEx','MOPS','TAIFEX'),required=True);parser.add_argument('--seconds',type=int,default=2100);args=parser.parse_args()
 root=Path.cwd();load_release(root);plan=json.loads((root/PLAN).read_text());campaign=plan['campaign'];source=args.source;started=time.monotonic()
 store=GitCAS(root,'jarvis-source-preflight/'+campaign);revision,state=store.read(source)
 if state and state.get('plan_sha256')!=digest((root/PLAN).read_bytes()):raise ValueError('RECOVERY_PLAN_CHANGED')
 state=state or dict(source=source,tasks={},plan_sha256=digest((root/PLAN).read_bytes()),campaign=campaign)
 production=Coordinator(GitCAS(root),source,ttl=600)
 from scripts.annual_actual_firstpass import Drive,service
 drive=Drive(service());cache={};rows=[]
 if not state.get('finished'):rows=load_rows(store,plan,source)
 def checkpoint():
  nonlocal revision
  state['counts']=dict(collections.Counter(t['status'] for t in state['tasks'].values()));state['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
  if not store.cas(source,revision,state):raise ValueError('RECOVERY_CHECKPOINT_CONFLICT')
  revision,_=store.read(source)
  summary=dict(campaign=campaign,baseline_held=plan['baseline_source_counts'][source],processed=len(state['tasks']),counts=state['counts'],finished=state.get('finished',False),state_commit=revision,source_requests=sum(t.get('source_requests',0) for t in state['tasks'].values()),raw_writes=sum(t.get('raw_writes',0) for t in state['tasks'].values()),full_acceptance=False,original_admission_unchanged=True,updated_at=state['updated_at'])
  production.update(lambda s:s.setdefault('problem_recovery',{}).update({campaign:summary}))
  print(json.dumps(summary),flush=True)
 def cleanup(key):
  def remove(s):
   task=s['tasks'].get(key)
   if task and task.get('problem_recovery')==campaign and not task.get('owner') and task['status'] not in ('REQUEST_INTENT','RECONCILE','STORED','RETAINED_CHECK','READY','LEASED','RETRY_WAIT'):del s['tasks'][key]
  production.update(remove)
 since_save=0
 # Finish retained checks first. A source cooldown must not hide other valid RAW.
 for task in rows:
  if time.monotonic()-started>args.seconds:break
  key=task['definition']['key'];previous=state['tasks'].get(key)
  if previous:continue
  result=recheck(task,plan,drive,cache)
  state['tasks'][key]=result;since_save+=1
  if since_save>=20:checkpoint();since_save=0
 checkpoint()
 for task in rows:
  if time.monotonic()-started>args.seconds:break
  key=task['definition']['key'];previous=state['tasks'].get(key)
  promotion=(previous.get('pending_promotion') or (previous if previous.get('reason')=='VALID_REJECTED_RAW_REQUIRES_PROMOTION' else None)) if previous else None
  if not previous or not promotion and (not historical_candidate(task) or task['attempts']>=4):continue
  if previous.get('historical_query_complete'):cleanup(key);continue
  _,shared=production.store.read(source)
  if (shared or {}).get('hold'):
   previous.update(historical_query_complete=True,reason='SHARED_SOURCE_HOLD_REQUIRES_REVIEW');checkpoint();continue
  budget=(shared or {}).get('http_budget',{});delay=max(0,budget.get('next_at',0)-production.clock())
  if 0<delay<=5:time.sleep(delay)
  result=historical_query(task,production,drive,campaign,promotion=promotion)
  result['historical_query_complete']=result.get('terminal',False)
  state['tasks'][key]=result;checkpoint()
  if result.get('terminal'):cleanup(key)
  # A deferred HTTP operation stays durable and is resumed on the next wakeup.
  else:break
 if rows:
  state['finished']=len(state['tasks'])==plan['baseline_source_counts'][source] and all(state['tasks'].get(t['definition']['key'],{}).get('reason')!='VALID_REJECTED_RAW_REQUIRES_PROMOTION' and not state['tasks'].get(t['definition']['key'],{}).get('pending_promotion') and (not historical_candidate(t) or t['attempts']>=4 or state['tasks'].get(t['definition']['key'],{}).get('historical_query_complete')) for t in rows)
 checkpoint()
 Path('results').mkdir(exist_ok=True);(Path('results')/'problem-recovery.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
 if state.get('finished') and len(state['tasks'])!=plan['baseline_source_counts'][source]:raise ValueError('RECOVERY_FINISH_COUNT')
if __name__=='__main__':main()
