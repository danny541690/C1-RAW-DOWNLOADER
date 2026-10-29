"""One consolidated final check; reports unimplemented release work honestly."""
import json,subprocess,sys
from pathlib import Path

def main():
 out=Path('results/final-prelaunch');out.mkdir(parents=True,exist_ok=True)
 p=subprocess.run([sys.executable,'-m','scripts.v093_source_preflight','--out',str(out/'regression')],capture_output=True,text=True)
 if p.returncode:raise RuntimeError('CONSOLIDATED_REGRESSION_FAILED')
 local=json.loads((out/'regression/summary.json').read_text());config=json.loads(Path('config/v093_seven_source_design.json').read_text());modes=[]
 for slot in config['slots']:
  cmd=[sys.executable,'-m','scripts.v093_source_worker','--source',slot['source'],'--direction',slot['direction'],'--mode','production','--namespace','must-not-activate']
  probe=subprocess.run(cmd,capture_output=True,text=True)
  blocked=probe.returncode!=0 and 'PRODUCTION_RELEASE_BLOCKED' in probe.stderr
  if not blocked:raise RuntimeError('UNEXPECTED_PRODUCTION_ACTIVATION_PATH')
  modes.append(dict(source=slot['source'],direction=slot['direction'],production_mode='BLOCKED_BEFORE_IO'))
 result=dict(schema='JARVIS_FINAL_PRELAUNCH_BUNDLE_V1',regression=local['tests'],entry_yaml_passed=local['yaml_files'],production_entry_probes=modes,
  deployment_ready=False,source_requests=0,formal_raw_writes=0,
  required_release_work=[dict(id='G1',status='CATALOG_ROLLOUT_AND_RELEASE_APPROVAL_REQUIRED',item='Production runtime now reads pinned catalogs and bounded active chunks; compile/verify seven production catalogs and approve the disabled release manifest'),dict(id='G2',status='PARTIAL_TYPES_AND_LIVE_ACCEPTANCE',item='Complete required source contract types and positive download/save/revalidation cases; keep unknown history held'),dict(id='G3',status='INTEGRATION_AND_LIVE_LOAD_REQUIRED',item='Wire durable continuation/watchdog and measure provider quotas, lease heartbeat and storage throughput on the actual worker'),dict(id='G4',status='RELEASE_REQUIRED',item='After G1-G3 pass, merge pinned candidate, recheck old writers/ghost queue and validate the initial formal batch')],
  nonblocking_backlog='1602 historical empty-response tasks remain source-coverage review; they do not have to all be resolved before a safe admitted-task worker can start',
  evidence_scope='Local/isolated readiness checks, not a production smoke pass')
 if '--probe-drive' in sys.argv:
  from scripts.annual_actual_firstpass import Drive,service
  from scripts.v093_rejected_evidence import preserve
  d=Drive(service());raw=b'JARVIS REJECTION STORAGE PROBE ONLY - NOT MARKET DATA'
  first=preserve(d,'TWSE',raw,qa=True);second=preserve(d,'TWSE',raw,qa=True)
  if first!=second:raise ValueError('REJECTION_STORAGE_REPLAY_CHANGED')
  result['rejected_evidence_storage_probe']=dict(fixture_only=True,first=first,repeated=second)
 (out/'release-gates.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
