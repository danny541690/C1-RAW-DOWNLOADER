import unittest
from scripts.v093_source_pit_unit_evidence import assess_evidence,mops_html_evidence,mops_revenue_header_evidence,mops_revenue_table_probe
class SourcePITUnitEvidenceTests(unittest.TestCase):
 def test_revenue_identity_and_exact_amount_without_pit_promotion(self):
  html='<p>上市公司115年9月份</p><p>出表日期：115/10/16</p><p>單位：千元</p><table><tr><th>公司代號</th><th>公司名稱</th><th>當月營收</th><th>上月營收</th></tr><tr><td>1101</td><td>台泥</td><td>14,321,556</td><td>2330</td></tr><tr><td>合計</td><td></td><td>14,321,556</td></tr></table>'
  x=mops_revenue_table_probe(html)
  self.assertEqual(x['distinct_symbol_column_pairs'],1)
  self.assertEqual(x['revenue_candidates'],1)
  r=x['revenue_candidate_samples'][0]
  self.assertEqual(r['value_100m_ntd'],'143.21556')
  self.assertEqual(r['stock_id'],'1101')
  self.assertIsNone(r['publication_date'])
  self.assertFalse(r['certified'])
  self.assertFalse(r['pit_verified'])
 def test_unheaded_four_digit_values_are_not_stocks(self):
  x=mops_revenue_table_probe('<table><tr><td>2330</td><td>1234</td></tr></table>')
  self.assertEqual(x['distinct_symbol_column_pairs'],0)
  self.assertEqual(x['revenue_candidates'],0)
 def test_missing_unit_blocks_revenue_conversion(self):
  x=mops_revenue_table_probe('<p>上市公司115年9月份</p><table><tr><th>公司代號</th><th>公司名稱</th><th>當月營收</th></tr><tr><td>1101</td><td>台泥</td><td>1234</td></tr></table>')
  self.assertEqual(x['revenue_candidates'],0)
  self.assertEqual(x['rejected_revenue_rows'],1)
 def test_mops_roc_period_unit_and_export_not_pit(self):
  html="<table><tr><td>上市公司115年9月份(累計與當月)營業收入統計表</td></tr><tr><td>出表日期：115/10/16</td></tr><tr><td>單位：千元</td></tr></table>"
  x=mops_revenue_header_evidence(html)
  self.assertEqual(x["report_period"],"2026-09")
  self.assertEqual(x["export_date"],"2026-10-16")
  self.assertEqual(x["unit_code"],"NTD_THOUSANDS")
  self.assertTrue(x["unit_evidence_complete"])
  self.assertIsNone(x["publication_date"])
  self.assertFalse(x["pit_verified"])
  self.assertFalse(x["certified"])
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
