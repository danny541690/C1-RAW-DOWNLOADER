"""Actual native parser/storage repair QA from a labelled corrupted COPY.

Reuses an already verified official TDCC payload; zero official HTTP. Never
claims a user database file was corrupt or repaired. Both QA versions remain.
"""
import argparse,copy,hashlib,json
from pathlib import Path
from scripts.v093_source_adapters import NativeAdapter
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
from scripts.v093_source_git_store import GitCAS
from scripts.v093_native_missing_batch import later_qa_progress
from scripts.v093_acceptance_publish import publish,DriveArchive,encode

def main():
 from scripts.annual_actual_firstpass import Drive,service
 p=argparse.ArgumentParser();p.add_argument('--namespace',required=True);p.add_argument('--resume-namespace');a=p.parse_args();root=Path.cwd();out=Path('results');out.mkdir(exist_ok=True);d=Drive(service())
 history,pins=later_qa_progress(root);known='TDCC|2025-12|20251205|8401'
 if known not in history or history[known]['attempts']!=2 or history[known]['status']!='RAW_BASIC_VERIFIED':raise ValueError('LATEST_NATIVE_PROGRESS_NOT_PRESERVED')
 baseline=GitCAS(root,'jarvis-source-preflight/native-positive-40910020200-1');_,saved=baseline.read('TDCC');good=saved['tasks'][known];case=good['execution_contract']
 adapter=NativeAdapter(None,d,dict(source='TDCC',key=known),good,target_root=saved['qa_root']);raw=adapter.read(good['raw_reference'])
 if hashlib.sha256(raw).hexdigest()!=good['raw_sha256']:raise ValueError('VERIFIED_SOURCE_RAW_CHANGED')
 adapter.validate(raw);bad=raw.replace(b'</form>',b'</broken-form>')
 if bad==raw:raise ValueError('FAULT_COPY_NOT_CREATED')
 if a.resume_namespace:
  folder=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','EXPLICIT_FAULT_COPY_REPAIR_'+a.resume_namespace)
  c=Coordinator(GitCAS(root,'jarvis-source-preflight/'+a.resume_namespace),'TDCC',ttl=600);_,state=c.store.read('TDCC')
  if not state or len(state['tasks'])!=1:raise ValueError('EXPECTED_SINGLE_INTERRUPTED_QA_REPAIR')
  key,task=next(iter(state['tasks'].items()));proof=task['execution_contract']['repair_evidence'];bad_ref=proof['reference'];bad_sha=proof['sha256']
  adapter=NativeAdapter(c,d,dict(source='TDCC',key=key),task,target_root=folder)
  if adapter.read(bad_ref)!=bad or task.get('owner'):raise ValueError('QA_REPAIR_RECONCILIATION_SCOPE')
  ref=adapter.find_locator(task['save_intent']['locator']);recovered=adapter.read(ref)
  if hashlib.sha256(recovered).hexdigest()!=task['save_intent']['sha256']:raise ValueError('QA_REPAIR_RECOVERY_SHA')
  adapter.validate(recovered)
  if task['status']=='RAW_BASIC_VERIFIED':
   receipt=task['storage_receipt'];stored=adapter.read(receipt['reference'])
   if hashlib.sha256(stored).hexdigest()!=receipt['sha256']:raise ValueError('QA_STORED_RECEIPT_CHANGED')
   result=dict(reference=ref,sha256=task['raw_sha256'],stats=adapter.validate(recovered),already_verified=True)
  else:
   if task['status']!='CONTENT_BLOCKED' or task.get('error')!=dict(phase='READBACK',code='ValueError'):raise ValueError('QA_REPAIR_RECONCILIATION_SCOPE')
   def reconcile(s):
    current=s['tasks'][key]
    if current!=task:raise ValueError('QA_REPAIR_CHANGED_DURING_RECONCILIATION')
    current.update(status='RECONCILE',reconciliation=dict(evidence_id='INDEPENDENT_STABLE_VERSION_AND_EXPECTED_SHA',readback_verified=True,sha256=task['save_intent']['sha256']))
   c.update(reconcile);result=Executor(c,adapter).resume('DESC','native-qa-cold-repair')

 else:
  folder=d.folder('1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','EXPLICIT_FAULT_COPY_REPAIR_'+a.namespace);bad_sha=hashlib.sha256(bad).hexdigest();name='EXPLICIT_CORRUPTED_QA_COPY_'+bad_sha+'.html';d.direct_readback=True;d.put(folder,name,bad,'text/html',overwrite=False);bad_ref=d.find(folder,name)['id']
  key=known+'|EXPLICIT_QA_COPY';repair=copy.deepcopy(case);repair.update(key=key,mode='REPAIR');repair.pop('missing_evidence',None)
  repair['repair_evidence']=dict(source='TDCC',key=key,period=case['period'],reference=bad_ref,sha256=bad_sha,download_approved=True,reason='NATIVE_CONTENT_REJECTED',official_evidence_id='VERIFIED_NATIVE_QA_STATE:'+good['raw_reference'],replacement_reference=good['raw_reference'],replacement_sha256=good['raw_sha256'],replacement_verified=True,fixture_only=True)
  c=Coordinator(GitCAS(root,'jarvis-source-preflight/'+a.namespace),'TDCC',ttl=600)
  if c.store.remote_head('TDCC')!=0:raise ValueError('FRESH_REPAIR_QA_NAMESPACE')
  legacy=dict(source='TDCC',task_key=key,attempts=good['attempts'],action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(source='TDCC',period=case['period'],raw_reference=bad_ref,sha256=bad_sha,fixture_only=True)])
  c.add([dict(source='TDCC',key=key,period=case['period'],slot='DESC')]);c.update(lambda s:s['tasks'][key].update(attempts=good['attempts'],legacy_review=legacy,execution_contract=repair))
  _,state=c.store.read('TDCC');adapter=NativeAdapter(c,d,dict(source='TDCC',key=key),state['tasks'][key],target_root=folder);result=Executor(c,adapter).one('DESC','native-qa-repair')
 _,state=c.store.read('TDCC');task=state['tasks'][key]
 if task['status']!='RAW_BASIC_VERIFIED' or adapter.source_requests or adapter.read(bad_ref)!=bad or adapter.read(good['raw_reference'])!=raw or task['raw_reference'] in (bad_ref,good['raw_reference']):raise ValueError('QA_IMMUTABLE_REPAIR_INVARIANT')
 report=dict(schema='JARVIS_FAULT_COPY_NATIVE_REPAIR_V1',source='TDCC',period=case['period'],code=case['code'],explicit_fault_injected_copy=True,cold_recovered=bool(a.resume_namespace),qa_copy_repaired=1,new_qa_repairs_this_job=0 if result.get('already_verified') else 1,real_market_invalid_file_repaired=0,formal_raw_writes=0,formal_data_repaired=0,source_requests=0,old_qa_reference=bad_ref,old_qa_sha256=bad_sha,verified_replacement_reference=good['raw_reference'],verified_replacement_sha256=good['raw_sha256'],result=result,storage_receipt=task['storage_receipt'],latest_native_history=history,history_pins=pins,production_activation=False,full_acceptance=False)
 (out/'native-repair-real-storage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 # Repair the original final publisher outbox without hiding its first failure.
 prefix='jarvis-source-preflight/record-40910020200-1-native-positive-summary';coordinator=Coordinator(GitCAS(root,prefix),'TDCC');_,pending=coordinator.store.read('TDCC')
 if not pending:raise ValueError('ORIGINAL_PUBLICATION_NOT_FOUND')
 record=dict(schema='JARVIS_AUTOMATIC_ACCEPTANCE_RECORD_V1',metadata=pending['record_metadata'],files=pending['tasks'])
 if hashlib.sha256(encode(record)).hexdigest()!=pending['record_sha256']:raise ValueError('ORIGINAL_PUBLICATION_DIGEST_CHANGED')
 receipt=publish(coordinator,record,DriveArchive('40910020200-1-native-positive-summary'))
 (out/'reconciled-original-publication.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(dict(schema=report['schema'],period=case['period'],qa_copy_repaired=1,formal_data_repaired=0,source_requests=0,later_qa_task_count=len(history),old_publisher_reconciled=receipt['publication_state'],production_activation=False)),flush=True)
if __name__=='__main__':main()
