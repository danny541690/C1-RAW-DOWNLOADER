import concurrent.futures
import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import v093_stage06_ledger as m

H = 'a' * 64
OUT = 'b' * 64
PROOF = 'c' * 64


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'ledger.json'
        self.now = dt.datetime(2026, 10, 22, tzinfo=dt.timezone.utc).timestamp()
        self.ledger = m.Ledger(m.FileStore(self.path), lambda: self.now)
        self.unit = dict(source='TWSE', market='TSE', dataset='prices', security_id='2330',
                         period_start='2026-10-20', period_end='2026-10-20', native_unit_id='test-2330')

    def gap(self, kind='PARSER_MAPPING', owner='PRICE', **kw):
        return self.ledger.observe(self.unit, kind, owner, H, 'TEST_GAP', **kw)

    def task(self, kind='PARSER_MAPPING', owner='PRICE', approved=True, **kw):
        g = self.gap(kind, owner, **kw)
        if approved:
            self.ledger.approve_version(owner, 'V1', PROOF)
        return self.ledger.enqueue(g['gap_id'], H, 'V1', 'RULES_V1')

    def raw(self, prior=0):
        return self.task('RAW_MISSING', 'RAW', prior_attempts=prior,
                         attempt_evidence_sha256=PROOF, expected_evidence_sha256=PROOF)

    def claim(self, owner='PRICE', worker='worker', ttl=10):
        return self.ledger.claim(owner, worker, ttl)

    def receipt(self, task, kind='PARSER_MAPPING'):
        return dict(task_id=task['task_id'], owner=task['owner'], fence=task['fence'],
                    input_sha256=task['input_sha256'], processor_version=task['processor_version'],
                    output_sha256=OUT, validation_evidence_sha256=PROOF,
                    checks={k: True for k in m.RULES[kind][1]})

    def test_persistence_dedup_and_resolved_gap_does_not_reopen(self):
        self.task(); t = self.claim(); r = self.receipt(t)
        self.ledger.complete(t['task_id'], 'worker', t['fence'], r)
        self.ledger.complete(t['task_id'], 'worker', t['fence'], r)
        reopened = m.Ledger(m.FileStore(self.path))
        self.assertEqual(reopened.observe(self.unit, 'PARSER_MAPPING', 'PRICE', H, 'TEST_GAP')['status'], 'RESOLVED')
        self.assertEqual(len(reopened.snapshot()['gaps']), 1)
        self.assertEqual(len(reopened.snapshot()['tasks']), 1)

    def test_unapproved_task_never_claimed_until_version_approved(self):
        t = self.task(approved=False)
        self.assertEqual(t['status'], 'BLOCKED_APPROVAL')
        self.assertIsNone(self.claim())
        self.ledger.approve_version('PRICE', 'V1', PROOF)
        self.assertEqual(self.claim()['task_id'], t['task_id'])

    def test_wrong_owner_and_input_hash_rejected(self):
        g = self.gap()
        with self.assertRaisesRegex(ValueError, 'INPUT_EVIDENCE_HASH'):
            self.ledger.enqueue(g['gap_id'], OUT, 'V1', 'R1')
        with self.assertRaisesRegex(ValueError, 'INVALID_GAP_OWNER'):
            self.gap('RAW_MISSING', 'PRICE')
        self.task()
        self.assertIsNone(self.claim('QA1'))

    def test_two_independent_clients_claim_once(self):
        self.task()
        def claim(i):
            return m.Ledger(m.FileStore(self.path), lambda: self.now).claim('PRICE', 'worker' + str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertEqual(sum(t is not None for t in results), 1)

    def test_cas_stale_writer_cannot_overwrite(self):
        store = m.FileStore(self.path)
        old, state = store.read()
        self.gap()
        self.assertFalse(store.cas(old, state))
        self.assertEqual(len(store.read()[1]['gaps']), 1)

    def test_transaction_retries_conflict_without_duplicate(self):
        store = self.ledger.store
        real = store.cas
        calls = []
        def once(expected, state):
            calls.append(1)
            return False if len(calls) == 1 else real(expected, state)
        with patch.object(store, 'cas', side_effect=once):
            self.gap()
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(self.ledger.snapshot()['gaps']), 1)

    def test_atomic_failure_preserves_previous_file(self):
        self.gap(); before = self.path.read_bytes()
        with patch.object(m.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.ledger.approve_version('PRICE', 'V1', PROOF)
        self.assertEqual(self.path.read_bytes(), before)

    def test_expired_fence_cannot_finish(self):
        self.task(); a = self.claim(); self.now += 11; b = self.claim(worker='new')
        self.assertGreater(b['fence'], a['fence'])
        with self.assertRaises(m.StaleClaim):
            self.ledger.complete(a['task_id'], 'worker', a['fence'], self.receipt(a))
        self.ledger.complete(b['task_id'], 'new', b['fence'], self.receipt(b))

    def test_versioned_tasks_cannot_run_same_unit_concurrently(self):
        t = self.task(); self.ledger.approve_version('PRICE', 'V2', PROOF)
        self.ledger.enqueue(t['gap_id'], H, 'V2', 'RULES_V1')
        a = self.claim(); self.assertIsNone(self.claim(worker='other'))
        self.ledger.complete(a['task_id'], 'worker', a['fence'], self.receipt(a))
        self.assertIsNone(self.claim(worker='other'))
        self.assertIn('CANCELLED_SUPERSEDED', {t['status'] for t in self.ledger.snapshot()['tasks'].values()})

    def test_receipt_identity_and_required_checks(self):
        self.task(); t = self.claim(); receipt = self.receipt(t)
        bad = copy.deepcopy(receipt); bad['input_sha256'] = OUT
        with self.assertRaisesRegex(ValueError, 'RECEIPT_IDENTITY'):
            self.ledger.complete(t['task_id'], 'worker', t['fence'], bad)
        bad = copy.deepcopy(receipt); bad['checks']['security_ok'] = False
        with self.assertRaisesRegex(ValueError, 'GAP_SPECIFIC'):
            self.ledger.complete(t['task_id'], 'worker', t['fence'], bad)
        self.assertNotEqual(self.ledger.snapshot()['gaps'][t['gap_id']]['status'], 'RESOLVED')

    def test_numeric_and_pit_require_their_own_evidence_checks(self):
        for kind in ('NUMERIC_CONFLICT', 'PIT_UNKNOWN'):
            with self.subTest(kind=kind):
                self.unit['native_unit_id'] = kind
                self.task(kind); t = self.claim()
                with self.assertRaisesRegex(ValueError, 'GAP_SPECIFIC'):
                    self.ledger.complete(t['task_id'], 'worker', t['fence'], self.receipt(t))
                self.ledger.complete(t['task_id'], 'worker', t['fence'], self.receipt(t, kind))
        result = m.summary(self.ledger.snapshot())
        self.assertFalse(result['numeric_verified']); self.assertFalse(result['pit_verified'])

    def test_raw_requires_expected_registry_evidence(self):
        g = self.gap('RAW_MISSING', 'RAW')
        with self.assertRaisesRegex(ValueError, 'EXPECTED_UNIT_EVIDENCE'):
            self.ledger.enqueue(g['gap_id'], H, 'V1', 'R1')

    def test_unknown_attempts_hold_raw_and_prior_count_never_decreases(self):
        t = self.task('RAW_MISSING', 'RAW', expected_evidence_sha256=PROOF)
        self.assertEqual(t['status'], 'BLOCKED_ATTEMPT_RECONCILIATION')
        self.assertIsNone(self.claim('RAW'))
        self.gap('RAW_MISSING', 'RAW', prior_attempts=3, attempt_evidence_sha256=PROOF)
        self.gap('RAW_MISSING', 'RAW', prior_attempts=1, attempt_evidence_sha256=PROOF)
        self.assertEqual(next(iter(self.ledger.snapshot()['attempts'].values()))['used'], 3)
        self.assertIsNotNone(self.claim('RAW'))

    def test_fourth_attempt_is_final_and_new_version_does_not_reset(self):
        self.raw(3); t = self.claim('RAW')
        a = self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'request4')
        self.assertTrue(a['send_allowed']); self.assertEqual(a['record']['attempt'], 4)
        self.ledger.end_request(t['task_id'], 'worker', t['fence'], 'request4', OUT)
        a = self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'request5')
        self.assertFalse(a['send_allowed']); self.assertEqual(a['reason'], 'RETRY_EXHAUSTED')
        self.assertEqual(self.ledger.enqueue(t['gap_id'], H, 'V2', 'R2')['status'], 'RETRY_EXHAUSTED')
        self.assertEqual(next(iter(self.ledger.snapshot()['attempts'].values()))['used'], 4)

    def test_duplicate_request_id_never_authorizes_second_send(self):
        self.raw(); t = self.claim('RAW')
        self.assertTrue(self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r1')['send_allowed'])
        self.assertFalse(self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r1')['send_allowed'])
        with self.assertRaisesRegex(ValueError, 'RECONCILE_UNKNOWN'):
            self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r2')
        with self.assertRaisesRegex(ValueError, 'UNRECONCILED_HTTP'):
            self.ledger.complete(t['task_id'], 'worker', t['fence'], self.receipt(t, 'RAW_MISSING'))

    def test_crash_after_intent_requires_reconcile_and_reuses_saved_response(self):
        self.raw(3); t = self.claim('RAW')
        self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r4')
        self.now += 11; self.assertIsNone(self.claim('RAW'))
        self.ledger.reconcile(t['task_id'], 'r4', PROOF, OUT)
        t = self.claim('RAW', worker='new')
        with self.assertRaisesRegex(ValueError, 'SAVED_RESPONSE_MUST_BE_REUSED'):
            self.ledger.begin_request(t['task_id'], 'new', t['fence'], 'r5')
        self.ledger.complete(t['task_id'], 'new', t['fence'], self.receipt(t, 'RAW_MISSING'))
        self.assertEqual(next(iter(self.ledger.snapshot()['attempts'].values()))['used'], 4)

    def test_lost_fourth_response_remains_exhausted(self):
        self.raw(3); t = self.claim('RAW')
        self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r4')
        self.now += 11; self.claim('RAW')
        result = self.ledger.reconcile(t['task_id'], 'r4', PROOF)
        self.assertEqual(result['status'], 'RETRY_EXHAUSTED'); self.assertIsNone(self.claim('RAW'))

    def test_raw_cannot_close_without_observed_matching_saved_response(self):
        self.raw(); t = self.claim('RAW'); receipt = self.receipt(t, 'RAW_MISSING')
        with self.assertRaisesRegex(ValueError, 'SAVED_RAW_RESPONSE'):
            self.ledger.complete(t['task_id'], 'worker', t['fence'], receipt)
        self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r1')
        self.ledger.end_request(t['task_id'], 'worker', t['fence'], 'r1', OUT)
        self.ledger.complete(t['task_id'], 'worker', t['fence'], receipt)

    def test_future_requests_and_transform_downloads_forbidden(self):
        self.unit['period_end'] = '2026-10-31'; self.raw(); t = self.claim('RAW')
        with self.assertRaisesRegex(ValueError, 'FUTURE_UNIT'):
            self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'future')
        self.task(); t = self.claim()
        with self.assertRaisesRegex(ValueError, 'NETWORK_DOWNLOAD_NOT_ALLOWED'):
            self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'wrong-owner')

    def test_priority_then_newest_month(self):
        old = self.task()
        self.unit = dict(self.unit, native_unit_id='new', period_end='2026-10-21')
        new = self.task()
        self.assertEqual(self.claim()['task_id'], new['task_id'])
        self.now += 11
        self.unit = dict(self.unit, native_unit_id='blocking', period_start='2026-10-19', period_end='2026-10-19')
        g = self.gap(); blocking = self.ledger.enqueue(g['gap_id'], H, 'V1', 'R1', priority=10)
        self.assertEqual(self.claim()['task_id'], blocking['task_id'])

    def test_import_quarantine_is_idempotent_and_never_downloads(self):
        state = {'units': {'x': dict(status='QUARANTINED', source='TWSE', category='prices',
                                    period='2026-10', raw_sha256=H, error='NO_SECURITY_ID')}}
        with patch.object(m.urllib.request, 'urlopen', side_effect=AssertionError('unexpected network')):
            for _ in range(2):
                self.assertEqual(m.import_quarantine(self.ledger, 'PRICE', state, 'CANDIDATE_V1'), 1)
        result = m.summary(self.ledger.snapshot())
        self.assertEqual((result['gaps'], result['tasks']), (1, 1))
        self.assertEqual(result['task_statuses'], {'BLOCKED_APPROVAL': 1})
        self.assertEqual(result['source_downloads_performed'], 0)

    def test_live_lease_or_arbitrary_github_path_forbidden(self):
        for path in ('.github/live-state/five-stage-leases.json', 'config/x.json', '.github/live-state/stage06-../x.json'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                m.GitHubStore('owner/repo', path, 'unused')

    def test_saved_fourth_response_survives_crash_before_validation(self):
        self.raw(3); t = self.claim('RAW')
        self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r4')
        self.ledger.end_request(t['task_id'], 'worker', t['fence'], 'r4', OUT)
        self.now += 11; recovered = self.claim('RAW', worker='new')
        self.assertTrue(recovered['validation_only'])
        self.ledger.complete(recovered['task_id'], 'new', recovered['fence'], self.receipt(recovered, 'RAW_MISSING'))

    def test_failed_validation_preserves_attempt_count(self):
        self.raw(2); t = self.claim('RAW')
        self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r3')
        self.ledger.end_request(t['task_id'], 'worker', t['fence'], 'r3', OUT)
        self.ledger.fail(t['task_id'], 'worker', t['fence'], 'INVALID_PAYLOAD', PROOF)
        t = self.claim('RAW')
        self.assertEqual(self.ledger.begin_request(t['task_id'], 'worker', t['fence'], 'r4')['record']['attempt'], 4)

    def test_unidentified_receipts_are_held_not_silently_dropped(self):
        state = {'month': '2026-10', 'units': {'legacy': dict(status='QUARANTINED', raw_sha256=H, unit_id='legacy')}}
        for _ in range(2):
            m.import_quarantine(self.ledger, 'PRICE', state, 'V1')
        result = m.summary(self.ledger.snapshot())
        self.assertEqual((result['identity_holds'], result['gaps'], result['tasks']), (1, 0, 0))


if __name__ == '__main__':
    unittest.main()
