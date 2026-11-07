import tempfile,unittest,json
from pathlib import Path
from scripts.v095_r6_merged_acceptance import assess
class R6FailClosedTests(unittest.TestCase):
 def test_no_files_never_permits_bulk(self):
  with tempfile.TemporaryDirectory() as d:
   report=assess(Path(d))
   self.assertFalse(report["production_bulk_ready"])
   self.assertIn("FORMULA_PIT_RELEASE",report["blockers"])
 def test_missing_release_flags_is_unsafe(self):
  with tempfile.TemporaryDirectory() as d:
   report=assess(Path(d))
   self.assertEqual("UNSAFE_RELEASE_CONFIGURATION",report["operational_status"])
 def test_good_candidate_evidence_never_promotes_to_pit(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/"governance/v095").mkdir(parents=True)
   (root/"governance/v095/PHASE1_FLAGS.json").write_text(json.dumps({"BULK_COPY_APPROVED":False,"RELEASE_APPROVED":False}))
   (root/"ultimate_r1").mkdir()
   good={f"{market}_{day}":{"bronze_id":"a","silver_id":"b","gold_id":"c","sha256":"1"*64}
         for market in ("TWSE","TPEx") for day in ("2026-11-02","2026-11-03","2026-11-06")}
   (root/"ultimate_r1/november_latest_bsg.json").write_text(json.dumps({"completed":good,"rejected":{},"pit_verified":False}))
   report=assess(root)
   status={x["id"]:x["state"] for x in report["stages"]}
   self.assertEqual(status["NOV_202611_SIX_DATES"],"PASS_SNAPSHOT_CANDIDATE_NOT_PIT")
   self.assertFalse(report["production_bulk_ready"])
   self.assertEqual(status["FORMULA_PIT_RELEASE"],"BLOCKED")
if __name__=="__main__":unittest.main()
