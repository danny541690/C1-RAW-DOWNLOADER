import json,unittest
from scripts.v095_historical_trade_days_twse import normalize_date,parse_native
class HistoricalTradeDaysTests(unittest.TestCase):
 def test_roc_and_gregorian_dates(self):
  self.assertEqual(normalize_date("89/01/04"),"2000-01-04")
  self.assertEqual(normalize_date("115/11/02"),"2026-11-02")
  self.assertEqual(normalize_date("2026/11/02"),"2026-11-02")
 def test_native_month_positive_evidence(self):
  raw=json.dumps({"stat":"OK","fields":["日期","交易量","指數"],"data":[["89/01/04","1000","8,000"],["89/01/05","1100","8,100"]]},ensure_ascii=False).encode()
  self.assertEqual(parse_native(raw,2000,1),["2000-01-04","2000-01-05"])
  with self.assertRaises(ValueError):parse_native(raw,2000,2)
 def test_errors_are_not_marked_closed(self):
  for raw in ({"stat":"很抱歉沒有符合條件的資料","fields":[],"data":[]},
              {"stat":"OK","fields":["日期"],"data":[]},
              {"stat":"OK","fields":["資料"],"data":[["89/01/04"]]}):
   with self.assertRaises(ValueError):parse_native(json.dumps(raw,ensure_ascii=False).encode(),2000,1)
 def test_duplicate_date_rejected(self):
  raw=json.dumps({"stat":"OK","fields":["日期","交易量"],"data":[["115/11/02","100"],["115/11/02","90"]]},ensure_ascii=False).encode()
  with self.assertRaises(ValueError):parse_native(raw,2026,11)
if __name__=="__main__":unittest.main()
