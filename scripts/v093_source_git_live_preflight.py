"""Real GitHub control-plane preflight; synthetic payload, no market/Drive calls."""
import argparse,hashlib,json,os
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_partition import COUNTS

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('seed','work','verify'))
 p.add_argument('--namespace',required=True);p.add_argument('--source',choices=tuple(COUNTS));p.add_argument('--slot',choices=('ASC','DESC'));p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 store=GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace)
 expected={s:('ASC','DESC') if n==2 else ('DESC',) for s,n in COUNTS.items()}
 report=dict(schema='JARVIS_REAL_GIT_CONTROL_PREFLIGHT_V1',mode=a.mode,namespace=a.namespace,
  market_requests=0,drive_writes=0,formal_acceptance=False)
 if a.mode=='seed':
  for source,slots in expected.items():
   Coordinator(store,source).add([dict(source=source,key='fixture-'+slot,slot=slot,period='2026-10-29') for slot in slots])
  report.update(sources=len(expected),task_slots=sum(map(len,expected.values())))
 elif a.mode=='work':
  if not a.source or a.slot not in expected[a.source]:raise ValueError('SLOT_NOT_ASSIGNED')
  c=Coordinator(store,a.source);t=c.claim(a.slot,a.namespace+'-'+a.source+'-'+a.slot)
  if t:
   c.begin_request(t);raw=('SYNTHETIC_CONTROL_ONLY|'+a.source+'|'+a.slot).encode();sha=hashlib.sha256(raw).hexdigest()
   c.saved(t,sha);c.verified(t,sha,True)
  _,state=store.read(a.source);item=state['tasks']['fixture-'+a.slot]
  if item['status']!='RAW_BASIC_VERIFIED' or item['attempts']!=1:raise ValueError('UNEXPECTED_TASK_STATE')
  report.update(source=a.source,slot=a.slot,newly_processed=bool(t),task=item)
 else:
  outcomes={};total=0
  for source,slots in expected.items():
   revision,state=store.read(source)
   if set(state['tasks'])!={'fixture-'+slot for slot in slots}:raise ValueError('MISSING_OR_EXTRA_TASKS')
   for task in state['tasks'].values():
    if task['status']!='RAW_BASIC_VERIFIED' or task['attempts']!=1 or task['full_acceptance'] is not False:raise ValueError('STATE_NOT_VERIFIED')
   outcomes[source]=dict(commit=revision,slots=len(slots));total+=len(slots)
  report.update(control_plane_verified=True,verified_slots=total,sources=outcomes,
   limitation='Real remote Git CAS across runners; all payloads synthetic; source HTTP, Drive and production continuation not exercised')
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
