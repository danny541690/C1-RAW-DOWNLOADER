import unittest
from unittest.mock import patch
from scripts import v093_taifex_independent as m

class AuditTests(unittest.TestCase):
 def worker(self, direction='ASC'):
  w=object.__new__(m.Worker);w.direction=direction;w.state={'receipts':{}};w.live=lambda:True;w.save=lambda:None
  return w
 def entry(self):
  return {'status':'SAVED_BASIC_VERIFIED','sha256':m.digest(b'raw'),'file_id':'kept','request':{'kind':'csv','start':'2001-01-01','end':'2001-01-31'}}
 def test_pass_deduplicates_and_never_downloads(self):
  w=self.worker();e=self.entry();w.state['receipts']['x']=e;calls=[];w.read_receipt_raw=lambda e:calls.append(1) or b'raw'
  with patch.object(m,'validate',return_value={'rows':1}):w.audit_saved();w.audit_saved()
  self.assertEqual(len(calls),1);self.assertEqual(e['raw_audit']['status'],'PASS_BASIC');self.assertEqual(e['file_id'],'kept')
 def test_timeout_preserves_receipt(self):
  w=self.worker();e=self.entry();w.state['receipts']['x']=e
  def fail(e):raise TimeoutError('transient')
  w.read_receipt_raw=fail;w.audit_saved();self.assertEqual(e['status'],'SAVED_BASIC_VERIFIED');self.assertNotIn('integrity_hold',e)
 def test_mismatch_is_held_not_overwritten(self):
  w=self.worker();e=self.entry();w.state['receipts']['x']=e;w.read_receipt_raw=lambda e:b'bad';w.audit_saved()
  self.assertTrue(e['integrity_hold']);self.assertEqual(e['sha256'],m.digest(b'raw'))
 def test_partition(self):
  w=self.worker('DESC');e=self.entry();w.state['receipts']['x']=e;w.read_receipt_raw=lambda e:self.fail('wrong partition');w.audit_saved();self.assertNotIn('raw_audit',e)
