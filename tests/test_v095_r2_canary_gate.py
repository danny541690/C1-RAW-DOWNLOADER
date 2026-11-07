import importlib.util
import unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location("r2_canary", Path(__file__).resolve().parents[1] / "scripts/v095_r2_canary_gate.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
class CanaryGateTests(unittest.TestCase):
    def test_realistic_transport_timeout_blocks(self):
        c={k:{"bronze_id":"b","silver_id":"s","gold_id":"g","sha256":"a"*64} for k in gate.EXPECTED if k!="TWSE_2026-11-06"}
        r=gate.evaluate({"completed":c,"rejected":{"TWSE_2026-11-06":"TimeoutError"},"pit_verified":False})
        self.assertEqual("PARTIAL_BLOCKED",r["outcome"])
        self.assertEqual(5,r["passed"])
    def test_missing_date_blocks(self):
        self.assertTrue(any("MISSING:" in x for x in gate.evaluate({"completed":{},"rejected":{}})["errors"]))
    def test_all_six_candidate_not_pit(self):
        c={k:{"bronze_id":"b","silver_id":"s","gold_id":"g","sha256":"a"*64} for k in gate.EXPECTED}
        r=gate.evaluate({"completed":c,"rejected":{},"pit_verified":False})
        self.assertEqual("PASS_CANDIDATE_NOT_PIT",r["outcome"])
        self.assertFalse(r["historical_pit_approved"])
    def test_forged_pit_claim_blocks(self):
        c={k:{"bronze_id":"b","silver_id":"s","gold_id":"g","sha256":"a"*64} for k in gate.EXPECTED}
        self.assertEqual("PARTIAL_BLOCKED",gate.evaluate({"completed":c,"rejected":{},"pit_verified":True})["outcome"])
    def test_absent_manifest_blocks(self):
        self.assertEqual("BLOCKED",gate.evaluate({})["outcome"])
if __name__=="__main__":unittest.main()
