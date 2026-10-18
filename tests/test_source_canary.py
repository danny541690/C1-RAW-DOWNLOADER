import unittest
from scripts.source_canary import inspect_twse_stock_day

class TestSourceCanary(unittest.TestCase):
    def test_historical_roc_dates(self):
        d={"stat":"OK","data":[["113/01/02","1","2"],["113/01/03","1","2"]]}
        r=inspect_twse_stock_day(d,2024,1)
        self.assertEqual(r["records"],2)
        self.assertEqual(r["first_date"],"2024-01-02")
        self.assertFalse(r["numeric_verified"])
    def test_wrong_year_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect_twse_stock_day({"stat":"OK","data":[["114/01/02"]]},2024,1)
    def test_error_page_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect_twse_stock_day({"stat":"ERROR","data":[]},2024,1)
if __name__=="__main__":
    unittest.main()
