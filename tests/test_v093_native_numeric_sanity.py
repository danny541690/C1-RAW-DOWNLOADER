import unittest
from scripts.v093_native_numeric_sanity import audit
def row(**kwargs):
 d={"source":"TWSE","native_archive":"a.zip","native_member":"a.json","native_table":"data","row_index":0,"date":"2024-06-03","stock_id":"2330","native_field":"收盤價","numeric_unscaled":100.0,"unit_verified":False,"numeric_verified":False,"pit_verified":False,"status":"STAGING_UNMAPPED"}
 d.update(kwargs);return d
class NativeSanityTests(unittest.TestCase):
 def test_valid_unverified_row(self):
  result=audit([row()],"2024-06")
  self.assertEqual(result["rows"],1)
  self.assertFalse(result["certified"])
  self.assertEqual(sum(v for k,v in result.items() if k not in ("rows","certified")),0)
 def test_quarantine_problems(self):
  bad=[row(date="2024-06-31"),row(native_field="股票代號__col_00",row_index=1),row(numeric_unscaled=float("inf"),row_index=2),row(pit_verified=True,row_index=3),row(status="CERTIFIED",row_index=4),row(stock_id="?",row_index=5)]
  out=audit(bad+[bad[0]],"2024-06")
  for key in ("invalid_date","identifier_as_numeric","nonfinite_numeric","premature_verification","premature_publication","invalid_stock_id","duplicate_lineage_key"):
   self.assertGreater(out[key],0,key)
if __name__=="__main__":unittest.main()
