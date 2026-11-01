"""Recheck pinned unresolved originals once per revision; never request a market source.

Completion describes this evidence review only. Unknown applicability, empty
responses, source limitations and unpromoted quarantine bytes remain open.
"""
import argparse,collections,copy,datetime as dt,json,time
from pathlib import Path
from scripts.v093_admission_runtime import load_release
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_official_followup import read_pin
from scripts.v093_problem_recovery import load_rows,recheck,PLAN as ORIGINAL_PLAN

PLAN='config/v093_unresolved_recheck_20261101.json'

def review(task,previous,plan,drive,cache):
 row=copy.deepcopy(task);row['attempts']=max(row['attempts'],previous['attempts'])
 result=recheck(row,plan,drive,cache)
 result.update(previous_reason=previous.get('reason'),previous_status=previous['status'],source_requests=0,raw_writes=0,request_attempts_preserved=previous['attempts'],reviewed_at=dt.datetime.now(dt.timezone.utc).isoformat())
 if result['status']=='REVIEW_REQUIRED':
  reason=result.get('reason','UNCLASSIFIED')
  if reason=='OFFICIAL_EMPTY_UNCONFIRMED':queue='OFFICIAL_CALENDAR_OR_COVERAGE_EVIDENCE_REQUIRED'
  elif reason=='HISTORICAL_ROUTE_OR_SOURCE_REVIEW':queue='HISTORICAL_ROUTE_OR_PARTITION_APPLICABILITY_REQUIRED'
  elif reason=='VALID_REJECTED_RAW_REQUIRES_PROMOTION':queue='VERIFIED_BYTES_REQUIRE_NATIVE_PROMOTION'
  else:queue='CONTENT_OR_STORAGE_DIAGNOSIS_REQUIRED'
  result['next_queue']=queue
 result.update(numeric_verified=False,pit_verified=False,full_acceptance=False)
 return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source',choices=('TWSE','MOPS'),required=True);parser.add_argument('--seconds',type=int,default=1800);args=parser.parse_args()
 root=Path.cwd();load_release(root);cfg=json.loads((root/PLAN).read_text());source=args.source;namespace=cfg['revision'];target=cfg['targets'][source]
 store=GitCAS(root,'jarvis-source-preflight/'+namespace);revision,state=store.read(source)
 if state and state.get('baseline_commit')!=target['commit']:raise ValueError('RECHECK_BASELINE_CHANGED')
 baseline=read_pin(store,target['commit'])
 previous={key:t for key,t in baseline['tasks'].items() if t['status']=='REVIEW_REQUIRED'}
 if len(previous)!=target['unresolved']:raise ValueError('RECHECK_UNRESOLVED_SCOPE_CHANGED')
 state=state or dict(source=source,tasks={},baseline_commit=target['commit'],revision=namespace,review_complete=False)
 original=json.loads((root/ORIGINAL_PLAN).read_text());started=time.monotonic()
 def checkpoint():
  nonlocal revision
  state.update(counts=dict(collections.Counter(t['status'] for t in state['tasks'].values())),reason_counts=dict(collections.Counter(t.get('reason','BASIC_VERIFIED') for t in state['tasks'].values())),updated_at=dt.datetime.now(dt.timezone.utc).isoformat(),source_requests=0,raw_writes=0)
  state['review_complete']=len(state['tasks'])==len(previous)
  state['all_issues_resolved']=state['review_complete'] and not any(t['status']=='REVIEW_REQUIRED' for t in state['tasks'].values())
  if not store.cas(source,revision,state):raise ValueError('RECHECK_CHECKPOINT_CONFLICT')
  revision,_=store.read(source)
  summary={key:state[key] for key in ('revision','review_complete','all_issues_resolved','counts','reason_counts','updated_at','source_requests','raw_writes')}
  summary.update(targets=len(previous),reviewed=len(state['tasks']),state_commit=revision,full_acceptance=False)
  Coordinator(GitCAS(root),source).update(lambda s:s.setdefault('problem_recheck',{}).update({namespace:summary}))
  print(json.dumps(summary),flush=True)
 if not state.get('review_complete'):
  from scripts.annual_actual_firstpass import Drive,service
  drive=Drive(service());cache={};rows=load_rows(store,original,source);since_save=0
  for task in rows:
   key=task['definition']['key']
   if key not in previous or key in state['tasks']:continue
   if time.monotonic()-started>args.seconds:break
   state['tasks'][key]=review(task,previous[key],original,drive,cache);since_save+=1
   if since_save>=10:checkpoint();since_save=0
 checkpoint()
 Path('results').mkdir(exist_ok=True);Path('results/unresolved-recheck.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
