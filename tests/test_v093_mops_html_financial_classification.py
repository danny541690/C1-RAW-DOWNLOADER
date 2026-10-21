import unittest
from scripts.v093_standard_r2 import classify_mops_html,parse
class MopsFinancialHtmlTests(unittest.TestCase):
 def test_financial_matrix_is_not_mislabelled_revenue(self):
  raw='<html><table><tr><td>(金額單位：新台幣仟元)</td></tr><tr><td>資產總額</td><td>123,456</td></tr><tr><td>負債總額</td><td>45,678</td></tr></table></html>'
  d=classify_mops_html(raw)
  self.assertEqual(d["kind"],"FINANCIAL_STATEMENT_MATRIX")
  self.assertEqual(d["unit_hint"],"NTD_THOUSANDS_UNVERIFIED")
  self.assertFalse(d["pit_verified"])
  self.assertFalse(d["stock_id_verified"])
  self.assertFalse(d["certified"])
  with self.assertRaisesRegex(ValueError,"MOPS_FINANCIAL_STATEMENT_MATRIX_REQUIRES_STOCK_ID_PERIOD_AND_PIT_METADATA"):
   parse("MOPS","sample.zip","financial.raw",raw.encode(),"2026-09")
 def test_unknown_html_fails_closed(self):
  self.assertEqual(classify_mops_html("<table><tr><td>Other</td></tr></table>")["kind"],"UNKNOWN_HTML")
if __name__=="__main__":unittest.main()
