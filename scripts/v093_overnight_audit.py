"""Read-only live audit of old triggers and writer runs, including quarantined queue."""
import datetime,json,os,urllib.request
from pathlib import Path
KEEP={'v093-offline-tests.yml','v093-one-shot-acceptance.yml','jarvis-pause-handoff-20261029.yml','jarvis-source-control-live-preflight.yml'}
def main():
 base='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
 def api(path):
  req=urllib.request.Request(base+path,headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
  with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
 def pages(path,key):
  result=[]
  for page in range(1,100):
   rows=api(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))[key];result+=rows
   if len(rows)<100:return result
  raise RuntimeError('INCOMPLETE_AUDIT_PAGINATION')
 def legacy(obj):
  name=obj['path'].split('/')[-1]
  return name not in KEEP and not name.startswith('jarvis-seven-')
 workflows=[dict(id=w['id'],path=w['path'],state=w['state']) for w in pages('/actions/workflows','workflows') if legacy(w)]
 outstanding={}
 for status in ('queued','in_progress','waiting','pending','requested'):
  for run in pages('/actions/runs?status='+status,'workflow_runs'):
   if legacy(run):outstanding[run['id']]=dict(id=run['id'],status=run['status'],path=run['path'])
 ghost=None
 if 39611764652 in outstanding:
  jobs=api('/actions/runs/39611764652/jobs?per_page=100');ghost=dict(outstanding[39611764652],job_count=jobs['total_count'])
  if ghost['status']=='queued' and ghost['job_count']==0:del outstanding[39611764652]
 result=dict(schema='JARVIS_OVERNIGHT_LIVE_OLD_WRITER_AUDIT_V1',checked_at_taipei=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),workflows=workflows,active_old_triggers=[w for w in workflows if w['state']=='active'],outstanding_old_writers=list(outstanding.values()),quarantined_metadata=ghost,read_only=True,production_activation=False)
 result['passed']=not result['active_old_triggers'] and not outstanding
 Path('results').mkdir(exist_ok=True);Path('results/old-writer-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
 if not result['passed']:raise RuntimeError('OLD_WRITER_OR_TRIGGER_STILL_ACTIVE')
if __name__=='__main__':main()
