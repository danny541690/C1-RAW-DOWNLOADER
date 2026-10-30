"""Live typed-action QA: local promotion and bounded automatic missing query.

All destinations remain isolated REPORT folders. Never flips production flags.
"""
import argparse,copy,json,os
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_adapters import NativeAdapter,RAW_ROOT
from scripts.v093_source_worker import run_batch
from scripts.v093_admission_runtime import prepare_row
REPORT='1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit'
def seed(c,rows):
 def change(state):
  for row in rows:
   key=row['definition']['key']
   if key in state['tasks']:raise ValueError('ACTION_QA_NO_PROGRESS_RESET')
   state['tasks'][key]=prepare_row('TDCC',row['definition']['slot'],key,row)
 c.update(change)
def run(c,d,root,rows,fault=False,limit=3):
 adapters=[]
 def factory(ticket,task):
  a=NativeAdapter(c,d,ticket,task,target_root=root);adapters.append(a)
  if fault:
   put=a.put
   def crash(name,raw):put(name,raw);raise OSError('EXPLICIT_ACTION_QA_COPY_FAULT')
   a.put=crash
  return a
 results=[]
 for slot in sorted({r['definition']['slot'] for r in rows}):results.append(run_batch(c,factory,slot,'action-'+slot,max_units=limit,seconds=600))
 return results,sum(a.source_requests for a in adapters)
