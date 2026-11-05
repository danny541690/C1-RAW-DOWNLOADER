"""v0.95 official-first three total attempts and evidence-gated FinMind Free."""
import unittest
from scripts.v095_official_first_fallback import POLICY,REQUIRED,next_action

class PolicyTests(unittest.TestCase):
 def test_default_official_first(self):
  self.assertEqual(next_action({})["action"],"OFFICIAL_DOWNLOAD")
  self.assertEqual(next_action({})["attempt_number"],1)
 def test_existing_raw_never_re_downloaded(self):
  self.assertEqual(next_action({"verified_existing_v095":True})["action"],"REUSE_V095_RAW")
  self.assertEqual(next_action({"verified_existing_v093":True})["action"],"COPY_V093_WITH_PROVENANCE")
 def test_retry_budget_includes_first_call(self):
  self.assertEqual(next_action({"official_attempts_total":1,"official_last_error":"INCOMPLETE_READ"})["attempt_number"],2)
  self.assertEqual(next_action({"official_attempts_total":2,"official_last_error":"NETWORK_TIMEOUT"})["attempt_number"],3)
  self.assertEqual(next_action({"official_attempts_total":3,"official_last_error":"NETWORK_TIMEOUT"})["action"],"HOLD_NOT_PROVEN_OFFICIAL_MISSING")
 def test_three_failures_do_not_prove_official_gap(self):
  self.assertEqual(next_action({"official_attempts_total":3,"official_missing_confirmed":False,"finmind_free_approved_evidence":list(REQUIRED)})["action"],"HOLD_NOT_PROVEN_OFFICIAL_MISSING")
 def test_empty_source_date_no_data_not_failure(self):
  self.assertEqual(next_action({"calendar_status":"EXPECTED_NON_TRADING_DAY"})["action"],"KEEP_EXPECTED_EXCEPTION")
  self.assertEqual(next_action({"calendar_status":"NOT_YET_PUBLISHED"})["action"],"KEEP_EXPECTED_EXCEPTION")
 def test_rate_limit_never_hammer(self):
  self.assertEqual(next_action({"official_attempts_total":1,"rate_limited":True})["action"],"DEFER_BY_RATE_LIMIT")
 def test_schema_mismatch_not_auto_retry(self):
  self.assertEqual(next_action({"official_attempts_total":1,"official_last_error":"SCHEMA_MISMATCH"})["action"],"REVIEW_OFFICIAL_FAILURE")
 def test_valid_official_not_retry(self):
  self.assertEqual(next_action({"official_attempts_total":2,"official_last_error":"INCOMPLETE_READ","verified_official_response_valid":True})["action"],"PRESERVE_OFFICIAL_BRONZE")
 def test_finmind_requires_every_proof(self):
  base={"official_attempts_total":3,"official_missing_confirmed":True,"official_last_error":"NETWORK_TIMEOUT"}
  self.assertEqual(next_action(base)["action"],"HOLD_FINMIND_NOT_ELIGIBLE")
  r=next_action({**base,"finmind_free_approved_evidence":sorted(REQUIRED)})
  self.assertEqual(r["action"],"FINMIND_FREE_GAP_DOWNLOAD")
  self.assertTrue(r["must_store_separate_provenance"])
  self.assertFalse(r["accepted"])
 def test_count_invalid(self):
  self.assertEqual(next_action({"official_attempts_total":4})["action"],"BLOCKED")
 def test_policy_is_fail_closed(self):
  self.assertFalse(POLICY["production_activation"])
  self.assertFalse(POLICY["finmind_free"]["never_auto_replace_official"] is False)
if __name__=="__main__":unittest.main()
