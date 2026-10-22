"""Primary and cleanup workers can own and persist the same stage concurrently."""
import copy
import os
import unittest
from unittest.mock import Mock, patch

from scripts import v093_live_five_stage as base
from scripts.v093_replanned_five_stage import Worker
from scripts.v093_stage06_fenced_store import FencedGitHubStore
from scripts.v093_five_stage_durable_gate import LeaseBusy


class IsolationTests(unittest.TestCase):
    def test_same_stage_has_independent_lease_and_mutable_drive_state(self):
        drive=Mock()
        drive.folder.side_effect=lambda parent,name: parent+'/'+name
        saved={};locks=set()
        def acquire(api,token,key,owner,**kwargs):
            if key in locks: raise LeaseBusy(key)
            locks.add(key);return 1
        def read(d,parent,name):return copy.deepcopy(saved.get((parent,name)))
        def write(d,parent,name,value):saved[parent,name]=copy.deepcopy(value)
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'owner/repo','GH_TOKEN':'test','GITHUB_RUN_ID':'123'}), \
             patch.object(base,'Drive',return_value=drive),patch.object(base,'service'), \
             patch.object(base,'FolderRegistry'),patch.object(base,'acquire',side_effect=acquire), \
             patch.object(base.engine,'getj',side_effect=read),patch.object(base.engine,'putj',side_effect=write), \
             patch.object(base.Worker,'owned'):
            for stage in base.STAGES:
                with patch.object(Worker,'initialize_history_cursor') as initialize:
                    primary=Worker(stage,60)
                    repair=Worker(stage,60,stage06=True)
                    self.assertEqual(initialize.call_count,int(stage=='RAW'))
                self.assertNotEqual(primary.lock,repair.lock)
                self.assertEqual(repair.primary_control,primary.control)
                self.assertNotEqual(primary.stagectrl,repair.stagectrl)
                self.assertNotEqual(primary.monthfolder(stage,'2026-10'),repair.monthfolder(stage,'2026-10'))
                primary.cursor['month_index']=11;primary.save_cursor()
                repair.cursor['month_index']=22;repair.save_cursor()
                self.assertEqual(saved[primary.stagectrl,'CURSOR.json']['month_index'],11)
                self.assertEqual(saved[repair.stagectrl,'CURSOR.json']['month_index'],22)
                with self.assertRaises(LeaseBusy): Worker(stage,60)

    def test_repair_receipts_bind_only_to_matching_independent_stage_pool(self):
        for stage in ('PRICE','FINANCIAL'):
            key='POOL_CONSUMER_STAGE06_'+stage+'_V1'
            store=FencedGitHubStore('owner/repo','.github/live-state/stage06-receipt.json','test',stage,key,'123/'+stage,1)
            self.assertEqual(store.lease_key,key)
            with self.assertRaisesRegex(ValueError,'POOL_MISMATCH'):
                FencedGitHubStore('owner/repo','.github/live-state/stage06-receipt.json','test',stage,
                    'POOL_CONSUMER_STAGE06_QA1_V1','123/'+stage,1)


if __name__=='__main__':unittest.main()
