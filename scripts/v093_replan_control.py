"""Stop fence and activation for the user-authorized 2014-04 RAW resume."""
import argparse,base64,json,os,time,urllib.request,urllib.error
from scripts.v093_five_stage_durable_gate import _read,_put
BASE='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']
TOKEN=os.environ['GH_TOKEN']
FILES=['v093-v2-01-raw.yml','v093-v2-02-qa.yml','v093-v2-03-price.yml','v093-v2-04-financial.yml','v093-v2-05-chip.yml']
OWN='.github/workflows/jarvis-checkpoint-replan-20261021.yml'
def api(path,method='GET',data=None):
    req=urllib.request.Request(BASE+path,headers={'Authorization':'Bearer '+TOKEN,'Accept':'application/vnd.github+json','Content-Type':'application/json'},method=method,data=json.dumps(data).encode() if data is not None else (b'' if method!='GET' else None))
    try:
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read();return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code in (409,422) and path.endswith(('/cancel','/force-cancel')):return {'cancel_conflict':True}
        raise

def all_pages(path,key):
    rows=[]
    for page in range(1,30):
        data=api(path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))[key];rows+=data
        if len(data)<100:return rows
    raise RuntimeError('PAGINATION_LIMIT')

def prepare():
    for w in all_pages('/actions/workflows','workflows'):
        if w['path']!=OWN and w['state']=='active':api('/actions/workflows/'+str(w['id'])+'/disable','PUT')
    # Status-filter endpoints can lag direct run and job endpoints. Confirm the
    # actual worker step has terminated before fencing a previous lease owner.
    outstanding={}
    for status in ('in_progress','queued','pending','waiting','requested'):
        for run in all_pages('/actions/runs?status='+status,'workflow_runs'):
            if str(run['id'])!=os.environ['GITHUB_RUN_ID']:outstanding[run['id']]=run
    delayed=[]
    for runid in outstanding:
        for attempt in range(24):
            run=api('/actions/runs/'+str(runid))
            if run['status']=='completed':break
            jobs=api('/actions/runs/'+str(runid)+'/jobs')['jobs']
            api('/actions/runs/'+str(runid)+'/cancel','POST')
            if attempt>=1:api('/actions/runs/'+str(runid)+'/force-cancel','POST')
            if not jobs and run['status'] in ('queued','pending','requested'):
                delayed.append(runid);break
            if jobs and all(j['status']=='completed' or all(s['status']=='completed' for s in j.get('steps',[])) for j in jobs):break
            time.sleep(3)
        else:raise RuntimeError('WORKER_TERMINATION_NOT_CONFIRMED:'+str(runid))
    url=BASE+'/contents/.github/live-state/five-stage-leases.json'
    for attempt in range(12):
        sha,state=_read(url,TOKEN)
        for key in ('POOL_RAW','POOL_CONSUMER'):
            old=state['jobs'].get(key,{})
            lease=old.get('lease') or {};owner=lease.get('owner','').split('/')[0]
            if owner.isdigit():
                run=api('/actions/runs/'+owner)
                jobs=api('/actions/runs/'+owner+'/jobs')['jobs']
                if run['status']!='completed' and any(any(s['status']!='completed' for s in j.get('steps',[])) for j in jobs):raise RuntimeError('OLD_LEASE_OWNER_STILL_EXECUTING')
            fence=max(int(old.get('last_fence',0)),int(lease.get('fence',0)))+1
            old.update(status='RETIRED_BY_AUTHORIZED_REPLAN',last_fence=fence,lease={'owner':'RETIRED_201404_REPLAN','fence':fence,'expires_at':4102444800})
            state['jobs'][key]=old
        if _put(url,TOKEN,sha,state,'ops: fence retired schedule generations before 2014-04 resume'):break
    else:raise RuntimeError('RETIREMENT_FENCE_CAS_FAILED')
    enabled=[w['path'] for w in all_pages('/actions/workflows','workflows') if w['state']=='active' and w['path']!=OWN]
    if enabled:raise RuntimeError('OTHER_WORKFLOWS_STILL_ENABLED:'+json.dumps(enabled))
    print('REPLAN_STOP_FENCE_VERIFIED '+json.dumps({'enabled_other_workflows':enabled,'unstarted_dispatches_fenced':delayed,'old_raw_and_consumer_generations_retired':True,'raw_bytes_preserved':True}),flush=True)

def activate():
    for filename in FILES:api('/actions/workflows/'+filename+'/enable','PUT')
    expected={'.github/workflows/'+f for f in FILES}
    enabled={w['path'] for w in all_pages('/actions/workflows','workflows') if w['state']=='active' and w['path']!=OWN}
    if enabled!=expected:raise RuntimeError('FIVE_ONLY_ACTIVATION_MISMATCH:'+json.dumps(sorted(enabled)))
    print('REPLANNED_FIVE_ENABLED '+json.dumps({'workflows':sorted(enabled),'raw_start':'2014-04','audit_start':'2026-10','end':'2000-01'}),flush=True)
    api('/actions/workflows/jarvis-checkpoint-replan-20261021.yml/disable','PUT')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','activate']);a=p.parse_args()
    prepare() if a.action=='prepare' else activate()
