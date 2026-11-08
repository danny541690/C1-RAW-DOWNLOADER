import datetime as dt, pathlib, tempfile, unittest
from scripts.v095_market_release_calendar_2000_2026 import (
    build,contracts,history_evidence,market_day,due,SOURCES
)
class TestG0MarketReleaseCalendar(unittest.TestCase):
    def test_six_sources_and_contracts(self):
        self.assertEqual(len(SOURCES),6)
        self.assertGreaterEqual(len(contracts()),25)
        self.assertEqual(len(history_evidence()),0)
    def test_no_invented_2000_2025_market_holidays(self):
        self.assertEqual(market_day("2004-02-02","TWSE")[0],"WEEKDAY_UNVERIFIED")
        self.assertEqual(market_day("2004-02-01","TPEx")[0],"WEEKEND_ASSUMED_UNVERIFIED")
        self.assertEqual(market_day("2026-02-12","TWSE")[0],"CONFIRMED_SETTLEMENT_ONLY")
        self.assertEqual(market_day("2026-01-02","TPEx")[0],"CONFIRMED_TRADING")
        self.assertEqual(market_day("2026-01-02","TAIFEX")[0],"WEEKDAY_UNVERIFIED")
    def test_tdcc_pre_2008_is_not_missing(self):
        now=dt.datetime(2026,11,8,11,0,tzinfo=dt.timezone(dt.timedelta(hours=8)))
        self.assertEqual(due("TDCC","ownership_distribution","2005-01-07",now),
                         "SOURCE_NOT_YET_AVAILABLE_CONFIRMED")
    def test_gap_and_due_separation(self):
        now=dt.datetime(2026,11,8,11,0,tzinfo=dt.timezone(dt.timedelta(hours=8)))
        self.assertEqual(due("TWSE","cash_prices","2026-01-01",now),"OFFICIAL_NONTRADING_NOT_GAP")
        self.assertEqual(due("TWSE","cash_prices","2004-02-02",now),"HISTORICAL_TRADE_DATE_UNKNOWN_NOT_GAP")
        self.assertEqual(due("MOPS","monthly_revenue","2026-10-01",now),"FILING_DEADLINE_NOT_ACTUAL_PUBLISH_TIMESTAMP")
        self.assertEqual(due("TDCC","ownership_distribution","2026-10-30",now),"WEEKLY_PUBLICATION_DATE_UNVERIFIED_NOT_GAP")
        self.assertEqual(due("TAIFEX","futures_daily","2026-11-10",now),"FUTURE_NOT_DUE")
        with self.assertRaises(ValueError):
            due("MOPS","monthly_revenue","2026-10-01",now,"2026-11-08T10:00:00")
    def test_full_generated_calendar(self):
        with tempfile.TemporaryDirectory() as folder:
            data=build(folder)
            self.assertEqual(data["calendar_rows"],9862*6)
            self.assertEqual(data["dataset_contracts"],26)
            self.assertFalse(data["g0_coverage_denominator_certified"])
            self.assertTrue((pathlib.Path(folder)/"market_dates_2000_2026.csv").exists())
if __name__=="__main__":unittest.main()
