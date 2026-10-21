import unittest
from scripts.v093_source_pit_unit_evidence import assess_evidence,mops_html_evidence
class SourcePITUnitEvidenceTests(unittest.TestCase):
 def test_unproven_mops_matrix_is_quarantined(self):
  x=mops_html_evidence('<table><tr><td>資產總額</td><td>1,234</td></tr></table><p>金額單位：新台幣仟元</p>')
  self.assertEqual(x["kind"],"FINANCIAL_STATEMENT_MATRIX")
  self.assertEqual(x["unit_hint"],"NTD_THOUSANDS_UNVERIFIED")
  self.assertFalse(x["has_stock_id_evidence"])
  self.assertFalse(x["has_publication_timestamp_evidence"])
  self.assertFalse(x["has_report_period_evidence"])
  self.assertFalse(x["certified"])
 def test_unit_hint_not_equivalent_to_unit_proof(self):
  x=assess_evidence("MOPS",None,None,None,"NTD_THOUSANDS_UNVERIFIED")
  self.assertFalse(x["pit_evidence_complete"])
  self.assertFalse(x["unit_evidence_complete"])
  self.assertFalse(x["verified"])
 def test_publication_date_cannot_precede_period(self):
  x=assess_evidence("MOPS","2330","2024-06","2024-05-31","NTD_THOUSANDS")
  self.assertIn("PUBLICATION_PRECEDES_REPORT_PERIOD",x["issues"])
 def test_cross_source_requires_lineage(self):
  x=assess_evidence("TWSE","2330","2024-06","2024-07-10","NTD",{"source":"TPEx","stock_id":"2330","report_period":"2024-06","metric":"close","unit":"NTD"})
  self.assertFalse(x["cross_source_metadata_comparable"])
  self.assertIn("COMPARISON_SOURCE_SHA256_MISSING",x["issues"])
 def test_even_metadata_evidence_does_not_certify_values(self):
  x=assess_evidence("MOPS","2330","2024-06","2024-07-10","NTD_THOUSANDS")
  self.assertTrue(x["pit_evidence_complete"])
  self.assertTrue(x["unit_evidence_complete"])
  self.assertFalse(x["verified"])
if __name__=="__main__":unittest.main()
