import csv,gzip,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import v093_prelaunch_acceptance_batch as b

class BatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name);self.reg=self.p/'register';self.reg.mkdir();self.cache=self.p/'cache';self.cache.mkdir()
  self.raw=json.dumps({'status':200,'data':[dict(date='2000-01-04',stock_id='1515',open=10,max=12,min=9,close=11)]}).encode()
  self.row={'來源':'FinMind','單元ID':'unit1','原件參照':'file1','已下載':'1','資料集':'TaiwanStockPrice','期間':'2000-01','月份':'2000-01','年份':'2000','RAW_SHA256':b.sha(self.raw),'代碼':'1515'}
 def write(self):
  with gzip.open(self.reg/'FinMind_units.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=self.row);w.writeheader();w.writerow(self.row)
 def test_real_content_and_no_release(self):
  self.write();(self.cache/'file1').write_bytes(self.raw);x=b.run(self.reg,self.cache,self.p/'out')
  self.assertEqual(x['counts']['new_content_units'],1);self.assertEqual(x['approved_scopes'],[]);self.assertEqual(x['production_writes'],0)
 def test_hash_conflict_keeps_task_open(self):
  self.write();(self.cache/'file1').write_bytes(b'corrupt');x=b.run(self.reg,self.cache,self.p/'out');self.assertEqual(x['counts']['CONTENT_BLOCKED'],1)
  self.assertEqual(json.loads((self.p/'out/checkpoint.json').read_text())['completed'],{})
 def test_missing_raw_is_deferred_not_downloaded(self):
  self.write();x=b.run(self.reg,self.cache,self.p/'out');self.assertEqual(x['counts']['RAW_NOT_IN_LOCAL_CACHE'],1);self.assertEqual(x['source_downloads'],0)
 def test_resume_reuses_only_bound_content(self):
  self.write();(self.cache/'file1').write_bytes(self.raw);b.run(self.reg,self.cache,self.p/'out')
  with patch.object(b,'inspect_raw',side_effect=AssertionError('must reuse prior check')):
   x=b.run(self.reg,self.cache,self.p/'next',self.p/'out/checkpoint.json')
  self.assertEqual(x['counts']['resumed_content_units'],1)
 def test_changed_bytes_do_not_reuse_pass(self):
  self.write();(self.cache/'file1').write_bytes(self.raw);b.run(self.reg,self.cache,self.p/'out');(self.cache/'file1').write_bytes(b'changed')
  x=b.run(self.reg,self.cache,self.p/'next',self.p/'out/checkpoint.json');self.assertEqual(x['counts']['CONTENT_BLOCKED'],1);self.assertEqual(x['counts'].get('resumed_content_units',0),0)
 def test_nonfinite_price_rejected(self):
  obj=json.loads(self.raw);obj['data'][0]['close']='NaN'
  with self.assertRaisesRegex(ValueError,'NONFINITE_PRICE'):b.inspect_raw(json.dumps(obj).encode(),self.row)

 def test_missing_register_is_not_a_successful_empty_batch(self):
  with self.assertRaisesRegex(ValueError,'REGISTER_INPUT_MISSING'):b.run(self.reg,self.cache,self.p/'out')
