"""Pinned admission catalogs and bounded active chunks for the native worker.

Catalogs use the existing checksummed GitCAS page format. Immutable page archives
retain outcomes and provenance while the active source state stays bounded.
"""
import copy,hashlib,json,re,time
from pathlib import Path
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_state_pages import encode,SCHEMA
from scripts.v093_source_adapters import NativeAdapter
ACTIVE={'READY','READY_CHECK','LEASED','RETRY_WAIT','REQUEST_INTENT','STORED','RECONCILE','RETAINED_CHECK'}
HELD={'APPLICABILITY_HOLD','CONTENT_BLOCKED','BLOCKED','SOURCE_HOLD','STORAGE_HOLD'}

def sha(value):return hashlib.sha256(encode(value)).hexdigest()

def catalog_state(source,slot,rows,as_of):
 prepared=[prepare_row(source,slot,row['definition']['key'],row) for row in rows]
 if len({r['definition']['key'] for r in prepared})!=len(prepared):raise ValueError('CATALOG_DUPLICATE_LOGICAL_TASK')
 prepared.sort(key=lambda r:(r['definition']['period'],r['definition']['key']))
 catalog_id=sha(dict(source=source,slot=slot,as_of=as_of,rows=prepared))
 return dict(source=source,admission_catalog=dict(schema='JARVIS_ADMISSION_CATALOG_V1',source=source,slot=slot,as_of=as_of,catalog_id=catalog_id,ordering='ORDINAL_PERIOD_ASC_V1'),tasks={str(i).zfill(12):row for i,row in enumerate(prepared)})

class Catalog:
 def __init__(self,store,entry,source,slot):
  commit=entry.get('commit');expected=entry.get('index_sha256')
  if not re.fullmatch('[0-9a-f]{40}',commit or '') or not re.fullmatch('[0-9a-f]{64}',expected or ''):raise ValueError('ADMISSION_CATALOG_PIN')
  store.git('fetch','--no-tags','--no-write-fetch-head','origin',commit)
  raw=store.git('show',commit+':state.json').stdout
  if len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('ADMISSION_INDEX_SHA_OR_SIZE')
  index=json.loads(raw);meta=index.get('state',{}).get('admission_catalog',{})
  if index.get('schema')!=SCHEMA or index['state'].get('source')!=source or meta.get('schema')!='JARVIS_ADMISSION_CATALOG_V1' or meta.get('source')!=source or meta.get('slot')!=slot:raise ValueError('ADMISSION_CATALOG_SCOPE')
  if not re.fullmatch('[0-9a-f]{64}',meta.get('catalog_id','')):raise ValueError('ADMISSION_CATALOG_ID')
  if sum(p['count'] for p in index['pages'])!=index['task_count'] or len({p['name'] for p in index['pages']})!=len(index['pages']):raise ValueError('ADMISSION_INDEX_COUNTS_OR_DUPLICATE_PAGES')
  if meta.get('ordering')!='ORDINAL_PERIOD_ASC_V1':raise ValueError('ADMISSION_GLOBAL_ORDER_REQUIRED')
  offsets={};total=0
  for page in index['pages']:offsets[page['name']]=total;total+=page['count']
  self.offsets=offsets
  if slot=='DESC':index['pages']=list(reversed(index['pages']))
  self.store=store;self.commit=commit;self.index=index;self.meta=meta;self.signature=sha(dict(commit=commit,index_sha256=expected,source=source,slot=slot));self.cache={}
 def page(self,number):
  if number in self.cache:return self.cache[number]
  page=self.index['pages'][number];name=page['name']
  if not re.fullmatch('page-[0-9]{6}.json',name):raise ValueError('ADMISSION_PAGE_NAME')
  raw=self.store.git('show',self.commit+':'+name).stdout
  if len(raw)>1048576 or hashlib.sha256(raw).hexdigest()!=page['sha256']:raise ValueError('ADMISSION_PAGE_SHA')
  values=json.loads(raw)
  if not isinstance(values,dict) or len(values)!=page['count']:raise ValueError('ADMISSION_PAGE_COUNT')
  expected={str(self.offsets[name]+i).zfill(12) for i in range(page['count'])}
  if set(values)!=expected:raise ValueError('ADMISSION_ORDINAL_RANGE')
  ordered=[values[k] for k in sorted(values)]
  if [(r['definition']['period'],r['definition']['key']) for r in ordered]!=sorted((r['definition']['period'],r['definition']['key']) for r in ordered):raise ValueError('ADMISSION_PERIOD_ORDER')
  if self.meta['slot']=='DESC':ordered.reverse()
  rows=[(row['definition']['key'],row) for row in ordered]
  if len({key for key,_ in rows})!=len(rows):raise ValueError('ADMISSION_DUPLICATE_KEY')
  self.cache[number]=rows;return rows
 def chunk(self,page,offset,limit):
  output={}
  while page<len(self.index['pages']) and len(output)<limit:
   rows=self.page(page)
   if not 0<=offset<=len(rows):raise ValueError('ADMISSION_PAGE_OFFSET')
   selected=rows[offset:offset+limit-len(output)]
   for key,row in selected:
    if key in output:raise ValueError('ADMISSION_DUPLICATE_KEY')
    output[key]=row
   offset+=len(selected)
   if offset==len(rows):page+=1;offset=0
  return output,dict(page=page,offset=offset),page<len(self.index['pages'])

