"""Seven-source coordinator-shaped handoff acceptance in isolated remote state."""
import argparse,collections,gzip,hashlib,json
from pathlib import Path
from scripts.v093_source_coordination import Coordinator,SOURCES
from scripts.v093_source_git_store import GitCAS
from scripts.v093_source_partition import COUNTS
from scripts.v093_source_state_pages import encode
from scripts.v093_review_import import install

def frozen(source):
 review=json.loads(gzip.decompress((Path('frozen')/(source+'.review.json.gz')).read_bytes()))
 assignments={}
 for slot in (('ASC','DESC') if COUNTS[source]==2 else ('DESC',)):
  queue=json.loads(gzip.decompress((Path('frozen')/(source+'.'+slot+'.queue.json.gz')).read_bytes()))
  if queue['source']!=source or queue['direction']!=slot:raise ValueError('QUEUE_IDENTITY')
  for key in queue['task_keys']:
   if key in assignments:raise ValueError('DOUBLE_OWNED_TASK')
   assignments[key]=slot
 return review,assignments

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('save','verify'));p.add_argument('--source',choices=sorted(SOURCES),required=True);p.add_argument('--namespace',required=True);a=p.parse_args()
 review,assignments=frozen(a.source);store=GitCAS(Path.cwd(),'jarvis-source-preflight/'+a.namespace);c=Coordinator(store,a.source)
 if a.mode=='save':
  if store.remote_head(a.source)!=0:raise ValueError('QA_NAMESPACE_EXISTS')
  if not install(c,review,assignments,'frozen-40812627597'):raise ValueError('IMPORT_NOT_INSTALLED')
 revision,state=store.read(a.source)
 if set(state['tasks'])!=set(review['tasks']):raise ValueError('TASK_COVERAGE')
 for key,row in review['tasks'].items():
  t=state['tasks'][key]
  if t['attempts']!=row['attempts'] or t['legacy_review']!=row:raise ValueError('PROVENANCE_OR_ATTEMPTS_LOST')
  if t['definition']!=dict(source=a.source,key=key,slot=assignments[key],period=row['provenance'][0]['period']):raise ValueError('DEFINITION_BINDING')
  if t['status'] not in ('RECONCILE','APPLICABILITY_HOLD','CONTENT_BLOCKED','BLOCKED'):raise ValueError('UNSAFE_IMPORT_PROMOTION')
  if t['download_authorized'] or t['numeric_verified'] or t['pit_verified'] or t['full_acceptance']:raise ValueError('FALSE_ACCEPTANCE')
 before=hashlib.sha256(encode(state)).hexdigest()
 # Idempotence is checked with an independent in-memory CAS to avoid rewriting
 # hundreds of MB remotely merely to prove an unchanged replay is a no-op.
 class CopyCAS:
  def read(self,source):return 1,state
  def cas(self,source,rev,new):
   if hashlib.sha256(encode(new)).hexdigest()!=before:raise ValueError('REPLAY_MUTATED_STATE')
   return True
 if install(Coordinator(CopyCAS(),a.source),review,assignments,'frozen-40812627597') is not False:raise ValueError('NON_IDEMPOTENT_IMPORT')
 result=dict(schema='JARVIS_FORMAL_SHAPED_IMPORT_QA_V1',mode=a.mode,source=a.source,tasks=len(review['tasks']),sha256=before,commit=revision,statuses=dict(collections.Counter(t['status'] for t in state['tasks'].values())),attempts_and_provenance_preserved=True,replay_idempotent=True,market_requests=0,drive_writes=0,production_activation=False,limitation='Isolated QA coordinator schema; production migration and source adapters not activated')
 out=Path('results');out.mkdir(exist_ok=True);(out/(a.source+'-'+a.mode+'.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
