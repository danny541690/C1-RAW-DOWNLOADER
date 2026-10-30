"""Two independent runner phases over samples from the exact pinned release queues.

Uses the real native worker, Git CAS, Drive and immutable chunk archives. No
production state or formal RAW writes. Holds remain data holds, not data passes.
"""
import argparse,hashlib,json,os
from pathlib import Path
from scripts.v093_admission_runtime import Catalog,GitArchive,catalog_state,run_catalog,validate_catalog_manifest,code_digest,HELD
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_coordination import Coordinator

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=('start','cold'),required=True);p.add_argument('--source',required=True);p.add_argument('--slot',required=True);p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();out=Path('results');out.mkdir(exist_ok=True)
 release=json.loads(Path('inputs/proposed-action-release.json').read_text());validate_catalog_manifest(release['catalogs']);source=a.source;slot=a.slot;pin=release['catalogs'][source][slot]
 original=Catalog(GitCAS(root,'jarvis-source-preflight/final-scope-reader'),pin,source,slot);rows,_,_=original.chunk(0,0,12)
 if not rows:raise ValueError('FINAL_SCOPE_EMPTY_SOURCE_SLOT')
 store=GitCAS(root,'jarvis-source-preflight/final-scope-'+a.namespace);c=Coordinator(store,source,ttl=600);d=Drive(service());cs=GitCAS(root,'jarvis-source-preflight/final-scope-catalog-'+a.namespace+'-'+slot)
 if a.phase=='start' and cs.remote_head(source)==0:
  if not cs.cas(source,0,catalog_state(source,slot,list(rows.values()),'2026-10-30')):raise ValueError('FINAL_SCOPE_CATALOG_CAS')
  cp=cs.remote_head(source);entry=dict(commit=cp,index_sha256=hashlib.sha256(cs.git('show',cp+':state.json').stdout).hexdigest())
  target=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','FINAL_SCOPE_'+a.namespace+'_'+source+'_'+slot)
  def register(s):
   if slot in s.get('scope_checks',{}):raise ValueError('FINAL_SCOPE_PHASE_NO_RESET')
   s.setdefault('scope_checks',{})[slot]=dict(pin=entry,target=target,original_pin=pin,case_count=len(rows))
  c.update(register)
 else:
  _,prior=store.read(source);binding=prior['scope_checks'][slot];entry=binding['pin'];target=binding['target']
  if binding['original_pin']!=pin or binding['case_count']!=len(rows):raise ValueError('FINAL_SCOPE_COLD_BINDING')
 catalog=Catalog(cs,entry,source,slot)
 archive=GitArchive(lambda snap:GitCAS(root,'jarvis-source-preflight/final-scope-archive-'+a.namespace+'-'+slot+'-'+str(snap['chunk_number'])))
 result=run_catalog(c,d,catalog,slot,'scope-'+a.phase,target,archive,max_units=6,seconds=600,chunk_limit=6)
 _,cold=GitCAS(root,'jarvis-source-preflight/final-scope-'+a.namespace).read(source);cursor=cold['admission'][slot];counts=cursor.get('archived_status_counts',{})
 snapshot_units=0;revalidated=0
 for chunk in range(cursor.get('chunk_number',0)):
  _,snapshot=GitCAS(root,'jarvis-source-preflight/final-scope-archive-'+a.namespace+'-'+slot+'-'+str(chunk)).read(source)
  if not snapshot or snapshot['source']!=source or snapshot['slot']!=slot:raise ValueError('FINAL_SCOPE_COLD_ARCHIVE')
  for key,task in snapshot['tasks'].items():
   if task['attempts']<task['legacy_review']['attempts'] or task.get('owner'):raise ValueError('FINAL_SCOPE_COLD_ATTEMPTS_OR_OWNER')
   if task['status']=='RAW_BASIC_VERIFIED':
    from scripts.v093_source_adapters import NativeAdapter
    adapter=NativeAdapter(None,d,dict(source=source,key=key),task,target_root=target);raw=adapter.read(task['raw_reference'])
    if hashlib.sha256(raw).hexdigest()!=task['raw_sha256']:raise ValueError('FINAL_SCOPE_INDEPENDENT_RAW_SHA')
    adapter.validate(raw);revalidated+=1
   snapshot_units+=1
 verified=counts.get('RAW_BASIC_VERIFIED',0);held=sum(counts.get(s,0) for s in HELD)
 operational=not result.get('source_hold') and snapshot_units==verified+held and (a.phase!='cold' or cursor.get('finished') is True and snapshot_units==len(rows))
 report=dict(schema='JARVIS_FINAL_SCOPE_NATIVE_PHASE_V1',phase=a.phase,source=source,slot=slot,code_sha=os.environ['GITHUB_SHA'],code_sha256=code_digest(root),original_pin=pin,case_count=len(rows),sample_is_not_full_database=True,units_basic_verified=verified,cold_revalidated_units=revalidated,units_classified_hold=held,data_all_basic_verified=held==0,operational_pass=operational,result=result,cold_cursor=cursor,source_http_intents=sum(v['cost'] for v in cold.get('http_budget',{}).get('intents',[])),formal_raw_writes=0,production_activation=False,full_acceptance=False)
 (out/'final-scope-phase.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
 if not operational:raise ValueError('FINAL_SCOPE_NATIVE_PHASE_NOT_ACCEPTED')
if __name__=='__main__':main()
