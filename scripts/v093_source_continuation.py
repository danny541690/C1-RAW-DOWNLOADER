"""Guarded production continuation and watchdog transport over the durable outbox.

Never activates a release. The same complete-manifest and code-fingerprint gates
used by the production worker run before any catalog, source state or dispatch.
"""
import json,os,re
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_admission_runtime import Catalog,stage,load_release
from scripts.v093_workflow_dispatch import WorkflowDispatch
from scripts.v093_dispatch_recovery import reconcile_pending

def acknowledge(c,slot,identity,run_id):
 if not identity:return True # Explicit initial start remains guarded by release + leases.
 if not re.fullmatch('[0-9a-f]{64}',identity):raise ValueError('CONTINUATION_IDENTITY')
 def change(state):
  entry=state.get('outbox',{}).get(identity)
  if not entry or entry.get('slot')!=slot:raise ValueError('CONTINUATION_OUTBOX_BINDING')
  if entry.get('status')=='RECEIVED':return entry.get('received_run_id')==run_id
  if entry.get('status') not in ('INTENT','SENT','UNKNOWN_RECONCILE_DISPATCH'):raise ValueError('CONTINUATION_OUTBOX_STATUS')
  entry.update(status='RECEIVED',received_run_id=run_id);return True
 return c.update(change)

def continue_slot(root,c,catalog,slot,run_id,dispatch):
 _,state=c.store.read(c.source)
 if state and (state.get('hold') or state.get('cooldown_until',0)>c.clock()):return False
 if any(e.get('status') in ('INTENT','SENT','UNKNOWN_RECONCILE_DISPATCH') for e in (state or {}).get('outbox',{}).values()):return False
 cursor=(state or {}).get('admission',{}).get(slot,{})
 if cursor.get('finished'):return False
 stage(c,catalog,limit=32) # Persist the next chunk before any dispatch intent.
 return c.dispatch_after_save(slot,run_id,dispatch)

def transport(root,source,slot,token):
 design=json.loads((root/'config/v093_seven_source_design.json').read_text())
 entries=[x for x in design['slots'] if x['source']==source and x['direction']==slot]
 if len(entries)!=1:raise ValueError('CONTINUATION_SLOT_BINDING')
 return WorkflowDispatch(os.environ['GITHUB_REPOSITORY'],entries[0]['workflow'],'main',token,dict(mode='production'))

def continuation_target(state,directions,current):
 for slot in directions:
  if slot!=current and not state.get('admission',{}).get(slot,{}).get('finished',False):return slot
 return current

def recover_source(root,c,directions,workflows,api,run_id,token):
 # A controller never competes with either direction's live source writer.
 if any(any(r['status']!='completed' for r in api.runs(workflows[slot])) for slot in directions):
  return [dict(source=c.source,slot=slot,recovery='ACTIVE_SOURCE_WORKER',continuation_sent=False) for slot in directions]
 rows=[]
 for slot in directions:
  recovery=reconcile_pending(c,slot,workflows[slot],api)
  rows.append(dict(source=c.source,slot=slot,recovery=recovery,continuation_sent=False))
 # Reconcile both directions before waking one, giving failed receivers priority.
 for row in sorted(rows,key=lambda r:r['recovery']!='RECONCILED_TERMINAL'):
  if row['recovery'] not in ('CLEAR','RECONCILED_TERMINAL'):continue
  slot=row['slot'];catalog=Catalog(c.store,directions[slot],c.source,slot)
  row['continuation_sent']=continue_slot(root,c,catalog,slot,run_id,transport(root,c.source,slot,token))
  if row['continuation_sent']:break
 return rows

def main():
 root=Path.cwd();release=load_release(root);token=os.environ['GH_TOKEN'];results=[]
 from scripts.v093_dispatch_recovery import ActionsEvidence,reconcile_pending
 bindings_path=root/'config/v093_legacy_receiver_bindings.json'
 bindings=json.loads(bindings_path.read_text()) if bindings_path.exists() else {}
 api=ActionsEvidence(os.environ['GITHUB_REPOSITORY'],token,bindings,fence_unacknowledged=True)
 design=json.loads((root/'config/v093_seven_source_design.json').read_text())
 for source,directions in release['catalogs'].items():
  try:
   c=Coordinator(GitCAS(root),source,ttl=600)
   workflows={slot:next(x['workflow'] for x in design['slots'] if x['source']==source and x['direction']==slot) for slot in directions}
   results.extend(recover_source(root,c,directions,workflows,api,'watchdog-'+os.environ['GITHUB_RUN_ID'],token))
  except Exception as exc:
   for slot in directions:
    results.append(dict(source=source,slot=slot,error=type(exc).__name__+(':'+str(exc) if str(exc).startswith('ACTIONS_HTTP_') else ''),continuation_sent=False))
 Path('results').mkdir(exist_ok=True);Path('results/watchdog.json').write_text(json.dumps(dict(slots=results,source_requests=0))+'\n')
 print(json.dumps(dict(slots=results,source_requests=0)),flush=True)
 if any('error' in r for r in results):raise RuntimeError('RECOVERY_SLOT_ERRORS_SEE_DECISIONS')
if __name__=='__main__':main()
