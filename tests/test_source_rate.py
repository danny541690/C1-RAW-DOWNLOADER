import concurrent.futures,tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from test_source_executor import DiskAdapter
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
from scripts.v093_source_rate import reserve,RequestDeferred
from scripts.v093_source_adapters import NativeAdapter
class RateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.now=[1000]
  self.store=SQLiteCAS(self.root/'state');self.c=Coordinator(self.store,'TWSE',clock=lambda:self.now[0])
  self.c.add([dict(source='TWSE',key=slot,slot=slot,period='2026-10-29') for slot in ('DESC','ASC')])
 def test_both_directions_share_atomic_quota_without_resetting_attempts(self):
  tickets=[self.c.claim(slot,slot,slot) for slot in ('DESC','ASC')]
  def work(ticket):
   try:reserve(self.c,ticket,limit=1,window=60,spacing=0);return True
   except RequestDeferred:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(work,tickets))
  self.assertEqual(sum(result),1);self.assertTrue(all(t['attempts']==0 for t in self.store.read('TWSE')[1]['tasks'].values()))
 def test_denial_defers_before_fetch_and_does_not_spend_attempt(self):
  t=self.c.claim('ASC','first','ASC');reserve(self.c,t)
  a=DiskAdapter(self.root);a.before_request=lambda ticket:reserve(self.c,ticket)
  with self.assertRaises(RequestDeferred):Executor(self.c,a).one('DESC','second')
  task=self.store.read('TWSE')[1]['tasks']['DESC'];self.assertEqual(task['attempts'],0);self.assertEqual(task['status'],'RETRY_WAIT');self.assertEqual(a.fetches,0)
  self.now[0]+=3;self.assertIsNotNone(self.c.claim('DESC','later'))
 def test_shared_policy_cannot_change_behind_other_runner(self):
  t=self.c.claim('DESC','first');reserve(self.c,t)
  with self.assertRaisesRegex(ValueError,'POLICY_CHANGED'):reserve(self.c,t,limit=100)
class AdapterBindingTests(unittest.TestCase):
 def test_all_seven_sources_bind_receipt_without_authorizing_new_download(self):
  for source in ('TWSE','TPEx','MOPS','TDCC','TAIFEX','NDC','FinMind'):
   definition=dict(source=source,key='k',period='2026-09',slot='DESC')
   task=dict(definition=definition,execution_contract=dict(source=source,key='k',period='2026-09',mode='RETAINED',reference='old',sha256='a'*64))
   task['legacy_review']=dict(source=source,task_key='k',provenance=[dict(raw_reference='old',sha256='a'*64,period='2026-09')])
   a=NativeAdapter(None,None,dict(source=source,key='k'),task)
   self.assertFalse(a.download_authorized);self.assertEqual(a.expected_receipt('k')['source'],source)
   with self.assertRaises(ValueError):a.find('other-task')
 def test_existing_raw_and_unapproved_finmind_cannot_be_downloaded(self):
  source='FinMind';definition=dict(source=source,key='k',period='2026-09',slot='DESC')
  task=dict(definition=definition,attempts=1,legacy_review=dict(source=source,task_key='k',attempts=1,provenance=[dict(status='UNRESOLVED')]),execution_contract=dict(source=source,key='k',period='2026-09',mode='MISSING',missing_evidence=dict(availability_verified=True,official_evidence_id='frozen',source=source,key='k',period='2026-09')))
  with self.assertRaisesRegex(ValueError,'FINMIND_GAP'):NativeAdapter(None,None,dict(source=source,key='k'),task)
  task['execution_contract']['reference']='already-saved'
  with self.assertRaisesRegex(ValueError,'LEGACY_PROOF'):NativeAdapter(None,None,dict(source=source,key='k'),task)
