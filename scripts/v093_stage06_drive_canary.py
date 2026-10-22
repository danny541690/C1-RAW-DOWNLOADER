"""Real Drive + GitHub owner-fenced integration in dedicated test state only."""
import base64
import io
import json
import os
import tempfile
import time
import urllib.error
from pathlib import Path

from googleapiclient.http import MediaIoBaseUpload
from scripts.annual_actual_firstpass import service
from scripts.v093_five_stage_durable_gate import acquire, commit
from scripts.v093_stage06_drive_artifacts import DriveImmutableArtifacts
from scripts.v093_stage06_fenced_store import FencedGitHubStore
from scripts.v093_stage06_ledger import FileStore, GitHubStore, Ledger, StaleClaim, digest
from scripts.v093_stage06_native_repair import VERSION, transform, validate_output
from scripts.v093_stage06_owner_replay import replay_one


def seed_json(api, path, payload):
    """Create exactly this test snapshot, reconciling unrelated branch conflicts."""
    if not path.startswith('.github/live-state/stage06-') or not path.endswith('.json'):
        raise ValueError('ISOLATED_TEST_PATH_REQUIRED')
    body = dict(message='stage06: initialize isolated integration snapshot',
                content=base64.b64encode(json.dumps(payload, sort_keys=True).encode()).decode())
    for _ in range(16):
        try:
            current = api('GET', '/contents/' + path)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
        else:
            if json.loads(base64.b64decode(current['content'])) != payload:
                raise ValueError('DIFFERENT_INTEGRATION_SNAPSHOT_ALREADY_EXISTS')
            return
        try:
            api('PUT', '/contents/' + path, body)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in (409, 422):
                raise
        except OSError:
            # A timed-out create may already have committed. Re-read first.
            pass
    raise ValueError('INTEGRATION_INITIALIZATION_CONFLICT_EXHAUSTED')