def prepare_row(source,slot,key,row):
 row=copy.deepcopy(row);definition=row.get('definition',{})
 if definition.get('source')!=source or definition.get('slot')!=slot or definition.get('key')!=key:raise ValueError('ADMISSION_TASK_SCOPE')
 attempts=row.get('attempts');old=row.get('legacy_review',{})
 if type(attempts) is not int or attempts<0 or old.get('source')!=source or old.get('task_key')!=key or type(old.get('attempts')) is not int or attempts<old['attempts']:raise ValueError('ADMISSION_LEGACY_ATTEMPTS')
 if type(row.get('materializations',0)) is not int or row.get('materializations',0)<0:raise ValueError('ADMISSION_MATERIALIZATION_COUNT')
 status=row.get('status')
 if status not in {'READY','READY_CHECK'}|HELD:raise ValueError('ADMISSION_TASK_STATUS')
 if status in ('READY','READY_CHECK'):
  if old.get('action')=='VERSION_CONFLICT_REVIEW' or {p.get('period') for p in old.get('provenance',[])}!={definition.get('period')}:raise ValueError('ADMISSION_UNRESOLVED_PERIOD_OR_VERSION')
  contract=row.get('execution_contract',{})
  if contract.get('mode') not in (('RETAINED',) if status=='READY_CHECK' else ('MISSING','REPAIR','PROMOTE')):raise ValueError('ADMISSION_TASK_MODE')
  NativeAdapter(None,None,dict(source=source,key=key),row)
  if status=='READY' and attempts>=4 and contract.get('mode')!='PROMOTE':status='BLOCKED'
 return dict(definition=definition,attempts=attempts,status=status,fence=0,owner=None,legacy_review=old,execution_contract=row.get('execution_contract'),check_only=status=='READY_CHECK',local_only=(row.get('execution_contract') or {}).get('mode')=='PROMOTE',materializations=row.get('materializations',0),full_acceptance=False,numeric_verified=False,pit_verified=False)

def stage(coordinator,catalog,limit=32):
 if type(limit) is not int or not 1<=limit<=64:raise ValueError('ADMISSION_ACTIVE_CHUNK_LIMIT')
 slot=catalog.meta['slot'];_,state=coordinator.store.read(coordinator.source);cursor=(state or {}).get('admission',{}).get(slot,{})
 if cursor and cursor['signature']!=catalog.signature:raise ValueError('CATALOG_CHANGE_REQUIRES_PROGRESS_MIGRATION')
 if cursor.get('active_keys'):return False
 page=cursor.get('page',0);offset=cursor.get('offset',0);rows,next_pos,more=catalog.chunk(page,offset,limit)
 prepared={key:prepare_row(coordinator.source,slot,key,row) for key,row in rows.items()}
 def change(s):
  existing=s.setdefault('admission',{}).get(slot,{})
  if existing!=cursor:raise ValueError('ADMISSION_CURSOR_CHANGED_RETRY')
  if any(t['definition']['slot']==slot for t in s['tasks'].values()):raise ValueError('EXISTING_PROGRESS_REQUIRES_MIGRATION')
  if set(prepared)&set(s['tasks']):raise ValueError('CROSS_DIRECTION_TASK_COLLISION')
  s['tasks'].update(prepared)
  s['admission'][slot]=dict(cursor,signature=catalog.signature,catalog_id=catalog.meta['catalog_id'],page=page,offset=offset,active_keys=list(prepared),next_position=next_pos,more_after_chunk=more,chunk_number=cursor.get('chunk_number',0),finished=not prepared and not more)
 coordinator.update(change);return bool(prepared)

