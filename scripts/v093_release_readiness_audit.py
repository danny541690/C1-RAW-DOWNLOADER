"""Explicit release readiness, separate from passing regression results."""
import json,os
from pathlib import Path
from scripts.v093_admission_runtime import validate_catalog_manifest
from scripts.v093_source_partition import COUNTS

def main():
 proposed=json.loads(Path('inputs/proposed-action-release.json').read_text());actions=json.loads(Path('inputs/action-catalogs.json').read_text());validate_catalog_manifest(proposed['catalogs'])
 automatic=set(actions['automatic_missing_sources']);missing_rules=sorted(set(COUNTS)-automatic)
 actual=json.loads(Path('config/v093_source_release.json').read_text())
 result=dict(schema='JARVIS_RELEASE_READINESS_AUDIT_V1',code_sha=os.environ['GITHUB_SHA'],candidate_manifest_complete=True,source_count=len(proposed['catalogs']),direction_count=sum(len(v) for v in proposed['catalogs'].values()),automatic_missing_sources=sorted(automatic),sources_without_automatic_missing_rules=missing_rules,actual_release_enabled=actual['enabled'],deployment_ready=False,source_requests=0,formal_raw_writes=0,remaining=[dict(item='Automatic missing/correction scope',status='INCOMPLETE',sources=missing_rules),dict(item='Actual provider long-run limits and throughput',status='NOT_RUN_FOR_FINAL_SCOPE'),dict(item='Merge fixed release and activate twelve schedules',status='NOT_DONE')],existing_formal_three_unit_canary='Prior verified storage handoff is not twelve-schedule activation')
 out=Path('results');out.mkdir(exist_ok=True);(out/'release-readiness.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
