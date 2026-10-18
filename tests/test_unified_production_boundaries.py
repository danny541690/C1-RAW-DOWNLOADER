import unittest
from scripts.unified_annual_downloader import plan
class ProductionBoundaries(unittest.TestCase):
    def test_all_months_four_sources(self):
        for month in range(1,13):
            units=plan(2024,month)
            self.assertEqual({u["source"] for u in units},{"TWSE","TPEx","MOPS","FinMind"})
            self.assertEqual(len(units),len({u["key"] for u in units}))
    def test_finmind_is_sample_not_full_market(self):
        for month in range(1,13):
            u=[x for x in plan(2024,month) if x["source"]=="FinMind"]
            self.assertEqual(len(u),1)
            self.assertIn("data_id=2330",u[0]["url"])
    def test_mops_is_revenue_only(self):
        for month in range(1,13):
            u=[x for x in plan(2024,month) if x["source"]=="MOPS"]
            self.assertEqual(len(u),2)
            self.assertTrue(all("t21sc03" in x["url"] for x in u))
    def test_non2024_mops_finmind_not_silent_full_year(self):
        self.assertFalse(any(x["source"] in ("MOPS","FinMind") for x in plan(2025,1)))
if __name__=="__main__":unittest.main()
