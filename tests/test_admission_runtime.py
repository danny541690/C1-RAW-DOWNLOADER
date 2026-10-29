import copy,tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_admission_runtime import stage,archive_completed,sha
class FakeCatalog:
 def __init__(self,rows,slot='DESC'):
  self.rows=rows;self.meta=dict(slot=slot,catalog_id='a'*64);self.signature='b'*64
 def chunk(self,page,offset,limit):
  if page:return {},dict(page=page,offset=0),False
  selected=dict(list(self.rows.items())[offset:offset+limit]);position=offset+len(selected);end=position>=len(self.rows)
  return selected,dict(page=1 if end else 0,offset=0 if end else position),not end
class AdmissionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.c=Coordinator(SQLiteCAS(Path(self.tmp.name)/'s'),'TWSE')
 def row(self,key='k',slot='DESC',attempts=4):
  review=dict(source='TWSE',task_key=key,attempts=attempts,action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(source='TWSE',period='2026-09-01',raw_reference='old',sha256='a'*64)])
  case=dict(source='TWSE',key=key,period='2026-09-01',mode='RETAINED',reference='old',sha256='a'*64,category='prices_indices')
  return dict(definition=dict(source='TWSE',key=key,period='2026-09-01',slot=slot),attempts=attempts,status='READY_CHECK',legacy_review=review,execution_contract=case)
 def archive(self,snapshot):return dict(sha256=sha(snapshot),readback_verified=True,commit='c'*40)
 def finish(self,key):self.c.update(lambda s:s['tasks'][key].update(status='RAW_BASIC_VERIFIED',owner=None))
 def test_exhausted_download_budget_still_allows_read_only_recheck(self):
  stage(self.c,FakeCatalog({'k':self.row()}));t=self.c.claim('DESC','read')
  self.assertIsNotNone(t);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['k']['attempts'],4)
  with self.assertRaisesRegex(ValueError,'REQUEST_NOT_ADMITTED'):self.c.begin_request(t)
 def test_stage_restart_does_not_reset_lease_attempt_or_progress(self):
  catalog=FakeCatalog({'k':self.row(attempts=2)});stage(self.c,catalog);t=self.c.claim('DESC','read');before=copy.deepcopy(self.c.store.read('TWSE')[1])
  self.assertFalse(stage(self.c,catalog));self.assertEqual(before,self.c.store.read('TWSE')[1])
 def test_bounded_chunks_archive_then_advance_and_preserve_totals(self):
  catalog=FakeCatalog({k:self.row(k) for k in ('a','b','c')});stage(self.c,catalog,limit=2)
  self.assertEqual(len(self.c.store.read('TWSE')[1]['tasks']),2)
  for k in ('a','b'):self.finish(k)
  self.assertTrue(archive_completed(self.c,'DESC',self.archive));stage(self.c,catalog,limit=2)
  state=self.c.store.read('TWSE')[1];self.assertEqual(set(state['tasks']),{'c'});self.assertEqual(state['admission']['DESC']['archived_status_counts']['RAW_BASIC_VERIFIED'],2)
 def test_archive_readback_failure_never_deletes_active_progress(self):
  stage(self.c,FakeCatalog({'k':self.row()}));self.finish('k');before=copy.deepcopy(self.c.store.read('TWSE')[1])
  with self.assertRaisesRegex(ValueError,'ARCHIVE_READBACK'):archive_completed(self.c,'DESC',lambda s:dict(sha256='0'*64,readback_verified=True))
  self.assertEqual(before,self.c.store.read('TWSE')[1])
 def test_lease_or_uncertain_save_cannot_be_archived(self):
  stage(self.c,FakeCatalog({'k':self.row()}));self.c.claim('DESC','working')
  self.assertFalse(archive_completed(self.c,'DESC',self.archive))
 def test_catalog_change_and_cross_direction_duplicate_rejected(self):
  catalog=FakeCatalog({'k':self.row()});stage(self.c,catalog);catalog.signature='d'*64
  with self.assertRaisesRegex(ValueError,'CATALOG_CHANGE'):stage(self.c,catalog)
  with self.assertRaisesRegex(ValueError,'CROSS_DIRECTION'):stage(self.c,FakeCatalog({'k':self.row(slot='ASC')},slot='ASC'))
 def test_import_never_reduces_old_attempts(self):
  row=self.row();row['attempts']=0
  with self.assertRaisesRegex(ValueError,'LEGACY_ATTEMPTS'):stage(self.c,FakeCatalog({'k':row}))
 def test_unreviewed_existing_progress_cannot_be_overwritten(self):
  self.c.add([dict(source='TWSE',key='other',slot='DESC',period='2026-09-01')])
  with self.assertRaisesRegex(ValueError,'EXISTING_PROGRESS'):stage(self.c,FakeCatalog({'k':self.row()}))

 def test_first_start_has_no_archive_before_any_progress_exists(self):
  self.assertFalse(archive_completed(self.c,'DESC',self.archive))
  self.assertIsNone(self.c.store.read('TWSE')[1])