def archive_completed(coordinator,slot,save_archive):
 _,state=coordinator.store.read(coordinator.source)
 if not state:return False
 cursor=state.get('admission',{}).get(slot,{})
 keys=cursor.get('active_keys',[])
 if not keys:return False
 rows={key:state['tasks'][key] for key in keys}
 if any(t.get('owner') or t['status'] in ACTIVE for t in rows.values()):return False
 if any(t['status']!='RAW_BASIC_VERIFIED' and t['status'] not in HELD for t in rows.values()):raise ValueError('ARCHIVE_UNCLASSIFIED_STATE')
 snapshot=dict(source=coordinator.source,slot=slot,catalog_id=cursor['catalog_id'],chunk_number=cursor['chunk_number'],tasks=rows,full_acceptance=False)
 receipt=save_archive(snapshot)
 if receipt.get('sha256')!=sha(snapshot) or receipt.get('readback_verified') is not True:raise ValueError('ARCHIVE_READBACK_REQUIRED')
 def change(s):
  current=s['admission'][slot]
  if current!=cursor or {key:s['tasks'][key] for key in keys}!=rows:raise ValueError('ARCHIVE_STATE_CHANGED_RETRY')
  counts=current.get('archived_status_counts',{})
  for key,t in rows.items():counts[t['status']]=counts.get(t['status'],0)+1;del s['tasks'][key]
  s['admission'][slot]=dict(signature=cursor['signature'],catalog_id=cursor['catalog_id'],**cursor['next_position'],active_keys=[],chunk_number=cursor['chunk_number']+1,finished=not cursor['more_after_chunk'],last_archive=receipt,archived_status_counts=counts)
 coordinator.update(change);return True

class GitArchive:
 def __init__(self,store_factory):self.store_factory=store_factory
 def __call__(self,snapshot):
  store=self.store_factory(snapshot);source=snapshot['source'];revision,old=store.read(source)
  if old and sha(old)!=sha(snapshot):raise ValueError('IMMUTABLE_ARCHIVE_CONFLICT')
  if not old and not store.cas(source,revision,snapshot):raise ValueError('ARCHIVE_CAS_CONFLICT_RETRY')
  commit,restored=store.read(source)
  if sha(restored)!=sha(snapshot):raise ValueError('ARCHIVE_COLD_READBACK_SHA')
  return dict(commit=commit,branch=store.ref(source),sha256=sha(snapshot),readback_verified=True)

def code_digest(root):
 paths=sorted(list((root/'scripts').glob('*.py'))+list((root/'.github/workflows').glob('*.yml')))
 return sha({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})

def run_catalog(coordinator,drive,catalog,slot,owner,target_root,archive,max_units=20,seconds=2700,chunk_limit=32):
 from scripts.v093_source_worker import run_native_batch
 archive_completed(coordinator,slot,archive)
 stage(coordinator,catalog,chunk_limit)
 result=run_native_batch(coordinator,drive,slot,owner,target_root,max_units,seconds)
 archived=archive_completed(coordinator,slot,archive)
 _,state=coordinator.store.read(coordinator.source);cursor=state['admission'][slot]
 result.update(admission_cursor=cursor,chunk_archived=archived,catalog_finished=cursor.get('finished',False),catalog_more=not cursor.get('finished',False),active_source_tasks=len(state['tasks']))
 return result

def run_until_budget(coordinator,drive,catalog,slot,owner,target_root,archive,seconds=2700,chunk_limit=32,monotonic=time.monotonic):
 """Process successive saved chunks immediately; defer only holds, cooldowns or no progress.

 The outer deadline covers catalog/archive IO as well as the native batch. The
 worker handles at most 20 units per checkpoint, so memory remains bounded.
 """
 if not 0<seconds<=2700:raise ValueError('CAMPAIGN_TIME_BUDGET')
 started=monotonic();batches=0;processed=0;last=None;stop='TIME_BUDGET'
 while seconds-(monotonic()-started)>5:
  remaining=seconds-(monotonic()-started)
  last=run_catalog(coordinator,drive,catalog,slot,owner,target_root,archive,max_units=20,seconds=min(2700,remaining),chunk_limit=chunk_limit)
  batches+=1;processed+=last['processed']
  if last.get('catalog_finished'):stop='CATALOG_FINISHED';break
  if last.get('source_hold'):stop='SOURCE_HOLD';break
  if (last.get('cooldown_until') or 0)>coordinator.clock():stop='SOURCE_COOLDOWN';break
  if not last['processed'] and not last.get('chunk_archived'):stop='NO_IMMEDIATE_WORK';break
 result=dict(last or {},batches=batches,total_processed=processed,stop_reason=stop,elapsed_campaign_seconds=round(monotonic()-started,3),production_activation=False)
 # Each batch has already saved its state. This summary must not replace it.
 return result

