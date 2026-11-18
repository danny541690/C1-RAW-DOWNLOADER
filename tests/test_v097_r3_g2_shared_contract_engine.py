import unittest
from hashlib import sha256
from scripts.v097_r3_g2_shared_contract_engine import approved_template,file_decision,confirm_g2_readback,date_census,group_candidates
SHA=sha256(b"real-immutable-fixture").hexdigest()
T={"source":"TAIFEX","dataset":"FUTURES_DAILY","historical_era":"TAIFEX_DAY_AND_AFTER_HOURS","required_fields":{"date":["日期"]}}
P={"schema":"R3_G2_APPROVED_SHARED_TEMPLATES_V1","templates":[{
 "source":"TAIFEX","dataset":"FUTURES_DAILY","historical_era":"TAIFEX_DAY_AND_AFTER_HOURS",
 "template_id":"TAIFEX-FUT-2017-AFTER","contract_version":"v1","native_format":"CSV_ZIP",
 "native_layout_id":"TAIFEX_AFTER_HOURS_DAILY","official_dataset_start_date":"2000-01-01",
 "effective_start_day":"2017-05-15","effective_end_day":"2026-12-31",
 "required_fields":["date","contract"],"optional_fields":["option"],
 "approved_aliases":{"日期":"date"},"primary_key":["date","contract"],
 "official_reference":"https://www.taifex.com.tw/cht/4/historyOfTrading",
 "official_document_drive_id":"actual-fixture","official_document_sha256":SHA,
 "official_document_origin_verified":True,"independent_reviewer_id":"verified-person",
 "independent_review_record_id":"fixture-immutable","independent_review_sha256":SHA,
 "publication_asof_verified":True,"approved_at":"2026-11-18",
 "approval_status":"APPROVED"}]}
ROW={"source":"TAIFEX","source_id":"TAIFEX:2017-05-16","source_sha256":SHA,"data_date":"2017-05-16"}
B={"source":"TAIFEX","source_id":ROW["source_id"],"source_sha256":SHA,
   "source_document_sha256":SHA,"dataset":"FUTURES_DAILY",
   "historical_era":"TAIFEX_DAY_AND_AFTER_HOURS",
   "native_format":"CSV_ZIP","native_layout_id":"TAIFEX_AFTER_HOURS_DAILY",
   "source_path":"original/archive.zip","source_data_date":"2017-05-16",
   "source_data_date_verified":True,"native_date_evidence_sha256":SHA,
   "publication_asof_verified":True,
   "native_layout_verified":True,"dataset_origin_verified":True,
   "independent_evidence_id":"fixture-proof","binding_version":"v1"}
class Tests(unittest.TestCase):
 def test_all_candidates_unique(self):
  self.assertEqual(len(group_candidates()),143)
 def test_no_approval_never_passes(self):
  self.assertEqual(approved_template(None,T,lambda p:True)[1],"NO_APPROVED_REGISTRY")
  self.assertEqual(file_decision(ROW,[],B)["status"],"HOLD")
 def test_template_remote_proof_required(self):
  self.assertEqual(approved_template(P,T,lambda p:False)[1],"OFFICIAL_DOCUMENT_REMOTE_PROOF_FAILED")
  self.assertEqual(len(approved_template(P,T,lambda p:True)[0]),1)
 def test_candidate_is_not_pass_until_readback(self):
  approved,_=approved_template(P,T,lambda p:True)
  self.assertEqual(file_decision(ROW,approved,None)["reason"],"G2_NATIVE_DATASET_BINDING_MISSING")
  candidate=file_decision(ROW,approved,B)
  self.assertEqual(candidate["status"],"CANDIDATE")
  self.assertEqual(confirm_g2_readback(candidate,candidate["certificate"])["status"],"PASS")
  self.assertEqual(confirm_g2_readback(candidate,{**candidate["certificate"],"source_id":"tamper"})["status"],"HOLD")
 def test_midmonth_era_and_sha(self):
  approved,_=approved_template(P,T,lambda p:True)
  bad={**B,"source_data_date":"2017-05-14"}
  self.assertEqual(file_decision({**ROW,"data_date":"2017-05-14"},approved,bad)["reason"],"G2_NO_UNIQUE_NATIVE_EDITION")
  bad_bind={**B,"source_sha256":"b"*64}
  self.assertEqual(file_decision(ROW,approved,bad_bind)["reason"],"G2_FROZEN_ID_OR_SHA_MISMATCH")
 def test_coverage_never_claims_official_start(self):
  c=date_census([ROW,{**ROW,"data_date":"2019-01-01"}])
  self.assertEqual(c["bronze_earliest_observed_date"],"2017-05-16")
  self.assertEqual(c["official_dataset_start_date"],"UNVERIFIED_FROM_BRONZE")
if __name__=="__main__":unittest.main()
