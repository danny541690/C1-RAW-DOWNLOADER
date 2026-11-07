import hashlib,unittest
from scripts.v095_r13_single_committer_contract import Revision,claim,commit,FencingError,InvalidEvidence,asof_allowed,simulate
class R13Fencing(unittest.TestCase):
 def test_all_probes_classified(self):
  self.assertEqual(simulate()["status"],"PASS_IN_MEMORY_MODEL_ONLY")
  self.assertFalse(simulate()["actual_github_cas_verified"])
 def test_competing_runner_rejected(self):
  state=claim(Revision(),0,"A",1)
  with self.assertRaises(FencingError):claim(state,0,"B",2)
 def test_preexpired_fence_does_not_claim(self):
  with self.assertRaises(FencingError):claim(Revision(fencing_epoch=7),0,"A",7)
 def test_replay_and_owner_rejected(self):
  state=claim(Revision(),0,"A",1)
  raw=b"raw";sha=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(FencingError):commit(state,1,"B",1,raw,sha,sha)
  done=commit(state,1,"A",1,raw,sha,sha)
  with self.assertRaises(FencingError):claim(done,2,"B",2)
 def test_corrupt_remote_readback_rejected(self):
  state=claim(Revision(),0,"A",1);raw=b"native";sha=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(InvalidEvidence):commit(state,1,"A",1,raw,sha,"0"*64)
 def test_future_and_revision_leaks_rejected(self):
  self.assertFalse(asof_allowed("2026-11-08T00:00:00Z","2026-11-07T00:00:00Z"))
  self.assertFalse(asof_allowed("2026-11-01T00:00:00Z","2026-11-07T00:00:00Z","2026-11-08T00:00:00Z"))
  self.assertFalse(asof_allowed("2026-11-01","2026-11-07T00:00:00Z"))
if __name__=="__main__":unittest.main()
