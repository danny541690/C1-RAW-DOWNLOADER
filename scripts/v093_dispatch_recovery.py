"""Reconcile a dispatched receiver only with terminal GitHub run evidence.

Never expires an unknown dispatch by age. Never modifies tasks or attempts.
"""
import json, re, urllib.request

PENDING = ('INTENT', 'SENT', 'UNKNOWN_RECONCILE_DISPATCH')

class ActionsEvidence:
 def __init__(self, repository, token):
  if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('REPOSITORY')
  self.base='https://api.github.com/repos/'+repository
  self.token=token
 def get(self,path,text=False):
  req=urllib.request.Request(self.base+path,headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json'})
  with urllib.request.urlopen(req,timeout=30) as response:
   raw=response.read().decode('utf-8')
  return raw if text else json.loads(raw)
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
  for run in runs:
   if run.get('conclusion') not in ('failure','cancelled','timed_out'):continue
   for page in range(1,4):
    jobs=self.get('/actions/runs/'+str(run['id'])+'/jobs?per_page=100&page='+str(page))['jobs']
    for job in jobs:
     if job.get('conclusion') not in ('failure','cancelled','timed_out'):continue
     log=self.get('/actions/jobs/'+str(job['id'])+'/logs',text=True)
     for identity in re.findall(r'CONTINUATION_ID:\s*([0-9a-f]{64})',log):
      if identity not in identities:continue
      # Check the same receiver again immediately before granting terminal evidence.
      current=self.get('/actions/runs/'+str(run['id']))
      if current['status']!='completed':return None
      if current.get('conclusion') not in ('failure','cancelled','timed_out'):continue
      found[identity]=dict(run_id=str(run['id']),run_attempt=current.get('run_attempt',1),conclusion=current['conclusion'],workflow=workflow)
    if len(jobs)<100:break
   if len(found)==len(identities):break
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
