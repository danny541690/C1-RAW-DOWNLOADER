import unittest
from scripts.v095_2026_annual_consolidated import MONTHS,SOURCES,ym,evaluate
class Annual2026(unittest.TestCase):
 def test_11_months_not_future(self):
  self.assertEqual(len(MONTHS),11)
  self.assertEqual(ym(("2026-01","data.json")),["2026-01"])
  self.assertEqual(ym(("202611","2026-11-07.csv")),["2026-11"])
  self.assertEqual(ym(("2026-12","x")),[])
  self.assertEqual(ym(("2026-09","2026-10")),["2026-09","2026-10"])
 def test_inventory_does_not_infer_month_completion(self):
  rows=[{"months":["2026-01"],"stage":"BRONZE","source":"TWSE","is_folder":False},
        {"months":["2026-11"],"stage":"SILVER","source":"UNKNOWN","is_folder":False}]
  r,work=evaluate(rows,[],[],[],[],[],{"immutable_receipts":[]})
  self.assertEqual(len(work),11*6)
  self.assertEqual(r["source_month_cells"],66)
  self.assertIsNone(r["eligible_dataset_denominator"])
  self.assertEqual(r["coverage_source_month"]["2026-01"]["TWSE"]["source_status"],"PRESENT_UNVERIFIED")
  self.assertEqual(r["coverage_source_month"]["2026-02"]["TWSE"]["source_status"],"NOT_LOCATED_UNPROVEN_MISSING")
  self.assertFalse(any(x["download_allowed"] for x in work))
  self.assertFalse(r["all_year_tier_release"])
 def test_scoped_lineage_not_confused_with_pit(self):
  r,work=evaluate([],[],[],[],[],[],{"immutable_receipts":[]},
    {"rejected":{},"completed":{"TWSE_2026-11-04":{
       "rows":1100,"gold_rows":1100,"native_numeric_exception_rows":0,
       "actions":["REUSED"]*3,"acquisition":"VERIFIED_IMMUTABLE_SNAPSHOT_NOT_FRESH_HTTP",
       "official_http_currently_available":False,"sha256":"f"*64,
       "bronze_id":"b","silver_id":"s","gold_id":"g"}}})
  self.assertEqual(r["current_canary"]["status"],"PASS_SCOPED_REUSED_NO_PIT")
  self.assertFalse(r["current_canary"]["days"]["TWSE_2026-11-04"]["pit"])
  self.assertFalse(r["verified_2026_full_year_complete"])
if __name__=="__main__":unittest.main()
