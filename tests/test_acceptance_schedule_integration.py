"""Offline pipeline integration, using the real native parser and durable bytes.

The remote adapter is a bounded in-memory fixture, not a live Drive acceptance.
"""
import concurrent.futures
import copy
import gzip
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts import v093_acceptance_scheduler as worker
from scripts.v093_prelaunch_acceptance_batch import inspect_raw
from scripts.v093_acceptance_summary import combine


class CombinedPipelineTests(unittest.TestCase):
    def make_reports(self, inventory='INVENTORY_COMPLETE', workers='SLICE_COMPLETE_NOT_FULL_ACCEPTANCE'):
        return [worker.report(dict(lane=lane), dict(status=inventory if lane == 'inventory' else workers,
                                                      inspected=0 if lane == 'inventory' else 2))
                for lane in ('inventory', 'worker-0', 'worker-1', 'worker-2')]

    def test_three_workers_resume_and_combine_without_duplicate_package_reads(self):
        payloads, metadata, rows = {}, [], []
        for index in range(12):
            fid = f'package_{index}'
            native = json.dumps({'status': 200, 'data': [dict(date='2000-01-04', stock_id='1515',
                                open=10, max=12, min=9, close=99 if index == 3 else 11)]}).encode()
            members = [('a.json', native), ('b.json', native)] if index == 0 else [('', native)]
            if index == 0:
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, 'w') as archive:
                    for name, raw in members:
                        archive.writestr(name, raw)
                payload = buffer.getvalue()
            else:
                payload = native
            payloads[fid] = payload
            metadata.append(dict(id=fid, name=fid, mimeType='application/octet-stream',
                                 size=str(len(payload)), version='1',
                                 md5Checksum=hashlib.md5(payload).hexdigest()))
            for name, raw in members:
                rows.append({'來源': 'FinMind', '單元ID': fid + name, '資料集': 'TaiwanStockPrice',
                             '原件參照': fid + ('/' + name if name else ''), '已下載': '1',
                             '年份': '2000', '月份': '2000-01', '期間': '2000-01', '代碼': '1515',
                             'RAW_SHA256': hashlib.sha256(raw).hexdigest()})
        original_payloads = copy.deepcopy(payloads)
        snapshot = dict(enumeration_complete=True, files=metadata)
        lookup = {f['id']: f for f in metadata}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run_slice(index, limit):
                path = root / f'worker-{index}.json.gz'
                state = worker.load(path) if path.exists() else dict(schema=worker.SCHEMA, lane=f'worker-{index}')
                reads = []
                def read(fid, size):
                    reads.append(fid)
                    return payloads[fid], dict(lookup[fid])
                result = worker.work(worker.shard_rows(rows, index, 3), snapshot, state, read, inspect_raw,
                                     {'FinMind': 'native-parser-v1'}, max_units=limit,
                                     now=100000, persist=lambda: worker.save(path, state))
                self.assertEqual(len(reads), len(set(reads)))
                return worker.report(state, result), reads
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                first = list(pool.map(lambda i: run_slice(i, 1), range(3)))
                second = list(pool.map(lambda i: run_slice(i, 1000), range(3)))
                third = list(pool.map(lambda i: run_slice(i, 1000), range(3)))
            self.assertEqual(sum(s['slice']['inspected'] for s, _ in first + second), len(rows))
            self.assertTrue(all(not reads for _, reads in third))
            owners = {}
            for index in range(3):
                for batch in (first, second):
                    for fid in batch[index][1]:
                        self.assertEqual(owners.setdefault(fid, index), index)
            outcomes = [r for index in range(3) for r in worker.load(root / f'worker-{index}.json.gz')['outcomes'].values()]
            self.assertEqual(len(outcomes), len(rows))
            self.assertEqual(sum(r['status'] == 'CONTENT_BLOCKED' for r in outcomes), 1)
            inventory = worker.report(dict(lane='inventory'), dict(status='INVENTORY_COMPLETE', inspected=0))
            combined = combine([inventory] + [s for s, _ in second], 'success', 'success')
            self.assertEqual(combined['pipeline_status'], 'PARTIAL_EVIDENCE_NOT_FULL_ACCEPTANCE')
            self.assertEqual(combined['approved_scopes'], [])
            self.assertEqual(combined['full_groups_passed'], 0)
            self.assertEqual(payloads, original_payloads)
            self.assertEqual(combined['progress']['checked_items'],len(rows))
            self.assertEqual(combined['progress']['content_blocked_items'],1)
            self.assertEqual(combined['progress']['repaired_content_blockers'],0)

    def test_failure_and_bad_json_still_write_durable_report_bytes(self):
        import os, subprocess, sys
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);reports=root/'reports';reports.mkdir()
            (reports/'summary.json').write_text('invalid json')
            env=dict(os.environ,INVENTORY_RESULT='failure',CONTENT_RESULT='skipped',GITHUB_RUN_ID='offline-failure-test')
            run=subprocess.run([sys.executable,'-m','scripts.v093_acceptance_summary','--reports',str(reports),
                '--out',str(root/'summary.json'),'--journal',str(root/'journal')],env=env,capture_output=True)
            self.assertEqual(run.returncode,2,run.stderr.decode())
            stored=worker.load(root/'journal/summary.json.gz')
            self.assertEqual(stored['pipeline_status'],'INCOMPLETE')
            self.assertIn('UPSTREAM_JOB_NOT_SUCCESSFUL',stored['errors'])
            self.assertEqual(stored['run_id'],'offline-failure-test')
            self.assertIsNone(stored['progress'])

    def test_missing_report_is_not_a_successful_combined_run(self):
        result = combine(self.make_reports()[:-1], 'success', 'success')
        self.assertEqual(result['pipeline_status'], 'INCOMPLETE')
        self.assertEqual(result['missing_lanes'], ['worker-2'])

    def test_duplicate_worker_cannot_replace_a_missing_worker(self):
        reports = self.make_reports()
        reports[-1] = copy.deepcopy(reports[-2])
        result = combine(reports, 'success', 'success')
        self.assertIn('DUPLICATE_LANE:worker-1', result['errors'])
        self.assertEqual(result['pipeline_status'], 'INCOMPLETE')

    def test_inventory_waiting_is_distinct_from_executed_content(self):
        result = combine(self.make_reports('INVENTORY_INCOMPLETE', 'WAITING_FOR_INVENTORY'), 'success', 'success')
        self.assertEqual(result['pipeline_status'], 'WAITING_FOR_INVENTORY')
        self.assertFalse(result['errors'])

    def test_failed_job_blocks_combination_even_with_all_reports(self):
        result = combine(self.make_reports(), 'success', 'failure')
        self.assertEqual(result['pipeline_status'], 'INCOMPLETE')

    def test_auth_hold_cannot_be_counted_as_completed_content(self):
        reports = self.make_reports()
        reports[1]['slice']['status'] = 'AUTH_HOLD_MANUAL_RESET_REQUIRED'
        self.assertEqual(combine(reports, 'success', 'success')['pipeline_status'], 'INCOMPLETE')

    def test_invalid_counts_or_unexpected_release_are_rejected(self):
        for value in (True, -1, '2'):
            reports = self.make_reports()
            reports[1]['slice']['inspected'] = value
            self.assertEqual(combine(reports, 'success', 'success')['pipeline_status'], 'INCOMPLETE')
        reports = self.make_reports()
        reports[2]['approved_scopes'] = ['unexpected']
        self.assertEqual(combine(reports, 'success', 'success')['pipeline_status'], 'INCOMPLETE')

    def test_rerun_artifacts_have_explicit_overwrite_and_unique_worker_names(self):
        import yaml
        workflow = yaml.safe_load((Path(__file__).resolve().parents[1] /
                                  '.github/workflows/jarvis-acceptance-scheduled.yml').read_text())
        names = []
        for job in workflow['jobs'].values():
            for step in job['steps']:
                if step.get('uses') == 'actions/upload-artifact@v4':
                    self.assertIs(step['with']['overwrite'], True)
                    names.append(step['with']['name'])
        self.assertEqual(len(names), len(set(names)))
        self.assertIn('jarvis-acceptance-worker-${{ matrix.shard }}-${{ github.run_id }}', names)


if __name__ == '__main__':
    unittest.main()
