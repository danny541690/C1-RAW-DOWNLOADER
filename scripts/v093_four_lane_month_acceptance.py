"""Actual four-lane scheduler/CAS/Drive; bounded synthetic monthly transport.

Fixtures exercise orchestration, NOT market coverage or real historical values.
All writes stay below the per-run PRELAUNCH_SANDBOX; no official source calls.
"""
import argparse,collections,copy,datetime as dt,hashlib,json,pathlib,time,urllib.error,urllib.parse
from unittest.mock import patch
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_prelaunch_live_recovery import context,sandbox
from scripts import v093_official_repair as repair
from scripts import v093_repair_coordination as coord
from scripts import v093_five_stage_durable_gate as gate
from scripts.v093_raw_month_coordination import capture_history_month
from scripts.v093_replanned_five_stage import ArchiveCache

MONTHS={'EARLY_ASC':['2006-05','2006-06','2006-07'],
        'EARLY_DESC':['2006-07','2006-06','2006-05'],
        'RECENT_ASC':['2019-05','2019-06','2019-07'],
        'RECENT_DESC':['2019-07','2019-06','2019-05']}
def encoded(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()
def load(d,parent,name):
    raw=d.read(parent,name)
    return json.loads(raw) if raw else None
def existing_folder(d,parent,name):
    item=d.find(parent,name)
    if not item or item['mimeType']!='application/vnd.google-apps.folder':raise ValueError('SANDBOX_FOLDER_MISSING:'+name)
    return item['id']
def scope(d,run):return existing_folder(d,sandbox(d,run,create=False),'FOUR_LANE_MONTHS')
def fixture_jobs(month):
    first=dt.date.fromisoformat(month+'-01');days=[]
    while len(days)<2:
        if first.weekday()<5:days.append(first.isoformat())
        first+=dt.timedelta(days=1)
    return [dict(source='TWSE',category='prices_indices',period=day,month=month,
        url='https://www.twse.com.tw/exchangeReport/MI_INDEX?date='+day.replace('-',''),
        params=None,test_fixture=True) for day in days]
def fixture_payload(job):
    return encoded(dict(stat='OK',date=job['period'].replace('-',''),test_fixture=True,
        fields=['證券代號','開盤價','最高價','最低價','收盤價','成交股數','成交金額'],
        data=[['2330','100','105','95','102','1000','102000']]))

def seed(d,run,url,token):
    root=d.folder(sandbox(d,run,create=True),'FOUR_LANE_MONTHS')
    rawroot=d.folder(root,'RAW');payloadroot=d.folder(root,'SOURCE_PAYLOADS')
    sourceparent=d.folder(payloadroot,'TWSE')
    for lane in MONTHS:d.folder(root,lane)
    for month in sorted(set(sum(MONTHS.values(),[]))):
        ctrl=d.folder(rawroot,month);target=d.folder(sourceparent,month)
        job=fixture_jobs(month)[0];raw=fixture_payload(job);stats=repair.validate_content(raw,job)
        key=repair.engine.key(job)
        receipt=dict(job,unit_id=key,status='SAVED_BASIC_VERIFIED',sha256=repair.native.sha(raw),
                     rows=stats['rows'],codes_found=stats['codes'],bucket='units',numeric_verified=False,pit_verified=False)
        archive=repair.engine.packed([(receipt,raw)]);name='SYNTHETIC_'+repair.native.sha(archive)+'.zip'
        d.put(target,name,archive,'application/zip',overwrite=False);fid=d.find(target,name)['id']
        receipt.update(evidence_file=fid+'/'+key+'.raw',archive_sha256=repair.native.sha(archive))
        state=dict(month=month,units={key:receipt},financial_units={},finmind_units={},inventory={},stocks=['2330'],test_fixture=True)
        d.put(ctrl,'MONTH_STATE.json',encoded(state),'application/json',overwrite=False)
    for lane,months in MONTHS.items():
        allowed,_=coord.claim_month(url,token,lane,months[0])
        if not allowed:raise ValueError('INITIAL_FRONTIER_CLAIM_FAILED')
    d.put(root,'SCOPE.json',encoded(dict(months=MONTHS,test_fixture=True,production_gate='BLOCKED')),'application/json',overwrite=False)
    print('FOUR_MONTH_FLOW_SEED_PASS '+json.dumps({'test_parent_id':root,'synthetic_months':6,'production_writes':0}),flush=True)

class FlowWorker(repair.RepairWorker):
    """Actual run/capture_month/repair_one; override only sandbox routing and setup."""
    def revisit_parameter_incident(self):
        # This isolated fixture contains six synthetic months, no production June.
        return
    def __init__(self,d,root,url,token,run,lane):
        self.d=d;self.control=root;self.api=url;self.token=token;self.lane=lane
        self.direction=coord.LANES[lane][2];self.stage='RAW';self.phase='SYNTHETIC_MONTH_ACCEPTANCE'
        self.stagectrl=existing_folder(d,root,lane);self.payloadroot=existing_folder(d,root,'SOURCE_PAYLOADS')
        self.roots={s:None for s in ('RAW','QA1','PRICE','FINANCIAL','CHIP')};self.roots['RAW']=existing_folder(d,root,'RAW')
        self.owner=run+'/RAW';self.lock='SANDBOX_POOL_'+lane
        self.fence=gate.acquire(url,token,self.lock,self.owner,ttl=900)
        self.until=time.monotonic()+550;self.today=dt.date(2026,10,24);self.months=MONTHS[lane]
        self.cursor=load(d,self.stagectrl,'CURSOR.json') or dict(month_index=0,sweeps=0,direction=self.direction,test_fixture=True)
        self.pending_index=load(d,self.stagectrl,'RETRY_MONTHS.json') or {}
        self.cache=ArchiveCache();self.checked=self.repaired=self.downloaded=self.saved=self.processed=0
        self.circuit=collections.Counter();self.source_requests=collections.Counter();self.registry=type('Registry',(),{'flush':lambda self:None})()
    def owned(self):
        _,manifest=gate._read(self.api,self.token);lease=manifest['jobs'][self.lock].get('lease') or {}
        if lease.get('owner')!=self.owner or lease.get('fence')!=self.fence or lease.get('expires_at',0)<=time.time():
            raise gate.LeaseConflict('SANDBOX_STALE_OWNER')
    def restore(self,month,ctrl):
        self.active=month;self.monthctrl=ctrl;self.state=load(self.d,ctrl,'MONTH_STATE.json')
        if not self.state or self.state.get('month')!=month or self.state.get('test_fixture') is not True:raise ValueError('SANDBOX_STATE_SCOPE_MISMATCH')
    def folder(self,source,month):return existing_folder(self.d,existing_folder(self.d,self.payloadroot,source),month)

def worker(d,root,url,token,run,lane,phase):
    requests=0;iterations=1 if phase=='frontier' else 12
    for iteration in range(iterations):
        w=FlowWorker(d,root,url,token,run,lane)
        def transport(address,params=None):
            nonlocal requests
            query=urllib.parse.parse_qs(urllib.parse.urlparse(address).query)
            date=query['date'][0];period=date[:4]+'-'+date[4:6]+'-'+date[6:]
            requests+=1
            if phase=='frontier':raise urllib.error.HTTPError(address,429,'SYNTHETIC_LIMIT',{},None)
            return fixture_payload(dict(period=period))
        with patch.object(repair.native.Audit,'jobs',side_effect=lambda audit,m,closed:fixture_jobs(m)), \
             patch.object(repair.native,'request',side_effect=transport), \
             patch.object(repair,'RETRY_COOLDOWN_SECONDS',3):
            w.run()
        if phase=='frontier' or not any(s.get('retry_units') for s in w.pending_index.values()):break
        time.sleep(3.2)
    if phase=='resume' and any(s.get('retry_units') for s in w.pending_index.values()):raise ValueError('DUE_QUEUE_NOT_DRAINED')
    proof=dict(lane=lane,phase=phase,cursor=w.cursor,pending_index=w.pending_index,
        simulated_source_calls=requests,real_official_source_calls=0,test_fixture=True,
        production_data_writes=0,production_gate='BLOCKED')
    w.d.put(w.stagectrl,'FLOW_'+phase.upper()+'.json',encoded(proof),'application/json',overwrite=True)
    print('FOUR_MONTH_FLOW_WORKER_PASS '+json.dumps(proof),flush=True)

def verify(d,root,url,token,phase):
    _,manifest=gate._read(url,token);plan=manifest['jobs'][coord.PLAN]
    expected=set(sum(MONTHS.values(),[]))
    if set(plan['months'])!=expected:raise ValueError('MONTH_CLAIMS_MISSING_OR_EXTRA')
    for pair in (('EARLY_ASC','EARLY_DESC'),('RECENT_ASC','RECENT_DESC')):
        statuses=[plan['workers'][lane]['status'] for lane in pair]
        if statuses.count('PAUSED_AT_MEETING')!=1 or statuses.count('FRONTIERS_MET_RANGE_VISITED_NOT_CERTIFIED')!=1:
            raise ValueError('MEETING_DID_NOT_LEAVE_ONE_PAUSED_ONE_SURVIVOR:'+str(statuses))
    counts=collections.Counter();archives=0
    for month in sorted(expected):
        parent=existing_folder(d,existing_folder(d,root,'RAW'),month)
        state=load(d,parent,'MONTH_STATE.json');journal=load(d,parent,'OFFICIAL_REPAIR_STATE.json')
        jobs=fixture_jobs(month);keys={repair.engine.key(j) for j in jobs}
        if phase=='frontier':
            if not any(not r.get('complete') for r in journal['units'].values()):raise ValueError('SYNTHETIC_LIMIT_WAS_SILENTLY_CLOSED')
        else:
            if set(state['units'])!=keys or any(state['units'][k].get('status')!='SAVED_BASIC_VERIFIED' for k in keys):
                raise ValueError('SYNTHETIC_MONTH_NOT_SAVED:'+month)
            for k in keys:
                repair.cached_payload(d,state['units'][k],ArchiveCache())
                counts['saved_and_readback_verified_units']+=1
            if any(not r.get('complete') for r in journal['units'].values()):raise ValueError('DUE_MONTH_STILL_OPEN:'+month)
            payloadroot=existing_folder(d,root,'SOURCE_PAYLOADS')
            destination=existing_folder(d,existing_folder(d,payloadroot,'TWSE'),month)
            if not getattr(d,'test_memory_backend',False):
                files=repair.native.listing(d,destination)
                if len(files)!=2:raise ValueError('DUPLICATE_OR_ORPHAN_ARCHIVES:'+month)
        archives+=len(state['units'])
    for lane in MONTHS:
        parent=existing_folder(d,root,lane);proof=load(d,parent,'FLOW_'+phase.upper()+'.json')
        if not proof or proof['real_official_source_calls']!=0:raise ValueError('LANE_PROOF_MISSING')
        if phase=='resume' and any(s.get('retry_units') for s in proof['pending_index'].values()):raise ValueError('QUEUE_PROOF_NOT_DRAINED')
    live=not getattr(d,'test_memory_backend',False)
    result=dict(phase=phase,synthetic_months=6,frontiers=4,meeting_pairs=2,
        actual_github_cas=live,actual_drive_checkpoints=live,test_fixture=True,
        counts=dict(counts),receipt_count=archives,test_parent_id=root,
        production_data_writes=0,official_source_requests=0,production_gate='BLOCKED',
        limitation='Scheduler monthly fixtures only; not full-market historical coverage or source endpoint acceptance')
    d.put(root,'FLOW_VERIFY_'+phase.upper()+'.json',encoded(result),'application/json',overwrite=True)
    pathlib.Path('reports').mkdir(exist_ok=True);pathlib.Path('reports/four-month-flow-'+phase+'.json').write_bytes(encoded(result))
    print('FOUR_MONTH_FLOW_VERIFY_PASS '+json.dumps(result),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['seed','frontier','resume','verify-frontier','verify-resume']);p.add_argument('--lane',choices=tuple(MONTHS));a=p.parse_args()
    run,url,token=context();d=Drive(service());d.direct_readback=True
    if a.mode=='seed':seed(d,run,url,token);return
    root=scope(d,run)
    if a.mode.startswith('verify-'):verify(d,root,url,token,a.mode.split('-',1)[1])
    else:
        if not a.lane:raise ValueError('LANE_REQUIRED')
        worker(d,root,url,token,run,a.lane,a.mode)

if __name__=='__main__':main()
