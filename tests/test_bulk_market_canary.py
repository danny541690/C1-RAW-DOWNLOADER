import unittest,json
from scripts.bulk_market_canary import measure
class MarketBulkTests(unittest.TestCase):
 def test_twse_market_table_not_index_table(self):
  x={"tables":[{"fields":["指數","收盤"],"data":[[1,2]]},{"fields":["證券代號","收盤價"],"data":[["2330","1"]]*400}]}
  self.assertEqual(measure("TWSE",json.dumps(x).encode())["rows"],400)
 def test_reject_small_sample(self):
  x={"tables":[{"fields":["證券代號","收盤價"],"data":[["2330","1"]]}]}
  with self.assertRaises(ValueError):measure("TWSE",json.dumps(x).encode())
