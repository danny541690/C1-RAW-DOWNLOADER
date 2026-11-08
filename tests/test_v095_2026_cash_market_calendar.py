import unittest
from scripts.v095_2026_cash_market_calendar import load_calendar,status,is_verified_closed,require_trade_date
class TestCashMarketCalendar2026(unittest.TestCase):
    def test_365_explicit_dates_and_verified_counts(self):
        rows,sha,counts=load_calendar()
        self.assertEqual(len(rows),365)
        self.assertEqual(counts,{"TRADING":243,"HOLIDAY":16,"SETTLEMENT_ONLY":2,"WEEKEND":104})
        self.assertEqual(len(sha),64)
    def test_official_new_year_and_festival(self):
        for source in ("TWSE","TPEx"):
            self.assertEqual(status("2026-01-01",source),"HOLIDAY")
            self.assertEqual(status("2026-01-02",source),"TRADING")
            self.assertEqual(status("2026-02-12",source),"SETTLEMENT_ONLY")
            self.assertEqual(status("2026-02-13",source),"SETTLEMENT_ONLY")
            self.assertEqual(status("2026-02-23",source),"TRADING")
            self.assertTrue(is_verified_closed("2026-02-20",source))
            self.assertTrue(require_trade_date("2026-02-23",source))
            with self.assertRaises(ValueError):require_trade_date("2026-02-12",source)
    def test_no_calendar_invention_for_other_sources_or_years(self):
        with self.assertRaises(ValueError):status("2026-01-02","TAIFEX")
        with self.assertRaises(ValueError):status("2025-12-31","TWSE")
if __name__=="__main__":unittest.main()
