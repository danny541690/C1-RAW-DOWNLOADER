"""Closed-loop executor; expected receipt binding and durable failure classification."""
import hashlib,math,re,urllib.error
from email.utils import parsedate_to_datetime
class ApplicabilityUnproven(ValueError):
 """Source answered without sufficient evidence for this task; never absence proof."""

class Executor:
 def __init__(self,coordinator,adapter):self.c=coordinator;self.a=adapter
 def expected_retained(self,ticket,reference):
  getter=getattr(self.a,'expected_receipt',None)
  if not callable(getter):raise ValueError('RETAINED_RECEIPT_CONTRACT_MISSING')
  receipt=getter(ticket['key']);_,state=self.c.store.read(self.c.source)
  definition=state['tasks'][ticket['key']]['definition']
  if not isinstance(receipt,dict) or any(receipt.get(k)!=v for k,v in dict(source=ticket['source'],task_key=ticket['key'],period=definition['period'],reference=reference).items()):raise ValueError('RETAINED_RECEIPT_BINDING_MISMATCH')
  sha=receipt.get('sha256')
  if not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('RETAINED_EXPECTED_SHA_MISSING')
  return sha
 def finish(self,ticket,raw,reference):
  expected=hashlib.sha256(raw).hexdigest();readback=self.a.read(reference)
  if hashlib.sha256(readback).hexdigest()!=expected:raise ValueError('REMOTE_RAW_SHA_MISMATCH')
  stats=self.a.validate(readback)
  if not isinstance(stats,dict) or stats.get('basic_verified') is not True:raise ValueError('CONTENT_VALIDATION_NOT_PASSED')
  self.c.verified(ticket,expected,True)
  return dict(task_key=ticket['key'],sha256=expected,reference=reference,stats=stats,numeric_verified=False,pit_verified=False,full_acceptance=False)
 def retry_delay(self,exc):
  header=getattr(exc,'headers',None);value=header.get('Retry-After') if header else None
  if value:
   try:
    delay=float(value)
    if math.isfinite(delay):return max(0,delay)
   except (ValueError,TypeError):
    try:return max(0,parsedate_to_datetime(value).timestamp()-self.c.clock())
    except (ValueError,TypeError,OverflowError):pass
  return 60
 def record_error(self,ticket,phase,exc):
  code=type(exc).__name__ # No URL, token, response body or exception text persisted.
  if phase=='FETCH':
   status=getattr(exc,'code',None)
   if isinstance(status,int):code+='_'+str(status)
   if status in (408,429,500,502,503,504) or isinstance(exc,(TimeoutError,ConnectionError)) or isinstance(exc,OSError) and not isinstance(exc,urllib.error.HTTPError):
    self.c.failed(ticket,retry_after=self.retry_delay(exc),source_cooldown=status in (429,503),error_code=code);return
   self.c.error(ticket,'SOURCE_HOLD',phase,code,source_hold=status in (401,403) or status is None);return
  if phase=='VALIDATE' and isinstance(exc,ApplicabilityUnproven):self.c.error(ticket,'APPLICABILITY_HOLD',phase,code);return
  if phase=='AUTHORIZE':self.c.error(ticket,'APPLICABILITY_HOLD',phase,code);return
  if phase in ('RECEIPT_BINDING','VALIDATE','HASH_CHECK') or phase=='READBACK' and isinstance(exc,ValueError):
   self.c.error(ticket,'CONTENT_BLOCKED',phase,code);return
  self.c.error(ticket,'RECONCILE',phase,code)
 def one(self,slot,owner):
  t=self.c.claim(slot,owner,slot)
  if not t:return None
  return self.execute(t)
 def execute(self,t):
  _,state=self.c.store.read(self.c.source);self.c.owned(state,t)
  phase='LOOKUP'
  try:
   found=self.a.find(t['key'])
   if found:
    phase='RECEIPT_BINDING';expected=self.expected_retained(t,found)
    self.c.prepare_retained(t,expected,found)
    phase='READ_RETAINED';raw=self.a.read(found)
    phase='HASH_CHECK'
    if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('RETAINED_EXPECTED_SHA_MISMATCH')
    phase='VALIDATE';self.a.validate(raw);self.c.retained(t,expected,found)
    phase='READBACK';return self.finish(t,raw,found)
   phase='AUTHORIZE'
   if self.a.download_authorized is not True:raise ValueError('DOWNLOAD_NOT_AUTHORIZED')
   self.c.begin_request(t);phase='FETCH';raw=self.a.fetch();sha=hashlib.sha256(raw).hexdigest()
   phase='VALIDATE';self.a.validate(raw)
   phase='PREPARE_SAVE';locator=self.a.locator(t['key'],sha);self.c.prepare_save(t,sha,locator)
   self.c.heartbeat(t);phase='STORE';reference=self.a.put(locator,raw);self.c.saved(t,sha)
   phase='READBACK';return self.finish(t,raw,reference)
  except Exception as exc:
   self.record_error(t,phase,exc);raise
 def resume(self,slot,owner):
  t=self.c.recover(slot,owner)
  if not t:return None
  return self.resume_ticket(t)
 def resume_ticket(self,t):
  _,state=self.c.store.read(self.c.source);self.c.owned(state,t)
  phase='LOOKUP'
  try:
   _,state=self.c.store.read(self.c.source);item=state['tasks'][t['key']];intent=item['save_intent']
   ref=item['raw_reference'] if item.get('reused_existing') else self.a.find_locator(intent['locator'])
   if not ref:raise ValueError('INTERRUPTED_SAVE_NOT_FOUND_RECONCILIATION_REQUIRED')
   phase='READBACK';raw=self.a.read(ref);phase='HASH_CHECK'
   if hashlib.sha256(raw).hexdigest()!=intent['sha256']:raise ValueError('INTERRUPTED_SAVE_HASH_MISMATCH')
   self.c.saved(t,intent['sha256']);phase='READBACK';return self.finish(t,raw,ref)
  except Exception as exc:
   self.record_error(t,phase,exc);raise
 def reconcile_unsaved(self,key):
  getter=getattr(self.a,'reconcile_request',None)
  if not callable(getter):raise ValueError('ADAPTER_RECONCILIATION_REQUIRED')
  self.c.resolve_unsaved(key,getter(key))
