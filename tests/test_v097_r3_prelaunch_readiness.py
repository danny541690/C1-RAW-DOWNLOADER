import tempfile
import unittest
from pathlib import Path
from scripts.v097_r3_prelaunch_readiness import report, REQUIRED

class PrelaunchReleaseTests(unittest.TestCase):
    def test_conflicting_old_writer_blocks_release(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/"v097_old_writer.yml").write_text(
                "name: old\non:\n  schedule:\n    - cron: '* * * * *'\njobs:\n  run:\n    steps:\n      - run: echo checkpoint\n        env:\n          GOOGLE_CLIENT_ID: fake\n",encoding="utf-8")
            result=report(p)
            self.assertEqual(result["production_release"],"BLOCKED")
            self.assertIn("G0_NO_LEGACY_WRITERS",result["blockers"])
            self.assertIn("v097_old_writer.yml",result["legacy_scheduled"])
    def test_no_old_writers_still_requires_real_drive_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            result=report(Path(d))
            self.assertEqual(result["production_release"],"BLOCKED")
            self.assertNotIn("G0_NO_LEGACY_WRITERS",result["blockers"])
            self.assertIn("G5_DRIVE_COMMIT_READBACK",result["blockers"])
    def test_unverified_caller_claim_does_not_release(self):
        with tempfile.TemporaryDirectory() as d:
            result=report(Path(d),{x:True for x in REQUIRED})
            self.assertEqual(result["production_release"],"BLOCKED")
            self.assertGreater(len(result["blockers"]),0)
if __name__=="__main__":unittest.main()
