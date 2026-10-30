"""Reconcile a dispatched receiver only with terminal GitHub run evidence.

Never expires an unknown dispatch by age. Never modifies tasks or attempts.
"""
import json, re, requests

PENDING = ('INTENT', 'SENT', 'UNKNOWN_RECONCILE_DISPATCH')

class ActionsEvidence:
 def __init__(self, repository, token,bindings=None,fence_unacknowledged=False):
  if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('REPOSITORY')
  self.base='https://api.github.com/repos/'+repository
  self.token=token
  self.bindings=bindings or {}
  self.fence_unacknowledged=fence_unacknowledged
 def get(self,path,text=False):
  response=requests.get(self.base+path,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json'},timeout=30)
  if response.status_code>=400:raise RuntimeError('ACTIONS_HTTP_'+str(response.status_code)+'_'+('LOGS' if path.endswith('/logs') else 'METADATA'))
  return response.text if text else response.json()

 def runs(self,workflow):
  # Bounded history; absence is never proof that a dispatch did not arrive.
  rows=[]
  for page in range(1,4):
   batch=self.get('/actions/workflows/'+workflow+'/runs?branch=main&event=workflow_dispatch&per_page=100&page='+str(page))['workflow_runs']
   rows.extend(batch)
   if len(batch)<100:break
  return rows
 def terminal_receivers(self,workflow,identities):
  runs=self.runs(workflow)
  if any(r['status']!='completed' for r in runs):return None
  found={}
  if not identities:return found
  legacy_scans=0
  for run in runs:
   if run.get('conclusion') not in ('failure','cancelled','timed_out'):continue
   candidates=re.findall(r'production \| ([0-9a-f]{64})',run.get('display_title',''))
   binding=self.bindings.get(str(run['id']),{})
   if binding.get('workflow')==workflow and binding.get('verified_job_id'):
    candidates.append(binding.get('identity',''))
   if not candidates and legacy_scans<3 and not self.fence_unacknowledged:
    legacy_scans+=1
    jobs=self.get('/actions/runs/'+str(run['id'])+'/jobs?per_page=100&page=1')['jobs']
    for job in jobs:
     if job.get('conclusion') not in ('failure','cancelled','timed_out'):continue
     try:log=self.get('/actions/jobs/'+str(job['id'])+'/logs',text=True)
     except (RuntimeError,requests.RequestException):continue # Missing logs are not evidence.
     candidates.extend(re.findall(r'CONTINUATION_ID:\s*([0-9a-f]{64})',log))
   for identity in candidates:
    if identity not in identities:continue
    current=self.get('/actions/runs/'+str(run['id']))
    if current['status']!='completed':return None
    if current.get('conclusion') not in ('failure','cancelled','timed_out'):continue
    found[identity]=dict(run_id=str(run['id']),run_attempt=current.get('run_attempt',1),conclusion=current['conclusion'],workflow=workflow)
   if len(found)==len(identities):break
  if self.fence_unacknowledged:
   for identity in identities-set(found):
    found[identity]=dict(run_id=None,workflow=workflow,disposition='NO_ACTIVE_RECEIVER_IDENTITY_RETIRED')
  return found

def reconcile_pending(c,slot,workflow,api):
 _,state=c.store.read(c.source)
 pending={k:dict(v) for k,v in (state or {}).get('outbox',{}).items() if v.get('slot')==slot and v.get('status') in PENDING}
 # Even without a pending outbox, an active runner must not get a duplicate wakeup.
 evidence=api.terminal_receivers(workflow,set(pending))
 if evidence is None:return 'ACTIVE_RECEIVER'
 if not pending:return 'CLEAR'
 if set(evidence)!=set(pending):return 'UNKNOWN_RECEIVER_REQUIRES_RECONCILIATION'
 def change(s):
  # Preserve live leases and fail closed if another controller changed an entry.
  if any(t['definition']['slot']==slot and t.get('owner') and t.get('expires',0)>c.clock() for t in s.get('tasks',{}).values()):return 'ACTIVE_LEASE'
  if any(s.get('outbox',{}).get(k)!=v for k,v in pending.items()):return 'STATE_CHANGED'
  recovery=s.setdefault('dispatch_recovery',{}).setdefault(slot,dict(attempts=0))
  if recovery['attempts']>=4:return 'DISPATCH_RECOVERY_LIMIT'
  recovery['attempts']+=1
  for k in pending:s['outbox'][k].update(status='RESOLVED_TERMINAL',terminal_receiver=evidence[k])
  return 'RECONCILED_TERMINAL'
 return c.update(change)
