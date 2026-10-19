import hashlib
import unittest
from scripts.v093_layer02_governance import (
 digest_bytes,transformation_key,classify_input,compare_candidates,
 dirty_trade_days,gate_release,plan_pointer_change,GateBlocked,REQUIRED_QA
)
class GovernanceTests(unittest.TestCase):
 def setUp(self):
  self.sha=digest_bytes(b"historical raw bytes")
  self.input={"source":"TWSE","dataset":"quotes","raw_sha256":self.sha,"adapter_version":"r2"}
 def test_sha_idempotence(self):
  self.assertEqual(digest_bytes(b"abc"),hashlib.sha256(b"abc").hexdigest())
  self.assertEqual(classify_input(self.input,self.input),"SKIP_VERIFIED_INPUT")
  self.assertEqual(transformation_key(**self.input),transformation_key(**self.input))
 def test_new_source_and_revision(self):
  new={**self.input,"source":"FinMind"}
  self.assertEqual(classify_input(self.input,new),"NEW_INPUT")
  amended={**self.input,"raw_sha256":digest_bytes(b"corrected")}
  self.assertEqual(classify_input(self.input,amended),"NEW_RAW_VERSION")
  self.assertEqual(classify_input(self.input,{**self.input,"adapter_version":"r3"}),"ADAPTER_REBUILD")
 def test_block_undocumented_pit(self):
  r={"source":"TWSE","value":100.0,"stock_id":"2330","period":"2025-01-02","field":"close",
    "unit":"NTD/share","definition_version":"raw","as_of_mode":"AS_KNOWN",
    **{k:True for k in ("schema_ok","unit_ok","date_ok","pit_ok","numeric_ok","universe_ok")}}
  self.assertEqual(compare_candidates([r],approved_sources=["TWSE"])["status"],"CANDIDATE_COMPATIBLE")
  self.assertEqual(compare_candidates([{**r,"pit_ok":False}],approved_sources=["TWSE"])["status"],"BLOCKED")
 def test_conflict_never_average(self):
  r={"source":"TWSE","value":100.0,"stock_id":"2330","period":"2025-01-02","field":"close",
    "unit":"NTD/share","definition_version":"raw","as_of_mode":"AS_KNOWN",
    **{k:True for k in ("schema_ok","unit_ok","date_ok","pit_ok","numeric_ok","universe_ok")}}
  ans=compare_candidates([r,{**r,"source":"FinMind","value":101.0}],approved_sources=["TWSE","FinMind"])
  self.assertEqual(ans["status"],"CONFLICT_VALUE")
  self.assertIsNone(ans["chosen"])
 def test_revision_affects_forward_windows(self):
  q=dirty_trade_days("2025-01-02",[5,20,240])
  self.assertEqual(q["required_forward_trading_sessions"],239)
  self.assertEqual(q["status"],"DIRTY_REQUIRES_TRADING_CALENDAR")
 def test_staging_cannot_publish(self):
  manifest={"kind":"STAGING_UNMAPPED","qa":{k:True for k in REQUIRED_QA},
    "generation_id":"new","parquet_sha256":self.sha,"input_digests":[self.sha]}
  with self.assertRaises(GateBlocked):gate_release(manifest)
  with self.assertRaises(GateBlocked):plan_pointer_change("old","bad",{**manifest,"kind":"APPROVED_STANDARD"})
  self.assertTrue(gate_release({**manifest,"kind":"APPROVED_STANDARD"}))
  p=plan_pointer_change("old","old",{**manifest,"kind":"APPROVED_STANDARD"})
  self.assertEqual(p["action"],"CAS_PLAN_ONLY_NOT_COMMITTED")
 def test_missing_gate_is_blocked(self):
  manifest={"kind":"APPROVED_STANDARD","qa":{"sha_readback":True},
    "generation_id":"ok","parquet_sha256":self.sha,"input_digests":[self.sha]}
  with self.assertRaises(GateBlocked):gate_release(manifest)
if __name__=="__main__":unittest.main()
