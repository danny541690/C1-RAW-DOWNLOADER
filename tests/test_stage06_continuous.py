import copy
import json
import os
import tempfile
import time
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import Mock, patch
from scripts import v093_stage06_live as live
from scripts.v093_stage06_ledger import Ledger, FileStore, Conflict
from scripts.v093_stage06_fenced_store import FencedGitHubStore


class ContinuousReconciliationTests(unittest.TestCase):
    def run_case(self, initial_index=0, waits=(True, False), max_months=0, remaining=None):
        with tempfile.TemporaryDirectory() as tmp:
            obj=object.__new__(live.Reconciler)
            obj.until=time.monotonic()+3600
            store=FileStore(Path(tmp)/'ledger.json');store.remaining=remaining
            obj.runtime=Ledger(store)
            obj.runtime.transaction(lambda d,n:d.update(control={'month_index':initial_index,'independent_revision':'INDEPENDENT_STAGE06_20261022_V2'}))
            obj.month=Mock(side_effect=lambda m:{'_coverage':{'coverage_certified':False,'seen':m}})
            obj.wait_for_recheck=Mock(side_effect=waits)
            obj.refresh_inputs=Mock();obj.d=Mock();obj.root='root'
            obj.lease_url='test';obj.token='test';obj.owner='owner';obj.fence=1
            with patch.dict(os.environ,{'GITHUB_RUN_ID':'test'}),patch.object(live.base,'MONTHS',['2026-10','2000-01']),patch.object(live,'commit') as release,patch('builtins.print'):
                result=obj.run(max_months,continuous=True,recheck_seconds=300)
            return obj,result,copy.deepcopy(obj.runtime.snapshot()),release.call_count

    def test_finished_sweep_returns_to_latest_and_refreshes_new_upstream(self):
        obj,result,state,releases=self.run_case()
        self.assertEqual([x.args[0] for x in obj.month.call_args_list],['2026-10','2000-01']*2)
        obj.refresh_inputs.assert_called_once()
        self.assertEqual(state['control']['next_month'],'2026-10')
        self.assertEqual(state['control']['phase'],'WAITING_RECHECK')
        self.assertEqual(result['cycles_completed_this_run'],2)
        self.assertFalse(state['control']['coverage_certified'])
        self.assertEqual(releases,1)
        waiting=[json.loads(c.args[2]) for c in obj.d.put.call_args_list if json.loads(c.args[2]).get('status')=='WAITING_RECHECK']
        self.assertEqual(len(waiting),2)

    def test_partial_sweep_resumes_saved_month_before_starting_new_cycle(self):
        obj,result,state,_=self.run_case(initial_index=1)
        self.assertEqual([x.args[0] for x in obj.month.call_args_list],['2000-01','2026-10','2000-01'])
        self.assertEqual(result['months_scanned_this_run'],3)

    def test_explicit_month_limit_still_stops_and_retains_checkpoint(self):
        obj,result,state,_=self.run_case(max_months=1)
        self.assertEqual(result['months_scanned_this_run'],1)
        self.assertEqual(state['control']['next_month'],'2000-01')
        obj.wait_for_recheck.assert_not_called()

    def test_low_api_quota_preserves_cursor_without_starting_more_work(self):
        obj,result,state,releases=self.run_case(initial_index=1,remaining=199)
        obj.month.assert_not_called();obj.refresh_inputs.assert_not_called()
        self.assertEqual(state['control']['month_index'],1)
        self.assertEqual(releases,1)

    def test_recheck_wait_is_bounded_and_does_not_run_past_worker_budget(self):
        obj=object.__new__(live.Reconciler);obj.until=200;obj.guard=Mock()
        with patch.object(live.time,'monotonic',return_value=100),patch.object(live.time,'sleep') as sleep:
            self.assertFalse(obj.wait_for_recheck(60))
        sleep.assert_not_called()

    def test_wait_checks_owner_in_chunks_instead_of_spinning(self):
        obj=object.__new__(live.Reconciler);obj.until=1000;obj.guard=Mock();clock=[0]
        def sleep(seconds):clock[0]+=seconds
        with patch.object(live.time,'monotonic',side_effect=lambda:clock[0]),patch.object(live.time,'sleep',side_effect=sleep) as pauses:
            self.assertTrue(obj.wait_for_recheck(90))
        self.assertEqual(clock[0],90);self.assertEqual(pauses.call_count,3)
        self.assertEqual(obj.guard.call_count,3)

    def test_failed_owner_check_aborts_wait(self):
        obj=object.__new__(live.Reconciler);obj.until=1000;obj.guard=Mock(side_effect=ValueError('lost owner'))
        with patch.object(live.time,'monotonic',return_value=0),patch.object(live.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'lost owner'):obj.wait_for_recheck(90)
        sleep.assert_not_called()

    def test_slow_owner_check_cannot_cause_negative_sleep(self):
        obj=object.__new__(live.Reconciler);obj.until=1000;clock=[0]
        obj.guard=Mock(side_effect=lambda:clock.__setitem__(0,100))
        with patch.object(live.time,'monotonic',side_effect=lambda:clock[0]),patch.object(live.time,'sleep') as sleep:
            self.assertTrue(obj.wait_for_recheck(60))
        sleep.assert_not_called()

    def test_owner_check_consuming_remaining_budget_prevents_next_cycle(self):
        obj=object.__new__(live.Reconciler);obj.until=200;clock=[0]
        obj.guard=Mock(side_effect=lambda:clock.__setitem__(0,190))
        with patch.object(live.time,'monotonic',side_effect=lambda:clock[0]),patch.object(live.time,'sleep') as sleep:
            self.assertFalse(obj.wait_for_recheck(60))
        sleep.assert_not_called()

    def test_invalid_interval_is_rejected_before_acquiring_owner(self):
        with patch('sys.argv',['stage06','--recheck-seconds','0']),patch.object(live,'Reconciler') as owner:
            with self.assertRaisesRegex(ValueError,'INVALID_RECHECK_INTERVAL'):live.main()
        owner.assert_not_called()

    def test_owner_conflict_defers_without_claiming_other_month_or_changing_cursor(self):
        worker=SimpleNamespace(stage='FINANCIAL',d=Mock(),control='control',stagectrl='financial',
            token='test',lock='lock',owner='run/FINANCIAL',fence=1,cursor={'month_index':4},
            until=time.monotonic()+600)
        worker.owned=Mock();worker.d.find.side_effect=[{'id':'root'},None]
        ledger=Mock();ledger.store.remaining=None
        listing=[{'name':'ARTIFACTS_FINANCIAL_'+m,'id':m,'mimeType':'application/vnd.google-apps.folder'} for m in ['2026-06','2026-03']]
        before=copy.deepcopy(worker.cursor);until=worker.until
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'test/repo'}),patch.object(live,'authorized'),patch.object(live.native,'listing',return_value=listing),patch.object(live.engine,'getj',return_value=[]),patch.object(live,'Ledger',return_value=ledger) as ledgers,patch.object(live,'FencedGitHubStore'),patch.object(live,'LiveDriveArtifacts'),patch.object(live,'replay_one',side_effect=Conflict('CAS_RETRY_EXHAUSTED')) as replay,patch('builtins.print'):
            result=live.repair_owner(worker)
        self.assertEqual(result['status'],'DEFERRED_CAS_CONTENTION')
        self.assertEqual(result['completed'],0);self.assertEqual(result['deferred'],1)
        self.assertEqual(replay.call_count,1);self.assertEqual(ledgers.call_count,1)
        self.assertEqual(worker.cursor,before);self.assertEqual(worker.until,until)


class ConflictBackoffTests(unittest.TestCase):
    def test_retry_uses_backoff_and_preserves_unchanged_failed_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=FileStore(Path(tmp)/'state.json');ledger=Ledger(store)
            before=ledger.snapshot();store.cas=Mock(return_value=False);store.conflict_backoff=Mock()
            with self.assertRaises(Conflict):ledger.transaction(lambda d,n:d.update(extra='candidate'))
            self.assertEqual(store.conflict_backoff.call_count,15)
            self.assertEqual(ledger.snapshot(),before)

    def test_remote_backoff_is_bounded(self):
        obj=object.__new__(FencedGitHubStore)
        with patch('scripts.v093_stage06_fenced_store.random.uniform',return_value=.2),patch('scripts.v093_stage06_fenced_store.time.sleep') as sleep:
            obj.conflict_backoff(100)
        sleep.assert_called_once_with(1.2)

if __name__=='__main__':unittest.main()
