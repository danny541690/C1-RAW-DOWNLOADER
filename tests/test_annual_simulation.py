import tempfile
import unittest
from scripts.annual_simulation import simulate

class AnnualSimulationTest(unittest.TestCase):
    def test_twelve_months_and_deferred_repairs(self):
        with tempfile.TemporaryDirectory() as root:
            a=simulate(2024,root)
            self.assertEqual(a["months_processed"],12)
            self.assertEqual(a["saved_units"],46)
            self.assertEqual(a["missing_units"],2)
            self.assertEqual(a["source_requests"],51)
            q={(x["month"],x["source"],x["status"],x["attempts"]) for x in a["deferred_repair_queue"]}
            self.assertEqual(q,{(3,"TPEx","FAILED_RETRY_LIMIT",4),
                                (7,"MOPS","SOURCE_HOLD",1)})
            b=simulate(2024,root)
            self.assertEqual(b["source_requests"],0)
            self.assertEqual(b["saved_units"],46)
