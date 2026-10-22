import copy
import io
import os
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts import v093_stage06_live as live
from scripts.v093_stage06_ledger import empty, digest
from scripts.v093_stage06_fenced_store import FencedGitHubStore
from tests.test_stage06_drive_publish import DriveDouble


class LiveActivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(Path('tests/fixtures/stage06_native/manifest.json').read_text())
        self.entry=self.fixture[0]

    def row(self,entry=None):
        e=entry or self.entry;u=e['unit']
        period=u['period_start'] if u['period_start']==u['period_end'] else u['period_start'][:7]
        return dict(status='QUARANTINED',source=u['source'],category=u['dataset'],period=period,
            unit_id=u['native_unit_id'],raw_sha256=e['input_sha256'],error='NO_SECURITY_ID')

    def test_scope_and_authorization_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'plan.json';p.write_text('{}')
            with patch.object(live,'PLAN_PATH',p),self.assertRaisesRegex(ValueError,'NOT_AUTHORIZED'):live.authorized()

    def test_reconciler_cannot_borrow_price_pool(self):
        with self.assertRaisesRegex(ValueError,'POOL_MISMATCH'):
            FencedGitHubStore('test/repo','.github/live-state/stage06-live-control.json','x',
                'RECONCILE','POOL_CONSUMER_PRICE_REPLAN_201404_V1','owner',1)

    def test_dedicated_reconciler_pool_is_valid(self):
        store=FencedGitHubStore('test/repo','.github/live-state/stage06-live-control.json','x',
            'RECONCILE',live.POOL,'owner',1)
        self.assertEqual(store.stage,'RECONCILE')

    def test_native_repair_enqueued_ready_without_touching_old_receipt(self):
        row=self.row();state={'month':'2026-10','units':{'old':row}}
        before=copy.deepcopy(state)
        out=live.reconcile_snapshot(empty(),'PRICE',state,[])
        self.assertEqual(state,before)
        self.assertEqual([t['status'] for t in out['tasks'].values()],['READY'])
        self.assertFalse(out['test_only']);self.assertFalse(out['production_data_approved'])

    def test_repeated_scan_preserves_done_receipt(self):
        state={'month':'2026-10','units':{'old':self.row()}}
        out=live.reconcile_snapshot(empty(),'PRICE',state,[])
        gap=next(iter(out['gaps'].values()));task=next(iter(out['tasks'].values()))
        gap['status']='RESOLVED';task.update(status='DONE',receipt={'proof':'unchanged'})
        again=live.reconcile_snapshot(out,'PRICE',state,[])
        self.assertEqual(again['tasks'],out['tasks'])

    def test_unvalidated_dataset_is_blocked_not_auto_approved(self):
        row=self.row();row['category']='valuation'
        out=live.reconcile_snapshot(empty(),'PRICE',{'units':{'old':row}},[])
        self.assertEqual([t['status'] for t in out['tasks'].values()],['BLOCKED_APPROVAL'])

    def test_missing_raw_does_not_guess_attempts_or_send_request(self):
        row=self.row();row['error']='RAW_READBACK_HASH_MISMATCH'
        out=live.reconcile_snapshot(empty(),'PRICE',{'units':{'old':row}},[])
        self.assertFalse(out['tasks'])
        self.assertEqual(next(iter(out['gaps'].values()))['owner'],'RAW')
        self.assertFalse(next(iter(out['attempts'].values()))['known'])

    def test_missing_identity_stays_on_hold(self):
        row=self.row();row.pop('source')
        out=live.reconcile_snapshot(empty(),'PRICE',{'month':'2026-10','units':{'old':row}},[])
        self.assertFalse(out['tasks'])
        self.assertEqual(len(out['import_holds']),1)

    def test_identity_reconciles_only_exact_native_hash(self):
        row=self.row();row.pop('source')
        u=self.entry['unit'];registry=[dict(unit_id=u['native_unit_id'],sha256=self.entry['input_sha256'],
            status='SAVED_BASIC_VERIFIED',source=u['source'],category=u['dataset'],period=row['period'])]
        out=live.reconcile_snapshot(empty(),'PRICE',{'month':'2026-10','units':{'old':row}},registry)
        self.assertEqual([t['status'] for t in out['tasks'].values()],['READY'])

    def test_test_folder_is_rejected_for_live_artifacts(self):
        with patch.object(live,'authorized',return_value={}),self.assertRaisesRegex(ValueError,'LIVE_REPAIR_FOLDER'):
            live.LiveDriveArtifacts(DriveDouble(),'test-folder')

    def test_authorized_folder_uses_immutable_live_references(self):
        api=DriveDouble()
        api.get=lambda **kw:api.request(lambda:dict(mimeType='application/vnd.google-apps.folder',
            appProperties=dict(jarvis_stage06_scope='LIVE_REPAIR_ONLY',deployment=live.DEPLOYMENT)))
        with patch.object(live,'authorized',return_value={}):backend=live.LiveDriveArtifacts(api,'live-folder')
        backend.put_immutable('output',b'bytes',lambda:None)
        self.assertEqual(backend.reference('output')['backend'],'GOOGLE_DRIVE_IMMUTABLE_LIVE_REPAIR')
        self.assertNotIn('file_id',backend.reference('output'))
        with self.assertRaisesRegex(ValueError,'KEY_CONFLICT'):backend.put_immutable('output',b'changed',lambda:None)

    def cutover_context(self, path, status='completed', next_lease=None):
        lease=dict(owner='123/PRICE',fence=7,expires_at=9999999999)
        state={'jobs':{'POOL_CONSUMER_PRICE_REPLAN_201404_V1':{'lease':lease}}}
        later=copy.deepcopy(state)
        if next_lease is not None:later['jobs']['POOL_CONSUMER_PRICE_REPLAN_201404_V1']['lease']=next_lease
        response=lambda req,**kw:io.BytesIO(json.dumps(dict(path=path,status=status)).encode())
        return state,later,response

    def test_cutover_releases_only_a_confirmed_terminal_price_owner(self):
        state,later,response=self.cutover_context('.github/workflows/v093-v2-03-price.yml')
        with patch.object(live,'authorized'),patch.dict(os.environ,{'GITHUB_REPOSITORY':'test/repo','GH_TOKEN':'x'}),patch.object(live,'_read',side_effect=[('a',state),('b',later)]),patch.object(live.urllib.request,'urlopen',side_effect=response),patch.object(live,'commit') as commit:
            live.cutover_price()
        self.assertEqual(commit.call_args.args[3:5],('123/PRICE',7))

    def test_cutover_never_retires_a_newer_owner(self):
        state,later,response=self.cutover_context('.github/workflows/v093-v2-03-price.yml',next_lease=dict(owner='124/PRICE',fence=8,expires_at=9999999999))
        with patch.object(live,'authorized'),patch.dict(os.environ,{'GITHUB_REPOSITORY':'test/repo','GH_TOKEN':'x'}),patch.object(live,'_read',side_effect=[('a',state),('b',later)]),patch.object(live.urllib.request,'urlopen',side_effect=response),patch.object(live,'commit') as commit:
            live.cutover_price()
        commit.assert_not_called()

    def test_cutover_rejects_unrelated_workflow(self):
        state,later,response=self.cutover_context('.github/workflows/other.yml')
        with patch.object(live,'authorized'),patch.dict(os.environ,{'GITHUB_REPOSITORY':'test/repo','GH_TOKEN':'x'}),patch.object(live,'_read',return_value=('a',state)),patch.object(live.urllib.request,'urlopen',side_effect=response),patch.object(live,'commit') as commit:
            with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):live.cutover_price()
        commit.assert_not_called()

    def test_cutover_preserves_lease_if_old_worker_not_terminal(self):
        state,later,response=self.cutover_context('.github/workflows/v093-v2-03-price.yml',status='in_progress')
        with patch.object(live,'authorized'),patch.dict(os.environ,{'GITHUB_REPOSITORY':'test/repo','GH_TOKEN':'x'}),patch.object(live,'_read',return_value=('a',state)),patch.object(live.urllib.request,'urlopen',side_effect=response),patch.object(live.time,'sleep'),patch.object(live,'commit') as commit:
            with self.assertRaisesRegex(ValueError,'NOT_TERMINAL'):live.cutover_price()
        commit.assert_not_called()

    def test_month_order_is_october_2026_to_january_2000(self):
        self.assertEqual(live.base.MONTHS[0],'2026-10');self.assertEqual(live.base.MONTHS[-1],'2000-01')
        self.assertEqual(len(live.base.MONTHS),322)
        with self.assertRaises(ValueError):live.queue_path('PRICE','2026-11')

    def test_unsupported_owner_does_not_read_drive(self):
        worker=SimpleNamespace(stage='RAW',d=Mock())
        result=live.repair_owner(worker)
        self.assertEqual(result['completed'],0);worker.d.find.assert_not_called()

    def test_primary_work_does_not_call_stage06_repair_binding(self):
        from scripts import v093_replanned_five_stage as module
        worker=object.__new__(module.Worker)
        worker.stage='PRICE';worker.consume=Mock(side_effect=RuntimeError('primary work reached'))
        worker.api='test';worker.token='test';worker.lock='test';worker.owner='test';worker.fence=1
        worker.putj=Mock(side_effect=RuntimeError('stop after primary work'))
        with patch.object(live,'repair_owner',side_effect=RuntimeError('repair must be independent')) as repair,patch.object(module,'commit'):
            with self.assertRaisesRegex(RuntimeError,'primary work reached'):worker.run()
        worker.consume.assert_called_once();repair.assert_not_called()


if __name__=='__main__':unittest.main()
