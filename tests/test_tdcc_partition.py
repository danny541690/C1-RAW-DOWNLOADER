import unittest
from scripts.v093_tdcc_independent import assigned_dates
class TDCCPartitionTests(unittest.TestCase):
 def test_disjoint_sorted_and_complete(self):
  dates=['20261022','20251031','20260430','20260508']
  a=assigned_dates(dates,'ASC');d=assigned_dates(dates,'DESC')
  self.assertEqual(a,['20251031','20260430']);self.assertEqual(d,['20261022','20260508']);self.assertEqual(set(a+d),set(dates));self.assertFalse(set(a)&set(d))
 def test_does_not_invent_2000_data(self):
  self.assertEqual(assigned_dates(['20251031'],'ASC'),['20251031'])

class TDCCRequestedHistoryPlanTests(unittest.TestCase):
 def test_2000_requested_floor_not_relabelled_as_2025_start(self):
  import datetime as dt
  from scripts.v093_tdcc_independent import history_plan
  p=history_plan(['20261022','20251031','20260430'],'ASC',dt.date(2026,10,24))
  self.assertEqual(p['requested_scan_start'],'2000-01-01')
  self.assertEqual(p['requested_range']['end'],'2026-10-24')
  self.assertEqual(p['first_assigned_available_date'],'20251031')
  gap=p['not_offered_intervals'][0]
  self.assertEqual((gap['start'],gap['end']),('2000-01-01','2025-10-30'))
  self.assertFalse(gap['downloaded']);self.assertFalse(gap['historical_absence_certified'])
 def test_empty_menu_is_not_evidence_of_2000_absence(self):
  import datetime as dt
  from scripts.v093_tdcc_independent import history_plan
  p=history_plan([],'ASC',dt.date(2026,10,24))
  self.assertIsNone(p['first_offered_date']);self.assertEqual(p['not_offered_intervals'],[])
 def test_newest_lane_does_not_claim_2000_scan(self):
  import datetime as dt
  from scripts.v093_tdcc_independent import history_plan
  p=history_plan(['20251031','20261022'],'DESC',dt.date(2026,10,24))
  self.assertEqual(p['assigned_range']['start'],'2026-05-01')
  self.assertEqual(p['not_offered_intervals'],[])
