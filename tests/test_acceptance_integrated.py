import csv,gzip,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.v093_acceptance_integrated import aggregate,run,verify_diagnostic
from scripts.v093_prelaunch_acceptance_batch import ArchiveCache,retained_raw,sha
ROOT=Path(__file__).resolve().parent.parent
PLAN=ROOT/'reports/raw-acceptance/20261028_acceleration_plan/execution_plan.json'
class IntegratedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name);self.cache=self.p/'cache';self.cache.mkdir();self.reg=self.p/'reg';self.reg.mkdir();self.plan=json.loads(PLAN.read_text())
 def inputs(self):
  b=json.dumps(dict(status=200,data=[dict(date='2000-01-04',stock_id='1515',open=10,max=12,min=9,close=11)])).encode();(self.cache/'f1').write_bytes(b)
  r={'來源':'FinMind','單元ID':'u1','原件參照':'f1','已下載':'1','資料集':'TaiwanStockPrice','期間':'2000-01','月份':'2000-01','年份':'2000','RAW_SHA256':sha(b),'代碼':'1515'}
  with gzip.open(self.reg/'FinMind_units.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=r);w.writeheader();w.writerow(r)
 def test_complete_entrypoint_cannot_promote_partial_raw_to_release(self):
  self.inputs();r=run(self.reg,self.cache,self.p/'out',PLAN);self.assertEqual(r['completed_groups'],0);self.assertEqual(r['formal_release'],'BLOCKED');self.assertEqual(len(r['rules']),37);self.assertEqual(r['rule_counts'],{'UNKNOWN':37});self.assertEqual(r['recovery']['units_verified'],1);self.assertEqual(r['production_writes'],0);self.assertTrue((self.p/'out/repair_queue.csv.gz').is_file())
 def test_forged_plan_group_passes_not_trusted(self):
  for g in self.plan['groups']:g['status']='PASS'
  r=aggregate(self.plan,{'counts':{}},[]);self.assertEqual(r['completed_groups'],0);self.assertFalse(any(g['complete'] for g in r['groups']))
 def test_missing_rule_blocks(self):
  self.plan['rule_ownership'].pop()
  with self.assertRaisesRegex(ValueError,'EXACT_37_RULE_OWNERSHIP_REQUIRED'):aggregate(self.plan,{'counts':{}},[])
 def test_duplicate_rule_cannot_replace_missing_rule(self):
  self.plan['rule_ownership'][-1]=self.plan['rule_ownership'][0]
  with self.assertRaisesRegex(ValueError,'EXACT_37_RULE_OWNERSHIP_REQUIRED'):aggregate(self.plan,{'counts':{}},[])
 def test_unknown_diagnostic_cannot_create_partial_r05(self):
  r=aggregate(self.plan,{'counts':{}},[],diagnostic={'result':'INVALIDATED_DIAGNOSTIC'});self.assertEqual(next(g['result'] for g in r['groups'] if g['id']=='R05'),'UNKNOWN')
 def test_repeated_member_extraction_uses_shared_archive_cache(self):
  with zipfile.ZipFile(self.cache/'f','w') as z:z.writestr('x',b'raw')
  a=ArchiveCache();self.assertEqual(retained_raw(self.cache,'f/x',a)[0],b'raw');self.assertEqual(retained_raw(self.cache,'f/x',a)[0],b'raw');self.assertEqual(a.member_extractions,1)
 def test_diagnostic_sha_change_invalidates_import(self):
  with zipfile.ZipFile(self.cache/'f','w') as z:z.writestr('x',b'changed')
  d=self.p/'d.json';d.write_text(json.dumps(dict(inputs=[dict(archive_id='f',member='x',sha256=sha(b'old'))],checks={'open':{'compared_pairs':1}})))
  r=verify_diagnostic(d,self.cache,ArchiveCache());self.assertEqual(r['result'],'INVALIDATED_DIAGNOSTIC');self.assertEqual(r['input_references_checked'],0)
 def test_independent_phase_failure_does_not_stop_rule_report(self):
  self.inputs();bad=self.p/'bad.json';bad.write_text('{}')
  with patch('scripts.v093_acceptance_integrated.recover_readback_scope',side_effect=ValueError('injected failure')):r=run(self.reg,self.cache,self.p/'out',PLAN,diagnostic_file=bad)
  self.assertEqual(r['recovery']['result'],'RECOVERY_ERROR');self.assertEqual(r['diagnostic']['result'],'DIAGNOSTIC_ERROR');self.assertEqual(len(r['rules']),37)
 def test_identical_inputs_reuse_checkpoint(self):
  self.inputs();first=run(self.reg,self.cache,self.p/'out',PLAN)
  second=run(self.reg,self.cache,self.p/'next',PLAN,resume=self.p/'out/content/checkpoint.json');self.assertEqual(second['content_counts']['resumed_content_units'],1)

 def test_native_diagnostic_counter_maps_are_supported(self):
  with zipfile.ZipFile(self.cache/'f','w') as z:z.writestr('x',b'raw')
  d=self.p/'d.json';d.write_text(json.dumps(dict(inputs=[dict(archive_id='f',member='x',sha256=sha(b'raw'))],checks={'open':{'compared_pairs':{'FinMind__TWSE':3,'FinMind__TPEx':2},'mismatch':{}}})))
  r=verify_diagnostic(d,self.cache,ArchiveCache());self.assertEqual(r['reported_field_pairs'],5);self.assertEqual(r['reported_mismatches'],0);self.assertFalse(r['recomputed_numeric_pairs'])
 def test_empty_financial_body_routes_to_source_review(self):
  from scripts.v093_acceptance_integrated import triage_content_failures
  b=b'<div id="bodyTable"><table><thead><tr><th>company</th></tr></thead><tbody></tbody></table></div><input name="yearseason" value="2001Q1"><input name="reportName" value="1101">';(self.cache/'f').write_bytes(b);d=self.p/'content';d.mkdir()
  r=dict(task_key='MOPS|u1',source='MOPS',dataset='BalanceSheet',period='2001-03-31',raw_reference='f',raw_sha256=sha(b),status='CONTENT_BLOCKED',next_action='ACCOUNT_MATRIX_ROW_MISMATCH')
  with gzip.open(d/'next_round.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=r);w.writeheader();w.writerow(r)
  x=triage_content_failures(d,self.cache,ArchiveCache())[0];self.assertEqual(x['diagnosis'],'RETAINED_MOPS_RESPONSE_HAS_NO_ACCOUNT_ROWS');self.assertEqual(x['proposed_queue'],'SOURCE_ROUTE_REVIEW');self.assertFalse(x['raw_changed'])
 def test_wrong_period_empty_body_not_claimed_as_expected_response(self):
  from scripts.v093_acceptance_integrated import triage_content_failures
  b=b'<div id="bodyTable"><table><tbody></tbody></table></div><input name="yearseason" value="2026Q1">';(self.cache/'f').write_bytes(b);d=self.p/'content';d.mkdir()
  r=dict(task_key='MOPS|u1',source='MOPS',dataset='BalanceSheet',period='2001-03-31',raw_reference='f',raw_sha256=sha(b),status='CONTENT_BLOCKED',next_action='mismatch')
  with gzip.open(d/'next_round.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=r);w.writeheader();w.writerow(r)
  x=triage_content_failures(d,self.cache,ArchiveCache())[0];self.assertEqual(x['diagnosis'],'UNRESOLVED_CONTENT_FAILURE')
