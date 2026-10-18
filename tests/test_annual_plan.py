import unittest
from scripts.annual_plan import build_plan

class AnnualPlanTest(unittest.TestCase):
    def test_plan_has_48_blocked_units(self):
        d = build_plan(2023)
        self.assertEqual(len(d["units"]), 48)
        self.assertEqual(d["verified_units"], 0)
        self.assertFalse(d["data_verified"])
        self.assertTrue(all(x["status"] == "BLOCKED_UNIMPLEMENTED" for x in d["units"]))

if __name__ == "__main__":
    unittest.main()
