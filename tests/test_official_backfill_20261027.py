import unittest
from scripts.v093_official_repair import reopen_backfill,BACKFILL_PASS
class Backfill(unittest.TestCase):
 def test_exhausted_reopened_once_with_evidence(self):
  old=dict(status='UNRESOLVED_RETRY_CYCLES_EXHAUSTED',terminal=True,complete=False,attempts=3,retry_cycle=4,error='timeout',raw_sha256='retain')
  new=reopen_backfill(old)
  self.assertFalse(new['terminal']);self.assertEqual(new['attempts'],0);self.assertEqual(new['raw_sha256'],'retain');self.assertEqual(old['attempts'],3)
  new.update(terminal=True,attempts=3)
  self.assertIs(reopen_backfill(new),new)
 def test_success_and_scope_blocks_preserved(self):
  for row in [dict(status='CONTENT_CHECK_PASS',complete=True),dict(status='OFFICIAL_PERIOD_NOT_PROVIDED',terminal=True),dict(status='UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE',terminal=True)]:
   self.assertIs(reopen_backfill(row),row)
 def test_empty_is_pending_not_complete(self):
  row=reopen_backfill(dict(status='SOURCE_NO_DATA_UNCONFIRMED',terminal=True))
  self.assertFalse(row['complete']);self.assertEqual(row['backfill_pass'],BACKFILL_PASS)
