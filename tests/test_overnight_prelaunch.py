import unittest,yaml,json
from pathlib import Path
from scripts.v093_overnight_catalogs import bound_row,receipt_contract
from scripts.v093_source_partition import COUNTS
class OvernightTests(unittest.TestCase):
 def test_controller_exact_twelve_bindings_and_no_cancellation_of_writers(self):
  d=yaml.load(Path('.github/workflows/jarvis-seven-watchdog.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertNotIn('schedule',d['on'])
  active=yaml.load(Path('.github/workflows/jarvis-seven-production-watchdog.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertEqual(active['on']['schedule'][0]['cron'],'3,13,23,33,43,53 * * * *')
  self.assertEqual(active['permissions']['actions'],'write')
  design=json.loads(Path('config/v093_seven_source_design.json').read_text())
  expected={(s,slot) for s,n in COUNTS.items() for slot in (('DESC','ASC') if n==2 else ('DESC',))}
  self.assertEqual({(r['source'],r['direction']) for r in design['slots']},expected)
  self.assertEqual(len(design['slots']),12)
  worker=yaml.load(Path('.github/workflows/jarvis-seven-worker.yml').read_text(),Loader=yaml.BaseLoader)['jobs']['worker']
  self.assertEqual(worker['concurrency']['cancel-in-progress'],'false')
 def test_compiler_rejects_conflicts_and_keeps_exhausted_read_only_attempts(self):
  case=dict(source='TWSE',key='k',period='2026-10-01',reference='ref',sha256='a'*64,category='prices_indices')
  item=dict(source='TWSE',task_key='k',attempts=4,action='VERIFY_RETAINED_RAW_FIRST',provenance=[dict(period=case['period'],raw_reference='ref',sha256='a'*64)])
  row=bound_row('TWSE',item,case,'ASC');self.assertEqual(row['attempts'],4);self.assertEqual(row['status'],'READY_CHECK');self.assertTrue(row['check_only'])
  item['action']='VERSION_CONFLICT_REVIEW'
  with self.assertRaisesRegex(ValueError,'UNREVIEWED'):bound_row('TWSE',item,case,'ASC')
 def test_tdcc_native_key_must_agree_with_date(self):
  row=dict(task_key='k',period='2026-09-11',raw_reference='ref',sha256='a'*64,legacy_unit_id='20260911|6912')
  self.assertEqual(receipt_contract('TDCC',row,{})['code'],'6912')
  row['period']='2026-09-10';self.assertIsNone(receipt_contract('TDCC',row,{}))
