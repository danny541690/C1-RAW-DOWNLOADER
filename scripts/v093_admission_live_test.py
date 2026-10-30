"""One real retained NDC task through pinned catalog, bounded pool and archive.

Uses isolated Git state and unchanged Drive RAW; no production activation.
"""
import argparse,gzip,hashlib,json
from pathlib import Path
from scripts.v093_admission_runtime import Catalog,GitArchive,catalog_state,run_catalog,code_digest
from scripts.v093_native_reuse_batch import select
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();source='NDC';slot='DESC'
 if json.loads(Path('config/v093_source_release.json').read_text())['enabled']:raise ValueError('LIVE_TEST_MUST_NOT_ENABLE_PRODUCTION')
 case=select(source);case['mode']='RETAINED';review=json.loads(gzip.decompress(Path('frozen/NDC.review.json.gz').read_bytes()))['tasks'][case['key']]
 row=dict(definition=dict(source=source,key=case['key'],period=case['period'],slot=slot),attempts=review['attempts'],status='READY_CHECK',legacy_review=review,execution_contract=case)
 catalog_store=GitCAS(root,'jarvis-source-preflight/catalog-'+a.namespace)
 if catalog_store.remote_head(source)!=0:raise ValueError('QA_CATALOG_EXISTS')
 if not catalog_store.cas(source,0,catalog_state(source,slot,[row],'2026-10-29')):raise ValueError('CATALOG_SAVE_CONFLICT')
 commit=catalog_store.remote_head(source);raw=catalog_store.git('show',commit+':state.json').stdout
 entry=dict(commit=commit,index_sha256=hashlib.sha256(raw).hexdigest())
 store=GitCAS(root,'jarvis-source-preflight/'+a.namespace);catalog=Catalog(store,entry,source,slot);c=Coordinator(store,source,ttl=600);d=Drive(service())
 archive=GitArchive(lambda snap:GitCAS(root,'jarvis-source-preflight/archive-'+a.namespace+'-'+str(snap['chunk_number'])))
 result=run_catalog(c,d,catalog,slot,'admission-start','ISOLATED_RETAINED_ONLY_NO_PUT',archive,max_units=1,seconds=120,chunk_limit=1)
 if result['processed']!=1 or not result['chunk_archived'] or not result['catalog_finished'] or result['active_source_tasks']!=0:raise ValueError('CATALOG_NATIVE_ARCHIVE_INVARIANT')
 fresh=Coordinator(GitCAS(root,'jarvis-source-preflight/'+a.namespace),source);_,restored=fresh.store.read(source);receipt=restored['admission'][slot]['last_archive']
 archive_store=GitCAS(root,'jarvis-source-preflight/archive-'+a.namespace+'-0');_,saved=archive_store.read(source);task=saved['tasks'][case['key']]
 if task['attempts']!=review['attempts'] or task['legacy_review']!=review or task['status']!='RAW_BASIC_VERIFIED':raise ValueError('ARCHIVED_LEGACY_PROGRESS_LOST')
 repeated=run_catalog(fresh,d,Catalog(fresh.store,entry,source,slot),slot,'admission-restart','ISOLATED_RETAINED_ONLY_NO_PUT',archive,max_units=1,seconds=120,chunk_limit=1)
 if repeated['processed']!=0 or repeated['active_source_tasks']!=0 or repeated['admission_cursor']['archived_status_counts']!={'RAW_BASIC_VERIFIED':1}:raise ValueError('RESTART_REPROCESSED_FINISHED_TASK')
 report=dict(schema='JARVIS_PINNED_ADMISSION_NATIVE_QA_V1',catalog_entry=entry,result=result,cold_restart=repeated,archive_receipt=receipt,old_attempts_preserved=True,legacy_provenance_preserved=True,source_requests=0,formal_raw_writes=0,production_enabled=False,code_manifest_sha256=code_digest(root),limitation='One retained NDC case through new admission runtime; seven production catalogs not approved')
 out=Path('results');out.mkdir(exist_ok=True);(out/'admission-runtime.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':main()
