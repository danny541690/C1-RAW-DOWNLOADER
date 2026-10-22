import base64
import copy
import hashlib
import io
import json
import unittest
import urllib.error
from unittest.mock import Mock

from scripts.v093_stage06_drive_artifacts import DriveImmutableArtifacts
from scripts.v093_stage06_fenced_store import FencedGitHubStore
from scripts.v093_stage06_ledger import Ledger, StaleClaim, empty
from scripts.v093_stage06_owner_replay import replay_one


def sha(raw): return hashlib.sha256(raw).hexdigest()


class MemoryGit(FencedGitHubStore):
    """Git graph double: branch moves only to a direct child, never by force."""
    def __init__(self):
        self.now = 1000
        super().__init__('test/repo', '.github/live-state/stage06-test.json', 'unused', 'PRICE',
            'POOL', 'owner', 1, clock=lambda: self.now, test_only=True,
            lease_path='.github/live-state/stage06-integration-leases-unit.json')
        self.head = 'initial'
        self.snapshots = {'initial': {self.lease_path: {'jobs': {'POOL': {'lease': {
            'owner': 'owner', 'fence': 1, 'expires_at': 2000}}}}, self.path: empty()}}
        self.trees = {}; self.commits = {}; self.before_patch = None; self.requests = []

    def advance(self, lease=None):
        state = copy.deepcopy(self.snapshots[self.head])
        if lease is not None: state[self.lease_path]['jobs']['POOL']['lease'] = lease
        self.head += '-next'; self.snapshots[self.head] = state

    def _api(self, method, path, payload=None):
        self.requests.append((method, path, copy.deepcopy(payload)))
        if path == '/git/ref/heads/main': return {'object': {'sha': self.head}}
        if path.startswith('/contents/'):
            file, ref = path[len('/contents/'):].split('?ref=')
            return {'content': base64.b64encode(json.dumps(self.snapshots[ref][file]).encode()).decode()}
        if method == 'GET' and path.startswith('/git/commits/'):
            return {'tree': {'sha': path.rsplit('/', 1)[1]}}
        if path == '/git/trees':
            key = 'tree' + str(len(self.trees)); self.trees[key] = copy.deepcopy(payload)
            return {'sha': key}
        if path == '/git/commits':
            key = 'commit' + str(len(self.commits)); self.commits[key] = copy.deepcopy(payload)
            return {'sha': key}
        if method == 'PATCH':
            if self.before_patch:
                callback, self.before_patch = self.before_patch, None; callback()
            commit = self.commits[payload['sha']]
            if payload['force'] is not False: raise AssertionError('force update forbidden')
            if commit['parents'] != [self.head]:
                raise urllib.error.HTTPError('test', 422, 'not fast forward', {}, io.BytesIO())
            state = copy.deepcopy(self.snapshots[self.head])
            for item in self.trees[commit['tree']]['tree']: state[item['path']] = json.loads(item['content'])
            self.head = payload['sha']; self.snapshots[self.head] = state
            return {'object': {'sha': self.head}}
        raise AssertionError((method, path))


class FencedPublicationTests(unittest.TestCase):
    def test_success_preserves_owner_lease_and_publishes_only_ledger(self):
        store = MemoryGit(); head, state = store.read()
        state['revision'] = 1
        self.assertTrue(store.cas(head, state))
        self.assertEqual(store.snapshots[store.head][store.lease_path], store.snapshots['initial'][store.lease_path])
        self.assertEqual(store.read()[1]['revision'], 1)

    def test_owner_changes_between_final_check_and_ref_update_rejects_publication(self):
        store = MemoryGit(); head, state = store.read()
        state['revision'] = 99
        store.before_patch = lambda: store.advance(dict(owner='new', fence=2, expires_at=3000))
        self.assertFalse(store.cas(head, state))
        self.assertEqual(store.snapshots[store.head][store.path]['revision'], 0)
        with self.assertRaises(StaleClaim): store.read()

    def test_unrelated_head_change_retries_and_preserves_external_commit(self):
        store = MemoryGit(); store.before_patch = store.advance
        ledger = Ledger(store, lambda: 1000)
        ledger.approve_version('PRICE', 'V1', 'a' * 64)
        self.assertIn('PRICE:V1', store.read()[1]['approved_versions'])
        self.assertTrue(any(c['parents'] == ['initial-next'] for c in store.commits.values()))

    def test_expired_or_near_expiry_owner_rejected(self):
        for instant in (1940, 1999, 2000):
            with self.subTest(now=instant):
                store = MemoryGit(); store.now = instant
                with self.assertRaises(StaleClaim): store.read()

    def test_expiration_during_git_object_creation_prevents_ref_write(self):
        store = MemoryGit(); head, state = store.read(); original = store._api
        def api(method, path, payload=None):
            result = original(method, path, payload)
            if path == '/git/commits': store.now = 2000
            return result
        store._api = api
        with self.assertRaises(StaleClaim): store.cas(head, state)
        self.assertFalse(any(method == 'PATCH' for method, _, _ in store.requests))

    def test_claim_deadline_cannot_outlive_enclosing_owner(self):
        store = MemoryGit(); head, state = store.read()
        state['tasks']['task'] = {'owner': 'PRICE', 'claim': {'worker': 'owner', 'expires_at': 9000}}
        store.cas(head, state)
        self.assertEqual(store.read()[1]['tasks']['task']['claim']['expires_at'], 1940)

    def test_wrong_fence_is_rejected(self):
        store = MemoryGit(); store.fence = 2
        with self.assertRaises(StaleClaim): store.read()

    def test_price_cannot_use_raw_owner_pool(self):
        with self.assertRaisesRegex(ValueError, 'STAGE_OWNER_POOL_MISMATCH'):
            FencedGitHubStore('test/repo', '.github/live-state/stage06-test.json', 'unused',
                'PRICE', 'POOL_RAW_REPLAN_201404_V1', 'owner', 1)

    def test_test_lease_override_requires_explicit_test_path(self):
        with self.assertRaises(ValueError):
            FencedGitHubStore('test/repo', '.github/live-state/stage06-test.json', 'x', 'PRICE', 'POOL',
                'owner', 1, lease_path='arbitrary.json', test_only=True)


