import unittest
from scripts.v097_r3_g2_seven_source_periodic_templates import library_set,bound_start,bound_end
from scripts.v097_seven_historical_format_registry import OFFICIAL_VERSIONS
from scripts.v097_r3_g2_seven_source_template_compare import path_month
class TestSevenSourceTemplateArchitecture(unittest.TestCase):
 def test_exactly_seven_sources_143_candidate_joins(self):
  libraries=library_set({"templates":[]})
  self.assertEqual(len(libraries),7)
  self.assertEqual(sum(x["candidate_matrix_count"] for x in libraries.values()),143)
  self.assertEqual(libraries["TWSE"]["candidate_periods"],4)
  self.assertEqual(libraries["MOPS"]["candidate_periods"],4)
 def test_datasets_are_nested_per_source(self):
  libraries=library_set({"templates":[]})
  for s,lib in libraries.items():
   self.assertEqual(len(lib["datasets"]),len(OFFICIAL_VERSIONS[s]["datasets"]))
   for ds in lib["datasets"]:
    self.assertEqual(len(ds["editions"]),len(OFFICIAL_VERSIONS[s]["periods"]))
    self.assertEqual(ds["dataset_official_begin_status"],"MISSING_DATASET_SPECIFIC_PRIMARY_EVIDENCE")
    self.assertTrue(all(e["g2_release_state"]=="CANDIDATE_ONLY_HOLD" for e in ds["editions"]))
 def test_month_windows_are_not_invented_official_day_precision(self):
  self.assertEqual(bound_start("2003-12"),"2003-12-01")
  self.assertEqual(bound_end("2004-02"),"2004-02-29")
  self.assertIsNone(bound_end("9999-12"))
  self.assertEqual(path_month("2019/TWSE/2019-03/archive.zip"),"2019-03")
  self.assertIsNone(path_month("unknown/original.zip"))
if __name__=="__main__":unittest.main()
