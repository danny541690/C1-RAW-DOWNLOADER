import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from scripts.v093_source_continuation import acknowledge,continue_slot
from scripts.v093_admission_runtime import load_release
class SourceContinuationTests(unittest.TestCase):
 def test_completed_source_runs_wake_guarded_recovery_with_cron_fallback(self):
  import yaml
  workflow=yaml.load(Path('.github/workflows/jarvis-seven-production-watchdog.yml').read_text(),Loader=yaml.BaseLoader)
  trigger=workflow['on']['workflow_run']
  design=json.loads(Path('config/v093_seven_source_design.json').read_text())
  expected={(Path('.github/workflows')/s['workflow']).read_text().splitlines()[0].split(': ',1)[1] for s in design['slots']}
  self.assertEqual(set(trigger['workflows']),expected);self.assertEqual(len(trigger['workflows']),12)
  self.assertEqual(trigger['types'],['completed']);self.assertEqual(trigger['branches'],['main'])
  self.assertIn('schedule',workflow['on']);self.assertEqual(workflow['permissions']['actions'],'write')
 def coordinator(self,state):
  c=Mock();c.source='TWSE';c.clock.return_value=100;c.store.read.return_value=('commit',state);c.update.side_effect=lambda fn:fn(state);return c
 def test_disabled_release_blocks_before_catalog_or_dispatch(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'config').mkdir();(root/'config/v093_source_release.json').write_text(json.dumps(dict(enabled=False)))
   with self.assertRaisesRegex(ValueError,'RELEASE_NOT_APPROVED'):load_release(root)
 def test_saved_unknown_dispatch_blocks_duplicate_watchdog_and_no_staging(self):
  s=dict(outbox={'a'*64:dict(slot='DESC',status='UNKNOWN_RECONCILE_DISPATCH')});c=self.coordinator(s)
  with patch('scripts.v093_source_continuation.stage') as stage:
   self.assertFalse(continue_slot(Path('.'),c,None,'DESC','run',Mock()));stage.assert_not_called();c.dispatch_after_save.assert_not_called()
 def test_ack_is_bound_to_slot_and_duplicate_run_cannot_process(self):
  s=dict(outbox={'a'*64:dict(slot='DESC',status='SENT')});c=self.coordinator(s)
  self.assertTrue(acknowledge(c,'DESC','a'*64,'one'));self.assertTrue(acknowledge(c,'DESC','a'*64,'one'));self.assertFalse(acknowledge(c,'DESC','a'*64,'two'))
  with self.assertRaisesRegex(ValueError,'BINDING'):acknowledge(c,'ASC','a'*64,'one')
 def test_stage_is_saved_before_outbox_transport(self):
  c=self.coordinator(dict(admission={},outbox={}));order=[]
  c.dispatch_after_save.side_effect=lambda *args:order.append('dispatch') or True
  with patch('scripts.v093_source_continuation.stage',side_effect=lambda *a,**k:order.append('saved')):
   self.assertTrue(continue_slot(Path('.'),c,None,'DESC','run',Mock()))
  self.assertEqual(order,['saved','dispatch'])
 def test_hold_cooldown_and_finished_do_not_dispatch(self):
  for state in [dict(hold='auth'),dict(cooldown_until=200),dict(admission=dict(DESC=dict(finished=True)))]:
   c=self.coordinator(state)
   with patch('scripts.v093_source_continuation.stage') as stage:self.assertFalse(continue_slot(Path('.'),c,None,'DESC','run',Mock()));stage.assert_not_called()
