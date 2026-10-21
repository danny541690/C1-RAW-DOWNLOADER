import unittest
from scripts.v093_twse_disclosure_pit import audit_disclosure_rows
class TWSEAllRowsPITTests(unittest.TestCase):
 def test_counts_every_row_without_certifying(self):
  rows=[{"資料年月":"11509","出表日期":"1151016"},{"資料年月":"11509","出表日期":"1151016"},{"資料年月":"11509","出表日期":"1150920"},{"資料年月":"11508","出表日期":"1150920"},{"資料年月":"11509","出表日期":"1150230"}]
  r=audit_disclosure_rows(rows,"2026-09")
  self.assertEqual(r["counts"]["total_rows"],5)
  self.assertEqual(r["counts"]["DISCLOSURE_AFTER_TARGET_MONTH"],2)
  self.assertEqual(r["counts"]["DATA_MONTH_DIFFERENT_FROM_TARGET"],1)
  self.assertEqual(r["counts"]["REPORT_DATE_MISSING_OR_INVALID"],1)
  self.assertEqual(r["counts"]["no_detected_month_mismatch_but_pit_unverified"],1)
  self.assertFalse(r["certified"])
if __name__=="__main__":unittest.main()
