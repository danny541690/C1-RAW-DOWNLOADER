"""Opposite-direction history workers share month ownership, not cursors."""
import ast
import copy
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import v093_raw_month_coordination as coordination
from scripts.v093_five_stage_durable_gate import LeaseBusy, terminal_owner

# Load the actual worker decisions without initializing Google SDKs or credentials.
source=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_stage07_ascending.py').read_text())
namespace=dict(Worker=object,REVISION='PLAN',
    RAW_MONTHS=[f'{y}-{m:02d}' for y in range(2014,1999,-1) for m in range(12,0,-1) if (y,m)<=(2014,4)],
    STOPPED={'STOPPED_MET_PRIMARY','STOPPED_PRIMARY_SCOPE_VISITED','STOPPED_UPPER_BOUND'},
    MONTHS7=[f'{y}-{m:02d}' for y in range(2000,2013) for m in range(1,13)],
    time=time,json=json,native=SimpleNamespace(sha=lambda raw:'a'*64,stamp=lambda:'now'),
    engine=SimpleNamespace(getj=Mock()),commit=Mock(),capture_history_month=Mock())
nodes=[n for n in source.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('primary_frontier','AscendingWorker')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_stage07_worker','exec'),namespace)
Worker7=namespace['AscendingWorker']


class MonthOwnershipTests(unittest.TestCase):
    def worker(self):
        return SimpleNamespace(api='api',token='token',owner='123/RAW',capture_month=Mock(return_value=True))
    def test_busy_month_is_never_downloaded(self):
        worker=self.worker()
        with patch.object(coordination,'acquire',side_effect=LeaseBusy),patch.object(coordination,'commit') as release:
            self.assertFalse(coordination.capture_history_month(worker,'2000-01'))
        worker.capture_month.assert_not_called();release.assert_not_called()
    def test_source_error_releases_only_our_month_fence(self):
        worker=self.worker();worker.capture_month.side_effect=ValueError('source')
        with patch.object(coordination,'acquire',return_value=7),patch.object(coordination,'commit') as release:
            with self.assertRaises(ValueError):coordination.capture_history_month(worker,'2000-01')
        self.assertEqual(release.call_args.args[2:5],('RAW_HISTORY_MONTH_2000_01','123/RAW',7))
    def test_frontier_rechecked_after_ownership_before_source_request(self):
        worker=self.worker()
        with patch.object(coordination,'acquire',return_value=7),patch.object(coordination,'commit'):
            self.assertFalse(coordination.capture_history_month(worker,'2000-01',can_start=lambda:False))
        worker.capture_month.assert_not_called()


class AscendingMeetingTests(unittest.TestCase):
    def worker(self,index=0):
        worker=object.__new__(Worker7)
        worker.cursor={'month_index':index,'status':'ACTIVE'}
        worker.until=time.monotonic()+60;worker.d=Mock();worker.primary_stagectrl='primary'
        worker.stagectrl='ascending';worker.api='api';worker.token='token'
        worker.lock='own-pool';worker.owner='123/RAW';worker.fence=2
        worker.processed=0;worker.saved=0;worker.save_cursor=Mock();worker.putj=Mock()
        return worker
    def set_frontier(self,month):
        index=namespace['RAW_MONTHS'].index(month) if month else len(namespace['RAW_MONTHS'])
        namespace['engine'].getj=Mock(return_value={'execution_plan':'PLAN','month_index':index})
    def test_oldest_month_first_and_stop_before_primary_active_month(self):
        worker=self.worker();self.set_frontier('2000-02')
        capture=Mock(side_effect=lambda w,m,can_start:can_start())
        namespace['capture_history_month']=capture
        result=worker.run()
        self.assertEqual([c.args[1] for c in capture.call_args_list],['2000-01'])
        self.assertEqual(result['status'],'STOPPED_MET_PRIMARY')
        self.assertEqual(result['month_index'],1)
        self.assertEqual(result['meeting_month'],'2000-02')
    def test_persisted_meeting_cannot_restart_downloads(self):
        worker=self.worker();worker.cursor['status']='STOPPED_MET_PRIMARY'
        capture=Mock();namespace['capture_history_month']=capture
        worker.run();capture.assert_not_called()
    def test_interrupted_month_retains_ascending_checkpoint(self):
        worker=self.worker();self.set_frontier('2012-08')
        namespace['capture_history_month']=Mock(return_value=False)
        result=worker.run()
        self.assertEqual(result['month_index'],0)
        self.assertEqual(result['next_month'],'2000-01')
    def test_primary_has_finished_scope(self):
        worker=self.worker();self.set_frontier(None)
        self.assertFalse(worker.may_start('2000-01'))
        self.assertEqual(worker.cursor['status'],'STOPPED_PRIMARY_SCOPE_VISITED')
    def test_unknown_primary_cursor_fails_closed(self):
        worker=self.worker();namespace['engine'].getj=Mock(return_value={'month_index':0})
        with self.assertRaises(ValueError):worker.may_start('2000-01')
    def test_scope_never_advances_into_2013(self):
        worker=self.worker(len(namespace['MONTHS7'])-1);self.set_frontier('2014-04')
        namespace['capture_history_month']=Mock(return_value=True)
        result=worker.run()
        self.assertEqual(result['status'],'STOPPED_UPPER_BOUND')
        self.assertIsNone(result['next_month'])


class RecoveryIdentityTests(unittest.TestCase):
    def test_month_lease_only_recovers_matching_terminal_download_workflow(self):
        lease={'owner':'123/RAW'}
        for path,allowed in [('.github/workflows/v093-v2-07-raw-ascending.yml',True),
                             ('.github/workflows/v093-v2-01-raw.yml',True),
                             ('.github/workflows/v093-v2-06-reconcile-repair.yml',False)]:
            with patch('scripts.v093_five_stage_durable_gate.open_json',
                       return_value=({'id':123,'status':'completed','path':path},{})):
                self.assertEqual(terminal_owner('https://api.github.com/repos/test/repo/contents/state',
                    'token','RAW_HISTORY_MONTH_2000_01',lease),allowed)


if __name__=='__main__':unittest.main()
