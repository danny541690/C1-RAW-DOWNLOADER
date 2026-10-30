import unittest
from scripts.v093_native_reuse_batch import descriptor
class NativeContractTests(unittest.TestCase):
 def row(self):return dict(task_key='k',period='2026-09',raw_reference='old/member',sha256='a'*64,attempts=2,ledger_path='frozen',ledger_origin={'sha256':'b'*64})
 def test_unknown_categories_not_silently_accepted(self):
  self.assertIsNone(descriptor('TPEx',self.row(),dict(category='unknown')))
  self.assertIsNone(descriptor('MOPS',self.row(),dict(category='financial_unknown')))
  self.assertIsNone(descriptor('FinMind',self.row(),dict(dataset='TaiwanStockPrice')))
 def test_taifex_job_binding_rejects_wrong_domain_or_snapshot(self):
  job=dict(kind='csv',start='2026-09-01',end='2026-09-30',key='x',url='https://example.invalid/data')
  self.assertIsNone(descriptor('TAIFEX',self.row(),dict(request=job)))
  job['url']='https://www.taifex.com.tw/cht/3/report'
  self.assertEqual(descriptor('TAIFEX',self.row(),dict(request=job))['native_job'],job)
  job['kind']='snapshot';self.assertIsNone(descriptor('TAIFEX',self.row(),dict(request=job)))
 def test_retained_identity_and_old_attempts_preserved(self):
  d=descriptor('MOPS',self.row(),dict(category='revenue_sii_0'))
  self.assertEqual(d['reference'],'old/member');self.assertEqual(d['sha256'],'a'*64);self.assertEqual(d['attempts'],2)
