import unittest
from dataclasses import replace
from scripts.v093_five_stage_scheduler_gate import Work,STAGES,eligible,claim,can_publish,validate_partition

SHA='a'*64
class FiveStageSchedulerGateTests(unittest.TestCase):
    def test_five_stages(self): self.assertEqual(len(STAGES),5)
    def test_raw_eligible_without_qa(self): self.assertTrue(eligible(Work('2026-10','RAW','ohlc')))
    def test_qa_needs_committed_raw(self):
        self.assertFalse(eligible(Work('2026-10','QA1','ohlc')))
        self.assertTrue(eligible(Work('2026-10','QA1','ohlc',raw_committed=True,raw_sha256=SHA)))
    def test_deep_needs_qa_receipt(self):
        x=Work('2026-10','PRICE','ohlc',raw_committed=True,raw_sha256=SHA)
        self.assertFalse(eligible(x))
        self.assertTrue(eligible(replace(x,qa_complete=True,qa_sha256=SHA)))
    def test_lanes_are_disjoint(self):
        for stage,field in [('PRICE','revenue'),('FINANCIAL','ohlc'),('CHIP','pit')]:
            self.assertFalse(eligible(Work('2026-10',stage,field,raw_committed=True,raw_sha256=SHA,qa_complete=True,qa_sha256=SHA)))
    def test_lease_collision_rejected(self):
        x=Work('2026-10','RAW','ohlc')
        lock=claim(x,None,worker='runner1',now=100,ttl=50)
        with self.assertRaisesRegex(ValueError,'ALREADY_LEASED'):claim(x,lock,worker='runner2',now=101,ttl=50)
        self.assertEqual(claim(x,lock,worker='runner2',now=151)['owner'],'runner2')
    def test_retry_cap(self):
        self.assertTrue(eligible(Work('2026-10','RAW','ohlc',attempts=3)))
        self.assertFalse(eligible(Work('2026-10','RAW','ohlc',attempts=4)))
    def test_partial_done_is_not_certified(self):
        x=Work('2026-10','QA1','ohlc',done=True,raw_committed=True,raw_sha256=SHA)
        self.assertFalse(can_publish(x))
    def test_certification_needs_all_receipts(self):
        x=Work('2026-10','CHIP','margin',done=True,certified=True,raw_committed=True,raw_sha256=SHA,qa_complete=True,qa_sha256=SHA)
        self.assertTrue(can_publish(x))
        self.assertFalse(can_publish(replace(x,qa_sha256='')))
    def test_completed_not_requeued(self):
        self.assertFalse(eligible(Work('2026-10','RAW','ohlc',done=True)))
    def test_month_order(self):
        self.assertTrue(validate_partition(['2026-10','2026-09','2026-08']))
        with self.assertRaisesRegex(ValueError,'DUPLICATE_MONTH'):validate_partition(['2026-10','2026-10'])
        with self.assertRaisesRegex(ValueError,'NOT_NEWEST_FIRST'):validate_partition(['2026-09','2026-10'])
if __name__=='__main__':unittest.main()
