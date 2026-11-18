"""Full frozen-cohort arithmetic and failure replay; synthetic only."""
import unittest
from scripts.v097_r3_gate_core import SOURCES, COHORT, reconcile
COUNTS={"TWSE":12071,"TPEx":13200,"MOPS":1935,"TDCC":40384,"TAIFEX":3140,"NDC":320,"FinMind":3700}

class R3FrozenCohortTests(unittest.TestCase):
    def test_full_74750_distribution_and_terminal(self):
        self.assertEqual(sum(COUNTS.values()),COHORT)
        records=[]
        for src,n in COUNTS.items():
            for j in range(n):
                state="SILVER_READY" if j%13 else "HOLD"
                records.append({"record_id":f"{src}:{j}","source":src,"status":state})
        result=reconcile(records)
        self.assertEqual(result["count"],74750)
        self.assertEqual(result["sources"],COUNTS)
        self.assertTrue(result["complete"])
        self.assertEqual(result["states"]["SILVER_READY"]+result["states"]["HOLD"],COHORT)
        missing=records[:-1]
        self.assertFalse(reconcile(missing)["complete"])
    def test_no_inflated_progress_from_partial_results(self):
        rows=[{"record_id":f"R:{i}","source":"TWSE","status":"PENDING" if i%2 else "HOLD"} for i in range(100)]
        self.assertFalse(reconcile(rows)["complete"])
        with self.assertRaises(ValueError):
            reconcile(rows+[{"record_id":"R:0","source":"TWSE","status":"SILVER_READY"}])
    def test_invalid_status_prevents_reconciliation(self):
        with self.assertRaises(ValueError):
            reconcile([{"record_id":"x","source":"TWSE","status":"PASS"}])
if __name__=="__main__":
    unittest.main()
