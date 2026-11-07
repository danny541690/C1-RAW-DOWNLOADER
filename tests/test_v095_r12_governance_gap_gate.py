import csv,json,tempfile,unittest
from pathlib import Path
from scripts.v095_r12_production_governance_gap_gate import assess,ROOT
class ActualGovernanceGate(unittest.TestCase):
 def test_main_repo_does_not_pretend_bulk_ready(self):
  x=assess(ROOT)
  self.assertFalse(x["production_backfill_ready"])
  self.assertEqual(x["source_download_tasks_released"],0)
 def test_empty_header_only_is_no_checkpoint(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/"governance/v095").mkdir(parents=True)
   for name in ("MANIFEST_INDEX.csv","CHECKPOINTS.csv","SOURCE_REGISTRY.csv","DATASET_CONTRACTS.csv"):
    (root/"governance/v095"/name).write_text("a,b\n")
   (root/"governance/v095/PHASE1_FLAGS.json").write_text(
    json.dumps({"BULK_COPY_APPROVED":False,"RELEASE_APPROVED":False}))
   r=assess(root)
   self.assertEqual(r["manifest_data_rows"],0)
   self.assertEqual(r["checkpoint_data_rows"],0)
   self.assertFalse(r["durable_committed_checkpoint_observed"])
   self.assertFalse(r["verified_bronze_manifest_observed"])
 def test_candidate_contracts_do_not_promote_to_ready(self):
  x=assess(ROOT)
  self.assertEqual(x["production_ready_dataset_contracts"],0)
if __name__=="__main__":unittest.main()