class ContinuousBudgetTests(unittest.TestCase):
 def test_advances_chunks_without_waiting_between_batches(self):
  from unittest.mock import patch,Mock
  from scripts.v093_admission_runtime import run_until_budget
  c=Mock();c.clock.return_value=10
  outputs=[dict(processed=20,chunk_archived=True,catalog_finished=False),dict(processed=3,chunk_archived=True,catalog_finished=True)]
  with patch('scripts.v093_admission_runtime.run_catalog',side_effect=outputs) as run:
   r=run_until_budget(c,None,None,'DESC','owner','root',None,monotonic=lambda:0)
  self.assertEqual(run.call_count,2);self.assertEqual(r['total_processed'],23);self.assertEqual(r['stop_reason'],'CATALOG_FINISHED')
 def test_unready_catalog_does_not_spin_on_future_retry_or_other_owner(self):
  from unittest.mock import patch,Mock
  from scripts.v093_admission_runtime import run_until_budget
  for extra,expected in [({},'NO_IMMEDIATE_WORK'),({'source_hold':'AUTH'},'SOURCE_HOLD'),({'cooldown_until':50},'SOURCE_COOLDOWN')]:
   c=Mock();c.clock.return_value=10
   value=dict(processed=0,chunk_archived=False,catalog_finished=False,**extra)
   with patch('scripts.v093_admission_runtime.run_catalog',return_value=value) as run:
    r=run_until_budget(c,None,None,'DESC','owner','root',None,monotonic=lambda:0)
   self.assertEqual(run.call_count,1);self.assertEqual(r['stop_reason'],expected)
 def test_archive_only_chunk_immediately_advances(self):
  from unittest.mock import patch,Mock
  from scripts.v093_admission_runtime import run_until_budget
  c=Mock();c.clock.return_value=10
  outputs=[dict(processed=0,chunk_archived=True,catalog_finished=False),dict(processed=1,chunk_archived=True,catalog_finished=True)]
  with patch('scripts.v093_admission_runtime.run_catalog',side_effect=outputs):
   r=run_until_budget(c,None,None,'DESC','owner','root',None,monotonic=lambda:0)
  self.assertEqual(r['batches'],2)
 def test_campaign_budget_covers_between_batch_work(self):
  from unittest.mock import patch,Mock
  from scripts.v093_admission_runtime import run_until_budget
  c=Mock();c.clock.return_value=10
  ticks=iter([0,0,0,40,40,61,61])
  with patch('scripts.v093_admission_runtime.run_catalog',return_value=dict(processed=20,chunk_archived=True,catalog_finished=False)) as run:
   r=run_until_budget(c,None,None,'DESC','owner','root',None,seconds=60,monotonic=lambda:next(ticks))
  self.assertEqual(run.call_count,2);self.assertEqual(r['total_processed'],40);self.assertEqual(r['stop_reason'],'TIME_BUDGET')
 def test_shared_worker_carries_drive_credentials_to_execution_step(self):
  import yaml
  doc=yaml.load(Path('.github/workflows/jarvis-seven-worker.yml').read_text(),Loader=yaml.BaseLoader)
  step=next(x for x in doc['jobs']['worker']['steps'] if x.get('name')=='Run guarded source worker')
  for name in ('GOOGLE_CLIENT_ID','GOOGLE_CLIENT_SECRET','GOOGLE_REFRESH_TOKEN'):
   self.assertEqual(step['env'][name],'${{ secrets.'+name+' }}')
