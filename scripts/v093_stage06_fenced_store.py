"""Publish a repair receipt only if its owner lease is still in the same Git head.

Drive files are immutable candidates. A non-forced branch fast-forward publishes
the ledger using the exact parent whose lease was checked. A changed lease or any
other commit rejects publication; the transaction reloads and validates again.
"""
import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from scripts.v093_stage06_ledger import GitHubStore, StaleClaim, empty, validate


class FencedGitHubStore(GitHubStore):
    owner_fenced = True

    def __init__(self, repo, path, token, stage, lease_key, owner, fence,
                 lease_path='.github/live-state/five-stage-leases.json', clock=time.time, test_only=False):
        super().__init__(repo, path, token)
        if stage not in ('RAW', 'QA1', 'PRICE', 'FINANCIAL', 'CHIP', 'RECONCILE') or type(fence) is not int or fence <= 0:
            raise ValueError('INVALID_OWNER_BINDING')
        if not lease_key or not owner:
            raise ValueError('INVALID_OWNER_BINDING')
        if lease_path == '.github/live-state/five-stage-leases.json':
            plan = json.loads((Path(__file__).resolve().parents[1] / 'config/v093_execution_plan_20261021.json').read_text())
            expected_key = 'POOL_STAGE06_REPAIR_V1' if stage == 'RECONCILE' else (
                ('POOL_RAW' + plan['lease_suffix']) if stage == 'RAW' else
                'POOL_CONSUMER' + plan['stage_lease_suffix'][stage])
            if lease_key != expected_key:
                raise ValueError('STAGE_OWNER_POOL_MISMATCH')
        if lease_path != '.github/live-state/five-stage-leases.json':
            if not test_only or not re.fullmatch(r'\.github/live-state/stage06-integration-leases-[A-Za-z0-9_-]+\.json', lease_path):
                raise ValueError('INVALID_LEASE_PATH')
        if path == lease_path:
            raise ValueError('LEDGER_AND_OWNER_LEASE_MUST_DIFFER')
        self.base = 'https://api.github.com/repos/' + repo
        self.path, self.stage, self.lease_key = path, stage, lease_key
        self.owner, self.fence, self.lease_path, self.clock = owner, fence, lease_path, clock

    def _api(self, method, path, payload=None):
        request = urllib.request.Request(self.base + path, method=method, headers=self.headers,
            data=json.dumps(payload).encode() if payload is not None else None)
        with urllib.request.urlopen(request, timeout=35) as response:
            return json.load(response)

    def _json_at(self, head, path, missing=False):
        try:
            result = self._api('GET', '/contents/' + path + '?ref=' + head)
            return json.loads(base64.b64decode(result['content']))
        except urllib.error.HTTPError as exc:
            if missing and exc.code == 404:
                return empty()
            raise

    def _lease(self, head):
        state = self._json_at(head, self.lease_path)
        lease = state.get('jobs', {}).get(self.lease_key, {}).get('lease') or {}
        # Stop at least 60 seconds before expiry; each HTTP call times out at 35.
        # A changed owner/fence is independently protected by the branch CAS.
        if lease.get('owner') != self.owner or lease.get('fence') != self.fence or lease.get('expires_at', 0) <= self.clock() + 60:
            raise StaleClaim('LIVE_OWNER_LEASE_CHANGED_OR_EXPIRED')
        return lease

    def read(self):
        head = self._api('GET', '/git/ref/heads/main')['object']['sha']
        self._lease(head)
        return head, validate(self._json_at(head, self.path, missing=True))

    def cas(self, expected, doc):
        validate(doc)
        # This check also bounds claims to the enclosing owner's expiration.
        lease = self._lease(expected)
        for task in doc['tasks'].values():
            claim = task.get('claim')
            if task['owner'] == self.stage and claim and claim['worker'] == self.owner:
                claim['expires_at'] = min(claim['expires_at'], lease['expires_at'] - 60)
        raw = json.dumps(doc, sort_keys=True, separators=(',', ':'))
        if len(raw.encode()) > 800_000:
            raise ValueError('LEDGER_SHARD_REQUIRED')
        if self._api('GET', '/git/ref/heads/main')['object']['sha'] != expected:
            return False
        parent = self._api('GET', '/git/commits/' + expected)
        tree = self._api('POST', '/git/trees', dict(base_tree=parent['tree']['sha'], tree=[
            dict(path=self.path, mode='100644', type='blob', content=raw)]))
        commit = self._api('POST', '/git/commits', dict(message='stage06: owner-fenced repair ledger publication',
            parents=[expected], tree=tree['sha']))
        self._lease(expected)  # Check wall-clock expiration again after API calls.
        try:
            # A commit with exactly expected as parent cannot fast-forward a
            # different intervening head. No force update is ever permitted.
            self._api('PATCH', '/git/refs/heads/main', dict(sha=commit['sha'], force=False))
            return True
        except urllib.error.HTTPError as exc:
            if exc.code in (409, 422):
                current = self._api('GET', '/git/ref/heads/main')['object']['sha']
                if current != expected:
                    return False
            raise
