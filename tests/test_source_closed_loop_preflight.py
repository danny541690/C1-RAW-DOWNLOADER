"""Local storage + fake official HTTP through the existing native TDCC worker.
Not acceptance of the new eleven-slot distributed production service.
"""
import hashlib,json,tempfile,time,types,unittest
from pathlib import Path
from scripts import v093_tdcc_independent as tdcc

def page(date='20261016'):
 rows=''.join(f'<tr><td>{i}</td><td>級距</td><td>1</td><td>1000</td><td>1</td></tr>' for i in range(1,17))
 return ('<form></form>證券代號：2330 資料日期：'+date+'<table><tr><th>序</th><th>持股/單位數分級</th><th>人數</th><th>股數/單位數</th><th>比例</th></tr>'+rows+'</table>').encode()

class FakeDrive:
 def __init__(self,root):self.root=root;self.ids={};self.corrupt=False;self.api=types.SimpleNamespace(files=lambda:self)
 def folder(self,parent,name):return parent+'/'+name
 def put(self,parent,name,raw,mime,overwrite=False):
  key=parent+'/'+name;path=self.root/hashlib.sha256(key.encode()).hexdigest()
  if path.exists() and not overwrite and path.read_bytes()!=raw:raise ValueError('IMMUTABLE_CONFLICT')
  path.write_bytes(raw);self.ids[key]=path
 def find(self,parent,name):return {'id':parent+'/'+name}
 def get_media(self,fileId):return b'corrupt' if self.corrupt else self.ids[fileId].read_bytes()
 def call(self,func):return func()

class ClosedLoopTests(unittest.TestCase):
 def worker(self,root):
  w=object.__new__(tdcc.Worker);w.state=dict(receipts={},history_receipts={});w.saved=0;w.skipped=0
  w.until=time.monotonic()+300;w.ctrl='control';w.folders={};w.d=FakeDrive(root)
  w.save=lambda:(root/'checkpoint.json').write_text(json.dumps(w.state))
  return w
 def test_fetch_save_readback_validate_checkpoint_and_reuse(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);w=self.worker(root);calls=[]
   def request(url,data=None):calls.append(data);return b'<form></form>' if data is None else page()
   w.request=request;w.process('20261016|2330',tdcc.QUERY,'distribution','html','20261016','2330')
   e=json.loads((root/'checkpoint.json').read_text())['history_receipts']['20261016|2330']
   self.assertEqual(e['status'],'SAVED_BASIC_VERIFIED');self.assertTrue(e['remote_readback_hash_verified'])
   self.assertFalse(e['numeric_verified']);self.assertFalse(e['pit_verified'])
   w.process('20261016|2330',tdcc.QUERY,'distribution','html','20261016','2330');self.assertEqual(len(calls),2)
 def test_wrong_date_is_quarantined_then_corrected_response_is_reverified(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);w=self.worker(root);result=[page('20261009')]
   w.request=lambda url,data=None:b'<form></form>' if data is None else result[0]
   key='20261016|2330';w.process(key,tdcc.QUERY,'distribution','html','20261016','2330')
   first=w.state['history_receipts'][key];self.assertEqual(first['status'],'UNRESOLVED');self.assertIn('quarantine_file',first)
   first['retry_after_epoch']=0;result[0]=page();w.process(key,tdcc.QUERY,'distribution','html','20261016','2330')
   self.assertEqual(w.state['history_receipts'][key]['status'],'SAVED_BASIC_VERIFIED')
   self.assertEqual(w.state['history_receipts'][key]['attempts'],2)
 def test_storage_readback_corruption_cannot_become_success(self):
  with tempfile.TemporaryDirectory() as directory:
   w=self.worker(Path(directory));w.d.corrupt=True
   w.request=lambda url,data=None:b'<form></form>' if data is None else page()
   key='20261016|2330';w.process(key,tdcc.QUERY,'distribution','html','20261016','2330')
   e=w.state['history_receipts'][key];self.assertEqual(e['status'],'UNRESOLVED')
   self.assertEqual(e['error_class'],'READBACK_MISMATCH')
 def test_revision_change_does_not_reset_attempts(self):
  with tempfile.TemporaryDirectory() as directory:
   w=self.worker(Path(directory));key='20261016|2330'
   w.state['history_receipts'][key]=dict(status='UNRESOLVED',attempts=2,repair_revision='old',retry_after_epoch=0)
   def fail(*args):raise TimeoutError('fixture timeout')
   w.request=fail;w.process(key,tdcc.QUERY,'distribution','html','20261016','2330')
   self.assertEqual(w.state['history_receipts'][key]['attempts'],3)
 def test_exhausted_old_revision_does_not_request_again(self):
  with tempfile.TemporaryDirectory() as directory:
   w=self.worker(Path(directory));key='20261016|2330'
   w.state['history_receipts'][key]=dict(status='UNRESOLVED',attempts=3,repair_revision='old')
   w.request=lambda *args:self.fail('Exhausted task must not reset on revision')
   w.process(key,tdcc.QUERY,'distribution','html','20261016','2330')
   self.assertEqual(w.state['history_receipts'][key]['attempts'],3)
