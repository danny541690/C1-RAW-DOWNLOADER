"""Approve only the frozen admitted campaign from real phase evidence; never enable it."""
import json,os
from pathlib import Path
from scripts.v093_admission_runtime import code_digest,validate_catalog_manifest
from scripts.v093_source_partition import COUNTS

def main():
 root=Path.cwd();digest=code_digest(root);reports=[json.loads(p.read_text()) for p in Path('collected').rglob('final-scope-phase.json')];cold=[r for r in reports if r['phase']=='cold'];expected={(s,slot) for s,n in COUNTS.items() for slot in (('DESC','ASC') if n==2 else ('DESC',))}
 if len(cold)!=12 or {(r['source'],r['slot']) for r in cold}!=expected:raise ValueError('FINAL_SCOPE_TWELVE_RESULTS_REQUIRED')
 proof_versions={r['code_sha'] for r in reports};proof_digests={r['code_sha256'] for r in reports}
 if any(r['operational_pass'] is not True for r in reports) or len(proof_versions)!=1 or len(proof_digests)!=1:raise ValueError('FINAL_SCOPE_CODE_OR_OPERATIONAL_GATE')
 proof=next(iter(proof_versions))
 if proof==os.environ['GITHUB_SHA']:
  if next(iter(proof_digests))!=digest:raise ValueError('FINAL_SCOPE_CODE_DIGEST')
 else:
  # Reuse actual native evidence only when the native worker dependency tree is unchanged; publisher has separate real reconciliation.
  from scripts.v093_source_git_store import GitCAS
  git=GitCAS(root,'jarvis-source-preflight/final-code-proof');git.git('fetch','--no-tags','--no-write-fetch-head','origin',proof)
  changes=set(git.git('diff','--name-only',proof,os.environ['GITHUB_SHA']).stdout.decode().splitlines())
  allowed={'scripts/v093_final_release_catalogs.py','scripts/v093_final_scope_summary.py','tests/test_final_release_catalogs.py','.github/workflows/jarvis-seven-final-release-build.yml','scripts/v093_acceptance_publish.py','scripts/v093_reconcile_scope_publications.py'}
  if not changes<=allowed:raise ValueError('FINAL_SCOPE_PRODUCTION_CODE_CHANGED_REVALIDATION_REQUIRED')

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
 from scripts.v093_final_release_catalogs import compile_release
 final_pins,handoff_counts,handoff_events=compile_release(root,proposed,cold,os.environ['GITHUB_RUN_ID'])
 proposed['catalogs']=final_pins
 proposed.update(enabled=False,tested_code_sha256=digest,approved_checks=dict(source_contracts=True,continuation_and_quota=True,cutover=True),candidate_scope='FROZEN_ADMITTED_NATIVE_CAMPAIGN_ONLY',activation_evidence_run=os.environ['GITHUB_RUN_ID'])
 result=dict(native_code_sha=proof,native_worker_code_unchanged=True,handoff_counts=handoff_counts,handoff_events=handoff_events,schema='JARVIS_FINAL_ADMITTED_CAMPAIGN_ACCEPTANCE_V1',code_sha=os.environ['GITHUB_SHA'],code_sha256=digest,run_id=os.environ['GITHUB_RUN_ID'],admitted_campaign_ready=True,production_activation=False,full_database_complete=False,three_day_throughput_guaranteed=False,slots=cold,verified_units=sum(r['units_basic_verified'] for r in cold),classified_hold_units=sum(r['units_classified_hold'] for r in cold),real_transport=transport,old_writers=old,formal_raw_writes=0,limitation='Two real runner phases on samples from the exact frozen queues; unsupported/empty history remains held, no numeric/PIT/full-universe certification')
 Path('results/final-campaign-acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');Path('results/approved-disabled-release.json').write_text(json.dumps(proposed,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(admitted_campaign_ready=True,verified_units=result['verified_units'],classified_hold_units=result['classified_hold_units'],production_activation=False)),flush=True)
if __name__=='__main__':main()
