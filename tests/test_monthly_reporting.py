import unittest,json,csv,io
from scripts.monthly_reporting import build_month
class MonthlyReportingTests(unittest.TestCase):
    def test_reports_have_correct_year_first_paths_and_deferred_gaps(self):
        units=[{"key":"a","source":"TWSE","status":"SAVED_BASIC_VALID","attempts":1,"bytes":60},
               {"key":"b","source":"TPEx","status":"FAILED_RETRY_LIMIT","attempts":4,"last_error":"HTTP_503"}]
        out=build_month(2024,2,units)
        report=json.loads(out["MONTHLY_PROGRESS.json"])
        self.assertEqual(report["sources"]["TWSE"]["raw_path"],"2024/TWSE/2024-02")
        self.assertEqual(report["sources"]["TPEx"]["raw_path"],"2024/TPEx/2024-02")
        self.assertEqual((report["saved_basic_valid"],report["missing"]),(1,1))
        self.assertFalse(report["market_coverage_complete"])
        rows=list(csv.DictReader(io.StringIO(out["MISSING_UNITS.csv"])))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["key"],"b")
        self.assertEqual(report["sources"]["TPEx"]["requests"],4)
    def test_empty_month_never_claims_full_coverage(self):
        r=json.loads(build_month(2024,1,[])["MONTHLY_PROGRESS.json"])
        self.assertFalse(r["market_coverage_complete"])
