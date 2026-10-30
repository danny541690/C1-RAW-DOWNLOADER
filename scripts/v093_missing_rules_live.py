"""Bounded real provider acceptance of generated rules, isolated from formal RAW.

Zero candidates is explicitly NOT_RUN, never a passed provider acceptance.
"""
import argparse,copy,json
from pathlib import Path
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_adapters import NativeAdapter
from scripts.v093_source_worker import run_batch
from scripts.v093_admission_runtime import prepare_row

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 import hashlib
 payload=Path('inputs/missing-rule-actions.data').read_bytes();index=json.loads(Path('inputs/missing-rule-action-index.json').read_text())
 if hashlib.sha256(payload).hexdigest()!=index['sha256']:raise ValueError('MISSING_RULE_INPUT_SHA')
 rows=json.loads(payload)['actions']
 if len(rows)!=index['count']:raise ValueError('MISSING_RULE_INPUT_COUNT')
 rows=sorted([r for r in rows if r['definition']['source']==a.source],key=lambda r:(r['definition']['period'],r['definition']['key']),reverse=True)
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/missing-rule-canary'),a.source,ttl=600)
 _,prior=c.store.read(a.source);tasks=(prior or {}).get('tasks',{});known=set(tasks)
 pending=[copy.deepcopy(t) for t in tasks.values() if t['status'] in ('READY','READY_CHECK','RETRY_WAIT','RECONCILE','REQUEST_INTENT','STORED','LEASED')]
 rows=pending[:2]+[r for r in rows if r['definition']['key'] not in known][:max(0,2-len(pending))]
 out=Path('results');out.mkdir(exist_ok=True)
 report=dict(schema='JARVIS_NATIVE_MISSING_RULE_CANARY_V1',source=a.source,selected=len(rows),source_requests=0,formal_raw_writes=0,production_activation=False,provider_acceptance='NOT_RUN_NO_ADMITTED_CANDIDATE',full_acceptance=False)
 if rows:
  d=Drive(service());folder=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','MISSING_RULE_CANARY_'+a.namespace+'_'+a.source)
  def seed(s):
   for row in rows:
    key=row['definition']['key']
    if key in s['tasks']:continue # Resume persisted attempts/save intent without reseeding.
    s['tasks'][key]=prepare_row(a.source,'DESC',key,row)
  c.update(seed);adapters=[]
  def factory(ticket,task):
   adapter=NativeAdapter(c,d,ticket,task,target_root=folder);adapters.append(adapter);return adapter
  batch=run_batch(c,factory,'DESC','rule-canary',max_units=2,seconds=240)
  _,state=c.store.read(a.source);evidence=[]
  for key in [r['definition']['key'] for r in rows]:
   t=state['tasks'][key]
   if t['attempts']<t['legacy_review']['attempts']:raise ValueError('CANARY_ATTEMPTS_DECREASED')
   if t['status']=='RAW_BASIC_VERIFIED':
    adapter=NativeAdapter(c,d,dict(source=a.source,key=key),t,target_root=folder);raw=adapter.read(t['raw_reference'])
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=t['raw_sha256'] or not t.get('storage_receipt',{}).get('readback_verified'):raise ValueError('CANARY_COLD_SHA_OR_SIDECAR')
    adapter.validate(raw)
   evidence.append(dict(key=key,status=t['status'],attempts=t['attempts'],prior_attempts=t['legacy_review']['attempts'],reference=t.get('raw_reference'),sha256=t.get('raw_sha256'),storage_receipt=t.get('storage_receipt'),error=t.get('error')))
  report.update(batch=batch,source_requests=sum(ad.source_requests for ad in adapters),evidence=evidence,provider_acceptance='BOUNDED_BASIC_VERIFIED' if any(t['status']=='RAW_BASIC_VERIFIED' for t in evidence) else 'HELD_OR_FAILED_NOT_ACCEPTED',long_run_acceptance=False)
 (out/'rule-canary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
 # Preserve classified holds, but do not call them provider acceptance.
if __name__=='__main__':main()
