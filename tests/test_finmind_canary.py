import unittest
from scripts.finmind_canary import validate

class FinMindCanaryTest(unittest.TestCase):
    def test_valid_historical(self):
        x=validate({"status":200,"data":[{"date":"2024-01-02","stock_id":"2330"}]})
        self.assertEqual(x["rows"],1)
        self.assertFalse(x["drive_uploaded"])
    def test_wrong_month(self):
        with self.assertRaises(ValueError):
            validate({"status":200,"data":[{"date":"2024-02-01","stock_id":"2330"}]})
    def test_wrong_stock(self):
        with self.assertRaises(ValueError):
            validate({"status":200,"data":[{"date":"2024-01-02","stock_id":"2317"}]})
