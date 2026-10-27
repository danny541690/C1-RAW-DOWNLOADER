"""Failure injection; local stores only, no live acceptance claims."""
import copy,unittest
from unittest.mock import Mock
from scripts import v093_repair_execution as e
from scripts.storage_verifier import MemoryStorage,persist_verified
from tests.test_stage06_financial_repair import sample

class RecoveryBatch(unittest.TestCase):
 def job(self):return dict(source='MOPS',category='CashflowStatement',period='2023-03-31',unit_id='recovery')
 def test_retry_same_raw_has_identical_name_bytes_and_receipt(self):
  raw=sample();store={};writes=[]
  def write(n,b):writes.append(n);store[n]=b
  a=e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,write,store.__getitem__)
  b=e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,write,store.__getitem__)
  self.assertEqual(a,b);self.assertEqual(len(store),1);self.assertEqual(len(writes),2)
  self.assertFalse(b['complete']);self.assertFalse(b['pit_verified'])
 def test_write_timeout_then_resume_does_not_certify_or_change_raw(self):
  raw=sample();before=bytes(raw);store={}
  def timeout(n,b):store[n]=b;raise TimeoutError('AFTER_WRITE')
  with self.assertRaises(TimeoutError):e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,timeout,store.__getitem__)
  receipt=e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,lambda n,b:store.__setitem__(n,b),store.__getitem__)
  self.assertEqual(raw,before);self.assertEqual(len(store),1);self.assertFalse(receipt['complete'])
 def test_read_timeout_then_resume_keeps_one_output(self):
  raw=sample();store={};write=lambda n,b:store.__setitem__(n,b)
  with self.assertRaises(TimeoutError):e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,write,Mock(side_effect=TimeoutError))
  receipt=e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,write,store.__getitem__)
  self.assertEqual(len(store),1);self.assertTrue(receipt['remote_readback_hash_verified']);self.assertFalse(receipt['numeric_verified'])
 def test_fence_expired_before_write_leaves_no_output(self):
  write=Mock();raw=sample()
  with self.assertRaisesRegex(RuntimeError,'EXPIRED'):e.reparse_financial(raw,self.job(),e.digest(raw),Mock(side_effect=RuntimeError('EXPIRED')),write,Mock())
  write.assert_not_called()
 def test_missing_readback_never_returns_receipt(self):
  raw=sample()
  with self.assertRaisesRegex(ValueError,'READBACK_SHA'):e.reparse_financial(raw,self.job(),e.digest(raw),lambda:None,Mock(),lambda n:None)
 def test_due_order_is_time_then_month_and_does_not_mutate(self):
  index={'2001-02':{'next_retry_at':10},'2001-01':{'next_retry_at':10},'2000-01':{'next_retry_at':11},'2000-02':{'next_retry_at':None}}
  old=copy.deepcopy(index);self.assertEqual(e.due_months(index,10),['2001-01','2001-02']);self.assertEqual(index,old)
 def test_blocked_and_completed_do_not_automatically_retry(self):
  j={'units':{'a':{'terminal':True,'complete':False},'b':{'complete':True},'c':{'status':'SOURCE_NO_DATA_UNCONFIRMED','next_retry_at':20}}}
  r=e.pending_month(j);self.assertEqual(r,dict(next_retry_at=20,retry_units=1,blocked_units=1,source_empty_units=1))
 def test_byte_write_failure_never_reads(self):
  s=MemoryStorage();s.write_bytes=Mock(side_effect=OSError('DISK'));s.read_bytes=Mock()
  with self.assertRaises(OSError):persist_verified(s,'x',b'abc')
  s.read_bytes.assert_not_called()
 def test_equal_length_corrupt_bytes_are_rejected(self):
  s=MemoryStorage();s.read_bytes=lambda p:b'xyz'
  with self.assertRaisesRegex(ValueError,'MISMATCH'):persist_verified(s,'x',b'abc')
 def test_text_readback_is_rejected(self):
  s=MemoryStorage();s.read_bytes=lambda p:'abc'
  with self.assertRaisesRegex(ValueError,'MISMATCH'):persist_verified(s,'x',b'abc')
