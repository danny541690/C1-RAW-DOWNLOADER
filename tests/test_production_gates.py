import unittest
from scripts.production_gates import month_days,raw_segments,coverage_status
class ProductionGateTests(unittest.TestCase):
    def test_leap_year(self):self.assertEqual(month_days(2024,2),29)
    def test_correct_folder_order(self):self.assertEqual(raw_segments(2024,"TWSE",1),("2024","TWSE","2024-01"))
    def test_bad_source(self):
        with self.assertRaises(ValueError):raw_segments(2024,"UNKNOWN",1)
    def test_invalid_month(self):
        with self.assertRaises(ValueError):month_days(2024,13)
    def test_no_unknown_denominator_claim(self):self.assertEqual(coverage_status(None,33),"COVERAGE_UNKNOWN")
    def test_partial(self):self.assertEqual(coverage_status(50,22),"PARTIAL")
    def test_basic_only_not_qa(self):self.assertEqual(coverage_status(50,50),"BASIC_ONLY")
    def test_qa_requires_both(self):
        self.assertEqual(coverage_status(50,50,True,False),"BASIC_ONLY")
        self.assertEqual(coverage_status(50,50,True,True),"QA_VERIFIED")
