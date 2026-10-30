"""Real consecutive-chunk and independent restart QA, retained NDC bytes only."""
import argparse,hashlib,json
from pathlib import Path
from scripts.v093_admission_runtime import Catalog,GitArchive,catalog_state,run_until_budget
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);a=p.parse_args();root=Path.cwd();rows=json.loads(Path('results/ndc-two-cases.json').read_text())
 if len(rows)!=2 or len({r['definition']['key'] for r in rows})!=2:raise ValueError('TWO_DISTINCT_RETAINED_CASES_REQUIRED')
 source='NDC';slot='DESC';cs=GitCAS(root,'jarvis-source-preflight/continuous-catalog-'+a.namespace)
 if cs.remote_head(source)!=0 or not cs.cas(source,0,catalog_state(source,slot,rows,'2026-10-29')):raise ValueError('FRESH_CONTINUOUS_CATALOG')
 commit=cs.remote_head(source);entry=dict(commit=commit,index_sha256=hashlib.sha256(cs.git('show',commit+':state.json').stdout).hexdigest())
 c=Coordinator(GitCAS(root,'jarvis-source-preflight/continuous-'+a.namespace),source,ttl=600)
 archive=GitArchive(lambda snap:GitCAS(root,'jarvis-source-preflight/continuous-archive-'+a.namespace+'-'+str(snap['chunk_number'])))
 first=run_until_budget(c,Drive(service()),Catalog(cs,entry,source,slot),slot,'first','ISOLATED_RETAINED_ONLY_NO_PUT',archive,seconds=600,chunk_limit=1)
 if first['batches']!=2 or first['total_processed']!=2 or first['stop_reason']!='CATALOG_FINISHED' or first['admission_cursor']['archived_status_counts']!={'RAW_BASIC_VERIFIED':2}:raise ValueError('REAL_CONSECUTIVE_CHUNK_VALIDATION_FAILED')
 fresh=Coordinator(GitCAS(root,'jarvis-source-preflight/continuous-'+a.namespace),source)
 second=run_until_budget(fresh,Drive(service()),Catalog(cs,entry,source,slot),slot,'cold','ISOLATED_RETAINED_ONLY_NO_PUT',archive,seconds=600,chunk_limit=1)
 if second['total_processed']!=0:raise ValueError('COLD_RESTART_REPROCESSED_FINISHED_RAW')
 result=dict(schema='JARVIS_OVERNIGHT_REAL_CONTINUOUS_V1',first=first,cold_restart=second,periods=[r['definition']['period'] for r in rows],source_requests=0,formal_raw_writes=0,data_repaired=0,verified_exceptions=0,numeric_verified=False,pit_verified=False,full_acceptance=False,production_activation=False)
 Path('results/real-continuous.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
