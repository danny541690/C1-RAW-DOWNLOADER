import hashlib,tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor,ApplicabilityUnproven
from scripts.v093_source_adapters import NativeAdapter
class FakeDrive:
 def __init__(self):self.data={};self.api=self;self.sidecar_fail=False
 def files(self):return self
 def folder(self,parent,name):return parent+'/'+name
 def find(self,folder,name):
  key=hashlib.sha256((folder+'/'+name).encode()).hexdigest();return {'id':key} if key in self.data else None
 def put(self,folder,name,raw,*args,**kw):
  if name.endswith('.receipt.json') and self.sidecar_fail:raise OSError('fixture sidecar interruption')
  key=hashlib.sha256((folder+'/'+name).encode()).hexdigest()
  if key in self.data and self.data[key]!=raw:raise ValueError('IMMUTABLE_CONFLICT')
  self.data[key]=raw
 def get_media(self,fileId):return self.data[fileId]
 def get(self,fileId,fields):return {'size':len(self.data[fileId]),'version':'1'}
 def call(self,fn):return fn()
class FixtureNative(NativeAdapter):
 def fetch(self):self.fetches+=1;return b'fixture valid'
 def validate(self,raw):
  if raw==b'fixture empty':raise ApplicabilityUnproven('not certified absence')
  if raw!=b'fixture valid':raise ValueError('fixture native content rejected')
  return dict(basic_verified=True,fixture_only=True)
 def preserve_rejected(self,raw):raise OSError('not needed for this fixture')
class NativeRepairTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.c=Coordinator(SQLiteCAS(Path(self.tmp.name)/'state'),'TWSE');self.d=FakeDrive();self.d.data['old']=b'fixture broken'
  sha=hashlib.sha256(self.d.data['old']).hexdigest()
  self.case=dict(source='TWSE',key='repair-one',period='2026-10-01',mode='REPAIR',category='prices_indices',repair_evidence=dict(source='TWSE',key='repair-one',period='2026-10-01',reference='old',sha256=sha,download_approved=True,reason='NATIVE_CONTENT_REJECTED',official_evidence_id='EXPLICIT_TEST_FIXTURE'))
  self.c.add([dict(source='TWSE',key='repair-one',period='2026-10-01',slot='DESC')])
  self.c.update(lambda s:s['tasks']['repair-one'].update(attempts=1,legacy_review=dict(source='TWSE',task_key='repair-one',attempts=1,action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(period='2026-10-01',raw_reference='old',sha256=sha)]),execution_contract=self.case))
 def adapter(self):
  task=self.c.store.read('TWSE')[1]['tasks']['repair-one'];a=FixtureNative(self.c,self.d,dict(source='TWSE',key='repair-one'),task,target_root='QA_ROOT');a.fetches=0;return a
 def test_repair_saves_new_and_sidecar_without_changing_bad_original(self):
  a=self.adapter();result=Executor(self.c,a).one('DESC','worker');task=self.c.store.read('TWSE')[1]['tasks']['repair-one']
  self.assertEqual(self.d.data['old'],b'fixture broken');self.assertEqual(a.fetches,1);self.assertEqual(task['attempts'],2);self.assertNotEqual(result['reference'],'old');self.assertTrue(task['storage_receipt']['readback_verified']);self.assertFalse(task['full_acceptance'])
 def test_good_old_data_cannot_be_redownloaded_under_repair_mode(self):
  a=self.adapter();self.d.data['old']=b'fixture valid';a.case['repair_evidence']['sha256']=hashlib.sha256(b'fixture valid').hexdigest()
  with self.assertRaisesRegex(ApplicabilityUnproven,'NOT_NEEDED'):Executor(self.c,a).one('DESC','worker')
  self.assertEqual(a.fetches,0);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['repair-one']['attempts'],1)
 def test_changed_old_evidence_cannot_authorize_download(self):
  a=self.adapter();self.d.data['old']=b'changed'
  with self.assertRaisesRegex(ApplicabilityUnproven,'EVIDENCE_CHANGED'):Executor(self.c,a).one('DESC','worker')
  self.assertEqual(a.fetches,0)
 def test_official_empty_is_not_automatically_treated_as_broken(self):
  a=self.adapter();self.d.data['old']=b'fixture empty';a.case['repair_evidence']['sha256']=hashlib.sha256(b'fixture empty').hexdigest()
  with self.assertRaises(ApplicabilityUnproven):Executor(self.c,a).one('DESC','worker')
  self.assertEqual(a.fetches,0)
 def test_sidecar_failure_recovers_saved_raw_without_second_fetch(self):
  a=self.adapter();self.d.sidecar_fail=True
  with self.assertRaises(OSError):Executor(self.c,a).one('DESC','worker')
  self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['repair-one']['status'],'RECONCILE')
  self.d.sidecar_fail=False;result=Executor(self.c,a).resume('DESC','recovery')
  self.assertIsNotNone(result);self.assertEqual(a.fetches,1);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['repair-one']['attempts'],2)
 def test_forged_storage_receipt_cannot_mark_task_verified(self):
  a=self.adapter();a.ensure_receipt=lambda *args:dict(reference='sidecar',sha256='a'*64,raw_reference='other',raw_sha256='b'*64,readback_verified=True)
  with self.assertRaisesRegex(ValueError,'RECEIPT_NOT_VERIFIED'):Executor(self.c,a).one('DESC','worker')
  self.assertNotEqual(self.c.store.read('TWSE')[1]['tasks']['repair-one']['status'],'RAW_BASIC_VERIFIED')

