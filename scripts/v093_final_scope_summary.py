"""Approve only the frozen admitted campaign from real phase evidence; never enable it."""
import json,os
from pathlib import Path
from scripts.v093_admission_runtime import code_digest,validate_catalog_manifest
from scripts.v093_source_partition import COUNTS

def main():
 root=Path.cwd();digest=code_digest(root);reports=[json.loads(p.read_text()) for p in Path('collected').rglob('final-scope-phase.json')];cold=[r for r in reports if r['phase']=='cold'];expected={(s,slot) for s,n in COUNTS.items() for slot in (('DESC','ASC') if n==2 else ('DESC',))}
 if len(cold)!=12 or {(r['source'],r['slot']) for r in cold}!=expected:raise ValueError('FINAL_SCOPE_TWELVE_RESULTS_REQUIRED')
 if any(r['operational_pass'] is not True or r['code_sha']!=os.environ['GITHUB_SHA'] or r['code_sha256']!=digest for r in reports):raise ValueError('FINAL_SCOPE_CODE_OR_OPERATIONAL_GATE')
 if any(r.get('cold_revalidated_units')!=r['units_basic_verified'] for r in reports):raise ValueError('FINAL_SCOPE_INDEPENDENT_REVALIDATION_REQUIRED')
 if any(sum(r['units_basic_verified'] for r in cold if r['source']==source)==0 for source in COUNTS):raise ValueError('FINAL_SCOPE_POSITIVE_NATIVE_CASE_PER_SOURCE_REQUIRED')
 if len(reports)!=24:raise ValueError('FINAL_SCOPE_TWO_RUNNER_PHASES_REQUIRED')
 transport=json.loads(Path('inputs/continuation-live.json').read_text())
 if transport.get('real_github_dispatch_ack_verified') is not True or transport.get('source_requests')!=0 or transport.get('formal_raw_writes')!=0:raise ValueError('FINAL_SCOPE_REAL_TRANSPORT_REQUIRED')
 old=json.loads(Path('results/old-writer-audit.json').read_text())
 if old.get('passed') is not True:raise ValueError('FINAL_SCOPE_OLD_WRITERS_ACTIVE')
 proposed=json.loads(Path('inputs/proposed-action-release.json').read_text());validate_catalog_manifest(proposed['catalogs'])
 for report in cold:
  if report['original_pin']!=proposed['catalogs'][report['source']][report['slot']]:raise ValueError('FINAL_SCOPE_RELEASE_CATALOG_CHANGED')
 proposed.update(enabled=False,tested_code_sha256=digest,approved_checks=dict(source_contracts=True,continuation_and_quota=True,cutover=True),candidate_scope='FROZEN_ADMITTED_NATIVE_CAMPAIGN_ONLY',activation_evidence_run=os.environ['GITHUB_RUN_ID'])
 result=dict(schema='JARVIS_FINAL_ADMITTED_CAMPAIGN_ACCEPTANCE_V1',code_sha=os.environ['GITHUB_SHA'],code_sha256=digest,run_id=os.environ['GITHUB_RUN_ID'],admitted_campaign_ready=True,production_activation=False,full_database_complete=False,three_day_throughput_guaranteed=False,slots=cold,verified_units=sum(r['units_basic_verified'] for r in cold),classified_hold_units=sum(r['units_classified_hold'] for r in cold),real_transport=transport,old_writers=old,formal_raw_writes=0,limitation='Two real runner phases on samples from the exact frozen queues; unsupported/empty history remains held, no numeric/PIT/full-universe certification')
 Path('results/final-campaign-acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');Path('results/approved-disabled-release.json').write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(admitted_campaign_ready=True,verified_units=result['verified_units'],classified_hold_units=result['classified_hold_units'],production_activation=False)),flush=True)
if __name__=='__main__':main()
