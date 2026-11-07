import unittest
from scripts.v095_r11_t1_three_month_manifest import analyse,detect_month,MONTHS,SOURCES
class BoundedManifest(unittest.TestCase):
 def test_all_three_months(self):
  self.assertEqual(detect_month('TWSE_2026-09.zip'),'2026-09')
  self.assertEqual(detect_month('202610_TPEX.csv'),'2026-10')
  self.assertEqual(detect_month('2026_11_sample.parquet'),'2026-11')
  self.assertIsNone(detect_month('202612_future.parquet'))
  self.assertIsNone(detect_month('20001001.csv'))
 def test_no_false_completeness_and_duplicates(self):
  rows=[{"id":"a","source":"TWSE","month":"2026-09","canonical":True},
        {"id":"a","source":"TWSE","month":"2026-09","canonical":True},
        {"id":"b","source":"TWSE","month":"2026-10","canonical":False},
        {"id":"c","source":"TPEx","month":"2026-11","canonical":True}]
  prior={"immutable_receipts":[{"key":"2026-09|TWSE|DATE","content_sha256":"a"*64}]}
  q=analyse(rows,prior,{})
  self.assertEqual(q["source_month_cells"],18)
  self.assertEqual(q["unique_metadata_object_ids"],3)
  self.assertEqual(q["summary_by_month"]["2026-09"]["canonical_source_cells_with_files"],1)
  self.assertEqual(q["summary_by_month"]["2026-10"]["alternate_cells_with_candidates"],1)
  self.assertIsNone(q["summary_by_month"]["2026-11"]["dataset_expected_denominator"])
  self.assertEqual(q["ready_download_tasks"],0)
  self.assertFalse(q["pit_certified"])
 def test_no_guess_unknown_source_from_filename(self):
  r=analyse([{"id":"x","source":"UNKNOWN","month":"2026-10","canonical":False}],{"immutable_receipts":[]},{})
  self.assertEqual(r["summary_by_month"]["2026-10"]["canonical_source_cells_with_files"],0)
if __name__=="__main__":unittest.main()