class NativeHistoryTests(unittest.TestCase):
 def test_history_excludes_saved_and_interrupted_tasks_without_reset(self):
  from unittest.mock import Mock,patch
  from scripts.v093_native_missing_batch import later_qa_progress
  control=Mock();control.git.return_value.stdout=('a'*40+' refs/heads/jarvis-source-preflight/native-positive-123-1/TDCC\n').encode()
  store=Mock();store.read.return_value=('a'*40,dict(tasks={'k':dict(definition=dict(source='TDCC',key='k',period='2026-09-11'),status='RECONCILE',attempts=3,save_intent={'sha256':'b'*64})}))
  with patch('scripts.v093_native_missing_batch.GitCAS',side_effect=[control,store]):tasks,refs=later_qa_progress(Path('.'))
  self.assertEqual(tasks['k']['attempts'],3);self.assertTrue(tasks['k']['has_save_intent']);self.assertEqual(len(refs),1)
 def test_cached_replacement_is_hashed_without_new_source_http(self):
  from unittest.mock import Mock
  a=object.__new__(NativeAdapter);a.case=dict(mode='REPAIR',source='TDCC',repair_evidence=dict(replacement_reference='good',replacement_sha256=hashlib.sha256(b'good').hexdigest()));a.read=Mock(return_value=b'good');a.validate=Mock();a.source_requests=0
  self.assertEqual(a.fetch(),b'good');self.assertEqual(a.source_requests,0)
  a.read.return_value=b'changed'
  with self.assertRaisesRegex(ValueError,'REPLACEMENT_SHA'):a.fetch()

class QueryProofTests(unittest.TestCase):
 def row(self):
  case=dict(source='TDCC',key='k',period='2026-09-11',mode='MISSING',date='20260911',code='6911',missing_evidence=dict(source='TDCC',key='k',period='2026-09-11',availability_verified=False,query_applicability_verified=True,official_evidence_id='fixture-menu-receipt',official_menu=dict(url='https://www.tdcc.com.tw/portal/zh/smWeb/qryStock',sha256='a'*64,offered_dates=['20260911'])))
  return dict(definition=dict(source='TDCC',key='k',period='2026-09-11',slot='DESC'),attempts=2,legacy_review=dict(source='TDCC',task_key='k',attempts=2,provenance=[dict(status='UNRESOLVED',period='2026-09-11')]),execution_contract=case)
 def test_official_menu_authorizes_query_without_claiming_data_exists(self):
  row=self.row();a=NativeAdapter(None,None,dict(source='TDCC',key='k'),row)
  self.assertTrue(a.download_authorized);self.assertFalse(a.case['missing_evidence']['availability_verified'])
 def test_unoffered_date_and_period_mismatch_cannot_trigger_query(self):
  for change in ('date','period'):
   row=self.row()
   if change=='date':row['execution_contract']['missing_evidence']['official_menu']['offered_dates']=[]
   else:row['execution_contract']['date']='20260912';row['execution_contract']['missing_evidence']['official_menu']['offered_dates']=['20260912']
   with self.assertRaises(ValueError):NativeAdapter(None,None,dict(source='TDCC',key='k'),row)