def main():
    repo = os.environ['GITHUB_REPOSITORY']; token = os.environ['GH_TOKEN']
    run = os.environ['GITHUB_RUN_ID'] + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    prefix = '.github/live-state/stage06-'
    lease_path = prefix + 'integration-leases-' + run + '.json'
    healthy_path = prefix + 'drive-ledger-' + run + '.json'
    race_path = prefix + 'drive-race-' + run + '.json'
    lease_key = 'POOL_CONSUMER_PRICE_REPLAN_201404_V1'
    offset = [0]
    clock = lambda: time.time() + offset[0]
    owner_a, owner_b = run + '/PRICE-A', run + '/PRICE-B'
    # These Git writes never reference the live five-stage manifest.
    probe = FencedGitHubStore(repo, healthy_path, token, 'PRICE', lease_key, owner_a, 1,
        lease_path=lease_path, clock=clock, test_only=True)
    seed_json(probe._api, lease_path, {'version': 'ISOLATED_TEST_ONLY', 'jobs': {lease_key: {}}})
    lease_url = probe.base + '/contents/' + lease_path
    fence_a = acquire(lease_url, token, lease_key, owner_a, now=int(clock()), ttl=1800)

    drive = service()
    found = drive.files().list(q="name = 'C1_0.93_CHATGPT_CONTINUATION.md' and trashed = false",
        fields='nextPageToken,files(id,parents)', pageSize=100).execute(num_retries=0)
    if found.get('nextPageToken') or len(found.get('files', [])) != 1 or len(found['files'][0].get('parents', [])) != 1:
        raise ValueError('UNIQUE_SYSTEM_CHECKPOINT_FOLDER_REQUIRED')
    parent = found['files'][0]['parents'][0]
    folder = drive.files().create(body=dict(name='STAGE06_DRIVE_PUBLISH_TEST_' + run,
        parents=[parent], mimeType='application/vnd.google-apps.folder',
        appProperties={'jarvis_stage06_scope': 'ISOLATED_TEST_ONLY'}), fields='id').execute(num_retries=0)['id']
    artifacts = DriveImmutableArtifacts(drive, folder)
    fixture_root = Path('tests/fixtures/stage06_native')
    entries = json.loads((fixture_root / 'manifest.json').read_text())
    raw_by_id = {e['unit']['native_unit_id']: (fixture_root / (e['unit']['native_unit_id'] + '.json')).read_bytes() for e in entries}

    def seed(path, selected, rules):
        with tempfile.TemporaryDirectory() as tmp:
            producer = Ledger(FileStore(Path(tmp) / 'ledger.json'))
            producer.approve_version('PRICE', VERSION, digest(dict(scope='ISOLATED_TEST_ONLY', run=run)))
            for e in selected:
                gap = producer.observe(e['unit'], 'PARSER_MAPPING', 'PRICE', e['input_sha256'], 'INTEGRATION_TEST')
                producer.enqueue(gap['gap_id'], e['input_sha256'], VERSION, rules)
            seed_json(probe._api, path, producer.snapshot())

    def fenced(path, owner, fence):
        return FencedGitHubStore(repo, path, token, 'PRICE', lease_key, owner, fence,
            lease_path=lease_path, clock=clock, test_only=True)

    def replay(ledger, owner, rules):
        return replay_one(ledger, 'PRICE', owner, VERSION, rules,
            lambda unit: raw_by_id[unit['native_unit_id']], transform, validate_output,
            artifacts, lambda: None, ttl=120)

    seed(healthy_path, entries, 'DRIVE_INTEGRATION_V1')
    healthy = Ledger(fenced(healthy_path, owner_a, fence_a), clock)
    completed = []
    for _ in entries:
        done = replay(healthy, owner_a, 'DRIVE_INTEGRATION_V1')
        assert done and done['status'] == 'DONE'
        completed.append(done)
    assert replay(healthy, owner_a, 'DRIVE_INTEGRATION_V1') is None
    cells = sum(json.loads(artifacts.read(t['receipt']['validation_key']))['validation']['evidence']['cells_compared'] for t in completed)
    assert cells == sum(e['expected_cells'] for e in entries)

    # Release and replace the enclosing stage lease at the exact receipt-ref
    # publication boundary. The old ledger commit must not fast-forward.
    seed(race_path, entries[:1], 'DRIVE_RACE_V1')
    race_store = fenced(race_path, owner_a, fence_a)
    original_api, original_cas = race_store._api, race_store.cas
    inject = [False]; fence_b = [None]
    def racing_api(method, path, payload=None):
        if method == 'PATCH' and inject[0]:
            inject[0] = False
            commit(lease_url, token, lease_key, owner_a, fence_a, digest('test owner release'), now=int(clock()))
            fence_b[0] = acquire(lease_url, token, lease_key, owner_b, now=int(clock()), ttl=1800)
        return original_api(method, path, payload)
    def racing_cas(expected, doc):
        inject[0] = any(t['status'] == 'DONE' for t in doc['tasks'].values())
        return original_cas(expected, doc)
    race_store._api, race_store.cas = racing_api, racing_cas
    race = Ledger(race_store, clock)
    try:
        replay(race, owner_a, 'DRIVE_RACE_V1')
    except StaleClaim:
        pass
    else:
        raise AssertionError('STALE_STAGE_OWNER_PUBLISHED_RECEIPT')
    _, pending = GitHubStore(repo, race_path, token).read()
    task = next(iter(pending['tasks'].values()))
    assert task['status'] == 'CLAIMED' and task['receipt'] is None and fence_b[0] > fence_a
    output_key = 'stage06/PRICE/' + task['task_id'] + '/output'
    candidate = artifacts.read(output_key)
    physical = artifacts.private_reference(output_key)
    # A duplicate identical object is a recoverable ambiguous-create outcome.
    meta = drive.files().get(fileId=physical['file_id'], fields='name').execute(num_retries=0)
    drive.files().create(body=dict(name=meta['name'], parents=[folder],
        appProperties={'jarvis_stage06_scope': 'ISOLATED_TEST_ONLY'}),
        media_body=MediaIoBaseUpload(io.BytesIO(candidate), mimetype='application/octet-stream'),
        fields='id').execute(num_retries=0)
    assert artifacts.read(output_key) == candidate
    offset[0] += 121  # The abandoned task's 120-second claim expires.
    successor = Ledger(fenced(race_path, owner_b, fence_b[0]), clock)
    recovered = replay(successor, owner_b, 'DRIVE_RACE_V1')
    assert recovered['status'] == 'DONE' and recovered['fence'] > task['fence']
    assert artifacts.read(output_key) == candidate and len(artifacts._objects(output_key)) == 2
    artifacts.put_immutable('conflict-test', b'one', lambda: successor.snapshot())
    try:
        artifacts.put_immutable('conflict-test', b'two', lambda: successor.snapshot())
    except ValueError:
        pass
    else:
        raise AssertionError('DIFFERENT_DRIVE_BYTES_OVERWROTE_KEY')
    result = dict(status='DRIVE_FENCED_PUBLISH_INTEGRATION_PASS_NOT_DEPLOYED', run=run,
        real_native_units_replayed=len(completed), native_cells_compared=cells,
        race_successor_replayed=1, stale_stage_owner_publication_rejected=True,
        duplicate_identical_objects_reconciled=True, saved_output_reused=True,
        conflicting_output_rejected=True, real_drive_readback=True, live_stage_locks_written=False,
        live_cursors_written=False, market_source_http_downloads=0, owner_runtime_integrated=False,
        production_data_approved=False, numeric_semantics_verified=False, pit_verified=False)
    # No private Drive IDs are published in the public GitHub test manifest.
    public = Ledger(fenced(healthy_path, owner_b, fence_b[0]), clock)
    public.transaction(lambda state, now: state.update(integration_result=result))
    raw = json.dumps(dict(result=result, folder_id=folder), sort_keys=True, indent=2).encode()
    receipt_file = drive.files().create(body=dict(name='RESULT.json', parents=[folder]),
        media_body=MediaIoBaseUpload(io.BytesIO(raw), mimetype='application/json'), fields='id').execute(num_retries=0)['id']
    assert drive.files().get_media(fileId=receipt_file).execute(num_retries=0) == raw
    commit(lease_url, token, lease_key, owner_b, fence_b[0], digest(result), now=int(clock()))
    print('STAGE06_DRIVE_FENCED_INTEGRATION ' + json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
