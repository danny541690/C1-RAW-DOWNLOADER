"""Repair only the isolated QA source hold caused by a truncated FETCH response."""
import json,time
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS

def reclassify(state,now):
 if state.get('hold')!='IncompleteRead':return 0
 tasks=state.get('tasks',{})
 if any(t.get('owner') for t in tasks.values()):raise ValueError('TRUNCATION_RECLASSIFY_ACTIVE_OWNER')
 held=[t for t in tasks.values() if t['status']=='SOURCE_HOLD']
 if not held or any(t.get('error')!=dict(phase='FETCH',code='IncompleteRead') or t.get('save_intent') or t.get('raw_reference') for t in held):raise ValueError('TRUNCATION_RECLASSIFY_AMBIGUOUS_HOLD')
 for task in held:
  attempts=task['attempts']
  if type(attempts) is not int or not 1<=attempts<=4:raise ValueError('TRUNCATION_RECLASSIFY_ATTEMPTS')
  task.update(status='BLOCKED' if attempts>=4 else 'RETRY_WAIT',next_at=now+60,reclassification=dict(reason='TRUNCATED_FETCH_IS_TRANSIENT_NO_SAVED_RAW',attempts_preserved=attempts))
 state.pop('hold',None);return len(held)

def main():
 c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/missing-rule-canary'),'TPEx')
 _,state=c.store.read('TPEx')
 count=c.update(lambda s:reclassify(s,time.time())) if state and state.get('hold')=='IncompleteRead' else 0
 report=dict(schema='JARVIS_TRUNCATED_QA_FETCH_RECLASSIFICATION_V1',tasks_reclassified=count,source_requests=0,attempts_reset=False,formal_raw_writes=0,production_activation=False)
 Path('results').mkdir(exist_ok=True);Path('results/truncation-reclassification.json').write_text(json.dumps(report)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
