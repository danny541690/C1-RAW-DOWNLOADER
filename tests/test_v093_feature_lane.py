import unittest
from scripts.v093_feature_lane import LEGACY_HEADS,legacy_action

class FeatureHandoff(unittest.TestCase):
    def legacy(self,status='pending'):
        return {'head_sha':sorted(LEGACY_HEADS)[0],'status':status}
    def test_cancel_only_verified_waiting_definition_without_jobs(self):
        self.assertEqual(legacy_action(self.legacy(),[]),'CANCEL_WAITING_ONLY')
        self.assertNotEqual(legacy_action(self.legacy('in_progress'),[]),'CANCEL_WAITING_ONLY')
    def test_active_feature_writer_must_finish(self):
        self.assertEqual(legacy_action(self.legacy('in_progress'),[{'name':'features','status':'in_progress'}]),'WAIT_FOR_FEATURE_WRITER')
    def test_financial_writer_does_not_block_completed_feature_job(self):
        jobs=[{'name':'features','status':'completed'},{'name':'repair (financial)','status':'in_progress'}]
        self.assertEqual(legacy_action(self.legacy('in_progress'),jobs),'IGNORE')
    def test_new_or_completed_definitions_cannot_be_cancelled(self):
        self.assertEqual(legacy_action({'head_sha':'new','status':'pending'},[]),'IGNORE')
        self.assertEqual(legacy_action(self.legacy('completed'),[]),'IGNORE')

if __name__=='__main__':unittest.main()
