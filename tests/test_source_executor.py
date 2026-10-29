import tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_executor import Executor
class DiskAdapter:
 download_authorized=True
 def __init__(self,root):self.root=root;self.fetches=0;self.crash=False
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