def validate_catalog_manifest(catalogs):
 from scripts.v093_source_partition import COUNTS
 if not isinstance(catalogs,dict) or set(catalogs)!=set(COUNTS):raise ValueError('PRODUCTION_RELEASE_BLOCKED_SEVEN_SOURCE_MANIFEST')
 for source,count in COUNTS.items():
  slots={'DESC','ASC'} if count==2 else {'DESC'}
  if not isinstance(catalogs[source],dict) or set(catalogs[source])!=slots:raise ValueError('PRODUCTION_RELEASE_BLOCKED_TWELVE_DIRECTION_MANIFEST')
  for pin in catalogs[source].values():
   if not isinstance(pin,dict) or not re.fullmatch('[0-9a-f]{40}',pin.get('commit') or '') or not re.fullmatch('[0-9a-f]{64}',pin.get('index_sha256') or ''):raise ValueError('PRODUCTION_RELEASE_BLOCKED_UNPINNED_CATALOG')

def load_release(root):
 release=json.loads((root/'config/v093_source_release.json').read_text())
 if release.get('enabled') is not True:raise ValueError('PRODUCTION_RELEASE_BLOCKED_RELEASE_NOT_APPROVED')
 if release.get('schema')!='JARVIS_NATIVE_RELEASE_V1' or any(release.get('approved_checks',{}).get(x) is not True for x in ('source_contracts','continuation_and_quota','cutover')):raise ValueError('PRODUCTION_RELEASE_BLOCKED_REQUIRED_CHECKS')
 if release.get('tested_code_sha256')!=code_digest(root):raise ValueError('PRODUCTION_RELEASE_BLOCKED_CODE_CHANGED')
 validate_catalog_manifest(release.get('catalogs'))
 from scripts.v093_source_adapters import RAW_ROOT
 if release.get('raw_root')!=RAW_ROOT:raise ValueError('PRODUCTION_RELEASE_BLOCKED_RAW_ROOT_CHANGED')
 return release

def production(root,source,slot,namespace):
 release=load_release(root)
 if namespace!='production':raise ValueError('PRODUCTION_RELEASE_BLOCKED_NAMESPACE')
 import os
 if not os.environ.get('GH_TOKEN'):raise ValueError('PRODUCTION_RELEASE_BLOCKED_CONTINUATION_TOKEN')
 from scripts.v093_source_git_store import GitCAS
 from scripts.annual_actual_firstpass import Drive,service
 store=GitCAS(root);catalog=Catalog(store,release['catalogs'][source][slot],source,slot)
 c=Coordinator(store,source,ttl=600)
 from scripts.v093_source_continuation import acknowledge
 if not acknowledge(c,slot,os.environ.get('CONTINUATION_ID',''),os.environ['GITHUB_RUN_ID']):return dict(production_activation=False,duplicate_continuation=True,source_requests=0)
 archive=GitArchive(lambda snap:GitCAS(root,'jarvis-source-archive/'+snap['catalog_id']+'/'+slot+'/'+str(snap['chunk_number']).zfill(6)))
 result=run_until_budget(c,Drive(service()),catalog,slot,'run-'+__import__('os').environ['GITHUB_RUN_ID'],release['raw_root'],archive,chunk_limit=32)
 from scripts.v093_source_continuation import continue_slot,transport,continuation_target
 _,checkpoint=c.store.read(source)
 next_slot=continuation_target(checkpoint,release['catalogs'][source],slot)
 next_catalog=catalog if next_slot==slot else Catalog(store,release['catalogs'][source][next_slot],source,next_slot)
 result['continuation_target']=next_slot
 result['continuation_sent']=continue_slot(root,c,next_catalog,next_slot,os.environ['GITHUB_RUN_ID'],transport(root,source,next_slot,os.environ['GH_TOKEN']))
 result['production_activation']=True
 return result
