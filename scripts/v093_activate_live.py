"""One-shot enable/dispatch using the already recorded user authorization."""
import json,os,time,urllib.request,urllib.error
BASE='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
HEADERS={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json','Content-Type':'application/json'}
FILES=['v093-v2-01-raw.yml','v093-v2-02-qa.yml','v093-v2-03-price.yml','v093-v2-04-financial.yml','v093-v2-05-chip.yml']
def api(path,method='GET',data=None):
    req=urllib.request.Request(BASE+path,headers=HEADERS,method=method,data=json.dumps(data).encode() if data is not None else (b'' if method!='GET' else None))
    with urllib.request.urlopen(req,timeout=30) as response:
        raw=response.read();return json.loads(raw) if raw else {}
def workflows():
    result=[]
    for page in range(1,20):
        rows=api('/actions/workflows?per_page=100&page='+str(page))['workflows'];result.extend(rows)
        if len(rows)<100:return result
    raise RuntimeError('WORKFLOW_PAGINATION_OVERFLOW')
def main():
    chosen={'.github/workflows/'+f for f in FILES}
    own='.github/workflows/jarvis-start-live-five-v2-20261021.yml'
    for w in workflows():
        if w['state']=='active' and w['path'] not in chosen|{own}:api('/actions/workflows/'+str(w['id'])+'/disable','PUT')
    # Cancel only superseded orchestration and its still-unstarted dispatch.
    for runid in (39611726506,39611764652):
        run=api('/actions/runs/'+str(runid))
        if str(runid)==os.environ['GITHUB_RUN_ID'] or run['status']=='completed':continue
        if runid==39611764652 and api('/actions/runs/'+str(runid)+'/jobs')['jobs']:
            print('EXISTING_RAW_ALREADY_STARTED_PRESERVE_IT',flush=True);continue
        try:api('/actions/runs/'+str(runid)+'/cancel','POST')
        except urllib.error.HTTPError as exc:
            if exc.code!=409:raise
            print('SUPERSEDED_CANCEL_CONFLICT_PRESERVE_SAFE_CONCURRENCY '+str(runid),flush=True)
    for file in FILES:api('/actions/workflows/'+file+'/enable','PUT')
    enabled=[w['path'] for w in workflows() if w['state']=='active' and w['path']!=own]
    if set(enabled)!=chosen:raise RuntimeError('UNEXPECTED_ENABLED_WORKFLOWS:'+json.dumps(enabled))
    print('LIVE_FIVE_STAGE_ENABLED '+json.dumps({'enabled':enabled,'scope':'2026-10 descending to 2000-01','initial_execution':'DIRECT_REUSABLE_WORKFLOW_JOBS','numeric_verified':False,'pit_verified':False}),flush=True)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(json.dumps({'enabled':enabled},indent=2))
if __name__=='__main__':main()
