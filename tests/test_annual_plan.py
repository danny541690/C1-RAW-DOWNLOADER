import unittest
from datetime import datetime, timezone
from scripts.annual_plan import build_plan

class AnnualPlanTest(unittest.TestCase):
    def test_plan_has_48_blocked_units(self):
        d = build_plan(2023)
        self.assertEqual(len(d["units"]), 48)
        self.assertEqual(d["expected_units"], 48)
        self.assertEqual(d["completed_units"], 0)
        self.assertEqual(d["verified_units"], 0)
        self.assertFalse(d["data_verified"])
        self.assertFalse(d["google_drive_uploaded"])
        self.assertEqual(d["run_mode"], "PLAN_ONLY_NO_DOWNLOAD")
        self.assertTrue(all(x["status"] == "BLOCKED_UNIMPLEMENTED" for x in d["units"]))
        self.assertTrue(all(x["request_count"] == 0 for x in d["units"]))

    def test_unique_month_and_source_pairs(self):
        d = build_plan(2023)
        keys = [(u["year"], u["month"], u["source"]) for u in d["units"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sorted({u["month"] for u in d["units"]}), [f"{m:02d}" for m in range(1, 13)])

    def test_invalid_years_fail_closed(self):
        for y in (1989, datetime.now(timezone.utc).year + 1):
            with self.assertRaises(ValueError):
                build_plan(y)

    def test_four_named_sources_and_capture_remains_blocked(self):
        d = build_plan(2023)
        self.assertIn("MOPS", d["sources"])
        self.assertEqual(set(d["sources"]), {"TWSE", "TPEx", "FinMind", "MOPS"})
        self.assertTrue(any("Google Drive" in b for b in d["blockers"]))

if __name__ == "__main__":
    unittest.main()
