"""Actual prelaunch crash/recovery tests, restricted to a per-run sandbox.

Writes a GitHub test manifest and tiny Drive test payload. Never calls capture,
STANDARD writers, release publication or production scheduling.
"""
import argparse,base64,concurrent.futures,hashlib,json,os,pathlib,subprocess,sys,threading,time,urllib.request
from unittest.mock import patch
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_standard_r1 import C1
from scripts.v093_isolated_guarded_drive_adapter import guarded_put
from scripts import v093_five_stage_durable_gate as gate

PAYLOAD=b'JARVIS isolated prelaunch crash recovery probe v1\n'

def context():
    run=os.environ['GITHUB_RUN_ID']
    if not run.isdigit():raise ValueError('INVALID_SANDBOX_RUN')
    url='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/contents/.github/test-state/prelaunch-'+run+'.json'
    return run,url,os.environ['GH_TOKEN']

def sandbox(d,run,create=False):
    parent=C1
    for name in ('05_CONTROL','PRELAUNCH_SANDBOX',run):
        if create:parent=d.folder(parent,name)
        else:
            item=d.find(parent,name)
            if not item or item['mimeType']!='application/vnd.google-apps.folder':raise ValueError('SANDBOX_MISSING')
            parent=item['id']
    return parent

def main(mode):
    run,url,token=context()
    if mode=='seed':
        body={'message':'test: seed isolated prelaunch recovery manifest','content':base64.b64encode(b'{"jobs":{}}').decode()}
        req=urllib.request.Request(url,method='PUT',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.status!=201:raise ValueError('SANDBOX_SEED_FAILED')
        print('ISOLATED_RECOVERY_SEED_PASS',flush=True);return
    if mode=='crash-child':
        d=Drive(service());parent=sandbox(d,run,create=True)
        # Kill the process after the actual immutable Drive write/readback,
        # immediately before the actual GitHub manifest commit.
        with patch('scripts.v093_isolated_guarded_drive_adapter.commit',side_effect=lambda *a,**kw:os._exit(23)):
            guarded_put(d,parent,'probe',PAYLOAD,url,token,run+'-crashed',ttl=3)
        raise AssertionError('CRASH_NOT_INJECTED')
    if mode=='crash':
        result=subprocess.run([sys.executable,'-m','scripts.v093_prelaunch_live_recovery','crash-child'],timeout=180)
        if result.returncode!=23:raise ValueError('UNEXPECTED_CHILD_EXIT_'+str(result.returncode))
        _,state=gate._read(url,token)
        row=state['jobs']['probe']
        if row.get('status') or not row.get('lease'):raise ValueError('CRASH_DID_NOT_LEAVE_PENDING_LEASE')
        d=Drive(service());parent=sandbox(d,run)
        name='probe_'+hashlib.sha256(PAYLOAD).hexdigest()+'.bin'
        if d.read(parent,name)!=PAYLOAD:raise ValueError('ORPHAN_BYTES_MISSING')
        print('ACTUAL_PROCESS_CRASH_AFTER_DRIVE_READBACK_PASS',flush=True);return
    if mode!='resume':raise ValueError('INVALID_MODE')
    started=time.monotonic();_,state=gate._read(url,token)
    # Use the real wall clock; wait only for the bounded test lease, never
    # backdate a production lease to manufacture a takeover.
    wait=max(0,state['jobs']['probe']['lease']['expires_at']-int(time.time())+1)
    if wait>5:raise ValueError('UNEXPECTED_SANDBOX_LEASE_DURATION')
    if wait:time.sleep(wait)
    d=Drive(service());parent=sandbox(d,run)
    result=guarded_put(d,parent,'probe',PAYLOAD,url,token,run+'-resumed',ttl=60)
    if result['fence']!=2:raise ValueError('TAKEOVER_FENCE_NOT_INCREMENTED')
    try:gate.commit(url,token,'probe',run+'-crashed',1,hashlib.sha256(PAYLOAD).hexdigest())
    except gate.LeaseConflict:pass
    else:raise AssertionError('STALE_OWNER_ACCEPTED')
    again=guarded_put(d,parent,'probe',PAYLOAD,url,token,run+'-resumed',ttl=60)
    if again['fence']!=3 or again['name']!=result['name']:raise ValueError('FENCE_RESET_OR_NONIDEMPOTENT_NAME')
    _,state=gate._read(url,token)
    if state['jobs']['probe'].get('certified') is not False:raise ValueError('PREMATURE_CERTIFICATION')
    # Force both real GitHub readers to see the same CAS version before either
    # writer can act. Only the read scheduling is synchronized, not storage.
    original=gate._read;barrier=threading.Barrier(2);local=threading.local()
    def synchronized_read(*args):
        answer=original(*args)
        if not getattr(local,'read_once',False):
            local.read_once=True;barrier.wait(timeout=45)
        return answer
    def contender(owner):
        try:return owner,gate.acquire(url,token,'collision',owner,ttl=60)
        except gate.LeaseBusy:return owner,None
    with patch.object(gate,'_read',side_effect=synchronized_read),concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        attempts=list(pool.map(contender,[run+'-a',run+'-b']))
    winners=[x for x in attempts if x[1] is not None]
    if len(winners)!=1:raise ValueError('CAS_COLLISION_MULTIPLE_OR_NO_WINNERS')
    owner,fence=winners[0]
    gate.commit(url,token,'collision',owner,fence,hashlib.sha256(b'collision').hexdigest())
    proof={'actual_process_crash':True,'actual_cross_job_resume':True,'real_wall_clock_expiry':True,
           'actual_github_cas_collision_winners':len(winners),'fences':[2,3],
           'immutable_payload_readback':d.read(parent,result['name'])==PAYLOAD,
           'elapsed_resume_seconds':round(time.monotonic()-started,3),
           'test_namespace':'per-run PRELAUNCH_SANDBOX and GitHub test-state',
           'production_data_writes':0,'production_schedules_changed':False,'certified':False,
           'limitation':'Sandbox adapter recovery only; five production stage paths remain unconnected.'}
    if not proof['immutable_payload_readback']:raise ValueError('FINAL_READBACK_FAILED')
    pathlib.Path('reports').mkdir(exist_ok=True)
    pathlib.Path('reports/live-recovery.json').write_text(json.dumps(proof,indent=2)+'\n')
    print('LIVE_SANDBOX_CRASH_RECOVERY_AND_CAS_PASS '+json.dumps(proof,sort_keys=True),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['seed','crash-child','crash','resume'])
    main(parser.parse_args().mode)
