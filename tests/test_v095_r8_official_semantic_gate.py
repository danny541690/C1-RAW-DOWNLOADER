import unittest
from scripts.v095_r8_official_semantic_gate import adjudicate
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config/v095_r8_official_source_semantics_20261107.json").read_text())
R=json.loads((ROOT/"governance/v095/202609_11_R7_ACCEPTED_CANDIDATE_RECEIPTS.json").read_text())
F=json.loads((ROOT/"governance/v095/PHASE1_FLAGS.json").read_text())
class OfficialSemantics(unittest.TestCase):
 def test_existing_rules_are_consistent_but_bulk_not_authorized(self):
  x=adjudicate(CFG,R,F)
  self.assertEqual(x["status"],"PASS_RULE_CONTRACT_NOT_DATA_RELEASE")
  self.assertFalse(x["bronze_bulk_download_enabled"])
  self.assertFalse(x["gold_research_release_enabled"])
 def test_tdcc_wrong_denominator_fails(self):
  c=json.loads(json.dumps(CFG));c["normalization"]["TDCC"]["share_percent_denominator"]="ISSUED_SHARES"
  self.assertIn("INVALID_TDCC_DENOMINATOR",adjudicate(c,R,F)["errors"])
 def test_outdated_tpex_bulk_history_fails(self):
  c=json.loads(json.dumps(CFG));c["source_documents"][0]["first_documented_month"]="2000-01"
  self.assertIn("INVALID_TPEX_BULK_EARLIEST",adjudicate(c,R,F)["errors"])
 def test_unknown_ohlc_not_zero(self):
  c=json.loads(json.dumps(CFG));c["normalization"]["TPEX"]["price_null_not_zero"]=False
  self.assertIn("TPEX_ZERO_OR_SUSPENSION_FABRICATION",adjudicate(c,R,F)["errors"])
 def test_release_must_remain_locked(self):
  f={**F,"BULK_COPY_APPROVED":True}
  self.assertIn("UNSAFE_EXISTING_RELEASE_FLAGS",adjudicate(CFG,R,f)["errors"])
if __name__=="__main__":unittest.main()
