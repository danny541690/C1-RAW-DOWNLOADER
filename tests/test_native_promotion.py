import hashlib,tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from test_native_repair import FakeDrive
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_adapters import NativeAdapter
from scripts.v093_source_executor import Executor
from scripts.v093_admission_runtime import prepare_row
class PromotionAdapter(NativeAdapter):
 def validate(self,raw):
  if raw!=b'fixture verified original':raise ValueError('BAD_FIXTURE')
  return dict(basic_verified=True,fixture_only=True)
class PromotionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.d=FakeDrive();self.raw=b'fixture verified original';self.d.data['qa']=self.raw;self.sha=hashlib.sha256(self.raw).hexdigest();self.c=self.coordinator('first')
 def coordinator(self,name):return Coordinator(SQLiteCAS(Path(self.tmp.name)/name),'TWSE')
 def row(self):
  proof=dict(source='TWSE',key='one',period='2026-10-01',reference='qa',sha256=self.sha,verified_evidence_id='EXPLICIT_FIXTURE_VERIFIED_RECEIPT')
  return dict(definition=dict(source='TWSE',key='one',period='2026-10-01',slot='DESC'),status='READY',attempts=4,legacy_review=dict(source='TWSE',task_key='one',action='VERIFY_RETAINED_RAW_FIRST',attempts=4,provenance=[dict(period='2026-10-01',raw_reference='qa',sha256=self.sha)]),execution_contract=dict(source='TWSE',key='one',period='2026-10-01',mode='PROMOTE',category='prices_indices',promotion_evidence=proof))
 def seed(self,c):
  row=prepare_row('TWSE','DESC','one',self.row());c.update(lambda s:s['tasks'].update(one=row));return row
 def adapter(self,c,row):return PromotionAdapter(c,self.d,dict(source='TWSE',key='one'),row,target_root='EXPLICIT_QA_DESTINATION')
 def test_local_move_preserves_exhausted_source_budget_and_original(self):
  row=self.seed(self.c);a=self.adapter(self.c,row);r=Executor(self.c,a).one('DESC','move');t=self.c.store.read('TWSE')[1]['tasks']['one']
  self.assertEqual(t['attempts'],4);self.assertEqual(t['materializations'],1);self.assertEqual(a.source_requests,0);self.assertNotEqual(r['reference'],'qa');self.assertEqual(self.d.data['qa'],self.raw);self.assertEqual(self.d.data[r['reference']],self.raw);self.assertTrue(t['storage_receipt']['readback_verified'])
 def test_existing_correct_destination_is_reused_without_second_materialization(self):
  row=self.seed(self.c);r=Executor(self.c,self.adapter(self.c,row)).one('DESC','first');other=self.coordinator('second');row=self.seed(other);second=Executor(other,self.adapter(other,row)).one('DESC','second')
  self.assertEqual(r['reference'],second['reference']);t=other.store.read('TWSE')[1]['tasks']['one'];self.assertEqual(t['materializations'],0);self.assertEqual(t['attempts'],4)
 def test_changed_source_never_becomes_verified_destination(self):
  row=self.seed(self.c);self.d.data['qa']=b'changed';a=self.adapter(self.c,row)
  with self.assertRaisesRegex(ValueError,'SOURCE_SHA_CHANGED'):Executor(self.c,a).one('DESC','move')
  self.assertEqual(a.source_requests,0);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['one']['status'],'CONTENT_BLOCKED')
 def test_sidecar_interruption_recovers_without_source_or_counter_reset(self):
  row=self.seed(self.c);a=self.adapter(self.c,row);self.d.sidecar_fail=True
  with self.assertRaises(OSError):Executor(self.c,a).one('DESC','first')
  self.d.sidecar_fail=False;r=Executor(self.c,a).resume('DESC','cold');t=self.c.store.read('TWSE')[1]['tasks']['one'];self.assertIsNotNone(r);self.assertEqual(t['attempts'],4);self.assertEqual(t['materializations'],1);self.assertEqual(a.source_requests,0)
 def test_ordinary_download_cannot_use_local_budget_bypass(self):
  self.c.add([dict(source='TWSE',key='x',period='2026-10-01',slot='DESC')]);ticket=self.c.claim('DESC','worker')
  with self.assertRaisesRegex(ValueError,'LOCAL_MATERIALIZATION_NOT_ADMITTED'):self.c.begin_materialization(ticket)

 def test_unsaved_local_interruption_uses_local_not_source_retry_budget(self):
  row=self.seed(self.c);ticket=self.c.claim('DESC','old');self.c.begin_materialization(ticket)
  self.c.error(ticket,'RECONCILE','READ_LOCAL','TimeoutError')
  self.c.resolve_unsaved('one',dict(storage_checked=True,receipt_checked=True,outcome='NO_DURABLE_RESULT',evidence_id='explicit-local-check'))
  task=self.c.store.read('TWSE')[1]['tasks']['one'];self.assertEqual(task['status'],'RETRY_WAIT');self.assertEqual(task['attempts'],4);self.assertEqual(task['materializations'],1)

class FormalScopeTests(unittest.TestCase):
 def test_canary_requires_explicit_scope_and_excludes_any_provider_download(self):
  from scripts.v093_action_live import formal_scope
  row=dict(definition=dict(source='TDCC'),execution_contract=dict(mode='PROMOTE'))
  formal_scope([row],'VERIFIED_TDCC_PROMOTION_CANARY')
  with self.assertRaises(ValueError):formal_scope([row],None)
  with self.assertRaises(ValueError):formal_scope([], 'VERIFIED_TDCC_PROMOTION_CANARY')
  row['execution_contract']['mode']='MISSING'
  with self.assertRaisesRegex(ValueError,'PROMOTION_ONLY'):formal_scope([row],'VERIFIED_TDCC_PROMOTION_CANARY')
