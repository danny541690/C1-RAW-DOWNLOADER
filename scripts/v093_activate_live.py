"""One-shot enable/dispatch using the already recorded user authorization."""
import json,os,time,urllib.request
BASE='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
HEADERS={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'}
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
    own='.github/workflows/jarvis-start-live-five-20261021.yml'
    for w in workflows():
        if w['state']=='active' and w['path'] not in chosen|{own}:api('/actions/workflows/'+str(w['id'])+'/disable','PUT')
    # Enable only RAW first; create its durable Drive control before consumer starts.
    results=[]
    for index,file in enumerate(FILES):
        api('/actions/workflows/'+file+'/enable','PUT')
        before={r['id'] for r in api('/actions/workflows/'+file+'/runs?per_page=30')['workflow_runs']}
        api('/actions/workflows/'+file+'/dispatches','POST',{'ref':'main','inputs':{'minutes':'8' if index==0 else '2'}})
        run=None
        for _ in range(180):
            rows=api('/actions/workflows/'+file+'/runs?per_page=30')['workflow_runs']
            matches=[r for r in rows if r['id'] not in before and r['event']=='workflow_dispatch']
            if matches:
                run=max(matches,key=lambda r:r['id']);print('LIVE_INITIAL_RUN '+json.dumps({k:run[k] for k in ('id','html_url','status','conclusion')}),flush=True)
                break
            time.sleep(5)
        if not run:raise RuntimeError('DISPATCH_NOT_OBSERVED:'+file)
        for _ in range(500):
            run=api('/actions/runs/'+str(run['id']))
            if run['status']=='completed':break
            time.sleep(5)
        if run['status']!='completed' or run['conclusion']!='success':raise RuntimeError('LIVE_WORKER_FAILED:'+json.dumps({k:run[k] for k in ('id','status','conclusion','html_url')}))
        results.append({k:run[k] for k in ('id','html_url','status','conclusion')})
    enabled=[w['path'] for w in workflows() if w['state']=='active' and w['path']!=own]
    if set(enabled)!=chosen:raise RuntimeError('UNEXPECTED_ENABLED_WORKFLOWS:'+json.dumps(enabled))
    print('LIVE_FIVE_STAGE_ENABLED '+json.dumps({'enabled':enabled,'initial_runs':results,'scope':'2026-10 descending to 2000-01','numeric_verified':False,'pit_verified':False}),flush=True)
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(json.dumps({'initial_runs':results,'enabled':enabled},indent=2))
    api('/actions/workflows/jarvis-start-live-five-20261021.yml/disable','PUT')
if __name__=='__main__':main()
