"""Bounded independent workers. Only v093_operations writes unified status."""
import argparse,datetime as dt,json,os,time,urllib.request
from scripts.v093_standard_r1 import Drive,service,C1,folder
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r4 import run as repair,VERSION,PARSER_REVISION
from scripts.v093_operations import repair_plan,conversion_plan_2024,github_jobs,run_bounded_repairs

LANES=('july','financial','features','2024')

def partition_items(items,lane):
    if lane not in ('july','financial','2024'):raise ValueError('INVALID_REPAIR_LANE')
    if lane=='2024':chosen=[dict(i) for i in items if i.get('year')==2024]
    else:chosen=[dict(i) for i in items if i.get('year')!=2024 and (i['key']=='2025-07')==(lane=='july')]
    if lane=='2024':return sorted(chosen,key=lambda i:i['month'],reverse=True)
    # Give untouched financial months a turn rather than blocking behind a large month.
    return sorted(chosen,key=lambda i:(i['status']=='CHECKPOINTED',i.get('finished_at','')))

def upgrade_parser_queue(queue):
    if queue.get('parser_revision')==PARSER_REVISION:return queue
    # Completed structural runs can still contain unparsed slice envelopes.
    for item in queue['items']:
        if item['status']=='STAGING_REPAIR_COMPLETE':
            item['status']='PENDING';item['requeue_reason']='FINMIND_ROWS_PARSER_UPGRADE'
    queue['parser_revision']=PARSER_REVISION
    return queue

def legacy_controller_active(runs,head):
    return any(r.get('path','').endswith('/v093-operational-control.yml') and r['status']!='completed' and r.get('head_sha')!=head for r in runs)

def main(lane,minutes=35):
    if lane not in LANES:raise ValueError('INVALID_LANE')
    state=github_jobs()
    token=os.environ['GITHUB_TOKEN'];repo=os.environ['GITHUB_REPOSITORY']
    req=urllib.request.Request('https://api.github.com/repos/'+repo+'/actions/workflows/v093-operational-control.yml/runs?per_page=30',headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=25) as response:runs=json.load(response)['workflow_runs']
    if state['active_staging'] or legacy_controller_active(runs,os.environ['GITHUB_SHA']):
        print(json.dumps({'lane':lane,'status':'DEFERRED_FOR_PREVIOUS_WRITER'}),flush=True);return
    d=Drive(service());qa=folder(d,folder(d,C1,'05_CONTROL'),'STANDARD_QA')
    registry=FolderRegistry(d,qa,namespace=lane.upper())
    ops=registry.folder(folder(d,C1,'05_CONTROL'),'OPERATIONS')
    if lane=='features':
        from scripts.v093_feature_warmup import prepare
        try:result=prepare(d,registry,qa,ops,minutes)
        except Exception as exc:
            raw=d.read(ops,'FEATURE_WARMUP_V2.json');failed=json.loads(raw) if raw else {'version':'FEATURE_WARMUP_V2'}
            failed.update(status='BLOCKED_INPUT_ERROR',reason=type(exc).__name__+':'+str(exc)[:180],approved=False,updated_at=dt.datetime.now(dt.timezone.utc).isoformat())
            d.put(ops,'FEATURE_WARMUP_V2.json',json.dumps(failed,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
            raise
    else:
        name='REPAIR_QUEUE_'+lane.upper()+'_V2.json';raw=d.read(ops,name)
        if raw:
            queue=json.loads(raw)
            if queue.get('version')!=VERSION or queue.get('lane')!=lane:raise ValueError('QUEUE_IDENTITY_CONFLICT')
        else:
            raw=d.read(ops,'TARGETED_REPAIR_QUEUE_V1.json') if lane!='2024' else None
            prior=json.loads(raw) if raw else {'version':VERSION,'items':conversion_plan_2024() if lane=='2024' else repair_plan()}
            if prior.get('version')!=VERSION:raise ValueError('MIGRATION_VERSION_CONFLICT')
            queue={'version':VERSION,'lane':lane,'items':partition_items(prior['items'],lane)}
        expected={i['key'] for i in partition_items(conversion_plan_2024() if lane=='2024' else repair_plan(),lane)}
        if {i['key'] for i in queue['items']}!=expected:raise ValueError('QUEUE_SCOPE_CONFLICT')
        canonical={i['key']:i for i in (conversion_plan_2024() if lane=='2024' else repair_plan())}
        if len(queue['items'])!=len(expected) or any(any(i.get(k)!=canonical[i['key']][k] for k in ('year','month','sources')) for i in queue['items']):raise ValueError('QUEUE_UNIT_IDENTITY_CONFLICT')
        queue=upgrade_parser_queue(queue)
        queue['items']=partition_items(queue['items'],lane)
        def save():
            queue['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
            d.put(ops,name,json.dumps(queue,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
        def run_one(y,m,sources,max_minutes):
            return repair(y,m,sources,max_minutes=max_minutes,registry_namespace=lane.upper())
        save();run_bounded_repairs(queue,run_one,save,seconds=minutes*60)
        result={'lane':lane,'complete':sum(i['status']=='STAGING_REPAIR_COMPLETE' for i in queue['items']),'total':len(queue['items']),'approved':False}
    registry.flush();print(json.dumps(result,ensure_ascii=False),flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('工作批次結果（尚未核准）\n\n```json\n'+json.dumps(result,ensure_ascii=False)+'\n```\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lane',choices=LANES,required=True);p.add_argument('--minutes',type=float,default=35);a=p.parse_args();main(a.lane,a.minutes)
