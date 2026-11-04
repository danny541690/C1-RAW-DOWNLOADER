"""R15 source-configuration release audit. Read-only, fail closed.
Run only in isolated PR; do not modify v093 campaign or schedule.
"""
import json
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[1]
class ConfigurationAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.active=json.loads((REPO/"config"/"v093_source_release.json").read_text())
        cls.design=json.loads((REPO/"config"/"v093_seven_source_design.json").read_text())
    def test_01_active_legacy_separate_from_new_design(self):
        self.assertTrue(self.active["enabled"])
        self.assertFalse(self.design["activate_production"])
    def test_02_production_gate_fails_closed_for_new_design(self):
        self.assertFalse(self.design.get("activate_production",False))
        self.assertFalse(self.design.get("legacy_import_allowed",True))
    def test_03_immutable_raw_and_tse_otc(self):
        self.assertTrue(self.design["raw_immutable"])
        self.assertEqual(self.design["analysis_markets"],["TSE","OTC"])
    def test_04_release_commit_provenance_exists(self):
        self.assertTrue(self.active["catalogs"])
        self.assertEqual(len(self.active["tested_code_sha256"]),64)
        for source,dirs in self.active["catalogs"].items():
            self.assertTrue(dirs,source)
            for direction,part in dirs.items():
                self.assertEqual(len(part["index_sha256"]),64)
                self.assertEqual(len(part["commit"]),40)
    def test_05_finmind_is_gap_not_primary(self):
        lanes=self.design["lanes"]
        self.assertEqual(len(lanes),7)
        finmind=[x for x in lanes if x["source"]=="FinMind"]
        self.assertEqual(len(finmind),1)
        self.assertTrue(any("GAP" in blocker for blocker in finmind[0]["readiness_blockers"]))
    def test_06_design_lanes_have_unresolved_blockers(self):
        self.assertTrue(all(len(x["readiness_blockers"])>0 for x in self.design["lanes"]))
        self.assertFalse(self.design["activate_production"])
    def test_07_retry_budget_persists_after_restart(self):
        self.assertEqual(self.design["attempts"]["max_total"],4)
        self.assertFalse(self.design["attempts"]["reset_on_restart"])
        self.assertTrue(self.design["attempts"]["respect_retry_after"])
    def test_08_interleaved_new_history_repair_capacity(self):
        shares=self.design["capacity_shares"]
        self.assertAlmostEqual(sum(shares[k] for k in ("new_updates","historical_desc","due_repairs")),1)
    def test_09_release_is_not_equivalent_to_full_coverage(self):
        self.assertEqual(self.active["candidate_scope"],"FROZEN_ADMITTED_NATIVE_CAMPAIGN_ONLY")
        self.assertTrue(self.active["missing_download_authority"])
    def test_10_all_names_unique_for_7_sources(self):
        names=[x["source"] for x in self.design["lanes"]]
        self.assertEqual(len(names),len(set(names)))
if __name__=="__main__":
    unittest.main(verbosity=2)
