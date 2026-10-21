import hashlib
import unittest
from unittest.mock import patch
from scripts.v093_isolated_guarded_drive_adapter import guarded_put,immutable_name
from scripts.annual_actual_firstpass import Drive
from scripts.v093_five_stage_durable_gate import LeaseConflict

class Request:
    def __init__(self,callback):self.callback=callback
    def execute(self,num_retries=0):return self.callback()
class API:
    def __init__(self):self.saved={};self.created=0
    def files(self):return self
    def create(self,body=None,media_body=None,fields=None):
        def action():
            self.created+=1
            self.saved[body['name']]=media_body._fd.getvalue()
            return {'id':body['name']}
        return Request(action)
    def update(self,**kwargs):raise AssertionError('MUTABLE_UPDATE_FORBIDDEN')
class FakeDrive(Drive):
    def __init__(self):
        self.api=API()
        self.corrupt=False
    def find(self,parent,name):
        return {'id':name,'name':name} if name in self.api.saved else None
    def read(self,parent,name):
        value=self.api.saved.get(name)
        return b'CORRUPT' if self.corrupt and value is not None else value

class GuardedDriveIntegrationTests(unittest.TestCase):
    def test_actual_drive_put_immutable_and_idempotent(self):
        d=FakeDrive()
        with patch('scripts.v093_isolated_guarded_drive_adapter.acquire',return_value=2),patch('scripts.v093_isolated_guarded_drive_adapter.commit',return_value=True) as commit:
            x=guarded_put(d,'parent','2026-10-ohlc',b'actual bytes','url','token','owner',now=100)
            y=guarded_put(d,'parent','2026-10-ohlc',b'actual bytes','url','token','owner',now=100)
        self.assertEqual(x['name'],y['name'])
        self.assertEqual(d.api.created,1)
        self.assertFalse(x['certified'])
        self.assertEqual(commit.call_count,2)
    def test_readback_corruption_does_not_commit(self):
        d=FakeDrive()
        with patch('scripts.v093_isolated_guarded_drive_adapter.acquire',return_value=1),patch('scripts.v093_isolated_guarded_drive_adapter.commit') as commit:
            with patch.object(d,'read',return_value=b'bad'):
                with self.assertRaises(ValueError):
                    guarded_put(d,'parent','2026-10-ohlc',b'good','url','token','owner',now=100)
            commit.assert_not_called()
    def test_crash_before_manifest_commit_recovers_idempotently(self):
        d=FakeDrive()
        with patch('scripts.v093_isolated_guarded_drive_adapter.acquire',return_value=1),patch('scripts.v093_isolated_guarded_drive_adapter.commit',side_effect=RuntimeError('CRASH')):
            with self.assertRaisesRegex(RuntimeError,'CRASH'):
                guarded_put(d,'parent','2026-10-ohlc',b'good','url','token','owner',now=100)
        self.assertEqual(d.api.created,1)
        with patch('scripts.v093_isolated_guarded_drive_adapter.acquire',return_value=2),patch('scripts.v093_isolated_guarded_drive_adapter.commit',return_value=True):
            x=guarded_put(d,'parent','2026-10-ohlc',b'good','url','token','owner2',now=111)
        self.assertEqual(d.api.created,1)
        self.assertEqual(x['fence'],2)
    def test_stale_owner_never_reports_success(self):
        d=FakeDrive()
        with patch('scripts.v093_isolated_guarded_drive_adapter.acquire',return_value=1),patch('scripts.v093_isolated_guarded_drive_adapter.commit',side_effect=LeaseConflict('STALE')):
            with self.assertRaises(LeaseConflict):
                guarded_put(d,'parent','2026-10-ohlc',b'good','url','token','owner',now=100)
        self.assertEqual(d.api.created,1)
    def test_name_safety(self):
        with self.assertRaises(ValueError):immutable_name('../bad',b'good')
        with self.assertRaises(ValueError):immutable_name('ok',b'')
if __name__=='__main__':unittest.main()
