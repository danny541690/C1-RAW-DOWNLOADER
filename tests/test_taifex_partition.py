import unittest
from scripts.v093_taifex_independent import partition_jobs
class PartitionTests(unittest.TestCase):
 def test_disjoint_and_complete(self):
  jobs=[{'start':str(y)+'-01-01','end':str(y)+'-12-31'} for y in range(2000,2027)]
  a=partition_jobs(jobs,'ASC');d=partition_jobs(jobs,'DESC')
  self.assertEqual(len(a)+len(d),len(jobs));self.assertFalse(any(x in d for x in a));self.assertEqual(a[0]['start'],'2000-01-01');self.assertEqual(d[0]['start'],'2013-01-01')
 def test_reject_crossing(self):
  with self.assertRaises(ValueError):partition_jobs([{'start':'2012-12-01','end':'2013-01-01'}],'ASC')
