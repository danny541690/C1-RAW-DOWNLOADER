import unittest
from unittest.mock import patch,Mock
from scripts import v093_taifex_independent as m
class SecondPass(unittest.TestCase):
 def test_previous_pass_rechecked_once_without_source_download(self):
  w=object.__new__(m.Worker);w.direction='ASC';w.audit_round=2;w.audit_revision='REMOTE_RAW_SECOND_PASS_20261026';w.live=lambda:True;w.save=Mock();w.request=Mock(side_effect=AssertionError('must not download valid RAW'))
  prior={'revision':'REMOTE_RAW_AUDIT_V9','sha256':m.digest(b'raw'),'status':'PASS_BASIC'}
  e={'status':'SAVED_BASIC_VERIFIED','sha256':m.digest(b'raw'),'file_id':'original','attempts':2,'raw_audit':prior,'request':{'kind':'csv','start':'2001-01-01','end':'2001-01-31'}}
  w.state={'receipts':{'x':e}};w.read_receipt_raw=Mock(return_value=b'raw')
  with patch.object(m,'validate',return_value={'rows':1}):w.audit_saved();w.audit_saved()
  self.assertEqual(w.read_receipt_raw.call_count,1);self.assertEqual(w.audited_this_run,1);self.assertEqual(e['file_id'],'original');self.assertEqual(e['attempts'],2);self.assertEqual(e['raw_audit_history'],[prior]);w.request.assert_not_called()
 def test_boundary_and_requested_direction(self):
  jobs=[{'key':'old','start':'2012-12-01','end':'2012-12-31','kind':'csv'}, {'key':'new','start':'2013-01-01','end':'2013-01-31','kind':'csv'}]
  self.assertEqual([x['key'] for x in m.partition_jobs(jobs,'ASC')],['old'])
  self.assertEqual([x['key'] for x in m.partition_jobs(jobs,'DESC')],['new'])
