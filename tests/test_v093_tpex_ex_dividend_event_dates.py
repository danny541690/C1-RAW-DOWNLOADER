import json,unittest
from scripts.v093_standard_r2 import parse
class TPExExDividendEventTests(unittest.TestCase):
 def test_real_roc_event_table_dates_and_symbols(self):
  payload={"date":"20240603","stat":"OK","tables":[{"fields":["除權息日期","代號","名稱","除權息前收盤價","息值"],"data":[["113/06/04","6788","華景電","146.50","6.000000"],["113/06/05","4123","Other","15","0.5"]]}]}
  rows,invalid,_=parse("TPEx","ex_dividend.zip","ex_dividend_2024-06.json",json.dumps(payload,ensure_ascii=False).encode(),"2024-06")
  self.assertEqual(invalid,0)
  self.assertEqual(len(rows),4)
  self.assertEqual({(r["stock_id"],r["date"]) for r in rows},{("6788","2024-06-04"),("4123","2024-06-05")})
  self.assertTrue(all(r["date_proof"]=="TPEx_EVENT_ROC_DATE" for r in rows))
  self.assertTrue(all("代號__col_" not in r["native_field"] for r in rows))
  self.assertTrue(all(not r["pit_verified"] and not r["unit_verified"] and not r["numeric_verified"] for r in rows))
 def test_out_of_month_event_rejected(self):
  payload={"date":"20240603","tables":[{"fields":["除權息日期","代號","息值"],"data":[["113/07/01","6788","6"]]}]}
  rows,invalid,_=parse("TPEx","ex_dividend.zip","ex_dividend_2024-06.json",json.dumps(payload,ensure_ascii=False).encode(),"2024-06")
  self.assertEqual(rows,[])
  self.assertEqual(invalid,1)
 def test_invalid_event_date_cannot_fallback_to_query_date(self):
  payload={"date":"20240603","tables":[{"fields":["除權息日期","代號","息值"],"data":[["unknown","6788","6"]]}]}
  rows,invalid,_=parse("TPEx","ex_dividend.zip","ex_dividend_2024-06.json",json.dumps(payload,ensure_ascii=False).encode(),"2024-06")
  self.assertEqual(rows,[])
if __name__=="__main__":unittest.main()
