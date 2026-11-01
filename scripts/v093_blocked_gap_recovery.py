"""Operator-reviewed one-shot recovery of existing blocked/missing tasks.

TPEx gets one normal request to the exact previously denied public report.
The original 403 hold is released only after RAW validation/save/readback.
MOPS only queries explicitly reviewed domestic historical missing keys.
All source requests use the existing coordinator, rate budget and attempt cap.
"""
import argparse,collections,copy,datetime as dt,json,re
from pathlib import Path
from scripts.v093_admission_runtime import load_release
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_official_followup import requery,reviewed_mops_route,NAMESPACE as FOLLOWUP
from scripts.v093_problem_recovery import load_rows,PLAN as ORIGINAL_PLAN

PLAN='config/v093_blocked_gap_recovery_20261101.json'

def valid_saved_result(result):
 receipt=(result or {}).get('storage_receipt') or {}
 return bool(result and result.get('status')=='RAW_BASIC_VERIFIED' and re.fullmatch('[0-9a-f]{64}',result.get('raw_sha256','')) and result.get('raw_reference') and receipt.get('readback_verified') is True and receipt.get('raw_sha256')==result['raw_sha256'] and receipt.get('raw_reference')==result['raw_reference'])

def settle_probe(shared,identity,result):
 probe=shared.get('hold_probe') or {}
 if probe.get('identity')!=identity:raise ValueError('PROBE_IDENTITY_CHANGED')
 released=valid_saved_result(result) and shared.get('hold') in (None,'HTTPError_403')
 if released:shared.pop('hold',None)
 elif not shared.get('hold'):shared['hold']=probe['previous_hold']
 shared['hold_probe_history']=dict(probe,completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),released=released,result_status=(result or {}).get('status','INTERRUPTED'))
 shared.pop('hold_probe',None)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',choices=('TPEx','MOPS'),required=True);args=parser.parse_args()
 root=Path.cwd();load_release(root);cfg=json.loads((root/PLAN).read_text());source=args.source;identity=cfg['identity'];target=cfg['targets'][source]
 store=GitCAS(root,'jarvis-source-preflight/'+identity);revision,journal=store.read(source);journal=journal or dict(source=source,tasks={},identity=identity)
 def checkpoint():
  nonlocal revision
  journal['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
  if not store.cas(source,revision,journal):raise ValueError('BLOCKED_RECOVERY_CHECKPOINT_CONFLICT')
  revision,_=store.read(source)
 if not journal.get('finished'):
  production=Coordinator(GitCAS(root),source,ttl=600)
  campaign=FOLLOWUP if source=='TPEx' else 'problem-recovery-20261031-v1'
  outcomes=GitCAS(root,'jarvis-source-preflight/'+campaign);out_rev,out_state=outcomes.read(source)
  original=json.loads((root/ORIGINAL_PLAN).read_text());rows={t['definition']['key']:t for t in load_rows(store,original,source)}
  from scripts.annual_actual_firstpass import Drive,service
  drive=Drive(service());follow_cfg=json.loads((root/'config/v093_official_followup_20261031.json').read_text())
  for key in target['keys']:
   if key in journal['tasks']:continue
   task=rows[key];prior=copy.deepcopy(out_state['tasks'][key]);_,shared=production.store.read(source)
   if prior['status']!='REVIEW_REQUIRED' or prior['attempts']>=4:
    journal['tasks'][key]=dict(status='SKIPPED_VERIFIED_OR_EXHAUSTED',attempts=prior['attempts']);checkpoint();continue
   if source=='MOPS':
    case=task['execution_contract']
    if case.get('mode')!='MISSING' or case.get('reference') or task.get('rejected_evidence'):raise ValueError('MOPS_REVIEWED_MISSING_SCOPE')
    reviewed_mops_route(case)
    if (shared or {}).get('hold'):
     journal['tasks'][key]=dict(status='SOURCE_HOLD_PRESERVED',hold=shared['hold']);checkpoint();continue
    proof=dict(kind='REVIEWED_MOPS_HISTORICAL_ROUTE',review_evidence=cfg['mops_route_review'],query_is_not_availability_proof=True)
   else:
    if journal.get('probe_started'):
     if (shared or {}).get('hold_probe',{}).get('identity')==identity:production.update(lambda s:settle_probe(s,identity,None))
     journal['tasks'][key]=dict(status='INTERRUPTED_PROBE_REQUIRES_RECONCILIATION');checkpoint();continue
    if (shared or {}).get('hold')!='HTTPError_403' or (shared or {}).get('cooldown_until',0)>production.clock():
     journal['tasks'][key]=dict(status='EXPECTED_HOLD_OR_COOLDOWN_CHANGED',hold=(shared or {}).get('hold'));checkpoint();continue
    journal['probe_started']=True;checkpoint()
    def begin(s):
     if s.get('hold')!='HTTPError_403' or s.get('hold_probe'):raise ValueError('PROBE_HOLD_CHANGED')
     s['hold_probe']=dict(identity=identity,key=key,previous_hold=s['hold'],started_at=journal['updated_at'],sent=False)
    production.update(begin)
    proof=dict(kind='OFFICIAL_ARCHIVED_HTML_ROUTE',raw_sha256=follow_cfg['tpex_archived_html']['query_page_sha256'],route=follow_cfg['tpex_archived_html'])
   result=None
   try:result=requery(root,source,task,prior,proof,drive)
   finally:
    if source=='TPEx':production.update(lambda s:settle_probe(s,identity,result))
   delta=result['attempts']-prior['attempts']
   if not 0<=delta<=1:raise ValueError('ONE_SHOT_REQUEST_LIMIT')
   result['reviewed_recovery_identity']=identity
   if source=='MOPS':
    result['source_requests']=prior.get('source_requests',0)+delta
    result['raw_writes']=prior.get('raw_writes',0)+int(valid_saved_result(result))
   out_state['tasks'][key]=result
   out_state['counts']=dict(collections.Counter(t['status'] for t in out_state['tasks'].values()))
   out_state['source_requests']=out_state.get('source_requests',0)+delta
   out_state['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
   out_state['all_issues_resolved']=out_state['counts'].get('REVIEW_REQUIRED',0)==0
   if source=='MOPS':
    out_state['source_requests']=sum(t.get('source_requests',0) for t in out_state['tasks'].values())
    out_state['raw_writes']=sum(t.get('raw_writes',0) for t in out_state['tasks'].values())
   if not outcomes.cas(source,out_rev,out_state):raise ValueError('RECOVERY_OUTCOME_CONFLICT')
   out_rev,_=outcomes.read(source)
   field='problem_followup' if source=='TPEx' else 'problem_recovery'
   def publish(s):
    summary=s[field][campaign];summary.update(counts=out_state['counts'],source_requests=out_state['source_requests'],updated_at=out_state['updated_at'],state_commit=out_rev)
    if source=='MOPS':summary['raw_writes']=out_state['raw_writes']
   production.update(publish)
   journal['tasks'][key]=dict(status=result['status'],reason=result.get('reason'),error=result.get('error'),attempts=result['attempts'],source_requests=delta,raw_reference=result.get('raw_reference'),raw_sha256=result.get('raw_sha256'),saved_readback_verified=valid_saved_result(result));checkpoint()
   if result.get('followup_terminal'):
    def clean(s):
     row=s['tasks'].get(key)
     if row and row.get('followup_repair')==FOLLOWUP and not row.get('owner'):del s['tasks'][key]
    production.update(clean)
  journal['finished']=True;checkpoint()
 Path('results').mkdir(exist_ok=True);Path('results/blocked-gap-recovery.json').write_text(json.dumps(journal,ensure_ascii=False,indent=2)+'\n');print(json.dumps(journal),flush=True)

if __name__=='__main__':main()
