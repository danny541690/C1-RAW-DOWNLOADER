import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v093_unresolved_recheck import review
from test_problem_recovery import retained

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
  cfg=json.loads(Path('config/v093_unresolved_recheck_20261101.json').read_text());self.assertFalse(cfg['market_source_requests']);self.assertEqual(sum(t['unresolved'] for t in cfg['targets'].values()),287)

if __name__=='__main__':unittest.main()
