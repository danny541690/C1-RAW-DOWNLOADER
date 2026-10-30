"""Real GitHub dispatch/ack acceptance with labelled control fixtures only."""
import argparse,hashlib,json,os,time
from pathlib import Path
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_admission_runtime import Catalog,catalog_state
from scripts.v093_source_continuation import continue_slot,acknowledge
from scripts.v093_workflow_dispatch import WorkflowDispatch

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=('send','receive'),required=True);p.add_argument('--namespace',required=True);p.add_argument('--continuation-id',default='');a=p.parse_args();root=Path.cwd()
 if not a.namespace.isdigit():raise ValueError('CONTROL_NAMESPACE')
 c=Coordinator(GitCAS(root,'jarvis-source-preflight/continuation-control-'+a.namespace),'TWSE',ttl=600)
 if a.phase=='receive':
  if not acknowledge(c,'DESC',a.continuation_id,os.environ['GITHUB_RUN_ID']):raise ValueError('CONTROL_DUPLICATE_RECEIVER')
  report=dict(phase='receive',acknowledged=True,fixture_only=True,source_requests=0,formal_raw_writes=0,production_activation=False)
 else:
  if c.store.remote_head('TWSE')!=0:raise ValueError('FRESH_CONTROL_NAMESPACE')
  key='EXPLICIT_NO_MARKET_NO_DRIVE_CONTROL_FIXTURE';period='2026-09-01';ref='NO_DRIVE_READ_CONTROL_ONLY';sha='a'*64
  old=dict(source='TWSE',task_key=key,attempts=0,action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(period=period,raw_reference=ref,sha256=sha)])
  row=dict(definition=dict(source='TWSE',slot='DESC',key=key,period=period),status='READY_CHECK',attempts=0,legacy_review=old,execution_contract=dict(source='TWSE',key=key,period=period,mode='RETAINED',reference=ref,sha256=sha,category='prices_indices'))
  cs=GitCAS(root,'jarvis-source-preflight/continuation-catalog-'+a.namespace)
  if cs.remote_head('TWSE')!=0 or not cs.cas('TWSE',0,catalog_state('TWSE','DESC',[row],'2026-10-30')):raise ValueError('FRESH_CONTROL_CATALOG')
  commit=cs.remote_head('TWSE');pin=dict(commit=commit,index_sha256=hashlib.sha256(cs.git('show',commit+':state.json').stdout).hexdigest());catalog=Catalog(cs,pin,'TWSE','DESC')
  dispatch=WorkflowDispatch(os.environ['GITHUB_REPOSITORY'],'jarvis-seven-continuation-live-test.yml','main',os.environ['GH_TOKEN'],dict(phase='receive',namespace=a.namespace))
  sent=continue_slot(root,c,catalog,'DESC',os.environ['GITHUB_RUN_ID'],dispatch)
  if not sent:raise ValueError('CONTROL_DISPATCH_NOT_SENT')
  received=None
  for _ in range(60):
   _,state=c.store.read('TWSE');entry=next(iter(state['outbox'].values()))
   if entry['status']=='RECEIVED':received=entry;break
   time.sleep(3)
  if not received:raise ValueError('CONTROL_REMOTE_ACK_NOT_RECEIVED')
  _,state=c.store.read('TWSE')
  if any(t['attempts']!=0 for t in state['tasks'].values()):raise ValueError('CONTROL_SPENT_SOURCE_ATTEMPT')
  report=dict(phase='send',real_github_dispatch_ack_verified=True,receiver=received,catalog_pin=pin,fixture_only=True,source_requests=0,formal_raw_writes=0,production_activation=False,limitation='Actual durable transport and receiver, no production data or sustained provider load')
 Path('results').mkdir(exist_ok=True);Path('results/continuation-live.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
