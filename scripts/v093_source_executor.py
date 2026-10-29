"""Closed-loop executor with typed source/storage adapters and persisted save intent."""
import hashlib
class Executor:
 def __init__(self,coordinator,adapter):self.c=coordinator;self.a=adapter
 def finish(self,ticket,raw,reference):
  expected=hashlib.sha256(raw).hexdigest()
  readback=self.a.read(reference)
  if hashlib.sha256(readback).hexdigest()!=expected:raise ValueError('REMOTE_RAW_SHA_MISMATCH')
  stats=self.a.validate(readback)
  if not isinstance(stats,dict) or stats.get('basic_verified') is not True:raise ValueError('CONTENT_VALIDATION_NOT_PASSED')
  self.c.verified(ticket,expected,True)
  return dict(task_key=ticket['key'],sha256=expected,reference=reference,stats=stats,
   numeric_verified=False,pit_verified=False,full_acceptance=False)
 def one(self,slot,owner):
  t=self.c.claim(slot,owner,slot)
  if not t:return None
  found=self.a.find(t['key'])
  if found:
   raw=self.a.read(found);self.a.validate(raw)
   self.c.retained(t,hashlib.sha256(raw).hexdigest(),found)
   return self.finish(t,raw,found)
  if self.a.download_authorized is not True:raise ValueError('DOWNLOAD_NOT_AUTHORIZED')
  self.c.begin_request(t)
  raw=self.a.fetch();sha=hashlib.sha256(raw).hexdigest();self.a.validate(raw)
  locator=self.a.locator(t['key'],sha)
  self.c.prepare_save(t,sha,locator)
  # Storage failures deliberately do not consume another market request or erase intent.
  self.c.heartbeat(t);reference=self.a.put(locator,raw)
  self.c.saved(t,sha)
  return self.finish(t,raw,reference)
 def resume(self,slot,owner):
  t=self.c.recover(slot,owner)
  if not t:return None
  _,state=self.c.store.read(self.c.source);intent=state['tasks'][t['key']]['save_intent']
  ref=self.a.find_locator(intent['locator'])
  if not ref:raise ValueError('INTERRUPTED_SAVE_NOT_FOUND_RECONCILIATION_REQUIRED')
  raw=self.a.read(ref)
  if hashlib.sha256(raw).hexdigest()!=intent['sha256']:raise ValueError('INTERRUPTED_SAVE_HASH_MISMATCH')
  self.c.saved(t,intent['sha256'])
  return self.finish(t,raw,ref)
