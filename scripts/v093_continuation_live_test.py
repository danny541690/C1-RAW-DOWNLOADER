"""Two independent GitHub runs test actual dispatch after durable save; no source I/O."""
import hashlib,json,os,re
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_workflow_dispatch import WorkflowDispatch
def main():
 phase=os.environ.get('PHASE') or 'start';namespace=os.environ.get('NAMESPACE') or os.environ['GITHUB_RUN_ID']
 if not re.fullmatch(r'\d+',namespace):raise ValueError('NAMESPACE')
 store=GitCAS(Path.cwd(),'jarvis-source-preflight/continuation-'+namespace);c=Coordinator(store,'TWSE')
 if phase=='start':
  c.add([dict(source='TWSE',key='continuation-probe',slot='DESC',period='2026-10-29')])
  dispatch=WorkflowDispatch(os.environ['GITHUB_REPOSITORY'],'jarvis-seven-continuation-test.yml','main',os.environ['GH_TOKEN'],dict(phase='verify',namespace=namespace))
  sent=c.dispatch_after_save('DESC',os.environ['GITHUB_RUN_ID'],dispatch)
  if not sent:raise RuntimeError('DISPATCH_NOT_RESERVED')
  if c.dispatch_after_save('DESC',os.environ['GITHUB_RUN_ID'],dispatch):raise RuntimeError('DUPLICATE_DISPATCH')
  result=dict(phase=phase,parent_run=os.environ['GITHUB_RUN_ID'],dispatch_after_durable_save=True,duplicate_suppressed=True)
 elif phase=='verify':
  identity=os.environ['CONTINUATION_ID'];_,s=store.read('TWSE');entry=s['outbox'].get(identity)
  if not entry or entry['status']!='SENT' or entry['run_id']!=namespace or namespace==os.environ['GITHUB_RUN_ID']:raise RuntimeError('OUTBOX_OR_FRESH_RUN_NOT_VERIFIED')
  c.update(lambda state:state['outbox'][identity].update(received_by=os.environ['GITHUB_RUN_ID']))
  result=dict(phase=phase,parent_run=namespace,receiver_run=os.environ['GITHUB_RUN_ID'],real_dispatch_verified=True,continued_from_saved_state=True)
 else:raise ValueError('PHASE')
 result.update(market_requests=0,drive_writes=0,production_activation=False)
 Path('results').mkdir(exist_ok=True);Path('results/continuation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
