import unittest,datetime as dt
from scripts.v095_g0_bronze_download_gate import classification
class TestG0BronzeEligibility(unittest.TestCase):
 def test_no_false_missing_closed(self):
  self.assertEqual(classification("TWSE","2026-01-01","CONFIRMED_CLOSED"),"SKIP_VERIFIED_NO_TRADE")
  self.assertEqual(classification("TPEx","2026-02-12","CONFIRMED_SETTLEMENT_ONLY"),"SKIP_VERIFIED_NO_TRADE")
 def test_unknown_is_discovery_not_missing(self):
  self.assertEqual(classification("TAIFEX","2000-01-03","WEEKDAY_UNVERIFIED"),"PROBE_SOURCE_ONLY_NOT_A_CONFIRMED_GAP")
 def test_non_daily_source_is_not_cash_trading(self):
  for s in ("MOPS","TDCC","NDC"):
   self.assertEqual(classification(s,"2004-03-04","WEEKDAY_UNVERIFIED"),"PUBLICATION_FREQUENCY_CHECK_ONLY_NOT_DAILY_TRADING_EXPECTATION")
 def test_no_native_trade_on_official_closure(self):
  with self.assertRaises(ValueError):
   classification("TWSE","2026-01-01","CONFIRMED_CLOSED",has_native_date=True)
 def test_positive_past_can_download(self):
  self.assertEqual(classification("TWSE","2005-03-01","CONFIRMED_TRADING"),"BRONZE_ELIGIBLE_WITH_SOURCE_VALIDATION")
if __name__=="__main__":unittest.main()
