"""Resume only explicit core gaps, with independent monthly time budgets."""
import argparse, collections, json, time
from scripts.v093_three_year_repair import Audit, ROOT, REPORT_ROOT, PASS, putj, read, stamp

def getj(a,name):
 f=a.d.find(a.ctrl,name)
 return json.loads(read(a.d,f)) if f else None

def month(year,mo):
 a=Audit(year,True);period=f'{year}-{mo:02d}';summary=getj(a,'year_summary.json')
 if not summary:raise ValueError('ORIGINAL_YEAR_SUMMARY_REQUIRED')
 targets=[x for x in summary['remaining_core_units'] if x['month']==period]
 if not targets:
  putj(a.d,a.ctrl,period+'_R2_continuation.json',{'month':period,'units':[],'requests':{},'new_files':0,'new_bytes':0,'state':'NO_RECORDED_GAPS'});return
 # Re-read only affected source/month directories, skipping already stored success.
 for source in sorted({x['source'] for x in targets}):a.scan(source,period)
 results=[]
 for i,target in enumerate(targets,1):
  j={k:target[k] for k in ('source','category','period','url','month')}
  result=a.repair_unit(j);results.append(result)
  if i%20==0:putj(a.d,a.ctrl,period+'_R2_checkpoint.json',{'done':i,'total':len(targets),'units':results})
 out={'month':period,'finished_utc':stamp(),'elapsed_seconds':round(time.monotonic()-a.started,2),'units':results,'counts':dict(collections.Counter(x['status'] for x in results)),'requests':dict(a.requests),'new_files':len(a.output),'new_bytes':sum(x['bytes'] for x in a.output),'state':'BOUNDED_MONTH_PASS_FINISHED','numeric_verified':False,'pit_verified':False}
 putj(a.d,a.ctrl,period+'_R2_continuation.json',out)
 print(json.dumps({k:v for k,v in out.items() if k!='units'}),flush=True)

def collect():
 for year in (2024,2025,2026):
  a=Audit(year,False);old=getj(a,'year_summary_R1_before_R2.json') or getj(a,'year_summary.json')
  if not old:continue
  entries={(e['source'],e['category'],e['period']):e for e in old['remaining_core_units']}
  counts=collections.Counter(old['core_counts']);newfiles=0;newbytes=0;requests=collections.Counter();seen=[]
  for mo in range(1,13):
   name=f'{year}-{mo:02d}_R2_continuation.json';r=getj(a,name)
   if not r:continue
   seen.append(name);newfiles+=r.get('new_files',0);newbytes+=r.get('new_bytes',0);requests.update(r.get('requests',{}))
   for e in r['units']:
    key=(e['source'],e['category'],e['period']);previous=entries.get(key)
    if previous:counts[previous['status']]-=1;counts[e['status']]+=1;entries[key]=e
  snapshot=a.d.find(a.ctrl,'year_summary_R1_before_R2.json')
  if not snapshot:putj(a.d,a.ctrl,'year_summary_R1_before_R2.json',old)
  old.update(core_counts={k:v for k,v in counts.items() if v},remaining_core_units=[e for e in entries.values() if e['status'] not in ('EXISTING_PAYLOAD_VERIFIED','REPAIRED_REMOTE_READBACK_VERIFIED')],R2_finished_utc=stamp(),R2_month_reports=seen,R2_new_core_files=newfiles,R2_new_core_bytes=newbytes,R2_source_requests=dict(requests),new_core_files=old['new_core_files']+newfiles,new_core_bytes=old['new_core_bytes']+newbytes)
  putj(a.d,a.ctrl,'year_summary.json',old)
  print(json.dumps({'year':year,'core_counts':old['core_counts'],'remaining':len(old['remaining_core_units']),'new_R2_files':newfiles}),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--year',type=int);p.add_argument('--month',type=int);p.add_argument('--collect',action='store_true');args=p.parse_args()
 if args.collect:collect()
 else:month(args.year,args.month)
