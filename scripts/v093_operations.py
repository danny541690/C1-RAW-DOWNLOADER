"""Single operational entry point for status, targeted repair and daily shadow.

All callers use one GitHub concurrency group. Older staging never becomes approval.
"""
import argparse,datetime as dt,json,os,urllib.request
import hashlib
from scripts.v093_standard_r1 import Drive,service,C1,folder,ls
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r4 import run as repair,VERSION
from scripts.v093_daily_shadow import capture,target_day
from scripts.v093_feature_shadow import pilot

R3_WORKFLOW='v093-layer02-r3-2025-2026.yml'

def github_jobs():
    token=os.environ.get('GITHUB_TOKEN');repo=os.environ.get('GITHUB_REPOSITORY')
    if not token or not repo:return {'status':'UNKNOWN','active_staging':True,'runs':[]}
    def get(path):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
    runs=get('/actions/runs?per_page=30').get('workflow_runs',[])
    matched=[r for r in runs if r.get('path','').endswith(R3_WORKFLOW) and r['status']!='completed']
    active=False;details=[]
    for r in matched:
        jobs=get('/actions/runs/'+str(r['id'])+'/jobs?per_page=100').get('jobs',[])
        if any(j['status']!='completed' for j in jobs):active=True
        details.append({'run_id':r['id'],'status':r['status'],'jobs':[{'name':j['name'],'status':j['status'],'conclusion':j.get('conclusion')} for j in jobs]})
    return {'status':'OBSERVED','active_staging':active,'runs':details,'historical_runs':[{'run_id':r['id'],'status':r['status']} for r in runs if 'history-2023-to-2014' in r.get('path','') and r['status']!='completed']}

def repair_plan():
    # Repair the known failed month first; only semantic sources need regeneration elsewhere.
    months=[(2025,7)]+[(2026,9)]+[(2025,m) for m in range(1,13) if m!=7]+[(2026,m) for m in range(1,11) if m!=9]
    return [{'key':f'{y}-{m:02d}', 'year':y,'month':m,'sources':['TWSE','TPEx','MOPS','FinMind'] if (y,m)==(2025,7) else ['MOPS','FinMind'],'status':'PENDING'} for y,m in months]

def aggregate_reports(reports):
    monthly={}
    for name,r in reports:
        period=r.get('period')
        if not period:continue
        version='R4' if 'NATIVE_R4' in name else 'R3'
        entries=r.get('archives',[])+r.get('standalone_files',[])
        monthly.setdefault(period,{})[version]={'status':r.get('status'),'scope':r.get('source_scope',['TWSE','TPEx','MOPS','FinMind']),'cells':sum(e.get('cells',0) for e in entries),'unresolved_occurrences':sum(e.get('unresolved_members',0) for e in entries),'input_errors':sum(e.get('status')=='INPUT_ERROR' for e in entries),'ohlc_violations':sum(e.get('checks',{}).get('OHLC_VIOLATIONS',0) for e in entries),'approved':False,'updated_at':r.get('updated_at')}
    return monthly

def retain_completed_outputs(previous,current):
    result=dict(current)
    for key in ('daily_shadow','feature_pilot'):
        if result.get(key) is None and previous.get(key) is not None:result[key]=previous[key]
    return result

