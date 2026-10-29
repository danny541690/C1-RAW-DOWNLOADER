import hashlib,tempfile,unittest,urllib.error
from pathlib import Path
from test_source_coordination import SQLiteCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
class DiskAdapter:
 download_authorized=True
 def __init__(self,root):self.root=root;self.fetches=0;self.crash=False
 def expected_receipt(self,key):return dict(source='TWSE',task_key=key,period='2026-10-01',reference=self.find(key),sha256=hashlib.sha256(b'valid source response').hexdigest())
 def find(self,key):return None
 def find_locator(self,path):return path if Path(path).exists() else None
 def read(self,ref):return Path(ref).read_bytes()
 def fetch(self):self.fetches+=1;return b'valid source response'
 def validate(self,raw):
  if raw!=b'valid source response':raise ValueError('CONTENT')
  return dict(basic_verified=True)
 def locator(self,key,sha):return str(self.root/(key+'-'+sha))
 def put(self,path,raw):
  p=Path(path)
  if p.exists() and p.read_bytes()!=raw:raise ValueError('IMMUTABLE_CONFLICT')
  p.write_bytes(raw)
  if self.crash:raise OSError('lost response after actual disk save')
  return path
class ExecutorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.now=[1]
  self.c=Coordinator(SQLiteCAS(self.root/'db'),'TWSE',clock=lambda:self.now[0],ttl=10)
  self.c.add([dict(source='TWSE',key='one',slot='DESC',period='2026-10-01')]);self.a=DiskAdapter(self.root)
 def task(self):return self.c.store.read('TWSE')[1]['tasks']['one']
 def test_source_timeout_persists_retry_without_reset_or_stall(self):
  def fetch():self.a.fetches+=1;raise TimeoutError('do-not-record-secret')
  self.a.fetch=fetch
  with self.assertRaises(TimeoutError):Executor(self.c,self.a).one('DESC','first')
  self.assertEqual(self.task()['status'],'RETRY_WAIT');self.assertEqual(self.task()['attempts'],1)
  self.assertEqual(self.task()['error'],dict(phase='FETCH',code='TimeoutError'))
  self.assertIsNone(self.c.claim('DESC','early'))
  self.now[0]+=61
  self.assertEqual(self.c.begin_request(self.c.claim('DESC','later')),2)
 def test_rate_limit_cooldown_is_shared_with_opposite_direction(self):
  self.c.add([dict(source='TWSE',key='tail',slot='ASC',period='2000-01')])
  def fetch():raise urllib.error.HTTPError('https://example.invalid',429,'limited',{'Retry-After':'120'},None)
  self.a.fetch=fetch
  with self.assertRaises(urllib.error.HTTPError):Executor(self.c,self.a).one('DESC','one')
  self.assertIsNone(self.c.claim('ASC','opposite','ASC'));self.now[0]+=121
  self.assertIsNotNone(self.c.claim('ASC','later','ASC'))
 def test_auth_error_holds_source_and_does_not_persist_secret(self):
  def fetch():raise urllib.error.HTTPError('https://example.invalid/secret',403,'secret',None,None)
  self.a.fetch=fetch
  with self.assertRaises(urllib.error.HTTPError):Executor(self.c,self.a).one('DESC','one')
  self.assertEqual(self.task()['status'],'SOURCE_HOLD');self.assertNotIn('secret',str(self.c.store.read('TWSE')[1]))
 def test_parse_error_is_content_hold_not_automatic_redownload(self):
  self.a.fetch=lambda:b'bad response'
  with self.assertRaises(ValueError):Executor(self.c,self.a).one('DESC','one')
  self.assertEqual(self.task()['status'],'CONTENT_BLOCKED');self.assertEqual(self.task()['attempts'],1)
  self.assertIsNone(self.c.claim('DESC','repeat'))
 def test_valid_looking_changed_raw_is_blocked_against_old_sha(self):
  p=self.root/'changed';p.write_bytes(b'valid but changed');self.a.find=lambda _:str(p)
  self.a.validate=lambda _:dict(basic_verified=True)
  with self.assertRaisesRegex(ValueError,'EXPECTED_SHA_MISMATCH'):Executor(self.c,self.a).one('DESC','reuse')
  self.assertEqual(self.task()['status'],'CONTENT_BLOCKED');self.assertEqual(self.a.fetches,0)
 def test_reference_and_period_cannot_be_substituted(self):
  p=self.root/'existing';p.write_bytes(b'valid source response');self.a.find=lambda _:str(p)
  self.a.expected_receipt=lambda key:dict(source='TWSE',task_key=key,period='2026-09-01',reference=str(p),sha256='a'*64)
  with self.assertRaisesRegex(ValueError,'BINDING_MISMATCH'):Executor(self.c,self.a).one('DESC','reuse')
  self.assertEqual(self.task()['attempts'],0)
 def test_unsaved_crash_requires_external_reconciliation_before_retry(self):
  ticket=self.c.claim('DESC','old');self.c.begin_request(ticket);self.now[0]+=11
  self.assertIsNone(self.c.claim('DESC','new'));self.assertEqual(self.task()['next_action'],'RECONCILE_SOURCE_AND_STORAGE')
  with self.assertRaises(ValueError):self.c.resolve_unsaved('one',{'storage_checked':True})
  self.a.reconcile_request=lambda _:dict(storage_checked=True,receipt_checked=True,outcome='NO_DURABLE_RESULT',evidence_id='receipt-and-storage-scan-1')
  Executor(self.c,self.a).reconcile_unsaved('one')
  self.assertEqual(self.c.begin_request(self.c.claim('DESC','retry')),2)
 def test_crash_after_real_save_recovers_without_second_market_request(self):
  self.a.crash=True
  with self.assertRaises(OSError):Executor(self.c,self.a).one('DESC','first')
  self.now[0]+=11;self.a.crash=False
  result=Executor(self.c,self.a).resume('DESC','restart')
  self.assertFalse(result['full_acceptance']);self.assertEqual(self.a.fetches,1)
  self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['one']['attempts'],1)
 def test_retained_raw_is_reused_without_fetch_or_attempt_reset(self):
  p=self.root/'existing';p.write_bytes(b'valid source response');self.a.find=lambda _:str(p)
  result=Executor(self.c,self.a).one('DESC','reuse')
  self.assertEqual(self.a.fetches,0);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['one']['attempts'],0)
 def test_unapproved_missing_data_cannot_trigger_source_request(self):
  self.a.download_authorized=False
  with self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):Executor(self.c,self.a).one('DESC','held')
  self.assertEqual(self.a.fetches,0)
 def test_crash_during_retained_readback_recovers_reference_without_download(self):
  p=self.root/'existing';p.write_bytes(b'valid source response');self.a.find=lambda _:str(p)
  original=self.a.read;calls=[0]
  def read(ref):
   calls[0]+=1
   if calls[0]==2:raise OSError('readback interrupted')
   return original(ref)
  self.a.read=read
  with self.assertRaises(OSError):Executor(self.c,self.a).one('DESC','reuse')
  self.now[0]+=11;self.a.read=original
  self.assertIsNotNone(Executor(self.c,self.a).resume('DESC','restart'))
  self.assertEqual(self.a.fetches,0);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['one']['attempts'],0)
