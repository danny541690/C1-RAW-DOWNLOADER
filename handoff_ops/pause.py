"""Pause legacy triggers, drain existing runs and freeze durable handoff evidence."""
import datetime,json,os,time,urllib.request,urllib.error,hashlib,gzip,subprocess
from pathlib import Path
OUT=Path('handoff');OUT.mkdir(exist_ok=True)
BASE='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
SELF=int(os.environ['GITHUB_RUN_ID'])
KEEP={'v093-offline-tests.yml','v093-one-shot-acceptance.yml','jarvis-pause-handoff-20261029.yml','jarvis-source-control-live-preflight.yml'}
def api(path,method='GET',data=None):
 req=urllib.request.Request(BASE+path,method=method,data=json.dumps(data).encode() if data is not None else None,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as r:
  b=r.read();return json.loads(b) if b else {}
def pages(path,key):
 out=[]
 for page in range(1,100):
  rows=api(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page));rows=rows[key] if key else rows
  out.extend(rows)
  if len(rows)<100:return out
 raise RuntimeError('PAGINATION_NOT_COMPLETE')
def write(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def legacy(w):
 name=w['path'].split('/')[-1]
 return name not in KEEP and not name.startswith('jarvis-seven-')
def outstanding():
 rows=[]
 for status in ('queued','in_progress','waiting','pending','requested'):
  rows.extend(pages('/actions/runs?status='+status,'workflow_runs'))
 return {r['id']:r for r in rows if r['id']!=SELF and legacy(r)}
def freeze():
 refs=api('/git/matching-refs/heads/')
 write('git_refs.json',refs)
 return refs
def main():
 workflows=pages('/actions/workflows','workflows');write('workflows_before.json',workflows)
 write('runs_before.json',list(outstanding().values()));freeze()
 disabled=[]
 for w in workflows:
  if legacy(w) and w['state']=='active':
   api('/actions/workflows/'+str(w['id'])+'/disable','PUT');disabled.append(w['id'])
 write('disabled_workflow_ids.json',disabled)
 # Cancel jobs that have not started. Running writers retain their normal save/finalize path.
 initial=outstanding()
 for rid,r in initial.items():
  if r['status']!='in_progress':
   try:api('/actions/runs/'+str(rid)+'/cancel','POST')
   except urllib.error.HTTPError as e:
    if e.code not in (409,422):raise
 deadline=time.monotonic()+65*60
 while True:
  active=outstanding();write('runs_remaining.json',list(active.values()))
  print('DRAIN_REMAINING',list(active),flush=True)
  if not active:break
  if time.monotonic()>deadline:raise RuntimeError('WRITERS_NOT_DRAINED_NO_FINAL_HANDOFF')
  time.sleep(20)
 remaining=pages('/actions/workflows','workflows');write('workflows_after.json',remaining)
 if any(legacy(w) and w['state']=='active' for w in remaining):raise RuntimeError('LEGACY_TRIGGER_ACTIVE')
 terminal=[api('/actions/runs/'+str(rid)) for rid in initial];write('drained_runs.json',terminal)
 freeze()
 write('freeze.json',dict(schema='JARVIS_LEGACY_DRAIN_V1',frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),run_id=SELF,old_triggers_disabled=True,old_writers_remaining=0,market_requests=0,new_schedules_started=False))
 print('LEGACY_DRAIN_COMPLETE',flush=True)
if __name__=='__main__':main()
