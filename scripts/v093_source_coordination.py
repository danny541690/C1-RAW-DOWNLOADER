"""Fenced per-source task coordinator over a caller-provided durable CAS store.

The store API is read(source)->(revision,state) and cas(source,revision,state)->bool.
The runtime adapter must provide globally shared durable CAS; a local store in
separate GitHub runners is NOT sufficient. No HTTP or RAW writes occur here.
"""
import copy,hashlib,re,time
SOURCES={'TWSE','TPEx','MOPS','TAIFEX','TDCC','NDC','FinMind'}
class Conflict(RuntimeError):pass
class StaleOwner(RuntimeError):pass

class Coordinator:
 def __init__(self,store,source,clock=time.time,ttl=300):
  if source not in SOURCES or ttl<=0:raise ValueError('SOURCE_OR_LEASE')
  self.store=store;self.source=source;self.clock=clock;self.ttl=ttl
 def update(self,change):
  for _ in range(100):
   revision,original=self.store.read(self.source)
   state=copy.deepcopy(original) if original else dict(source=self.source,tasks={},fence=0,outbox={})
   if state['source']!=self.source:raise ValueError('SOURCE_SCOPE')
   result=change(state)
   if self.store.cas(self.source,revision,state):return result
  raise Conflict('CAS_RETRY_EXHAUSTED')
 def add(self,rows):
  def change(state):
   for row in rows:
    if row['source']!=self.source:raise ValueError('CROSS_SOURCE_TASK')
    key=row['key'];definition={k:row[k] for k in ('source','key','slot','period')}
    old=state['tasks'].get(key)
    if old and old['definition']!=definition:raise ValueError('TASK_REASSIGNMENT_REQUIRES_MIGRATION')
    if not old:state['tasks'][key]=dict(definition=definition,status='READY',attempts=0,fence=0)
  self.update(change)
 def claim(self,slot,owner,direction='DESC'):
  if direction not in ('ASC','DESC') or not owner:raise ValueError('OWNER_DIRECTION')
  now=self.clock()
  def change(state):
   if state.get('hold') or state.get('cooldown_until',0)>now:return None
   for task in state['tasks'].values():
    if task.get('owner') and task['expires']<=now:
     uncertain=task['status'] in ('REQUEST_INTENT','STORED','RETAINED_CHECK')
     task.update(owner=None,status='RECONCILE' if uncertain else 'READY')
     if uncertain:task['next_action']='VERIFY_SAVE_INTENT' if task.get('save_intent') else 'RECONCILE_SOURCE_AND_STORAGE'
   available=[(key,t) for key,t in state['tasks'].items() if t['definition']['slot']==slot
    and (t['status']=='READY' or t['status']=='RETRY_WAIT' and t.get('next_at',0)<=now)]
   available.sort(key=lambda x:(x[1]['definition']['period'],x[0]),reverse=direction=='DESC')
   for key,task in available:
    if task['attempts']>=4:task['status']='BLOCKED';continue
    state['fence']+=1;task.update(status='LEASED',owner=owner,fence=state['fence'],expires=now+self.ttl)
    return dict(source=self.source,key=key,owner=owner,fence=task['fence'])
   return None
  return self.update(change)
 def owned(self,state,ticket):
  if ticket['source']!=self.source:raise StaleOwner('SOURCE_SCOPE')
  t=state['tasks'][ticket['key']]
  if t.get('owner')!=ticket['owner'] or t['fence']!=ticket['fence'] or t['expires']<=self.clock():raise StaleOwner('LEASE_EXPIRED_OR_REPLACED')
  return t
 def heartbeat(self,ticket):
  def change(s):self.owned(s,ticket)['expires']=self.clock()+self.ttl
  self.update(change)
 def begin_request(self,ticket):
  def change(s):
   t=self.owned(s,ticket)
   if s.get('hold') or s.get('cooldown_until',0)>self.clock():raise ValueError('SOURCE_ON_HOLD')
   if t['status']!='LEASED' or t['attempts']>=4:raise ValueError('REQUEST_NOT_ADMITTED')
   t.update(status='REQUEST_INTENT',attempts=t['attempts']+1);return t['attempts']
  return self.update(change)
 def saved(self,ticket,raw_sha):
  if not isinstance(raw_sha,str) or not re.fullmatch('[0-9a-f]{64}',raw_sha):raise ValueError('INVALID_RAW_SHA')
  def change(s):
   t=self.owned(s,ticket)
   if t['status']!='REQUEST_INTENT':raise ValueError('NO_REQUEST_INTENT')
   t.update(status='STORED',raw_sha256=raw_sha)
  self.update(change)
 def retained(self,ticket,raw_sha,reference):
  if not re.fullmatch('[0-9a-f]{64}',raw_sha) or not reference:raise ValueError('RETAINED_REFERENCE')
  def change(s):
   t=self.owned(s,ticket)
   if t['status'] not in ('LEASED','RETAINED_CHECK'):raise ValueError('NOT_LEASED')
   t.update(status='STORED',raw_sha256=raw_sha,raw_reference=reference,reused_existing=True,save_intent=dict(sha256=raw_sha,locator=reference))
  self.update(change)
 def prepare_retained(self,ticket,raw_sha,reference):
  if not re.fullmatch('[0-9a-f]{64}',raw_sha) or not reference:raise ValueError('RETAINED_REFERENCE')
  def change(s):
   t=self.owned(s,ticket)
   if t['status']!='LEASED':raise ValueError('NOT_LEASED')
   t.update(status='RETAINED_CHECK',raw_reference=reference,reused_existing=True,save_intent=dict(sha256=raw_sha,locator=reference))
  self.update(change)
 def error(self,ticket,status,phase,code,source_hold=False):
  if status not in ('RECONCILE','CONTENT_BLOCKED','APPLICABILITY_HOLD','SOURCE_HOLD','STORAGE_HOLD'):raise ValueError('ERROR_STATUS')
  def change(s):
   t=self.owned(s,ticket)
   t.update(status=status,owner=None,error=dict(phase=phase,code=code),next_action='VERIFY_SAVE_INTENT' if t.get('save_intent') else 'RECONCILE_SOURCE_AND_STORAGE')
   if source_hold:s['hold']=code
  self.update(change)
 def resolve_unsaved(self,key,evidence,retry_after=0):
  if not isinstance(evidence,dict) or evidence.get('storage_checked') is not True or evidence.get('receipt_checked') is not True or evidence.get('outcome')!='NO_DURABLE_RESULT' or not evidence.get('evidence_id'):raise ValueError('RECONCILIATION_EVIDENCE_REQUIRED')
  if retry_after<0:raise ValueError('RETRY_AFTER')
  def change(s):
   t=s['tasks'][key]
   if t.get('owner') and t.get('expires',0)>self.clock():raise StaleOwner('ACTIVE_OWNER')
   if t['status'] not in ('REQUEST_INTENT','RECONCILE') or t.get('save_intent'):raise ValueError('NOT_UNSAVED_REQUEST')
   t.update(owner=None,status='BLOCKED' if t['attempts']>=4 else 'RETRY_WAIT',next_at=self.clock()+retry_after,reconciliation=dict(evidence))
  self.update(change)
 def prepare_save(self,ticket,raw_sha,locator):
  if not re.fullmatch('[0-9a-f]{64}',raw_sha) or not locator:raise ValueError('SAVE_INTENT')
  def change(s):
   t=self.owned(s,ticket)
   if t['status']!='REQUEST_INTENT':raise ValueError('NO_REQUEST_INTENT')
   t.update(save_intent=dict(sha256=raw_sha,locator=locator))
  self.update(change)
 def recover(self,slot,owner):
  now=self.clock()
  def change(s):
   for key,t in s['tasks'].items():
    if t['definition']['slot']!=slot:continue
    if t.get('owner') and t.get('expires',0)>now:continue
    if t['status'] not in ('REQUEST_INTENT','STORED','RECONCILE','RETAINED_CHECK'):continue
    if not t.get('save_intent'):continue
    s['fence']+=1;t.update(owner=owner,fence=s['fence'],expires=now+self.ttl,status='REQUEST_INTENT')
    return dict(source=self.source,key=key,owner=owner,fence=t['fence'])
   return None
  return self.update(change)
 def verified(self,ticket,readback_sha,basic_qa):
  def change(s):
   t=self.owned(s,ticket)
   if t['status']!='STORED' or readback_sha!=t['raw_sha256'] or basic_qa is not True:raise ValueError('READBACK_OR_QA_NOT_VERIFIED')
   t.update(status='RAW_BASIC_VERIFIED',owner=None,numeric_verified=False,pit_verified=False,full_acceptance=False)
  self.update(change)
 def failed(self,ticket,retry_after=0,source_cooldown=False):
  if retry_after<0:raise ValueError('RETRY_AFTER')
  def change(s):
   t=self.owned(s,ticket)
   if t['status']!='REQUEST_INTENT':raise ValueError('NO_IN_FLIGHT_REQUEST')
   t.update(status='BLOCKED' if t['attempts']>=4 else 'RETRY_WAIT',owner=None,next_at=self.clock()+retry_after)
   if source_cooldown:s['cooldown_until']=max(s.get('cooldown_until',0),self.clock()+retry_after)
  self.update(change)
 def dispatch_after_save(self,slot,run_id,dispatch):
  now=self.clock();identity=hashlib.sha256((self.source+'|'+slot+'|'+run_id).encode()).hexdigest()
  def reserve(s):
   if s.get('hold') or s.get('cooldown_until',0)>now or identity in s['outbox']:return False
   tasks=[t for t in s['tasks'].values() if t['definition']['slot']==slot]
   if any(t.get('owner') and t.get('expires',0)>now for t in tasks):return False
   if not any(t['status']=='READY' or t['status']=='RETRY_WAIT' and t.get('next_at',0)<=now for t in tasks):return False
   s['outbox'][identity]=dict(status='INTENT',slot=slot,run_id=run_id);return True
  if not self.update(reserve):return False
  try:dispatch(identity)
  except Exception:
   def unknown(s):s['outbox'][identity]['status']='UNKNOWN_RECONCILE_DISPATCH'
   self.update(unknown);raise
  def sent(s):s['outbox'][identity]['status']='SENT'
  self.update(sent);return True
