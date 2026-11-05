import unittest
from scripts.v095_bronze_release_gate_98 import POLICY,admit
def base(**kwargs):
 d=dict(expected_due_units=100,valid_download_units=98,records_inspected=100,valid_records=98,
        inspectable_expected_records=100,contract_approved=True,calendar_approved=True,
        content_audit_method="EXHAUSTIVE",unisolated_critical_errors=0,
        admitted_bad_sha_count=0,admitted_bad_crc_count=0)
 d.update(kwargs);return d
class Bronze98GateTests(unittest.TestCase):
 def test_policy(self):
  self.assertEqual(POLICY["default_thresholds"]["expected_unit_coverage_min"],.98)
  self.assertEqual(POLICY["default_thresholds"]["valid_content_rate_min"],.98)
 def test_exactly_98_pass(self):self.assertEqual(admit(base())["status"],"PASS_98")
 def test_one_under_fails(self):self.assertEqual(admit(base(valid_download_units=97))["status"],"PARTIAL")
 def test_correctness_97_fails(self):self.assertEqual(admit(base(valid_records=97))["status"],"PARTIAL")
 def test_99_good_but_bad_sha_blocks(self):self.assertEqual(admit(base(valid_download_units=99,valid_records=99,admitted_bad_sha_count=1))["status"],"QUARANTINE")
 def test_99_good_but_bad_crc_blocks(self):self.assertEqual(admit(base(valid_download_units=99,valid_records=99,admitted_bad_crc_count=1))["status"],"QUARANTINE")
 def test_critical_id_problem_blocks(self):self.assertEqual(admit(base(unisolated_critical_errors=1))["status"],"QUARANTINE")
 def test_missing_entire_market_day(self):self.assertEqual(admit(base(whole_required_market_day_missing=True))["status"],"PARTIAL")
 def test_pit_problem_scoped_block(self):self.assertEqual(admit(base(pit_sensitive=True,pit_proven=False))["status"],"PARTIAL")
 def test_unknown_denominator_never_100(self):self.assertEqual(admit(base(expected_due_units=0))["status"],"UNKNOWN")
 def test_normal_holiday_not_due(self):self.assertEqual(admit(base(expected_due_units=0,source_not_due_proven=True))["status"],"NOT_DUE")
 def test_unapproved_contract_not_pass(self):self.assertEqual(admit(base(contract_approved=False))["status"],"UNKNOWN")
 def test_unapproved_calendar_not_pass(self):self.assertEqual(admit(base(calendar_approved=False))["status"],"UNKNOWN")
 def test_invalid_numerator(self):self.assertEqual(admit(base(valid_download_units=101))["status"],"UNKNOWN")
 def test_empty_content_denominator(self):self.assertEqual(admit(base(records_inspected=0))["status"],"UNKNOWN")
 def test_one_row_sample_not_sufficient(self):
  self.assertEqual(admit(base(records_inspected=1,valid_records=1,content_audit_method="SPOT_CHECK"))["status"],"UNKNOWN")
 def test_exhaustive_must_match_population(self):
  self.assertEqual(admit(base(records_inspected=1,valid_records=1))["status"],"UNKNOWN")
 def test_sample_plan_required(self):
  self.assertEqual(admit(base(content_audit_method="APPROVED_SAMPLE"))["status"],"UNKNOWN")
  self.assertEqual(admit(base(content_audit_method="APPROVED_SAMPLE",sampling_plan_approved=True))["status"],"PASS_98")
 def test_disabled_dataset_does_not_block_other(self):self.assertEqual(admit(base())["status"],"PASS_98")
if __name__=="__main__":unittest.main()
