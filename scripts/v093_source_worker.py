"""Bounded common worker for admitted tasks, plus explicit isolated entry QA.

Production remains fail-closed until release config and source adapters are
implemented. QA uses labelled fixtures; no market HTTP or formal RAW writes.
"""
import argparse,collections,hashlib,json,time
from pathlib import Path
from scripts.v093_source_coordination import Coordinator,SOURCES,StaleOwner
from scripts.v093_source_executor import Executor
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_partition import COUNTS

def run_batch(coordinator,adapter_factory,slot,owner,max_units=20,seconds=2700,monotonic=time.monotonic):
 if slot not in ('ASC','DESC') or COUNTS[coordinator.source]==1 and slot!='DESC' or not 1<=max_units<=100 or not 0<seconds<=2700:raise ValueError('WORKER_SCOPE_OR_BUDGET')
 started=monotonic();seen=set();outcomes=[]
 while len(seen)<max_units and monotonic()-started<seconds:
  ticket=coordinator.recover(slot,owner,exclude=seen);recovering=bool(ticket)
  if not ticket:ticket=coordinator.claim(slot,owner,slot,exclude=seen)
  if not ticket:break
  key=ticket['key'];seen.add(key)
  _,state=coordinator.store.read(coordinator.source);task=state['tasks'][key]
  try:adapter=adapter_factory(ticket,task)
  except Exception as exc:
   coordinator.error(ticket,'APPLICABILITY_HOLD','ADAPTER_BINDING',type(exc).__name__)
   outcomes.append(dict(key=key,outcome='ADAPTER_HOLD',error=type(exc).__name__));continue
  try:
   executor=Executor(coordinator,adapter)
   evidence=executor.resume_ticket(ticket) if recovering else executor.execute(ticket)
   outcomes.append(dict(key=key,outcome='BASIC_VERIFIED',recovered=recovering,evidence=evidence))
  except StaleOwner:outcomes.append(dict(key=key,outcome='LEASE_LOST'))
  except Exception as exc:outcomes.append(dict(key=key,outcome='ISOLATED_ERROR',error=type(exc).__name__))
 _,state=coordinator.store.read(coordinator.source);tasks=[t for t in state['tasks'].values() if t['definition']['slot']==slot]
 counts=dict(collections.Counter(t['status'] for t in tasks))
 result=dict(source=coordinator.source,slot=slot,processed=len(seen),outcomes=outcomes,task_status_counts=counts,task_scope=len(tasks),denominator_is_database_universe=False,elapsed_seconds=round(monotonic()-started,3),full_acceptance=False,ready_remaining=sum(t['status']=='READY' or t['status']=='RETRY_WAIT' and t.get('next_at',0)<=coordinator.clock() for t in tasks),source_hold=state.get('hold'),cooldown_until=state.get('cooldown_until'))
 coordinator.update(lambda s:s.setdefault('last_batches',{}).update({slot:result}))
 return result

def run_native_batch(coordinator,drive,slot,owner,target_root,max_units=20,seconds=2700):
 from scripts.v093_source_adapters import factory
 return run_batch(coordinator,factory(coordinator,drive,target_root),slot,owner,max_units,seconds)

class EntryFixture:
 """Explicit validation-only local payload; never used in production mode."""
 download_authorized=True
 def __init__(self,key,source):self.key=key;self.source=source;self.raw=('ENTRY_FIXTURE_ONLY|'+source+'|'+key).encode();self.root=Path('entry-fixtures');self.root.mkdir(exist_ok=True)
 def find(self,key):return None
 def fetch(self):return self.raw
 def validate(self,raw):
  if self.key.endswith('bad'):raise ValueError('EXPECTED_ENTRY_QA_BAD_FIXTURE')
  if raw!=self.raw:raise ValueError('FIXTURE_SHA')
  return dict(basic_verified=True,fixture_only=True)
 def locator(self,key,sha):return str(self.root/(sha+'.raw'))
 def put(self,locator,raw):Path(locator).write_bytes(raw);return locator
 def find_locator(self,locator):return locator if Path(locator).exists() else None
 def read(self,reference):return Path(reference).read_bytes()

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',choices=sorted(SOURCES),required=True);p.add_argument('--direction',choices=('ASC','DESC'),required=True);p.add_argument('--mode',choices=('entry-validation','production'),required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 if COUNTS[a.source]==1 and a.direction!='DESC':raise ValueError('SOURCE_DIRECTION')
 if a.mode=='production':raise ValueError('PRODUCTION_RELEASE_BLOCKED_SOURCE_ADAPTER_ROLLOUT_AND_QUOTA_NOT_ACCEPTED')
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace),a.source,ttl=600)
 c.add([dict(source=a.source,key='entry-'+a.direction+'-'+suffix,slot=a.direction,period='2026-10-29') for suffix in ('bad','good')])
 result=run_batch(c,lambda ticket,task:EntryFixture(ticket['key'],a.source),a.direction,'entry-'+a.direction,max_units=2,seconds=120)
 if result['task_status_counts']!={'CONTENT_BLOCKED':1,'RAW_BASIC_VERIFIED':1}:raise ValueError('ENTRY_WORKER_INTEGRATION_FAILED')
 result.update(schema='JARVIS_COMMON_WORKER_ENTRY_QA_V1',execution_mode='ENTRY_FIXTURES_ONLY',market_requests=0,formal_raw_writes=0,production_activation=False)
 out=Path('results');out.mkdir(exist_ok=True);(out/'entry.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
