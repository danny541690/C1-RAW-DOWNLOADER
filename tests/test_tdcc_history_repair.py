import unittest
from scripts.v093_tdcc_independent import migrate_history,history_summary,REPAIR_REVISION,validate_history,restore_history
class TDCCHistoryRepairTests(unittest.TestCase):
 def test_restart_preserves_receipts_and_backup(self):
  s={'completed_dates':['20261016'],'receipts':{'ok':{'status':'SAVED_BASIC_VERIFIED'}},'history_receipts':{'x':{'status':'SAVED_BASIC_VERIFIED'}}}
  self.assertTrue(migrate_history(s));self.assertEqual(s['completed_dates'],[]);self.assertIn('ok',s['receipts']);self.assertIn('x',s['history_receipts'])
  self.assertFalse(migrate_history(s));self.assertEqual(len(s['history_checkpoint_backups']),1)
 def test_failed_attempt_is_not_success(self):
  self.assertFalse(history_summary('20261016',['2330'],{'20261016|2330':{'status':'UNRESOLVED','attempts':3}})['candidate_set_complete'])
 def test_empty_universe_is_not_complete(self):
  self.assertFalse(history_summary('20261016',[],{})['candidate_set_complete'])
 def test_proven_receipt_is_complete_for_candidates_only(self):
  r=history_summary('20261016',['2330'],{'20261016|2330':dict(status='SAVED_BASIC_VERIFIED',file_id='f',sha256='s',remote_readback_hash_verified=True)})
  self.assertTrue(r['candidate_set_complete']);self.assertFalse(r['historical_universe_complete'])
 def test_no_data_html_is_rejected(self):
  with self.assertRaises(ValueError):validate_history(b'<html>No data</html>','20261016','2330')
 def test_restart_restores_successful_per_date_receipts(self):
  s={'history_receipt_date':'20261016'}
  saved='{"20261016|2330":{"status":"SAVED_BASIC_VERIFIED"}}'
  calls=[]
  restore_history(s,lambda name:calls.append(name) or saved)
  self.assertEqual(calls,['HISTORY_20261016.json'])
  self.assertEqual(s['history_receipts']['20261016|2330']['status'],'SAVED_BASIC_VERIFIED')
