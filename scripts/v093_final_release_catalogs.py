"""Carry every final live outcome into new immutable release catalogs.

Source attempts never decrease. Saved missing results become local PROMOTE;
held queries stay held so production cannot repeat them from a stale catalog.
"""
import collections,copy,hashlib
from scripts.v093_admission_runtime import Catalog,prepare_row,catalog_state,HELD,sha as state_sha
from scripts.v093_source_git_store import GitCAS
from scripts.v093_handoff_overlays import apply_task
from scripts.v093_action_catalogs import promotion_row

def apply_outcome(row,task,pin):
 row=copy.deepcopy(row);d=row['definition'];key=d['key'];source=d['source'];period=d['period']
 if task.get('definition')!=d or type(task.get('attempts')) is not int or task['attempts']<row['attempts']:raise ValueError('FINAL_HANDOFF_TASK_OR_ATTEMPTS')
 if task['status']=='RAW_BASIC_VERIFIED':
  reviews={source:{key:copy.deepcopy(row['legacy_review'])}};contract=apply_task(reviews,source,key,task,pin)
  updated=dict(definition=d,attempts=task['attempts'],status='READY_CHECK',legacy_review=reviews[source][key],execution_contract=contract)
  if row['execution_contract']['mode']!='RETAINED':return promotion_row(updated,'FINAL_NATIVE_COLD_VERIFIED:'+pin['commit'])
  return prepare_row(source,d['slot'],key,updated)
 if task['status'] not in HELD:raise ValueError('FINAL_HANDOFF_UNRESOLVED_WORK')
 row['attempts']=task['attempts'];row['legacy_review']['attempts']=task['attempts'];row['legacy_review'].setdefault('handoff_overlays',[]).append(dict(pin,status=task['status'],attempts=task['attempts'],error=task.get('error'),rejected_evidence=task.get('rejected_evidence')))
 row['legacy_review']['action']='FINAL_NATIVE_'+task['status'];row['status']=task['status']
 return prepare_row(source,d['slot'],key,row)

def compile_release(root,proposed,reports,namespace):
 pins={};summary={};events=[]
 for report in reports:
  source=report['source'];slot=report['slot'];cursor=report['cold_cursor'];last=cursor['last_archive']['branch'];suffix='/'+source
  if not last.startswith('refs/heads/jarvis-source-preflight/final-scope-archive-') or not last.endswith(suffix):raise ValueError('FINAL_HANDOFF_ARCHIVE_SCOPE')
  prefix=last.removeprefix('refs/heads/').removesuffix(suffix).rsplit('-',1)[0];outcomes={}
  for chunk in range(cursor['chunk_number']):
   store=GitCAS(root,prefix+'-'+str(chunk));commit,snapshot=store.read(source)
   if not snapshot or snapshot['slot']!=slot or snapshot['source']!=source:raise ValueError('FINAL_HANDOFF_ARCHIVE_MISSING')
   for key,task in snapshot['tasks'].items():
    if key in outcomes:raise ValueError('FINAL_HANDOFF_DUPLICATE_KEY')
    outcomes[key]=(task,dict(prefix=store.prefix,commit=commit))
  if len(outcomes)!=report['case_count']:raise ValueError('FINAL_HANDOFF_OUTCOME_COUNT')
  original=Catalog(GitCAS(root,'jarvis-source-preflight/final-handoff-reader'),proposed['catalogs'][source][slot],source,slot);rows=[];applied=set()
  for page in range(len(original.index['pages'])):
   for key,row in original.page(page):
    if key in outcomes:
     task,pin=outcomes[key];row=apply_outcome(row,task,pin);applied.add(key);events.append(dict(source=source,slot=slot,key=key,status=task['status'],attempts=task['attempts'],new_mode=row['execution_contract']['mode'],release_status=row['status'],pin=pin))
    rows.append(row)
  if applied!=set(outcomes):raise ValueError('FINAL_HANDOFF_UNAPPLIED_OUTCOME')
  state=catalog_state(source,slot,rows,'2026-10-30');store=GitCAS(root,'jarvis-source-preflight/release-final-'+namespace+'-'+slot)
  old=store.remote_head(source)
  if old!=0:
   _,prior=store.read(source)
   if state_sha(prior)!=state_sha(state):raise ValueError('FINAL_RELEASE_EXISTING_CATALOG_CONFLICT')
  elif not store.cas(source,0,state):raise ValueError('FINAL_RELEASE_CATALOG_CAS')
  commit=store.remote_head(source);entry=dict(commit=commit,index_sha256=hashlib.sha256(store.git('show',commit+':state.json').stdout).hexdigest());cold=Catalog(store,entry,source,slot)
  if sum(len(cold.page(i)) for i in range(len(cold.index['pages'])))!=len(rows):raise ValueError('FINAL_RELEASE_COLD_COUNTS')
  pins.setdefault(source,{})[slot]=entry;summary.setdefault(source,{})[slot]=dict(total=len(rows),status_counts=dict(collections.Counter(r['status'] for r in rows)),runnable_modes=dict(collections.Counter(r['execution_contract']['mode'] for r in rows if r['status'] in ('READY','READY_CHECK'))))
 return pins,summary,events