class DriveDouble:
    def __init__(self):
        self.objects = {}; self.sequence = 0; self.create_count = 0
        self.lost_response = False; self.before_create = None; self.page_size = 100
    def files(self): return self
    @staticmethod
    def request(fn):
        req = Mock(); req.execute.side_effect = lambda **kw: fn(); return req
    def get(self, **kw):
        return self.request(lambda: {'id': 'test-folder', 'mimeType': 'application/vnd.google-apps.folder',
            'appProperties': {'jarvis_stage06_scope': 'ISOLATED_TEST_ONLY'}})
    def list(self, **kw):
        def response():
            prefix = kw['q'].split("name contains '")[1].split("'")[0]
            values = [dict(id=i, name=v['name']) for i, v in sorted(self.objects.items()) if v['name'].startswith(prefix)]
            start = int(kw.get('pageToken') or 0); stop = start + self.page_size
            result = {'files': values[start:stop]}
            if stop < len(values): result['nextPageToken'] = str(stop)
            return result
        return self.request(response)
    def get_media(self, **kw): return self.request(lambda: self.objects[kw['fileId']]['raw'])
    def create(self, **kw):
        def response():
            if self.before_create: self.before_create()
            self.sequence += 1; self.create_count += 1; fid = str(self.sequence)
            raw = kw['media_body'].getbytes(0, kw['media_body'].size())
            self.objects[fid] = dict(name=kw['body']['name'], raw=raw)
            if self.lost_response:
                self.lost_response = False; raise OSError('response lost after save')
            return {'id': fid}
        return self.request(response)


class DrivePublicationTests(unittest.TestCase):
    def setUp(self):
        self.api = DriveDouble(); self.backend = DriveImmutableArtifacts(self.api, 'test-folder')
    def test_save_readback_and_same_bytes_reuse_without_another_upload(self):
        self.backend.put_immutable('key', b'bytes', lambda: None)
        self.backend.put_immutable('key', b'bytes', lambda: None)
        self.assertEqual(self.api.create_count, 1)
        self.assertEqual(self.backend.read('key'), b'bytes')
    def test_lost_upload_response_reconciles_existing_bytes(self):
        self.api.lost_response = True
        self.backend.put_immutable('key', b'bytes', lambda: None)
        self.assertEqual(self.api.create_count, 1)
    def test_different_bytes_never_overwrite(self):
        self.backend.put_immutable('key', b'one', lambda: None)
        with self.assertRaisesRegex(ValueError, 'KEY_CONFLICT'):
            self.backend.put_immutable('key', b'two', lambda: None)
        self.assertEqual(self.backend.read('key'), b'one')
    def test_duplicate_identical_objects_reconcile_across_pages(self):
        self.backend.put_immutable('key', b'one', lambda: None)
        self.api.objects['extra'] = copy.deepcopy(self.api.objects['1']); self.api.page_size = 1
        self.assertEqual(self.backend.read('key'), b'one')
    def test_conflicting_content_hashes_fail_closed(self):
        self.backend.put_immutable('key', b'one', lambda: None)
        self.api.objects['other'] = {'name': sha(b'key') + '-' + sha(b'two') + '.artifact', 'raw': b'two'}
        with self.assertRaisesRegex(ValueError, 'KEY_CONFLICT'): self.backend.read('key')
    def test_corrupt_remote_bytes_fail_readback(self):
        self.backend.put_immutable('key', b'one', lambda: None); self.api.objects['1']['raw'] = b'bad'
        with self.assertRaisesRegex(ValueError, 'READBACK_HASH'): self.backend.read('key')
    def test_expired_owner_after_upload_leaves_candidate_without_success(self):
        active = [True]
        def guard():
            if not active[0]: raise StaleClaim('expired')
        self.api.before_create = lambda: active.__setitem__(0, False)
        with self.assertRaises(StaleClaim): self.backend.put_immutable('key', b'one', guard)
        self.assertEqual(self.api.create_count, 1)
    def test_public_reference_does_not_expose_private_drive_ids(self):
        self.backend.put_immutable('key', b'one', lambda: None)
        self.assertNotIn('file_id', self.backend.reference('key'))
        self.assertEqual(self.backend.private_reference('key')['file_id'], '1')
    def test_unfenced_ledger_cannot_use_remote_backend(self):
        ledger = Mock(); ledger.store.owner_fenced = False
        with self.assertRaisesRegex(ValueError, 'OWNER_FENCED_LEDGER_REQUIRED'):
            replay_one(ledger, 'PRICE', 'owner', 'V1', 'R1', None, None, None, self.backend, lambda: None)
    def test_production_backend_requires_separate_activation(self):
        with self.assertRaisesRegex(ValueError, 'NOT_ACTIVATED'):
            DriveImmutableArtifacts(self.api, 'test-folder', test_only=False)


if __name__ == '__main__': unittest.main()
