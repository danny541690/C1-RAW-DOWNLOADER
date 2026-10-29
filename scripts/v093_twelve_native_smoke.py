"""Twelve disjoint real retained checks over shared per-source Git CAS.

Provider quotas are a labelled control fixture, not a market HTTP load test.
No production state, source HTTP or RAW writes.
"""
import argparse,hashlib,json,re
from pathlib import Path
from scripts.v093_admission_runtime import Catalog,GitArchive,catalog_state,run_until_budget
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_rate import reserve,RequestDeferred

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--direction',choices=('ASC','DESC'),required=True);p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();out=Path('results');out.mkdir(exist_ok=True)
 source=a.source;slot=a.direction;rows=json.loads(Path('inputs/slot-cases.json').read_text())[source+'|'+slot]
 cs=GitCAS(root,'jarvis-source-preflight/catalog-'+a.namespace+'-'+slot)
 if cs.remote_head(source)!=0 or not cs.cas(source,0,catalog_state(source,slot,rows,'2026-10-30')):raise ValueError('FRESH_TWELVE_NATIVE_CATALOG')
 commit=cs.remote_head(source);entry=dict(commit=commit,index_sha256=hashlib.sha256(cs.git('show',commit+':state.json').stdout).hexdigest())
 c=Coordinator(GitCAS(root,'jarvis-source-preflight/'+a.namespace),source,ttl=600)
 archive=GitArchive(lambda snap:GitCAS(root,'jarvis-source-preflight/archive-'+a.namespace+'-'+slot))
 result=run_until_budget(c,Drive(service()),Catalog(cs,entry,source,slot),slot,source+'-'+slot,'READ_ONLY_NO_PUT',archive,seconds=1200,chunk_limit=1)
 _,cold=GitCAS(root,'jarvis-source-preflight/'+a.namespace).read(source);cursor=cold['admission'][slot]
 passed=cursor.get('finished') is True and cursor.get('archived_status_counts',{}).get('RAW_BASIC_VERIFIED',0)==len(rows)
 report=dict(schema='JARVIS_TWELVE_REAL_NATIVE_SLOT_V1',source=source,slot=slot,case_count=len(rows),periods=[r['definition']['period'] for r in rows],result=result,cold_cursor=cursor,source_requests=0,formal_raw_writes=0,production_activation=False,passed=passed,quota_fixture_only=True)
 if not passed:
  # Save an isolated failure before raising; never relabel native rejection PASS.
  if rows:
   try:
    from scripts.v093_source_adapters import NativeAdapter
    row=rows[0];adapter=NativeAdapter(c,Drive(service()),dict(source=source,key=row['definition']['key']),row,target_root='READ_ONLY_NO_PUT');adapter.validate(adapter.read(row['execution_contract']['reference']))
   except Exception as exc:
    report['native_error_type']=type(exc).__name__
    if re.fullmatch('[A-Z0-9_]{1,100}',str(exc)):report['native_error_code']=str(exc)
  (out/'slot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True);raise ValueError('REAL_NATIVE_SLOT_NOT_VERIFIED')
 key='EXPLICIT_QUOTA_FIXTURE_'+slot;c.add([dict(source=source,key=key,period='2026-10-30',slot=slot)]);ticket=c.claim(slot,'quota-'+slot,slot)
 if not ticket or ticket['key']!=key:raise ValueError('QUOTA_FIXTURE_CLAIM_SCOPE')
 try:
  reserve(c,ticket,cost=1,limit=1,window=3600,spacing=0);quota='WIN';c.error(ticket,'APPLICABILITY_HOLD','QA_CONTROL','NO_MARKET_HTTP')
 except RequestDeferred as exc:quota='DEFER';c.defer(ticket,exc.seconds)
 _,state=c.store.read(source)
 if state['tasks'][key]['attempts']!=0:raise ValueError('CONTROL_FIXTURE_SPENT_DOWNLOAD_ATTEMPT')
 report.update(quota_result=quota,task_attempts_for_quota=0)
 (out/'slot.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
