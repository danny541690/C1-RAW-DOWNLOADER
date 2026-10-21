import unittest
from scripts.v093_cross_source_numeric_audit import compare_rows
def row(src,field,val,stock="2330",date="2026-09-01"):
 return {"source":src,"date":date,"stock_id":stock,"native_field":field,"numeric_unscaled":val}
class CrossSourceNumericTests(unittest.TestCase):
 def test_exact_matched_price(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TWSE":[row("TWSE","收盤價",100)]})
  self.assertEqual(r["compared_pairs"],{"FinMind__TWSE":1})
  self.assertEqual(r["within_tolerance"],{"FinMind__TWSE":1})
  self.assertFalse(r["certified"])
 def test_mismatch_and_no_false_join(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TWSE":[row("TWSE","收盤價",101),row("TWSE","收盤價",100,stock="2317")]})
  self.assertEqual(r["mismatch"],{"FinMind__TWSE":1})
  self.assertEqual(len(r["mismatch_examples"]),1)
 def test_no_overlapping_sources_not_pass(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TPEx":[row("TPEx","投信買賣超",100)]})
  self.assertEqual(r["compared_pairs"],{})
  self.assertFalse(r["independent_numeric_verified"])
 def test_duplicate_source_conflict(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100),row("FinMind","close",101)]})
  self.assertEqual(r["duplicate_conflicts"],1)
if __name__=="__main__":unittest.main()
