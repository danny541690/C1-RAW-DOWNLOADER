"""Complete three preserved native-test outboxes without re-running any data task."""
import hashlib,json
from pathlib import Path
from scripts.v093_acceptance_publish import publish,DriveArchive,encode
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_git_store import GitCAS

def main():
 identity='41001539894-1-final-scope-cold-ASC';reports=[]
 for source in ('TAIFEX','MOPS','TDCC'):
  c=Coordinator(GitCAS(Path.cwd(),'jarvis-source-preflight/record-'+identity),source);_,state=c.store.read(source)
  if not state or state['record_metadata']['source_namespace']!=source or state['record_metadata']['code_sha']!='fb0acb4d5b3360f0ea534e127cc320895bf775cf':raise ValueError('SCOPE_PUBLICATION_BINDING')
  record=dict(schema='JARVIS_AUTOMATIC_ACCEPTANCE_RECORD_V1',metadata=state['record_metadata'],files=state['tasks'])
  if hashlib.sha256(encode(record)).hexdigest()!=state['record_sha256']:raise ValueError('SCOPE_PUBLICATION_ORIGINAL_SHA')
  evidence=json.loads(record['files']['final-scope-phase.json']['text'])
  if evidence['operational_pass'] is not True or evidence.get('source')!=source or evidence.get('slot')!='ASC' or evidence.get('phase')!='cold':raise ValueError('SCOPE_PUBLICATION_NOT_NATIVE_PASS')
  receipt=publish(c,record,DriveArchive(identity+'-'+source))
  if receipt['publication_state']!='GIT_AND_DRIVE_READBACK_VERIFIED':raise ValueError('SCOPE_PUBLICATION_NOT_VERIFIED')
  reports.append(dict(source=source,original_record_sha256=state['record_sha256'],receipt=receipt))
 Path('results').mkdir(exist_ok=True);Path('results/reconciled-scope-publications.json').write_text(json.dumps(dict(source_requests=0,formal_raw_writes=0,original_records_unchanged=True,records=reports),indent=2)+'\n');print(json.dumps(dict(reconciled=len(reports),source_requests=0,formal_raw_writes=0)),flush=True)
if __name__=='__main__':main()
