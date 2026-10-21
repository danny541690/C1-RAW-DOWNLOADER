"""Move four consumers from a shared lease to independent stage leases."""
import json, os, time
from scripts.v093_replan_control import api, all_pages, BASE, TOKEN
from scripts.v093_five_stage_durable_gate import _read, _put

CONSUMERS=['v093-v2-02-qa.yml','v093-v2-03-price.yml','v093-v2-04-financial.yml','v093-v2-05-chip.yml']
STAGES=('QA1','PRICE','FINANCIAL','CHIP')
OWN='jarvis-parallel-four-30m-20261022.yml'

def main():
    request=json.load(open('requests/V093_FIVE_STAGE_202610_TO_200001_20261021.json'))
    plan=request['execution_plan']
    assert request['activation_authorized'] and not request['execution_control']['paused']
    assert plan['parallelism']=='ONE_WORKER_PER_STAGE_FIVE_INDEPENDENT_POOLS'
    paths={'.github/workflows/'+f for f in CONSUMERS}
    for filename in CONSUMERS:api('/actions/workflows/'+filename+'/disable','PUT')
    pending={}
    for status in ('in_progress','queued','pending','waiting','requested'):
        for run in all_pages('/actions/runs?status='+status,'workflow_runs'):
            if run['path'].split('@')[0] in paths:pending[run['id']]=run
    for runid in pending:
        for attempt in range(60):
            run=api('/actions/runs/'+str(runid))
            if run['status']=='completed':break
            api('/actions/runs/'+str(runid)+'/cancel','POST')
            if attempt>=2:api('/actions/runs/'+str(runid)+'/force-cancel','POST')
            jobs=api('/actions/runs/'+str(runid)+'/jobs')['jobs']
            if jobs and all(j['status']=='completed' for j in jobs):break
            if not jobs and run['status'] in ('queued','pending','requested'):
                # These pinned old workers cannot acquire the retired shared lease.
                old=api('/contents/config/v093_execution_plan_20261021.json?ref='+run['head_sha'])
                import base64
                oldplan=json.loads(base64.b64decode(old['content']))
                if not oldplan.get('stage_lease_suffix'):break
            time.sleep(2)
        else:raise RuntimeError('OLD_CONSUMER_NOT_STOPPED:'+str(runid))
    url=BASE+'/contents/.github/live-state/five-stage-leases.json'
    for attempt in range(12):
        sha,state=_read(url,TOKEN)
        old=state['jobs'].setdefault('POOL_CONSUMER'+plan['lease_suffix'],{})
        lease=old.get('lease') or {};owner=lease.get('owner','').split('/')[0]
        if owner.isdigit():
            run=api('/actions/runs/'+owner)
            jobs=api('/actions/runs/'+owner+'/jobs')['jobs']
            if run['status']!='completed' and (not jobs or any(j['status']!='completed' for j in jobs)):
                raise RuntimeError('SHARED_CONSUMER_OWNER_STILL_EXECUTING')
        fence=max(old.get('last_fence',0),lease.get('fence',0))+1
        old.update(last_fence=fence,status='RETIRED_SHARED_CONSUMER',lease={'owner':'RETIRED_PARALLEL_20261022','fence':fence,'expires_at':4102444800})
        for stage in STAGES:
            key='POOL_CONSUMER'+plan['stage_lease_suffix'][stage]
            row=state['jobs'].setdefault(key,{'last_fence':0,'lease':None,'certified':False})
            if row.get('lease'):raise RuntimeError('NEW_STAGE_ALREADY_OWNED:'+stage)
        state['parallel_cutover']={'status':'READY','authorized_by':plan['authorized_by'],'run_id':os.environ['GITHUB_RUN_ID'],'raw_lease_preserved':True,'old_consumers_stopped':sorted(pending)}
        if _put(url,TOKEN,sha,state,'ops: retire shared consumer lease and enable independent stage leases'):break
    else:raise RuntimeError('PARALLEL_CUTOVER_CAS_FAILED')
    for filename in CONSUMERS:api('/actions/workflows/'+filename+'/enable','PUT')
    enabled={w['path'] for w in all_pages('/actions/workflows','workflows') if w['state']=='active' and w['path']!='.github/workflows/'+OWN}
    expected=paths|{'.github/workflows/v093-v2-01-raw.yml'}
    if enabled!=expected:raise RuntimeError('EXPECTED_FIVE_ONLY:'+json.dumps(sorted(enabled)))
    print('PARALLEL_FOUR_30M_ENABLED '+json.dumps({'enabled':sorted(enabled),'budgets':plan['worker_budgets_minutes'],'global_two_worker_cap':False,'raw_checkpoint_reset':False,'old_consumers_stopped':sorted(pending)}),flush=True)
    for filename,stage in zip(CONSUMERS,STAGES):
        api('/actions/workflows/'+filename+'/dispatches','POST',{'ref':'main','inputs':{'minutes':'30'}})
        print('PARALLEL_STAGE_DISPATCHED '+stage,flush=True)
    api('/actions/workflows/'+OWN+'/disable','PUT')

if __name__=='__main__':main()
