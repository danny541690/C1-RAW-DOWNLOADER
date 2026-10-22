"""Regression checks for concurrent stage-six publication and temporary API faults."""
import io
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.v093_stage06_fenced_store import FencedGitHubStore
from scripts.v093_stage06_ledger import FileStore, Ledger, StaleClaim, empty


class GitResilienceTests(unittest.TestCase):
    def store(self):
        return FencedGitHubStore('test/repo','.github/live-state/stage06-test.json','test',
            'RECONCILE','POOL_STAGE06_REPAIR_V1','123/RECONCILE',1,clock=lambda:1000)

    @staticmethod
    def error(code):
        return urllib.error.HTTPError('https://api.github.com/test',code,'failure',{},io.BytesIO())

    def test_server_error_recovers_with_bounded_retry(self):
        store=self.store()
        with patch('scripts.v093_stage06_fenced_store.open_json',
                   side_effect=[self.error(500),({'ok':True},{'remaining':123})]) as call, \
             patch('scripts.v093_stage06_fenced_store.time.sleep'):
            self.assertEqual(store._api('GET','/git/ref/heads/main'),{'ok':True})
        self.assertEqual(call.call_count,2)
        self.assertEqual(store.remaining,123)

    def test_persistent_server_error_stops_after_four_attempts(self):
        with patch('scripts.v093_stage06_fenced_store.open_json',side_effect=self.error(503)) as call, \
             patch('scripts.v093_stage06_fenced_store.time.sleep'):
            with self.assertRaises(urllib.error.HTTPError):self.store()._api('GET','/git/ref/heads/main')
        self.assertEqual(call.call_count,4)

    def test_permission_error_is_not_blindly_retried(self):
        with patch('scripts.v093_stage06_fenced_store.open_json',side_effect=self.error(403)) as call:
            with self.assertRaises(urllib.error.HTTPError):self.store()._api('GET','/git/ref/heads/main')
        self.assertEqual(call.call_count,1)

    def publication(self,moved):
        store=self.store();head=['old']
        store._lease=Mock(return_value={'expires_at':2000})
        def api(method,path,payload=None):
            if path=='/git/ref/heads/main':return {'object':{'sha':head[0]}}
            if method=='GET':return {'tree':{'sha':'tree'}}
            if path=='/git/trees':return {'sha':'candidate-tree'}
            if path=='/git/commits':return {'sha':'candidate-commit'}
            self.assertEqual(method,'PATCH')
            self.assertFalse(payload['force'])
            if moved:head[0]='other-writer'
            raise self.error(403)
        store._api=Mock(side_effect=api)
        return store

    def test_obsolete_head_permission_response_reloads_without_publication(self):
        store=self.publication(True)
        self.assertFalse(store.cas('old',empty()))
        self.assertIsNone(store._read_cache)
        self.assertEqual(store._lease_cache,{})

    def test_real_permission_denial_still_fails_closed(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.publication(False).cas('old',empty())

    def test_extended_contention_retries_recompute_from_persisted_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=FileStore(Path(tmp)/'state.json')
            store.transaction_attempts=FencedGitHubStore.transaction_attempts
            original=store.cas;calls=[0]
            def cas(expected,doc):
                calls[0]+=1
                return False if calls[0]<=20 else original(expected,doc)
            store.cas=cas;store.conflict_backoff=Mock()
            Ledger(store).transaction(lambda doc,now:doc.update(marker='saved'))
            self.assertEqual(calls[0],21)
            self.assertEqual(store.read()[1]['marker'],'saved')

    def test_changed_owner_still_blocks_publication(self):
        store=self.store();store._lease_cache['old']={'owner':'other','fence':2,'expires_at':2000}
        with self.assertRaises(StaleClaim):store.cas('old',empty())


if __name__=='__main__':unittest.main()
