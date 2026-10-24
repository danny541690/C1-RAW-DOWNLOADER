import unittest
from scripts.v093_tdcc_independent import assigned_dates
class TDCCPartitionTests(unittest.TestCase):
 def test_disjoint_sorted_and_complete(self):
  dates=['20261022','20251031','20260430','20260508']
  a=assigned_dates(dates,'ASC');d=assigned_dates(dates,'DESC')
  self.assertEqual(a,['20251031','20260430']);self.assertEqual(d,['20261022','20260508']);self.assertEqual(set(a+d),set(dates));self.assertFalse(set(a)&set(d))
 def test_does_not_invent_2000_data(self):
  self.assertEqual(assigned_dates(['20251031'],'ASC'),['20251031'])
