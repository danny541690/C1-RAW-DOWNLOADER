import unittest
from hashlib import sha256
from scripts.v097_r3_g2_shared_contract_engine import file_decision,confirm_g2_readback
SHA=sha256(b"official-nonmock-structure-fixture").hexdigest()
ROW={"source_id":"NDC-fixture","source":"NDC","source_sha256":SHA}
T={"dataset":"BUSINESS_SIGNAL","historical_era":"NDC_SIGNAL_2024",
   "native_format":"JSON","native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
   "official_dataset_start_date":"2026-10-23","effective_start_day":"2026-10-23",
   "effective_end_day":"2026-10-23","era_basis":"source_publication_vintage",
   "template_id":"verified-source-snapshot","contract_version":"R3_NDC_VINTAGE_V1",
   "official_document_sha256":SHA,"independent_review_sha256":SHA}
B={"source_id":"NDC-fixture","source":"NDC","source_sha256":SHA,
   "source_document_sha256":SHA,"source_path":"NDC/2026-10/native.json",
   "dataset":"BUSINESS_SIGNAL","historical_era":"NDC_SIGNAL_2024",
   "native_format":"JSON","native_layout_id":"NDC_XLSX_5_SHEETS_DERIVED_JSON",
   "source_data_date":"2015-03-01","source_data_date_verified":True,
   "native_date_evidence_sha256":SHA,"publication_asof_verified":True,
   "native_layout_verified":True,"dataset_origin_verified":True,
   "independent_evidence_id":"real-review-doc-id","binding_version":"1",
   "source_publication_asof":"2026-10-23","source_publication_asof_verified":True}
class TestVintage(unittest.TestCase):
 def test_historical_observation_in_later_revised_vintage(self):
  result=file_decision(ROW,[T],B)
  self.assertEqual(result["status"],"CANDIDATE")
  self.assertFalse(result["certificate"]["historical_backtest_eligible_before_source_publication"])
  self.assertEqual(result["certificate"]["source_publication_asof"],"2026-10-23")
  self.assertEqual(confirm_g2_readback(result,result["certificate"])["status"],"PASS")
 def test_without_independent_vintage_time_no_certificate(self):
  b={**B,"source_publication_asof_verified":False}
  self.assertEqual(file_decision(ROW,[T],b)["status"],"HOLD")
 def test_future_observation_cannot_retroactively_fit_earlier_publication(self):
  b={**B,"source_data_date":"2026-11-01"}
  self.assertEqual(file_decision(ROW,[T],b)["status"],"HOLD")
 def test_separate_proof_sha_mismatch_blocks(self):
  b={**B,"source_document_sha256":"a"*64}
  self.assertEqual(file_decision(ROW,[T],b)["status"],"HOLD")
if __name__=="__main__":unittest.main()
