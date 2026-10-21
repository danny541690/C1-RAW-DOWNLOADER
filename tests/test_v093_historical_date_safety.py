import unittest
from scripts.v093_standard_r2 import normalize_date,source_date,parse

class HistoricalDateSafetyTests(unittest.TestCase):
 def test_valid_gregorian_and_roc(self):
  self.assertEqual(normalize_date("20000103"),"2000-01-03")
  self.assertEqual(normalize_date("2024/02/29"),"2024-02-29")
  self.assertEqual(normalize_date("113/06/04"),"2024-06-04")
  self.assertEqual(normalize_date("115/10/21"),"2026-10-21")
 def test_invalid_calendar_dates_fail_closed(self):
  for value in ("113/02/30","2024/13/01","2023/02/29","20000100","115/00/10","2026/04/31"):
   with self.subTest(value=value):self.assertIsNone(normalize_date(value))
 def test_filename_supports_older_history(self):
  for name,expected in (("TWSE_20000103.json","2000-01-03"),("TPEx_20140417.csv","2014-04-17"),("TWSE_20240603.json","2024-06-03")):
   with self.subTest(name=name):self.assertEqual(source_date(name),(expected,"FILENAME_ONLY"))
 def test_filename_rejects_impossible_date(self):
  self.assertEqual(source_date("TWSE_20240230.csv"),(None,"NONE"))
 def test_invalid_row_date_not_replaced_by_response(self):
  raw=b'{"date":"20240603","data":[{"date":"2024-02-30","stock_id":"2330","close":"100"}]}'
  rows,invalid,_=parse("TWSE","x.zip","x.json",raw,"2024-06")
  self.assertEqual(rows,[])
if __name__=="__main__":unittest.main()
