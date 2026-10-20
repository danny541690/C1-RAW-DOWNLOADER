"""Start the feature lane independently after a safe legacy workflow handoff."""
import json,os,urllib.request
from scripts.v093_parallel_worker import main as run_lane

# These exact pre-split definitions still include an unisolated feature job.
LEGACY_HEADS={'e4b45f3edd0eca8666d043db694e6fd4b1758b67','bf5b4ae88be40a5996bf724d607ef54d41fc7c3d'}

def legacy_action(run,jobs):
    if run.get('head_sha') not in LEGACY_HEADS or run.get('status')=='completed':return 'IGNORE'
    if run['status'] in ('pending','queued') and not jobs:return 'CANCEL_WAITING_ONLY'
    if any(j.get('name')=='features' and j.get('status')!='completed' for j in jobs):return 'WAIT_FOR_FEATURE_WRITER'
    # An old queued definition with not-yet-created feature jobs is not safe to bypass.
    if run['status'] in ('pending','queued'):return 'WAIT_FOR_LEGACY_START'
    return 'IGNORE'

def main():
    repo=os.environ['GITHUB_REPOSITORY'];token=os.environ['GITHUB_TOKEN']
    def request(path,method='GET'):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=25) as response:
            data=response.read();return json.loads(data) if data else {}
    runs=request('/actions/workflows/v093-parallel-workers.yml/runs?per_page=30')['workflow_runs']
    blocked=False
    for run in runs:
        if run.get('head_sha') not in LEGACY_HEADS or run['status']=='completed':continue
        jobs=request('/actions/runs/'+str(run['id'])+'/jobs?per_page=100')['jobs']
        action=legacy_action(run,jobs)
        if action=='CANCEL_WAITING_ONLY':
            request('/actions/runs/'+str(run['id'])+'/cancel','POST')
            print(json.dumps({'migration':'CANCELLED_WAITING_LEGACY_DEFINITION','run_id':run['id']}),flush=True)
        elif action.startswith('WAIT_'):blocked=True
    if blocked:
        print(json.dumps({'status':'DEFERRED_FOR_LEGACY_FEATURE_WRITER'}),flush=True);return
    run_lane('features',25)

if __name__=='__main__':main()
