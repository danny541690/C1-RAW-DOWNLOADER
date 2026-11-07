import importlib.util,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("source_smoke",Path(__file__).resolve().parent/"v095_r17_live_source_smoke.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class R17TWSEBoundary(unittest.TestCase):
 def test_timeout_then_same_endpoint_recovers(self):
  bad={"status":"BLOCKED","reason":"TimeoutError","http_code":None}
  good={"status":"PASS","reason":"VALID_DATA_RESPONSE","http_code":200}
  with patch.object(mod,"check_one_once",side_effect=[bad,good]) as get,patch.object(mod.time,"sleep"):
   r=mod.check_one("TWSE","https://example.test/immutable-actual-route","DATA_JSON")
  self.assertEqual(r["attempts"],2)
  self.assertEqual(get.call_count,2)
  self.assertEqual(get.call_args.args[1],"https://example.test/immutable-actual-route")
 def test_schema_error_not_retried(self):
  bad={"status":"BLOCKED","reason":"EMPTY_OR_UNEXPECTED_SCHEMA","http_code":200}
  with patch.object(mod,"check_one_once",return_value=bad) as get:
   r=mod.check_one("TWSE","https://example.test/same","DATA_JSON")
  self.assertEqual(r["attempts"],1)
  self.assertEqual(get.call_count,1)
 def test_three_transient_failures_stay_blocked(self):
  bad={"status":"BLOCKED","reason":"TimeoutError","http_code":None}
  with patch.object(mod,"check_one_once",return_value=bad) as get,patch.object(mod.time,"sleep"):
   r=mod.check_one("TWSE","https://example.test/same","DATA_JSON")
  self.assertEqual(r["attempts"],3)
  self.assertEqual(r["status"],"BLOCKED")
  self.assertEqual(get.call_count,3)
 def test_other_sources_one_attempt(self):
  bad={"status":"BLOCKED","reason":"TimeoutError","http_code":None}
  with patch.object(mod,"check_one_once",return_value=bad) as get:
   r=mod.check_one("TPEx","https://example.test/same","DATA_JSON")
  self.assertEqual(r["attempts"],1)
  self.assertEqual(get.call_count,1)
if __name__=="__main__":unittest.main()
