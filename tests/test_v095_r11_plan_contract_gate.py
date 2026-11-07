import copy,json,unittest
from pathlib import Path
from scripts.v095_r11_plan_contract_gate import evaluate,ROOT,PLAN,FLAGS,R2,R7
class R11ArchitectureGate(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=[json.loads(x.read_text()) for x in (PLAN,FLAGS,R2,R7)]
 def assess(self,modify=None):
  data=copy.deepcopy(self.base)
  if modify:modify(data)
  return evaluate(*data)
 def test_actual_plan_is_safe_and_five_phases(self):
  x=self.assess()
  self.assertEqual(x["status"],"PASS_NO_NETWORK_PILOT_SPEC")
  self.assertEqual(x["issues"],12)
  self.assertEqual(x["pilot_phases"],5)
  self.assertFalse(x["bulk_history_download_started"])
 def test_16_logical_slots_cannot_be_confused_with_14_qa_lanes(self):
  x=self.assess(lambda d:d[0]["architecture"].update(logical_ingest_slots=14))
  self.assertIn("R11_CONTROLLER_SLOT_TOPOLOGY",x["errors"])
  self.assertIn("R11_INGEST_VS_QA_CONFUSION",x["errors"])
 def test_forged_release_flag_fails_closed(self):
  x=self.assess(lambda d:d[1].update(BULK_COPY_APPROVED=True))
  self.assertIn("R11_UNSAFE_EXISTING_RELEASE",x["errors"])
 def test_no_historical_pit_promotion(self):
  x=self.assess(lambda d:d[0]["architecture"]["release_layers"].update(gold="SHARED_BRONZE_ONLY"))
  self.assertIn("R11_GOLD_PIT_NOT_GATED",x["errors"])
 def test_missing_scoped_sha_receipt_cannot_be_accepted(self):
  x=self.assess(lambda d:d[3]["immutable_receipts"][0].pop("content_sha256"))
  self.assertIn("R11_ACCEPTANCE_SHA_PROVENANCE",x["errors"])
 def test_unbounded_pilot_rejected(self):
  x=self.assess(lambda d:d[0]["trial_plan"][-1].update(units=2000))
  self.assertIn("R11_UNBOUNDED_CANARY",x["errors"])
 def test_unknown_denominator_is_never_zero_or_one(self):
  x=self.assess(lambda d:d[0]["rules"].update(unknown_denominator="100_PERCENT"))
  self.assertIn("R11_UNKNOWN_COVERAGE_MISSTATED",x["errors"])
 def test_duplicate_issue_id_cannot_hide_risk(self):
  x=self.assess(lambda d:d[0]["issues"][1].update(id=d[0]["issues"][0]["id"]))
  self.assertIn("R11_ISSUE_ID_DUPLICATION",x["errors"])
if __name__=="__main__":unittest.main()
