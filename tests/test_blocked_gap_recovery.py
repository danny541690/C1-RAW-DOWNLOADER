import copy,json,tempfile,unittest
from pathlib import Path
from scripts.v093_blocked_gap_recovery import valid_saved_result,settle_probe,release_saved_probe
from scripts.v093_official_followup import reviewed_mops_route,repair_row,EmptyQueryAdapter
from scripts.v093_source_coordination import Coordinator
from test_source_coordination import SQLiteCAS
from test_problem_recovery import retained

class BlockedGapRecoveryTests(unittest.TestCase):
 def good(self):return dict(status='RAW_BASIC_VERIFIED',raw_reference='raw',raw_sha256='a'*64,storage_receipt=dict(raw_reference='raw',raw_sha256='a'*64,readback_verified=True))
 def state(self):return dict(hold_probe=dict(identity='probe',key='only',previous_hold='HTTPError_403'))
 def test_probe_requires_bound_saved_raw_receipt_to_release_hold(self):
  good=self.good();self.assertTrue(valid_saved_result(good));s=self.state();settle_probe(s,'probe',good);self.assertNotIn('hold',s);self.assertTrue(s['hold_probe_history']['released'])
  for field,value in [('raw_sha256','b'*64),('raw_reference','wrong'),('readback_verified',False)]:
   bad=self.good();bad['storage_receipt'][field]=value;s=self.state();settle_probe(s,'probe',bad);self.assertEqual(s['hold'],'HTTPError_403');self.assertFalse(s['hold_probe_history']['released'])
 def test_failed_or_interrupted_probe_restores_hold(self):
  for result in (None,dict(status='REVIEW_REQUIRED')):
   s=self.state();settle_probe(s,'probe',result);self.assertEqual(s['hold'],'HTTPError_403');self.assertNotIn('hold_probe',s)
 def test_probe_cannot_override_an_unrelated_stricter_hold(self):
  s=self.state();s['hold']='HTTPError_401';settle_probe(s,'probe',self.good());self.assertEqual(s['hold'],'HTTPError_401');self.assertFalse(s['hold_probe_history']['released'])
 def test_probe_lease_cannot_admit_any_other_download(self):
  with tempfile.TemporaryDirectory() as folder:
   c=Coordinator(SQLiteCAS(Path(folder)/'db'),'TPEx');c.add([dict(source='TPEx',key=k,period='2004-11-16',slot='DESC') for k in ('only','other')]);c.update(lambda s:s.update(hold_probe=dict(key='only')))
   t=c.claim('DESC','probe');self.assertEqual(t['key'],'only');c.begin_request(t);self.assertIsNone(c.claim('DESC','other'));self.assertEqual(c.store.read('TPEx')[1]['tasks']['other']['attempts'],0)
 def test_reviewed_mops_route_is_domestic_historical_only(self):
  case=dict(source='MOPS',category='revenue_sii_0',period='2000-05');self.assertEqual(reviewed_mops_route(case),'https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_89_5.html')
  for changed in (dict(category='revenue_sii_1'),dict(source='TPEx'),dict(period='2010-01')):
   with self.assertRaises(ValueError):reviewed_mops_route(dict(case,**changed))
 def test_reviewed_route_preserves_attempts_and_still_uses_native_http(self):
  from unittest.mock import Mock
  task=retained(b'old',source='MOPS',period='2000-05',category='revenue_sii_0');task['execution_contract'].update(mode='MISSING',reference=None,sha256=None)
  row=repair_row(task,dict(attempts=3),dict(kind='REVIEWED_MOPS_HISTORICAL_ROUTE'));self.assertEqual(row['attempts'],3);self.assertFalse(row['local_only'])
  a=object.__new__(EmptyQueryAdapter);a.case=row['execution_contract'];a.http=Mock(return_value=b'raw');self.assertEqual(a.fetch(),b'raw');a.http.assert_called_once_with(reviewed_mops_route(a.case))
 def test_one_shot_targets_are_existing_keys_not_a_new_dataset(self):
  cfg=json.loads(Path('config/v093_blocked_gap_recovery_20261101.json').read_text());self.assertTrue(cfg['one_shot']);self.assertEqual(len(cfg['targets']['TPEx']['keys']),1);self.assertEqual(len(cfg['reviewed_mops_keys_history']),8);self.assertEqual(cfg['targets']['TPEx']['mode'],'PROMOTE_SAVED_PROBE');self.assertEqual(cfg['targets']['MOPS']['keys'],[])
 def test_saved_probe_release_requires_native_state_same_receipt_and_same_bytes(self):
  good=self.good();s=dict(hold='HTTPError_403',hold_probe_history=dict(identity='old',key='key',sent=True),tasks=dict(key=copy.deepcopy(good)))
  self.assertFalse(release_saved_probe(s,'old','key',good,'b'*64));self.assertEqual(s['hold'],'HTTPError_403')
  self.assertTrue(release_saved_probe(s,'old','key',good,'a'*64));self.assertNotIn('hold',s);self.assertTrue(s['hold_probe_history']['release_via_saved_response'])
 def test_saved_probe_without_matching_native_receipt_keeps_hold(self):
  good=self.good();s=dict(hold='HTTPError_403',hold_probe_history=dict(identity='old',key='key',sent=True),tasks=dict(key=dict(status='RAW_BASIC_VERIFIED',raw_sha256='a'*64)))
  self.assertFalse(release_saved_probe(s,'old','key',good,'a'*64));self.assertEqual(s['hold'],'HTTPError_403')
 def test_review_probe_keeps_403_and_spends_at_most_one_budgeted_request(self):
  from scripts.v093_source_rate import reserve
  with tempfile.TemporaryDirectory() as folder:
   c=Coordinator(SQLiteCAS(Path(folder)/'db'),'TPEx');c.add([dict(source='TPEx',key=k,period='2004-11-16',slot='DESC') for k in ('only','other')]);c.update(lambda s:s.update(hold='HTTPError_403',hold_probe=dict(identity='approved',key='only',sent=False)))
   t=c.claim('DESC','probe');self.assertEqual(t['key'],'only');reserve(c,t);c.begin_request(t);s=c.store.read('TPEx')[1];self.assertEqual(s['hold'],'HTTPError_403');self.assertTrue(s['hold_probe']['sent']);self.assertEqual(s['tasks']['only']['attempts'],1);self.assertEqual(len(s['http_budget']['intents']),1)
   self.assertIsNone(c.claim('DESC','other'))

if __name__=='__main__':unittest.main()
