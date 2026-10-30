import copy,unittest
from scripts.v093_final_release_catalogs import apply_outcome
class FinalReleaseHandoffTests(unittest.TestCase):
 def row(self):
  source='MOPS';key='MOPS|2023-01|one';period='2023-01'
  return dict(definition=dict(source=source,key=key,period=period,slot='ASC'),attempts=1,status='READY',legacy_review=dict(source=source,task_key=key,attempts=1,action='CLASSIFY_APPLICABILITY_AND_MISSING_EVIDENCE',provenance=[dict(period=period,status='UNRESOLVED')]),execution_contract=dict(source=source,key=key,period=period,mode='MISSING',category='revenue_sii_0'))
 def task(self,row,status='APPLICABILITY_HOLD'):
  return dict(definition=copy.deepcopy(row['definition']),status=status,attempts=2,error=dict(phase='FETCH',code='HTTPError_404'))
 def test_held_query_keeps_spent_attempt_and_cannot_become_ready_again(self):
  row=self.row();original=copy.deepcopy(row);out=apply_outcome(row,self.task(row),dict(commit='a'*40));self.assertEqual(out['attempts'],2);self.assertEqual(out['legacy_review']['attempts'],2);self.assertEqual(out['status'],'APPLICABILITY_HOLD');self.assertEqual(row,original)
 def test_saved_missing_becomes_local_promotion_without_new_source_attempt(self):
  row=self.row();task=self.task(row,'RAW_BASIC_VERIFIED');task.update(execution_contract=copy.deepcopy(row['execution_contract']),raw_reference='qa-original',raw_sha256='b'*64,save_intent=dict(sha256='b'*64))
  out=apply_outcome(row,task,dict(commit='a'*40));self.assertEqual(out['execution_contract']['mode'],'PROMOTE');self.assertTrue(out['local_only']);self.assertEqual(out['attempts'],2);self.assertEqual(out['execution_contract']['promotion_evidence']['reference'],'qa-original')
 def test_attempt_regression_wrong_identity_and_pending_work_block_handoff(self):
  row=self.row()
  for change in [dict(attempts=0),dict(definition=dict(row['definition'],slot='DESC')),dict(status='RETRY_WAIT')]:
   task=self.task(row);task.update(change)
   with self.assertRaises(ValueError):apply_outcome(row,task,dict(commit='a'*40))
