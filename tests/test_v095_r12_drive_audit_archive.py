import hashlib,json,unittest
from scripts.v095_r12_drive_audit_archive import canonical_bytes
class DriveAuditArchiveFixture(unittest.TestCase):
 def test_minimal_safe_non_market_audit_payload(self):
  deep={"scan_status":"PASS_BOUNDED_TRAVERSAL_NOT_COMPLETE_SOURCE_CONTRACT",
    "objects_examined":551,"stage_counts":{"BRONZE":271,"SILVER":143,"GOLD":63,"STAGING":74},
    "source_data_downloads":0,"drive_writes":0,"open_root_issues":["P0-01"]}
  gov={"manifest_data_rows":0,"checkpoint_data_rows":0,"source_registry_rows":8,
       "dataset_contract_rows":39,"production_ready_dataset_contracts":0}
  a=canonical_bytes(42,deep,gov)
  self.assertEqual(a,canonical_bytes(42,deep,gov))
  self.assertEqual(json.loads(a)["release_approved"],False)
  self.assertNotIn(b"drive_file_id",a)
  self.assertNotIn(b"private_parent_id",a)
  self.assertEqual(len(hashlib.sha256(a).hexdigest()),64)
 def test_market_data_activity_would_block_archive(self):
  deep={"scan_status":"PASS","objects_examined":0,"stage_counts":{},
    "source_data_downloads":1,"drive_writes":0,"open_root_issues":[]}
  gov={"manifest_data_rows":0,"checkpoint_data_rows":0,"source_registry_rows":8,
    "dataset_contract_rows":39,"production_ready_dataset_contracts":0}
  with self.assertRaises(AssertionError):canonical_bytes(42,deep,gov)
if __name__=="__main__":unittest.main()
