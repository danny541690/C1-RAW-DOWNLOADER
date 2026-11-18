import unittest
from hashlib import sha256
from scripts.v097_r3_g2_shared_contract_engine import group_candidates,file_decision,approved_template
from scripts.v097_r3_g2_shared_74750_reconcile import safe_origin
SHA=sha256(b'bronze').hexdigest()
class Tests(unittest.TestCase):
 def test_group_count(self):
  self.assertEqual(len(group_candidates()),143)
 def test_domain_is_properly_scoped(self):
  self.assertTrue(safe_origin('https://www.taifex.com.tw/cht/4/historyOfTrading','TAIFEX'))
  self.assertFalse(safe_origin('https://www.taifex.com.tw.evil.invalid/x','TAIFEX'))
  self.assertFalse(safe_origin('http://www.taifex.com.tw/x','TAIFEX'))
 def test_empty_approval_cannot_certify(self):
  t=group_candidates()[('TDCC','SHAREHOLDING_DISTRIBUTION','TDCC_WEEKLY_DISTRIBUTION')]
  a,reason=approved_template(None,t,lambda _: True)
  self.assertIsNone(a)
  self.assertEqual(reason,'NO_APPROVED_REGISTRY')
  result=file_decision({'source':'TDCC','source_id':'id','source_sha256':SHA,
                         'data_date':'2026-11-18'},[],{})
  self.assertEqual(result['status'],'HOLD')
 def test_no_native_attestation_no_pass_even_with_template(self):
  t={'source':'TDCC','dataset':'SHAREHOLDING_DISTRIBUTION',
      'historical_era':'TDCC_WEEKLY_DISTRIBUTION','template_id':'a',
      'official_dataset_start_date':'2008-07-01','effective_start_day':'2008-07-01',
      'effective_end_day':'2026-12-31','native_format':'HTML','native_layout_id':'16'}
  row={'source':'TDCC','source_id':'id','source_sha256':SHA,'data_date':'2026-11-18'}
  self.assertEqual(file_decision(row,[t],None)['reason'],'G2_NATIVE_DATASET_BINDING_MISSING')
if __name__=='__main__':unittest.main()
