import tempfile,unittest
from pathlib import Path
from scripts.v093_acceptance_dependencies import dependency_manifest,checker_signatures,cache_token,SOURCE_MODULES
class DependencyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'scripts').mkdir()
  names={x for v in SOURCE_MODULES.values() for x in v}|{'v093_prelaunch_acceptance_batch','v093_acceptance_dependencies'}
  for name in names:(self.root/'scripts'/(name+'.py')).write_text('X=1\n')
  (self.root/'requirements-qa.lock').write_text('fake==1\n')
 def test_unrelated_script_does_not_invalidate(self):
  first=checker_signatures(self.root);(self.root/'scripts/unrelated.py').write_text('X=99\n');self.assertEqual(first,checker_signatures(self.root))
 def test_mops_adapter_change_keeps_finmind_cache(self):
  first=checker_signatures(self.root);(self.root/'scripts/v093_stage06_financial_repair.py').write_text('X=2\n');second=checker_signatures(self.root);self.assertNotEqual(first['MOPS'],second['MOPS']);self.assertEqual(first['FinMind'],second['FinMind'])
 def test_transitive_import_change_invalidates(self):
  (self.root/'scripts/v093_stage06_financial_repair.py').write_text('from scripts import child\n');(self.root/'scripts/child.py').write_text('X=1\n');a=checker_signatures(self.root);(self.root/'scripts/child.py').write_text('X=2\n');self.assertNotEqual(a['MOPS'],checker_signatures(self.root)['MOPS'])
 def test_dependency_missing_fails_closed(self):
  (self.root/'scripts/v093_stage06_financial_repair.py').write_text('from scripts.missing import x\n')
  with self.assertRaisesRegex(ValueError,'CHECKER_DEPENDENCY_MISSING'):checker_signatures(self.root)
 def test_requirements_change_invalidates_all_sources(self):
  first=checker_signatures(self.root);(self.root/'requirements-qa.lock').write_text('fake==2\n');second=checker_signatures(self.root);self.assertTrue(all(first[k]!=second[k] for k in first))
 def test_task_scope_change_invalidates(self):
  r={'來源':'FinMind','代碼':'1269','月份':'2026-09','預期代碼':'[]'};a=cache_token(r,'a','b','c',{});r['預期代碼']='["2330"]';self.assertNotEqual(a,cache_token(r,'a','b','c',{}))
 def test_esb_evidence_scoped_by_code_month_and_source(self):
  r={'來源':'FinMind','代碼':'1269','月份':'2026-09'};a=cache_token(r,'a','b','c',{});e={('2026-09-01','1271'):{'proof':1}};self.assertEqual(a,cache_token(r,'a','b','c',e));e[('2026-09-01','1269')]={'proof':1};self.assertNotEqual(a,cache_token(r,'a','b','c',e))
