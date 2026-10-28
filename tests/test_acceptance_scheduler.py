import copy
import hashlib
import io
import json
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from scripts import v093_acceptance_scheduler as worker


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.raw = json.dumps({'actual_retained': [1, 2]}).encode()
        self.row = {'來源': 'FinMind', '單元ID': 'unit-1', '資料集': 'TaiwanStockPrice',
                    '原件參照': 'file_1', '年份': '2000', '月份': '2000-01', '代碼': '1515',
                    '期間': '2000-01', '已下載': '1',
                    'RAW_SHA256': hashlib.sha256(self.raw).hexdigest()}
        self.meta = dict(id='file_1', name='raw.json', mimeType='application/json',
                         size=str(len(self.raw)), md5Checksum=hashlib.md5(self.raw).hexdigest(),
                         modifiedTime='2026-10-28T00:00:00Z', version='1', parents=['scope'])
        self.snapshot = dict(enumeration_complete=True, files=[self.meta])
        self.state = dict(schema=worker.SCHEMA)
        self.reads = []
        self.inspections = []

    def read(self, fid, size):
        self.reads.append(fid)
        return self.raw, dict(self.meta)

    def inspect(self, raw, row, evidence):
        self.inspections.append(row['單元ID'])
        return {'parsed': json.loads(raw)}

    def run_work(self, **kwargs):
        params = dict(rows=[self.row], snapshot=self.snapshot, state=self.state,
                      read_remote=self.read, inspect=self.inspect, signatures={'FinMind': 'v1'}, now=100000)
        params.update(kwargs)
        return worker.work(**params)

    def test_resume_after_serialized_restart_does_not_read_unchanged_raw(self):
        self.run_work()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'worker.json.gz'
            worker.save(path, self.state)
            self.state = worker.load(path)
        self.assertEqual(self.run_work()['reused'], 1)
        self.assertEqual(len(self.reads), 1)
        self.assertEqual(len(self.inspections), 1)

    def test_changed_checker_invalidates_only_relevant_source(self):
        self.run_work()
        self.run_work(signatures={'FinMind': 'v2', 'MOPS': 'unrelated'})
        self.assertEqual(len(self.inspections), 2)
        self.run_work(signatures={'FinMind': 'v2', 'MOPS': 'changed'})
        self.assertEqual(len(self.inspections), 2)

    def test_unrelated_esb_evidence_does_not_invalidate(self):
        self.run_work()
        self.run_work(evidence={('2026-09-01', '9999'): {'new': 'unrelated'}})
        self.assertEqual(len(self.reads), 1)

    def test_changed_remote_version_forces_new_readback(self):
        self.run_work()
        self.meta['version'] = '2'
        self.run_work()
        self.assertEqual(len(self.reads), 2)

    def test_same_package_two_members_is_read_once(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('a.json', self.raw)
            archive.writestr('b.json', self.raw)
        payload = buffer.getvalue()
        self.meta.update(size=str(len(payload)), md5Checksum=hashlib.md5(payload).hexdigest())
        rows = [dict(self.row, 原件參照='file_1/' + name, 單元ID=name) for name in ('a.json', 'b.json')]
        reads = []
        result = self.run_work(rows=rows, read_remote=lambda fid, size: (reads.append(fid) or payload, dict(self.meta)))
        self.assertEqual(result['inspected'], 2)
        self.assertEqual(reads, ['file_1'])

    def test_hash_mismatch_is_blocked_not_retried_or_accepted(self):
        self.row['RAW_SHA256'] = '0' * 64
        self.run_work()
        self.assertEqual(next(iter(self.state['outcomes'].values()))['status'], 'CONTENT_BLOCKED')
        self.run_work()
        self.assertEqual(len(self.reads), 1)
        self.assertFalse(self.inspections)

    def test_transport_attempts_survive_restart_and_stop_at_three(self):
        def fail(fid, size):
            self.reads.append(fid)
            raise TimeoutError('sensitive provider response must not be saved')
        for now in (100000, 100001, 130000, 160000, 190000):
            self.run_work(read_remote=fail, now=now)
            self.state = copy.deepcopy(self.state)
        self.assertEqual(len(self.reads), 3)
        self.assertNotIn('sensitive', json.dumps(self.state))
        self.assertFalse(self.state['outcomes'])

    def test_partial_inventory_never_turns_missing_metadata_into_download(self):
        self.snapshot['enumeration_complete'] = False
        self.assertEqual(self.run_work()['status'], 'WAITING_FOR_INVENTORY')
        self.assertFalse(self.reads)

    def test_raw_not_in_this_inventory_is_unmatched_not_deleted(self):
        self.snapshot['files'] = []
        self.assertEqual(self.run_work()['inventory_unmatched'], 1)
        self.assertFalse(self.reads)

    def test_auth_hold_prevents_every_remote_read(self):
        self.state['auth_hold'] = True
        self.assertEqual(self.run_work()['status'], 'AUTH_HOLD_MANUAL_RESET_REQUIRED')
        self.assertFalse(self.reads)

    def test_size_and_unit_budgets_are_enforced(self):
        self.assertEqual(self.run_work(max_bytes=1)['inspected'], 0)
        self.assertFalse(self.reads)
        self.state = dict(schema=worker.SCHEMA)
        result = self.run_work(rows=[self.row, dict(self.row, 單元ID='second')], max_units=1)
        self.assertEqual(result['inspected'], 1)

    def test_changed_during_read_is_not_inspected(self):
        self.run_work(read_remote=lambda fid, size: (self.raw, dict(self.meta, version='2')))
        self.assertFalse(self.inspections)
        self.assertFalse(self.state['outcomes'])

    def test_md5_conflict_is_not_inspected(self):
        self.meta['md5Checksum'] = '0' * 32
        self.run_work()
        self.assertFalse(self.inspections)

    def test_corrupt_one_member_does_not_suppress_other_task(self):
        calls = []
        def inspector(raw, row, evidence):
            calls.append(row['單元ID'])
            if row['單元ID'] == 'unit-1':
                raise ValueError('CONTENT_ERROR')
            return {'rows': 1}
        self.run_work(rows=[self.row, dict(self.row, 單元ID='unit-2')], inspect=inspector)
        self.assertEqual(calls, ['unit-1', 'unit-2'])
        self.assertEqual({r['status'] for r in self.state['outcomes'].values()},
                         {'CONTENT_BLOCKED', 'PARTIAL_CONTENT_NOT_RELEASED'})

    def test_shards_are_disjoint_complete_and_package_affinity_is_preserved(self):
        rows = [dict(self.row, 原件參照=f'file_{i}/member{j}') for i in range(99) for j in (1, 2)]
        shards = [list(worker.shard_rows(rows, i, 3)) for i in range(3)]
        sets = [{r['原件參照'].split('/')[0] for r in shard} for shard in shards]
        self.assertEqual(sum(map(len, shards)), len(rows))
        self.assertEqual(len(set.union(*sets)), 99)
        for i in range(3):
            for j in range(i + 1, 3):
                self.assertFalse(sets[i] & sets[j])
        with self.assertRaises(ValueError):
            list(worker.shard_rows(rows, 0, 8))

    def test_successful_slice_never_promotes_eight_groups_or_releases_data(self):
        summary = worker.report(self.state, self.run_work())
        self.assertEqual(summary['approved_scopes'], [])
        self.assertEqual(summary['production_writes'], 0)
        self.assertEqual(summary['source_downloads'], 0)
        self.assertEqual(len(summary['groups']), 8)
        self.assertFalse(any(group['full_acceptance'] for group in summary['groups']))

    def test_existing_native_checker_is_used_without_granting_release(self):
        from scripts.v093_prelaunch_acceptance_batch import inspect_raw
        self.raw = json.dumps({'status': 200, 'data': [dict(date='2000-01-04', stock_id='1515',
                            open=10, max=12, min=9, close=11)]}).encode()
        self.row['RAW_SHA256'] = hashlib.sha256(self.raw).hexdigest()
        self.meta.update(size=str(len(self.raw)), md5Checksum=hashlib.md5(self.raw).hexdigest())
        self.run_work(inspect=inspect_raw)
        evidence = next(iter(self.state['outcomes'].values()))['content']
        self.assertEqual(evidence['ohlc_rows_checked'], 1)
        self.assertIs(evidence['analysis_release_approved'], False)

    def test_checkpoint_failure_stops_before_network_request(self):
        def fail_save():
            raise OSError('durable store unavailable')
        with self.assertRaises(OSError):
            self.run_work(persist=fail_save)
        self.assertFalse(self.reads)

    def test_inventory_entrypoint_uses_existing_paginated_collector_and_reuses_cursor(self):
        from scripts.v093_acceptance_remote_inventory import ROOT
        calls = []
        class FakeFiles:
            def list(inner, **kwargs):
                calls.append(kwargs['q'])
                if f"'{ROOT}' in parents" in kwargs['q']:
                    rows = [dict(id='year2000', name='2000', mimeType=worker.FOLDER, parents=[ROOT])]
                elif "'year2000' in parents" in kwargs['q']:
                    rows = [dict(id='sourceFM', name='FinMind', mimeType=worker.FOLDER, parents=['year2000'])]
                else:
                    rows = [dict(self.meta, parents=['sourceFM'])]
                return types.SimpleNamespace(execute=lambda **kw: {'files': rows})
        api = types.SimpleNamespace(files=lambda: FakeFiles())
        service_module = types.SimpleNamespace(service=lambda: api)
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            argv = ['worker', '--inventory-only', '--state', str(p / 'state'), '--out', str(p / 'out')]
            with patch.dict('sys.modules', {'scripts.annual_actual_firstpass': service_module}), patch('sys.argv', argv):
                worker.main()
                first_calls = len(calls)
                worker.main()
            self.assertEqual(first_calls, 3)
            self.assertEqual(len(calls), first_calls)
            inventory = worker.load(p / 'state/inventory.json.gz')
            self.assertEqual(inventory['phase'], 'DONE')
            self.assertEqual(set(inventory['files']), {'year2000', 'sourceFM', 'file_1'})
            self.assertEqual(json.loads((p / 'out/summary.json').read_text())['slice']['status'], 'INVENTORY_COMPLETE')


if __name__ == '__main__':
    unittest.main()
