"""Append-only JARVIS repair events. Never downloads or overwrites market RAW."""
import pathlib,csv,gzip,json,hashlib,datetime,fcntl,os,argparse,collections
ROOT=pathlib.Path(__file__).resolve().parent
HEAD=['event_id','task_id','source','month','unit_id','event_type','event_time','reason','reviewer','previous_sha256','new_sha256','new_file_ref','run_url','remote_hash_verified','period_verified','security_verified','numeric_verified','pit_verified','unit_scope_verified','unfilled_count']
def units(source=None):
 for p in sorted((ROOT/'units').glob('*_units.csv.gz')):
  if source and p.name!=source+'_units.csv.gz':continue
  with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def events():
 with open(ROOT/'repair_events.csv',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def true(x):return x is True or str(x).lower() in ['true','1']
def stamp(x):
 d=datetime.datetime.fromisoformat(x.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone required')
 return d

def record(p):
 for k in ['task_id','source','month','unit_id','event_type','event_time','reason','reviewer']:
  if not p.get(k):raise ValueError('Missing '+k)
 u=next((u for u in units(p['source']) if u['任務ID']==p['task_id']),None)
 if not u or u['月份']!=p['month'] or u['單元ID']!=p['unit_id']:raise ValueError('Unit identity mismatch')
 d=stamp(p['event_time']);kind=p['event_type']
 if kind not in ['DOWNLOADED','QUALITY_REVIEW','VERIFIED','CLOSED','REOPENED']:raise ValueError('Invalid event')
 if kind in ['DOWNLOADED','VERIFIED','CLOSED']:
  h=p.get('new_sha256','')
  if len(h)!=64 or any(c not in '0123456789abcdef' for c in h.lower()):raise ValueError('Need SHA256')
  if not p.get('new_file_ref') or not p.get('run_url') or not true(p.get('remote_hash_verified')):raise ValueError('Need file, execution and remote hash evidence')
 if kind in ['VERIFIED','CLOSED']:
  if not all(true(p.get(k)) for k in ['period_verified','security_verified','numeric_verified','pit_verified','unit_scope_verified']) or int(p.get('unfilled_count',-1))!=0:raise ValueError('Acceptance incomplete')
 eid=hashlib.sha256(json.dumps(p,sort_keys=True,ensure_ascii=False).encode()).hexdigest()[:24]
 with open(ROOT/'repair_events.csv','r+',encoding='utf-8-sig',newline='') as f:
  fcntl.flock(f.fileno(),fcntl.LOCK_EX);rows=list(csv.DictReader(f))
  if any(r['event_id']==eid for r in rows):return {'status':'already_recorded','event_id':eid}
  prior=[r for r in rows if r['task_id']==p['task_id']];last=prior[-1] if prior else None
  if last and d<stamp(last['event_time']):raise ValueError('Timestamp precedes latest event')
  if last and last['event_type']=='CLOSED' and kind!='REOPENED':raise ValueError('Must reopen closed task')
  if kind=='CLOSED' and (not last or last['event_type']!='VERIFIED' or last['new_sha256']!=p['new_sha256']):raise ValueError('CLOSED requires VERIFIED with same SHA')
  if kind=='REOPENED' and (not last or last['event_type']!='CLOSED'):raise ValueError('REOPENED requires CLOSED')
  row={k:p.get(k,'') for k in HEAD};row['event_id']=eid;row['previous_sha256']=p.get('previous_sha256') or (last['new_sha256'] if last else u['RAW_SHA256']);f.seek(0,2);csv.DictWriter(f,fieldnames=HEAD).writerow(row);f.flush();os.fsync(f.fileno())
 return {'status':'recorded','event_id':eid}
def rebuild():
 ev=events();latest={e['task_id']:e for e in ev};saved={e['task_id'] for e in ev if e['event_type'] in ['DOWNLOADED','VERIFIED','CLOSED']};a=collections.defaultdict(collections.Counter)
 for u in units():
  x=a[(u['來源'],u['月份'])];e=latest.get(u['任務ID']);closed=bool(e and e['event_type']=='CLOSED');down=u['任務ID'] in saved or u['已下載']=='1';quality=False if closed else u['明列品質問題']=='1'
  if e and e['event_type'] in ['QUALITY_REVIEW','REOPENED']:quality=True
  if e and e['event_type']=='VERIFIED':quality=False
  for k,v in {'已知計畫總數':1,'已下載':down,'未下載':not down,'明列品質問題':quality,'已驗收關閉':closed,'已重新開啟':bool(e and e['event_type']=='REOPENED')}.items():x[k]+=int(v)
 h=['來源','月份','已知計畫總數','已下載','未下載','明列品質問題','已驗收關閉','已重新開啟']
 with open(ROOT/'current_monthly.csv','w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(h)
  for k,x in sorted(a.items()):w.writerow([*k]+[x[c] for c in h[2:]])
 return {'units':sum(x['已知計畫總數'] for x in a.values()),'events':len(ev),'closed':sum(x['已驗收關閉'] for x in a.values())}
if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True);q=s.add_parser('find');q.add_argument('--source');q.add_argument('--month');q.add_argument('--task-id');q.add_argument('--limit',type=int,default=20);q=s.add_parser('record');q.add_argument('json_file');s.add_parser('rebuild');a=p.parse_args()
 if a.cmd=='record':print(json.dumps(record(json.load(open(a.json_file))),ensure_ascii=False));print(rebuild())
 elif a.cmd=='rebuild':print(rebuild())
 else:
  n=0;ev=events()
  for u in units(a.source):
   if a.month and u['月份']!=a.month:continue
   if a.task_id and u['任務ID']!=a.task_id:continue
   print(json.dumps({'unit':u,'history':[e for e in ev if e['task_id']==u['任務ID']]},ensure_ascii=False));n+=1
   if n>=a.limit:break
