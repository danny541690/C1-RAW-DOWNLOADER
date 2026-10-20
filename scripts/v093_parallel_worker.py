"""Bounded independent workers. Only v093_operations writes unified status."""
import argparse,datetime as dt,json,os,time,urllib.request
from scripts.v093_standard_r1 import Drive,service,C1,folder
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r4 import run as repair,VERSION,PARSER_REVISION
from scripts.v093_operations import repair_plan,github_jobs,run_bounded_repairs

LANES=('july','financial','features')

def partition_items(items,lane):
    if lane not in ('july','financial'):raise ValueError('INVALID_REPAIR_LANE')
    chosen=[dict(i) for i in items if (i['key']=='2025-07')==(lane=='july')]
    # Give untouched months a turn rather than blocking behind one large month.
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
        result=prepare(d,registry,qa,ops,minutes)
    else:
        name='REPAIR_QUEUE_'+lane.upper()+'_V2.json';raw=d.read(ops,name)
        if raw:
            queue=json.loads(raw)
            if queue.get('version')!=VERSION or queue.get('lane')!=lane:raise ValueError('QUEUE_IDENTITY_CONFLICT')
        else:
            raw=d.read(ops,'TARGETED_REPAIR_QUEUE_V1.json')
            prior=json.loads(raw) if raw else {'version':VERSION,'items':repair_plan()}
            if prior.get('version')!=VERSION:raise ValueError('MIGRATION_VERSION_CONFLICT')
            queue={'version':VERSION,'lane':lane,'items':partition_items(prior['items'],lane)}
        expected={i['key'] for i in partition_items(repair_plan(),lane)}
        if {i['key'] for i in queue['items']}!=expected:raise ValueError('QUEUE_SCOPE_CONFLICT')
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