def main(mode='monitor'):
    d=Drive(service());control=folder(d,C1,'05_CONTROL');qa=folder(d,control,'STANDARD_QA')
    registry=FolderRegistry(d,qa);ops=registry.folder(control,'OPERATIONS',True)
    previous_raw=d.read(ops,'LATEST.json');previous=json.loads(previous_raw) if previous_raw else {}
    # Seed a verified path alias, retaining both original folders and all payloads.
    std=registry.folder(C1,'02_STANDARD');year=registry.folder(std,'2025')
    july=registry.folder(year,'2025-07')
    status={'version':'OPERATIONS_V1_20261020','as_of':dt.datetime.now(dt.timezone.utc).isoformat(),'mode':mode,'production_ready':False,'july_path':'CANONICAL_REGISTERED_NO_FILES_MOVED','blockers':['SOURCE_CONTRACTS_AND_UNITS','HISTORICAL_UNIVERSE','PIT','FEATURE_GOLDEN','EVIDENCE_BACKED_RELEASE_NOT_PUBLISHED'],'run_id':os.environ.get('GITHUB_RUN_ID'),'code_commit':os.environ.get('GITHUB_SHA')}
    def heartbeat(stage):
        registry.flush()
        d.put(ops,'RUNNING.json',json.dumps({'run_id':os.environ.get('GITHUB_RUN_ID'),'stage':stage,'heartbeat':dt.datetime.now(dt.timezone.utc).isoformat(),'production_ready':False}).encode(),'application/json',overwrite=True)
        print(json.dumps({'stage':stage,'production_ready':False}),flush=True)
    heartbeat('READING_WORKER_STATUS')
    try:state=github_jobs()
    except Exception as exc:state={'status':'READ_FAILED','active_staging':True,'reason':type(exc).__name__}
    status['workers']=state
    raw=d.read(ops,'TARGETED_REPAIR_QUEUE_V1.json');queue=json.loads(raw) if raw else {'version':VERSION,'items':repair_plan()}
    if queue.get('version')!=VERSION:raise ValueError('REPAIR_QUEUE_VERSION_CONFLICT')
    if mode in ('bootstrap','auto','daily'):
        heartbeat('DAILY_OFFICIAL_SHADOW')
        try:
            shadow=capture(d,registry,qa)
            status['daily_shadow']={'trade_date':shadow['trade_date'],'status':shadow['status'],'sources':{s:{k:r.get(k) for k in ('status','attempts','staged_cells','reason')} for s,r in shadow['sources'].items()}}
        except Exception as exc:status['daily_shadow']={'status':'ERROR','reason':type(exc).__name__+':'+str(exc)[:150]}
    if mode=='bootstrap':
        heartbeat('SEPTEMBER_FEATURE_SHADOW')
        try:status['feature_pilot']=pilot(d,registry,qa)
        except Exception as exc:status['feature_pilot']={'status':'BLOCKED','reason':type(exc).__name__+':'+str(exc)[:180],'approved':False}
    status=retain_completed_outputs(previous,status)
    # Monitor-only runs must retain evidence produced by earlier bootstrap runs.
    if not status.get('daily_shadow'):
        try:
            daily_dir=registry.folder(qa,'DAILY_SHADOW')
            raw=d.read(daily_dir,target_day().isoformat()+'_OFFICIAL_SHADOW_V1.json')
            if raw:
                shadow=json.loads(raw)
                status['daily_shadow']={'trade_date':shadow['trade_date'],'status':shadow['status'],'sources':{s:{k:r.get(k) for k in ('status','attempts','staged_cells','reason')} for s,r in shadow['sources'].items()}}
        except FileNotFoundError:pass
    if not status.get('feature_pilot'):
        raw=d.read(qa,'2026-09_PRICE_SHADOW_V1_RESULT.json')
        if raw:status['feature_pilot']=json.loads(raw)
    # Do not add a fourth long-running worker while the old R3 matrix is active.
    if mode in ('auto','repair') and not state['active_staging']:
        heartbeat('BOUNDED_TARGETED_REPAIR')
        item=next((i for i in queue['items'] if i['status'] not in ('STAGING_REPAIR_COMPLETE','BLOCKED_INPUT_ERROR')),None)
        if item:
            item.update(status='RUNNING',run_id=os.environ.get('GITHUB_RUN_ID'),started_at=dt.datetime.now(dt.timezone.utc).isoformat())
            d.put(ops,'TARGETED_REPAIR_QUEUE_V1.json',json.dumps(queue,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
            try:
                result=repair(item['year'],item['month'],item['sources'],max_minutes=18)
                item.update(status='STAGING_REPAIR_COMPLETE' if result['status']=='STAGING_NOT_APPROVED' else 'CHECKPOINTED',unresolved=result.get('unresolved_member_occurrences'),finished_at=dt.datetime.now(dt.timezone.utc).isoformat(),approved=False)
            except (Exception,SystemExit) as exc:item.update(status='BLOCKED_INPUT_ERROR',reason=str(exc)[:180])
    status['repair_queue']={'complete':sum(i['status']=='STAGING_REPAIR_COMPLETE' for i in queue['items']),'total':len(queue['items']),'items':queue['items'],'deferred_for_active_R3':state['active_staging']}
    d.put(ops,'TARGETED_REPAIR_QUEUE_V1.json',json.dumps(queue,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    heartbeat('READING_MONTHLY_PROGRESS')
    reports=[]
    for f in ls(d,qa):
        if 'NATIVE_R3_20261020_1_AUDIT' in f['name'] or ('NATIVE_R4_20261020_1' in f['name'] and f['name'].endswith('_AUDIT.json')):
            try:reports.append((f['name'],json.loads(d.call(lambda:d.api.files().get_media(fileId=f['id'])))))
            except Exception as exc:status.setdefault('report_read_errors',[]).append({'name':f['name'],'reason':type(exc).__name__})
    status['monthly']=aggregate_reports(reports)
    history=registry.folder(registry.folder(C1,'07_REPORTS'),'HISTORY_202312_TO_201401_R1')
    hraw=d.read(history,'CURSOR.json');h=json.loads(hraw) if hraw else {}
    completed=h.get('finished_months',[])
    status['historical_raw']={'processed_months':len(completed),'total_months':120,'last_processed_month':completed[-1]['month'] if completed else None,'updated_at':h.get('updated_utc'),'quality_complete':False}
    pointer=d.read(ops,'ACTIVE_APPROVED_RELEASE.json')
    status['active_approved_release']=json.loads(pointer) if pointer else None
    status['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    body=json.dumps(status,ensure_ascii=False,indent=2,allow_nan=False).encode()
    immutable='SNAPSHOT_'+os.environ.get('GITHUB_RUN_ID',status['updated_at'].replace(':',''))+'_'+hashlib.sha256(body).hexdigest()[:12]+'.json'
    # Each invocation uses its own immutable receipt; LATEST is only a status pointer.
    d.put(ops,immutable,body,'application/json',overwrite=False)
    d.put(ops,'LATEST.json',body,'application/json',overwrite=True)
    complete=sum(v.get('R3',{}).get('status')=='STAGING_NOT_APPROVED' for v in status['monthly'].values())
    text='# 賈維斯統一進度\n\n更新：'+status['updated_at']+'\n\n'
    text+='- 歷史原始資料月份主流程：'+str(len(completed))+'/120；不代表完整率。\n'
    text+='- R3 暫存轉換已走完月份：'+str(complete)+'/22；不代表數值/PIT核准。\n'
    text+='- R4 定向修復：'+str(status['repair_queue']['complete'])+'/22；其他來源候選保留。\n'
    text+='- 正式核准版本：'+('存在，依版本限定範圍' if pointer else '尚未發布')+'。\n'
    text+='- 尚待：來源欄位與單位、歷史母體、PIT、指標Golden及暖機、完整發布證據。\n'
    text+='- 當前資源：'+('R3仍在執行，長時間R4修復延後。' if state['active_staging'] else '可處理一個有界R4修復單元。')+'\n'
    d.put(ops,'LATEST.md',text.encode(),'text/markdown',overwrite=True)
    heartbeat('COMPLETE')
    public={'status':'CONTROL_UPDATED','r3_months_processed':complete,'r4_targeted_months_processed':status['repair_queue']['complete'],'historical_months_processed':len(completed),'production_ready':False,'daily_shadow':status.get('daily_shadow'),'feature_pilot':{k:status.get('feature_pilot',{}).get(k) for k in ('status','rows','instruments_observed_not_universe','reason')},'deferred_for_active_R3':state['active_staging']}
    print(json.dumps(public,ensure_ascii=False),flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(text)
    return status

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('monitor','bootstrap','auto','daily','repair'),default='monitor');a=p.parse_args();main(a.mode)
