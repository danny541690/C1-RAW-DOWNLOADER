import unittest
from scripts.v096_raw_first_audit import check
from scripts.v096_raw_first import classify,safe_months

class V096SafetyTest(unittest.TestCase):
 def test_format_dispatch(self):
  self.assertEqual(classify("TWSE.2025.JSON"),"JSON")
  self.assertEqual(classify("legacy.zip"),"ZIP")
  self.assertEqual(classify("data.csv"),"CSV")
 def test_month_limits(self):
  self.assertEqual(safe_months("2025-01,2026-10"),("2025-01","2026-10"))
  for months in ("2024-01","2025-13","2025-01,2025-01",
                 "2025-01,2025-02,2025-03,2025-04,2025-05"):
   with self.assertRaises(ValueError):safe_months(months)
 def test_fail_closed_audit(self):
  raw={"schema":"JARVIS_V096_P0_SOURCE_MANIFEST_V1","rows":[{
   "original_drive_file_id":"original_1","source":"TWSE","month_folder":"2025-01",
   "size_bytes":123,"source_format":"ZIP","source_sha256":None,
   "raw_v096_storage":"REFERENCE_ORIGINAL_ID_ONLY",
   "historical_pit_verified":False,"original_file_deleted":False,
   "market_data_rewritten":False}]}
  report={"legacy_files_indexed":1,"silver_partitions_created":0,
   "gold_indicators_created":0,"official_downloads":0,"v095_mutated":False,
   "v093_mutated":False,"PIT_certified":False,
   "full_source_completeness_certified":False}
  self.assertEqual(check(raw,report)["status"],"PASS_METADATA_INDEX_ONLY")
  raw["rows"][0]["source_sha256"]="invented"
  with self.assertRaises(ValueError):check(raw,report)
  raw["rows"][0]["source_sha256"]=None
  report["gold_indicators_created"]=443
  with self.assertRaises(ValueError):check(raw,report)
if __name__=="__main__":unittest.main()
