"""Real full handoff capacity/restore test in isolated Git branches, no source HTTP."""
import argparse,gzip,hashlib,json
from pathlib import Path
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_state_pages import encode
from scripts.v093_source_coordination import SOURCES
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['save','verify']);p.add_argument('--namespace',required=True);a=p.parse_args()
 store=GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace);results={};total=0
 for source in sorted(SOURCES):
  if a.mode=='save':
   review=json.loads(gzip.decompress((Path('frozen')/(source+'.review.json.gz')).read_bytes()))
   state=dict(source=source,mode='HANDOFF_REVIEW_ONLY',tasks=review['tasks'],fence=0,outbox={},production_activation=False)
   if store.remote_head(source)!=0:raise RuntimeError('QA_NAMESPACE_ALREADY_EXISTS')
   if not store.cas(source,0,state):raise RuntimeError('QA_SAVE_CONFLICT')
   expected=dict(tasks=len(state['tasks']),sha256=hashlib.sha256(encode(state)).hexdigest())
  else:expected=json.loads(Path('expected/full-state-save.json').read_text())['sources'][source]
  revision,restored=store.read(source)
  digest=hashlib.sha256(encode(restored)).hexdigest()
  if len(restored['tasks'])!=expected['tasks'] or digest!=expected['sha256']:raise RuntimeError('COLD_RESTORE_MISMATCH')
  if any(t.get('full_acceptance') or t.get('download_authorized') for t in restored['tasks'].values()):raise RuntimeError('FALSE_PROMOTION')
  names=store.git('ls-tree','--name-only',revision).stdout.decode().splitlines()
  results[source]=dict(tasks=expected['tasks'],sha256=digest,commit=revision,page_files=len(names)-1,bytes=len(encode(restored)))
  total+=expected['tasks'];print('VERIFIED_SOURCE',source,expected['tasks'],len(names)-1,flush=True)
 if total!=189521:raise RuntimeError('EXPECTED_FROZEN_TASK_SCOPE_MISMATCH')
 out=Path('results');out.mkdir(exist_ok=True)
 result=dict(schema='JARVIS_FULL_PAGED_STATE_PREFLIGHT_V1',mode=a.mode,sources=results,total_tasks=total,
  full_scope_restore_verified=True,market_requests=0,drive_writes=0,production_activation=False)
 (out/('full-state-'+a.mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
