import unittest
from scripts.v093_twse_disclosure_pit import roc_compact_date,roc_compact_month,disclosure_evidence
class TWSEDisclosurePITTests(unittest.TestCase):
 def test_real_2026_september_archive_october_report(self):
  r=disclosure_evidence({"公司代號":"1101","資料年月":"11509","出表日期":"1151016"},"2026-09")
  self.assertEqual(r["data_month"],"2026-09")
  self.assertEqual(r["report_date"],"2026-10-16")
  self.assertIn("DISCLOSURE_AFTER_TARGET_MONTH",r["issues"])
  self.assertFalse(r["pit_eligible_for_target_month"])
  self.assertFalse(r["certified"])
 def test_invalid_roc_dates(self):
  self.assertIsNone(roc_compact_date("1150230"))
  self.assertIsNone(roc_compact_month("11513"))
 def test_matching_month_is_not_automatically_certified(self):
  r=disclosure_evidence({"資料年月":"11509","出表日期":"1150920"},"2026-09")
  self.assertIsNone(r["pit_eligible_for_target_month"])
  self.assertFalse(r["certified"])
if __name__=="__main__":unittest.main()
