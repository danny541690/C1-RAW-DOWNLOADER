import copy,gzip,json,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v093_unresolved_recheck import review
from test_problem_recovery import retained,sha

class UnresolvedRecheckTests(unittest.TestCase):
 def test_failed_pass_completion_does_not_hide_unresolved_originals(self):
  task=retained(b'empty',source='TWSE',period='2004-06-22',category='prices_indices');before=copy.deepcopy(task);previous=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',attempts=3)
  with patch('scripts.v093_unresolved_recheck.recheck',return_value=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',attempts=3)) as check:result=review(task,previous,{},None,{})
  self.assertEqual(task,before);self.assertEqual(result['source_requests'],0);self.assertEqual(result['raw_writes'],0);self.assertEqual(result['next_queue'],'OFFICIAL_CALENDAR_OR_COVERAGE_EVIDENCE_REQUIRED');self.assertFalse(result['full_acceptance']);self.assertEqual(check.call_args.args[0]['attempts'],3)
 def test_valid_quarantine_is_not_labeled_as_saved_raw(self):
  task=retained(b'raw');previous=dict(status='REVIEW_REQUIRED',attempts=4)
  with patch('scripts.v093_unresolved_recheck.recheck',return_value=dict(status='REVIEW_REQUIRED',reason='VALID_REJECTED_RAW_REQUIRES_PROMOTION')):result=review(task,previous,{},None,{})
  self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertEqual(result['next_queue'],'VERIFIED_BYTES_REQUIRE_NATIVE_PROMOTION');self.assertEqual(result['request_attempts_preserved'],4)
 def test_review_targets_are_only_the_existing_unresolved_counts(self):
  cfg=json.loads(Path('config/v093_unresolved_recheck_20261101.json').read_text());self.assertFalse(cfg['market_source_requests']);self.assertEqual(sum(t['unresolved'] for t in cfg['targets'].values()),285);self.assertTrue(cfg['latest_quarantine_evidence_first'])
 def test_newest_saved_response_replaces_old_missing_evidence_only_for_review(self):
  raw='公司93年9月份<table><td>1234</td></table>'.encode('cp950');task=retained(b'old',period='2004-09');before=copy.deepcopy(task)
  compressed=gzip.compress(raw);evidence=dict(reference='new-quarantine',encoding='gzip',raw_sha256=sha(raw),stored_sha256=sha(compressed),raw_bytes=len(raw),readback_verified=True,accepted_as_raw=False)
  previous=dict(status='REVIEW_REQUIRED',attempts=4,definition=task['definition'],followup_rejected_evidence=evidence)
  from test_native_repair import FakeDrive
  drive=FakeDrive();drive.data['new-quarantine']=compressed
  result=review(task,previous,dict(official_evidence={}),drive,{})
  self.assertEqual(task,before);self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertEqual(result['reason'],'VALID_REJECTED_RAW_REQUIRES_PROMOTION');self.assertEqual(result['raw_sha256'],sha(raw));self.assertNotIn('raw_reference',result);self.assertEqual(result['attempts'],4);self.assertEqual(result['source_requests'],0)
 def test_changed_latest_quarantine_does_not_fall_back_to_original(self):
  raw='公司93年9月份<table><td>1234</td></table>'.encode('cp950');task=retained(raw,period='2004-09');compressed=gzip.compress(raw)
  evidence=dict(reference='new',encoding='gzip',raw_sha256=sha(raw),stored_sha256='0'*64,raw_bytes=len(raw),readback_verified=True,accepted_as_raw=False)
  previous=dict(status='REVIEW_REQUIRED',attempts=4,definition=task['definition'],followup_rejected_evidence=evidence)
  from test_native_repair import FakeDrive
  drive=FakeDrive();drive.data['new']=compressed
  result=review(task,previous,dict(official_evidence={}),drive,{})
  self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertEqual(result['reason'],'RECOVERY_REJECTED_STORED_SHA');self.assertFalse(result['accepted_as_raw'])
 def test_latest_response_must_match_original_task_identity(self):
  task=retained(b'old');previous=dict(status='REVIEW_REQUIRED',attempts=4,definition=dict(task['definition'],period='2000-01'),followup_rejected_evidence=dict(reference='wrong',raw_sha256='a'*64))
  with self.assertRaisesRegex(ValueError,'IDENTITY'):review(task,previous,{},None,{})

if __name__=='__main__':unittest.main()