def formal_scope(rows,authorization):
 if authorization!='VERIFIED_TDCC_PROMOTION_CANARY' or not 1<=len(rows)<=10:raise ValueError('FORMAL_CANARY_SCOPE')
 if any(r['definition']['source']!='TDCC' or r['execution_contract']['mode']!='PROMOTE' for r in rows):raise ValueError('FORMAL_CANARY_PROMOTION_ONLY')

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('phase',choices=('capture','resume','missing','formal'));p.add_argument('--namespace',required=True);a=p.parse_args();d=Drive(service());out=Path('results');out.mkdir(exist_ok=True);samples=json.loads(Path('inputs/action-samples.json').read_text());rows=samples['promotions']
 prefix=('native-positive-' if a.phase=='missing' else 'formal-handoff-' if a.phase=='formal' else 'action-promotion-')+a.namespace;c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/'+prefix),'TDCC',ttl=600)
 if a.phase=='formal':
  rows=samples.get('all_promotions',rows);formal_scope(rows,os.environ.get('FORMAL_CANARY_AUTHORIZATION'))
  if c.store.remote_head('TDCC')!=0:raise ValueError('FRESH_FORMAL_CANARY_NAMESPACE')
  seed(c,rows);results,requests=run(c,d,RAW_ROOT,rows,limit=len(rows))
  _,state=c.store.read('TDCC')
  if requests or any(t['status']!='RAW_BASIC_VERIFIED' or t['attempts']!=t['legacy_review']['attempts'] or not t.get('storage_receipt',{}).get('readback_verified') for t in state['tasks'].values()):raise ValueError('FORMAL_PROMOTION_NOT_ALL_VERIFIED')
  evidence=[dict(key=k,period=t['definition']['period'],reference=t['raw_reference'],sha256=t['raw_sha256'],attempts=t['attempts'],reused_existing=bool(t.get('reused_existing')),storage_receipt=t['storage_receipt']) for k,t in state['tasks'].items()]
  report=dict(schema='JARVIS_VERIFIED_FORMAL_PROMOTION_CANARY_V1',destination_root=RAW_ROOT,units_verified=len(evidence),new_raw_files=sum(not e['reused_existing'] for e in evidence),existing_raw_reused=sum(e['reused_existing'] for e in evidence),evidence=evidence,source_requests=0,source_attempts_unchanged=True,qa_originals_retained=True,schedules_activated=False,production_activation=False,full_acceptance=False,results=results)
 elif a.phase=='capture':
  if len(rows)!=2 or c.store.remote_head('TDCC')!=0:raise ValueError('TWO_FRESH_PROMOTION_ACTIONS_REQUIRED')
  folder=d.folder(REPORT,'ACTION_PROMOTION_QA_'+a.namespace);seed(c,rows);c.update(lambda s:s.update(qa_root=folder));results,requests=run(c,d,folder,rows,fault=True)
  _,state=c.store.read('TDCC')
  if requests or any(t['status']!='RECONCILE' or not t.get('save_intent') or t['attempts']!=t['legacy_review']['attempts'] or t['materializations']!=1 for t in state['tasks'].values()):raise ValueError('ACTION_PROMOTION_FAULT_INVARIANT')
  report=dict(schema='JARVIS_PROMOTION_CAPTURE_V1',pending_saved_copies=len(rows),source_requests=0,source_attempts_unchanged=True,formal_raw_writes=0,production_activation=False,results=results)
 elif a.phase=='resume':
  _,before=c.store.read('TDCC');folder=before['qa_root'];results,requests=run(c,d,folder,rows)
  _,state=c.store.read('TDCC')
  if requests or any(t['status']!='RAW_BASIC_VERIFIED' or t['attempts']!=t['legacy_review']['attempts'] or t['materializations']!=1 or not t.get('storage_receipt') for t in state['tasks'].values()):raise ValueError('PROMOTION_COLD_RESUME_INVARIANT')
  evidence=[dict(key=k,period=t['definition']['period'],reference=t['raw_reference'],sha256=t['raw_sha256'],attempts=t['attempts'],materializations=t['materializations'],storage_receipt=t['storage_receipt']) for k,t in state['tasks'].items()]
  other=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/action-promotion-reuse-'+a.namespace),'TDCC');seed(other,rows);again,again_requests=run(other,d,folder,rows)
  _,reused=other.store.read('TDCC')
  if again_requests or any(not t.get('reused_existing') or t.get('materializations')!=0 or t['attempts']!=t['legacy_review']['attempts'] for t in reused['tasks'].values()):raise ValueError('CORRECT_DESTINATION_NOT_REUSED')
  report=dict(schema='JARVIS_PROMOTION_COLD_RESUME_V1',qa_copies_verified=len(evidence),source_requests=0,source_attempts_unchanged=True,evidence=evidence,existing_destination_reused=True,new_source_downloads=0,formal_raw_writes=0,production_activation=False,results=results,reuse_results=again)
 else:
  rows=samples.get('missing',[])
  if not rows:raise ValueError('NO_PROVEN_MISSING_ACTIONS_ADMITTED')
  if c.store.remote_head('TDCC')!=0:raise ValueError('FRESH_MISSING_ACTION_NAMESPACE_REQUIRED')
  folder=d.folder(REPORT,'ACTION_MISSING_QA_'+a.namespace);c.update(lambda s:s.update(qa_root=folder));results=[];requests=0;verified=[]
  for row in rows:
   seed(c,[row]);r,n=run(c,d,folder,[row],limit=1);results+=r;requests+=n;_,state=c.store.read('TDCC');verified=[dict(key=k,period=t['definition']['period'],reference=t.get('raw_reference'),sha256=t.get('raw_sha256'),attempts=t['attempts'],prior_attempts=t['legacy_review']['attempts'],storage_receipt=t.get('storage_receipt')) for k,t in state['tasks'].items() if t['status']=='RAW_BASIC_VERIFIED']
   c.update(lambda s:s.update(source_requests_total=requests))
   if verified or state.get('hold'):break
  report=dict(schema='JARVIS_AUTOMATIC_MISSING_ACTION_QA_V1',admitted_samples=len(rows),qa_downloaded_and_verified=len(verified),evidence=verified,source_requests=requests,formal_raw_writes=0,production_activation=False,results=results)
  (out/'automatic-missing.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
  if not verified:raise ValueError('NO_AUTOMATIC_MISSING_ACTION_VERIFIED')
 (out/(a.phase+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
