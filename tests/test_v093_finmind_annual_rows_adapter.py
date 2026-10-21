import json,unittest
from scripts.v093_standard_r2 import parse
class FinMindAnnualBatchTests(unittest.TestCase):
    def test_actual_annual_rows_container_yields_native_cells(self):
        payload={"dataset":"TaiwanStockPrice","stock_id":"1101","rows":[{"date":"2026-09-01","stock_id":"1101","open":42.5,"max":43,"min":42,"close":42.7,"Trading_Volume":12000}]}
        rows,invalid,enc=parse("FinMind","sample.zip","TaiwanStockPrice/1101.json",json.dumps(payload).encode(),"2026-09")
        self.assertEqual(invalid,0)
        self.assertGreaterEqual(len(rows),5)
        self.assertTrue(all(r["stock_id"]=="1101" and r["date"]=="2026-09-01" for r in rows))
        self.assertTrue(all(not r["pit_verified"] and not r["unit_verified"] and not r["numeric_verified"] for r in rows))
    def test_mismatched_month_cannot_be_staged(self):
        payload={"rows":[{"date":"2026-08-30","stock_id":"1101","open":40}]}
        rows,invalid,_=parse("FinMind","sample.zip","TaiwanStockPrice/1101.json",json.dumps(payload).encode(),"2026-09")
        self.assertEqual(rows,[])
        self.assertEqual(invalid,1)
    def test_no_stock_id_is_not_fabricated(self):
        payload={"rows":[{"date":"2026-09-01","name":"Unknown","buy":123}]}
        rows,invalid,_=parse("FinMind","sample.zip","unidentified.json",json.dumps(payload).encode(),"2026-09")
        self.assertEqual(rows,[])
        self.assertEqual(invalid,1)
if __name__=="__main__":unittest.main()
