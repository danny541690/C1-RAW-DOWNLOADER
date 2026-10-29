import copy,unittest
from scripts.v093_handoff_overlays import apply_task
class OverlayTests(unittest.TestCase):
 def data(self):
  key='TDCC|2025-12|20251205|8401';period='2025-12-05'
  item=dict(source='TDCC',task_key=key,attempts=1,action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE',provenance=[dict(source='TDCC',period=period,status='UNRESOLVED')])
  task=dict(definition=dict(source='TDCC',key=key,period=period),status='RAW_BASIC_VERIFIED',attempts=2,raw_reference='verified',raw_sha256='a'*64,save_intent=dict(sha256='a'*64))
  return key,{'TDCC':{key:item}},task
 def test_verified_missing_promotes_to_retained_and_keeps_old_provenance(self):
  key,reviews,task=self.data();old=copy.deepcopy(reviews['TDCC'][key]);case=apply_task(reviews,'TDCC',key,task,{'commit':'b'*40})
  self.assertEqual(case['mode'],'RETAINED');self.assertEqual(reviews['TDCC'][key]['attempts'],2);self.assertEqual(reviews['TDCC'][key]['provenance'][0],old['provenance'][0]);self.assertEqual(case['code'],'8401')
 def test_held_outcome_cannot_become_missing_or_retained_authority(self):
  key,reviews,task=self.data();task.update(status='APPLICABILITY_HOLD');case=apply_task(reviews,'TDCC',key,task,{})
  self.assertIsNone(case);self.assertEqual(reviews['TDCC'][key]['action'],'LATER_QA_APPLICABILITY_HOLD');self.assertEqual(reviews['TDCC'][key]['attempts'],2)
 def test_attempt_regression_and_unknown_fixture_keys_are_rejected(self):
  key,reviews,task=self.data();task['attempts']=0
  with self.assertRaisesRegex(ValueError,'ATTEMPTS'):apply_task(reviews,'TDCC',key,task,{})
  with self.assertRaisesRegex(ValueError,'SCOPE'):apply_task(reviews,'TDCC','fixture',task,{})
 def test_verified_flag_cannot_resolve_period_or_content_dispute(self):
  for conflict in ('period','sha'):
   key,reviews,task=self.data()
   if conflict=='period':reviews['TDCC'][key]['provenance'][0]['period']='2025-11-01'
   else:reviews['TDCC'][key]['provenance'][0].update(raw_reference='old',sha256='c'*64)
   with self.assertRaises(ValueError):apply_task(reviews,'TDCC',key,task,{})

class EmptyClassificationTests(unittest.TestCase):
 def test_known_empty_does_not_become_confirmed_historical_absence(self):
  from scripts.v093_source_adapters import unconfirmed_empty
  self.assertTrue(unconfirmed_empty('TWSE',ValueError('SOURCE_STATUS:很抱歉，沒有符合條件的資料!')))
  self.assertTrue(unconfirmed_empty('TPEx',ValueError('EMPTY_RESPONSE_NOT_COVERAGE')))
 def test_throttle_malformed_and_wrong_date_are_not_relabelled_empty(self):
  from scripts.v093_source_adapters import unconfirmed_empty
  for code in ('SOURCE_STATUS:too many requests','ROW_FIELD_WIDTH_MISMATCH','RESPONSE_DATE_MISMATCH:2000-01-01'):
   self.assertFalse(unconfirmed_empty('TWSE',ValueError(code)))

class RecoveryWorkflowTests(unittest.TestCase):
 def test_recovery_yaml_reuses_ten_passed_slots_and_runs_only_two_sources(self):
  import yaml
  from pathlib import Path
  d=yaml.load(Path('.github/workflows/jarvis-seven-oldest-side-recovery.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertEqual(d['jobs']['slots']['strategy']['matrix']['source'],['TWSE','TPEx'])
  self.assertIn('40968961523',Path('.github/workflows/jarvis-seven-oldest-side-recovery.yml').read_text())
