import unittest
from scripts.v095_r12_deep_manifest_and_preflight import month_of_path,official_status,analyze,scope_preflight,candidate_state,MONTHS
class R12BoundedDeepManifest(unittest.TestCase):
 def setUp(self):
  self.p={"issues":[{"id":x} for x in "abcdefghijkl"],"rules":{"license_and_finmind_access":"ONLY_ENABLED_AFTER_RIGHTS_VERIFIED"},
   "architecture":{"release_layers":{"gold":"VALID_FORMULA_PLUS_POINT_IN_TIME_LINEAGE"}}}
  self.f={"BULK_COPY_APPROVED":False,"RELEASE_APPROVED":False}
 def test_nested_month_dir_applies_to_unnamed_file(self):
  self.assertEqual(month_of_path(("2026","2026-10","TWSE","daily.zip")),["2026-10"])
  self.assertEqual(month_of_path(("2026_09","raw.csv")),["2026-09"])
  self.assertEqual(month_of_path(("legacy","2000-10","raw.csv")),[])
  self.assertEqual(month_of_path(("2026-12","raw.csv")),[])
 def test_ambiguous_multiple_months_not_assumed_valid(self):
  r=analyze([{"file_id":"1","stage":"SILVER","source":"UNKNOWN","logical_path":"2026-09/2026-10.parquet",
   "observed_months":["2026-09","2026-10"],"is_folder":False}],[],[],self.p,self.f)
  self.assertEqual(len(r["ambiguous_month_token_objects"]),1)
  self.assertIsNone(r["source_expected_dataset_counts"])
  self.assertEqual(r["source_data_downloads"],0)
 def test_truncation_is_blocked_not_missing(self):
  x=analyze([], [{"truncated":True,"error":None}],[],self.p,self.f)
  self.assertEqual(x["scan_status"],"BLOCKED_INCOMPLETE_TRAVERSAL")
  self.assertIsNone(x["missing_official_dataset_units"])
 def test_transport_error_does_not_create_ready_job(self):
  x=analyze([], [{"error":{"type":"API_RATE_LIMIT"},"truncated":False}],[],self.p,self.f)
  self.assertFalse(x["preflight"]["ready_to_download"])
  self.assertEqual(x["t2_write_gate"],"BLOCKED_NOT_PROVEN")
 def test_future_publication_cannot_be_downloaded_as_due(self):
  self.assertEqual(official_status("TWSE_DAILY_MARKET","2026-11",
   "2026-11-08T08:00:00Z","2026-11-07T00:00:00Z"),"NOT_YET_PUBLISHED")
  self.assertEqual(official_status("TDCC_WEEKLY_OWNERSHIP","2000-01"),"NOT_APPLICABLE_TO_SERIES")
  self.assertEqual(official_status("TPEX_DAILY_MARKET","2001-01"),"LEGACY_DATASET_DISCOVERY_REQUIRED")
  self.assertEqual(official_status("MOPS_REVENUE","2026-10"),"EXPECTED_DENOMINATOR_UNKNOWN")
 def test_manifest_candidate_classification_never_authenticates_by_name(self):
  x={"is_folder":False,"observed_months":["2026-09"],"source":"TWSE"}
  self.assertEqual(candidate_state(x),"PRESENT_UNVERIFIED_ORIGINAL_SHA")
  self.assertEqual(candidate_state({**x,"source":"UNKNOWN"}),"UNATTRIBUTED_SOURCE")
  self.assertEqual(candidate_state({**x,"observed_months":["2026-09","2026-10"]}),"UNKNOWN_OR_AMBIGUOUS_PERIOD")
  self.assertEqual(candidate_state({**x,"is_folder":True}),"STRUCTURAL_FOLDER_ONLY")
 def test_release_flag_blocks_preflight(self):
  p=scope_preflight(self.p,{"BULK_COPY_APPROVED":True,"RELEASE_APPROVED":False})
  self.assertFalse(p["security_flags_safe"])
  self.assertFalse(p["ready_to_download"])
if __name__=="__main__":unittest.main()
