import copy
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import v093_github_budget as budget
from scripts import v093_stage06_live as live
from scripts.v093_stage06_ledger import Ledger,FileStore,StaleClaim
from tests.test_stage06_drive_publish import MemoryGit


class CachedFencedReadsTests(unittest.TestCase):
    def test_cached_candidate_read_cannot_publish_after_owner_takeover(self):
        store=MemoryGit();store.read_cache_seconds=30;head,state=store.read()
        store.advance(dict(owner='successor',fence=2,expires_at=3000))
        self.assertEqual(store.read()[0],head)
        state['revision']=1
        self.assertFalse(store.cas(head,state))
        with self.assertRaises(StaleClaim):store.read()

    def test_cached_lease_still_checks_wall_clock_expiration(self):
        store=MemoryGit();store.read_cache_seconds=2000;store.read();store.now=1940
        with self.assertRaises(StaleClaim):store.read()

    def test_unrelated_head_change_reloads_and_preserves_new_fields(self):
        store=MemoryGit();store.read_cache_seconds=30;store.read();store.advance()
        store.snapshots[store.head][store.path]['external_evidence']='keep'
        ledger=Ledger(store,lambda:1000);ledger.approve_version('PRICE','NEW','a'*64)
        self.assertEqual(store.read()[1]['external_evidence'],'keep')

    def test_repeated_read_uses_cache_but_each_publication_checks_branch(self):
        store=MemoryGit();store.read_cache_seconds=30;head,state=store.read();before=len(store.requests)
        for _ in range(8):store.read()
        self.assertEqual(len(store.requests),before)
        state['revision']=1;self.assertTrue(store.cas(head,state))
        self.assertTrue(any(method=='GET' and path=='/git/ref/heads/main' for method,path,_ in store.requests[before:]))


class BudgetWaitTests(unittest.TestCase):
    def test_rate_headers_are_numeric_and_do_not_include_authorization(self):
        h={'X-RateLimit-Limit':'1000','X-RateLimit-Remaining':'0','X-RateLimit-Reset':'2000','Authorization':'secret'}
        out=budget.rate_fields(h);self.assertEqual(out['remaining'],0)
        self.assertNotIn('secret',json.dumps(out))

    def test_wait_does_not_poll_core_before_reset_or_acquire_a_lock(self):
        answers=[({'resources':{'core':{'limit':1000,'remaining':0,'reset':5}}},{}),
                 ({'resources':{'core':{'limit':1000,'remaining':900,'reset':3605}}},{})]
        with patch.dict(os.environ,{'GH_TOKEN':'secret'}),patch.object(budget,'open_json',side_effect=answers) as calls,patch.object(budget.time,'monotonic',return_value=0),patch.object(budget.time,'time',return_value=0),patch.object(budget.time,'sleep') as sleep,patch('builtins.print'):
            result=budget.wait_for_budget(400,20)
        self.assertEqual(result['remaining'],900);self.assertEqual(calls.call_count,2);sleep.assert_called_once_with(8)

    def test_reset_beyond_wait_budget_fails_without_sleeping(self):
        answer=({'resources':{'core':{'limit':1000,'remaining':0,'reset':5000}}},{})
        with patch.dict(os.environ,{'GH_TOKEN':'secret'}),patch.object(budget,'open_json',return_value=answer),patch.object(budget.time,'monotonic',return_value=0),patch.object(budget.time,'time',return_value=0),patch.object(budget.time,'sleep') as sleep,patch('builtins.print'):
            with self.assertRaisesRegex(RuntimeError,'NO_LOCK_ACQUIRED'):budget.wait_for_budget(400,20)
        sleep.assert_not_called()


class SparseCheckpointTests(unittest.TestCase):
    def run_reconciler(self,month_result,max_months=0):
        with tempfile.TemporaryDirectory() as tmp:
            obj=object.__new__(live.Reconciler);obj.until=time.monotonic()+3600
            store=FileStore(Path(tmp)/'ledger.json');store.remaining=None
            obj.runtime=Ledger(store);obj.runtime.transaction=Mock(wraps=obj.runtime.transaction)
            obj.month=Mock(return_value=month_result);obj.d=Mock();obj.root='test-root'
            obj.lease_url='test';obj.token='test';obj.owner='test';obj.fence=1
            with patch.dict(os.environ,{'GITHUB_RUN_ID':'test'}),patch.object(live,'commit'),patch('builtins.print'):
                result=obj.run(max_months)
            return result,obj.runtime.transaction.call_count,obj.runtime.snapshot()['control']

    def test_empty_scope_sweep_saves_sparse_checkpoints_and_final_month(self):
        result,writes,control=self.run_reconciler({'_coverage':{'coverage_certified':False}})
        self.assertEqual(result['months_scanned_this_run'],322);self.assertLess(writes,30)
        self.assertEqual(control['last_scanned_month'],'2000-01');self.assertFalse(control['coverage_certified'])

    def test_real_gap_month_and_explicit_limit_checkpoint_immediately(self):
        result,writes,control=self.run_reconciler({'PRICE':{'gaps':1}},2)
        self.assertEqual(writes,2);self.assertEqual(control['next_month'],'2026-08')


if __name__=='__main__':unittest.main()
