"""Bounded, read-only acceptance worker. Never publishes or repairs source RAW.

Run from the repository root. The durable directory belongs to this worker only.
An unchanged partial inspection is reusable, but never means full acceptance.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import time
import zipfile
from pathlib import Path

SCHEMA = 'JARVIS_ACCEPTANCE_SCHEDULER_V1'
FOLDER = 'application/vnd.google-apps.folder'
ID = re.compile(r'[A-Za-z0-9_-]+')
MAX_MEMBER = 32 * 1024 * 1024
MAX_EXPANSION = 256 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_bytes(gzip.compress(json.dumps(value, ensure_ascii=False,
                                             sort_keys=True).encode(), mtime=0))
    temp.replace(path)


def load(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def tasks(register):
    files = sorted(Path(register).glob('*_units.csv.gz'))
    if not files:
        raise ValueError('REGISTER_INPUT_MISSING')
    for file in files:
        with gzip.open(file, 'rt', encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                if row['已下載'] != '1':
                    continue  # Old missing flags are not new download orders.
                if not 2000 <= int(row['年份']) <= 2026:
                    raise ValueError('REGISTER_YEAR_OUT_OF_SCOPE')
                fid = row['原件參照'].partition('/')[0]
                if not ID.fullmatch(fid) or not re.fullmatch('[0-9a-f]{64}', row['RAW_SHA256']):
                    raise ValueError('REGISTER_REFERENCE_OR_SHA')
                yield row


def shard_rows(rows, index, count):
    if count != 3 or not 0 <= index < count:
        raise ValueError('INVALID_SHARD_THREE_WORKERS_REQUIRED')
    for row in rows:
        fid = row['原件參照'].partition('/')[0]
        if int(hashlib.sha256(fid.encode()).hexdigest(), 16) % count == index:
            yield row


def identity(row, metadata, checker, evidence_digest):
    # Metadata fingerprint changing invalidates even an unchanged logical task.
    return digest(dict(row=row, remote=metadata, checker=checker,
                       evidence=evidence_digest))


def checked_package(payload, metadata, max_bytes):
    if not payload or len(payload) > max_bytes:
        raise ValueError('RAW_EMPTY_OR_SIZE_LIMIT')
    if len(payload) != int(metadata['size']):
        raise ValueError('REMOTE_SIZE_MISMATCH')
    if not metadata.get('md5Checksum'):
        raise ValueError('REMOTE_CHECKSUM_MISSING')
    if hashlib.md5(payload).hexdigest() != metadata['md5Checksum']:
        raise ValueError('REMOTE_MD5_MISMATCH')
    if zipfile.is_zipfile(io.BytesIO(payload)):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            info = archive.infolist()
            if len({item.filename for item in info}) != len(info):
                raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
            if sum(item.file_size for item in info) > MAX_EXPANSION:
                raise ValueError('ARCHIVE_EXPANSION_LIMIT')
            if any(item.file_size > MAX_MEMBER for item in info):
                raise ValueError('ARCHIVE_MEMBER_SIZE_LIMIT')
            # CRC is verified when each requested member is read. Unread members
            # are not reported as validated, even though the package SHA is bound.
    return hashlib.sha256(payload).hexdigest()


def inspect_member(payload, row, inspect, evidence):
    _, sep, member = row['原件參照'].partition('/')
    if sep:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            raw = archive.read(member)
    else:
        raw = payload
    if len(raw) > MAX_MEMBER:
        raise ValueError('RAW_MEMBER_SIZE_LIMIT')
    if hashlib.sha256(raw).hexdigest() != row['RAW_SHA256']:
        raise ValueError('REGISTER_RAW_SHA_MISMATCH')
    return inspect(raw, row, evidence)


def work(rows, snapshot, state, read_remote, inspect, signatures, evidence=None,
         max_packages=8, max_bytes=128 * 1024 * 1024, max_units=1000,
         max_seconds=600, clock=time.monotonic, now=None, persist=lambda: None):
    """One bounded slice. Content failures are held until inputs/checker change.

    Transient read failures get at most three attempts across runs, not per run.
    No source requests, source writes, acceptance receipts or release operations.
    """
    if min(max_packages, max_bytes, max_units, max_seconds) <= 0:
        raise ValueError('INVALID_WORK_BUDGET')
    now = time.time() if now is None else now
    if state.get('schema') != SCHEMA:
        raise ValueError('STATE_SCHEMA')
    if not snapshot.get('enumeration_complete'):
        return dict(status='WAITING_FOR_INVENTORY', inspected=0, packages=0)
    if state.get('auth_hold'):
        return dict(status='AUTH_HOLD_MANUAL_RESET_REQUIRED', inspected=0, packages=0)
    metadata = {f['id']: f for f in snapshot['files'] if f['mimeType'] != FOLDER}
    grouped = {}
    for row in rows:
        fid = row['原件參照'].partition('/')[0]
        grouped.setdefault(fid, []).append(row)
    start = clock()
    counters = dict(status='SLICE_COMPLETE_NOT_FULL_ACCEPTANCE', inspected=0,
                    packages=0, bytes=0, reused=0, held=0, inventory_unmatched=0)
    # The stored outcomes hold exact source/task/RAW/metadata/checker context.
    outcomes = state.setdefault('outcomes', {})
    attempts = state.setdefault('package_attempts', {})
    evidence = evidence or {}
    for fid, members in sorted(grouped.items()):
        if clock() - start >= max_seconds or counters['inspected'] >= max_units:
            break
        meta = metadata.get(fid)
        if meta is None:
            counters['inventory_unmatched'] += len(members)
            continue  # Absence from this RAW-root enumeration is not deletion.
        pending = []
        for row in members:
            scoped_evidence = [(str(k), v) for k, v in sorted(evidence.items())
                               if row['來源'] == 'FinMind' and k[1] == row.get('代碼')
                               and k[0].startswith(row.get('月份') or '!')]
            evidence_digest = digest(scoped_evidence)
            token = identity(row, meta, signatures[row['來源']], evidence_digest)
            if token in outcomes:
                counters['reused'] += 1
            else:
                pending.append((token, row))
        if not pending:
            continue
        ptoken = digest(dict(id=fid, metadata=meta))
        retry = attempts.setdefault(ptoken, dict(attempts=0, next_at=0))
        if retry['attempts'] >= 3 or retry['next_at'] > now:
            counters['held'] += len(pending)
            continue
        try:
            size = int(meta.get('size', 0))
        except (TypeError, ValueError):
            size = 0
        if size <= 0 or size > min(max_bytes, MAX_EXPANSION):
            retry.update(attempts=3, error='PACKAGE_SIZE_REVIEW_REQUIRED')
            counters['held'] += len(pending)
            persist()
            continue
        if counters['packages'] >= max_packages or counters['bytes'] + size > max_bytes:
            continue
        # Persist the attempt BEFORE network access so interrupted runs do not
        # reset the retry budget. This is deliberately conservative on a crash.
        retry['attempts'] += 1
        retry['next_at'] = now + 6 * 3600
        persist()
        counters['packages'] += 1
        counters['bytes'] += size
        try:
            payload, readback_meta = read_remote(fid, size)
            if readback_meta != meta:
                raise ValueError('REMOTE_CHANGED_DURING_READ')
            package_sha = checked_package(payload, meta, max_bytes)
        except Exception as exc:
            status = getattr(getattr(exc, 'resp', None), 'status', None)
            retry['error'] = type(exc).__name__  # Never store OAuth response text.
            if status == 401:
                state['auth_hold'] = True
            persist()
            if state.get('auth_hold'):
                counters['status'] = 'AUTH_HOLD_MANUAL_RESET_REQUIRED'
                break
            continue
        # Successful reads release the transport retry counter. Content failures
        # below are saved as outcomes and are not retried for unchanged inputs.
        retry.update(attempts=0, next_at=0, error=None)
        for token, row in pending:
            if counters['inspected'] >= max_units or clock() - start >= max_seconds:
                break
            result = dict(source=row['來源'], dataset=row['資料集'],
                          task_id=row['單元ID'], period=row['期間'],
                          raw_reference=row['原件參照'], raw_sha256=row['RAW_SHA256'],
                          package_sha256=package_sha, remote_metadata=meta,
                          checker_signature=signatures[row['來源']],
                          checked_at=dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
                          status='PARTIAL_CONTENT_NOT_RELEASED')
            try:
                result['content'] = inspect_member(payload, row, inspect, evidence)
            except Exception as exc:
                result.update(status='CONTENT_BLOCKED', error=type(exc).__name__ + ':' + str(exc)[:240])
            outcomes[token] = result
            counters['inspected'] += 1
            if counters['inspected'] % 20 == 0:
                persist()
        persist()
    current=[]
    historical_blocks={(v['source'],v['task_id']) for v in outcomes.values() if v['status']=='CONTENT_BLOCKED'}
    for fid,members in grouped.items():
        if fid not in metadata:continue
        for row in members:
            scoped=[(str(k),v) for k,v in sorted(evidence.items()) if row['來源']=='FinMind' and k[1]==row.get('代碼') and k[0].startswith(row.get('月份') or '!')]
            token=identity(row,metadata[fid],signatures[row['來源']],digest(scoped))
            if token in outcomes:current.append(outcomes[token])
    total=sum(map(len,grouped.values()))
    state['progress']=dict(required_items=total,checked_items=len(current),
        partial_content_items=sum(v['status']=='PARTIAL_CONTENT_NOT_RELEASED' for v in current),
        content_blocked_items=sum(v['status']=='CONTENT_BLOCKED' for v in current),
        repaired_content_blockers=sum(v['status']=='PARTIAL_CONTENT_NOT_RELEASED' and (v['source'],v['task_id']) in historical_blocks for v in current),
        confirmed_exception_items=0,completed_items=0,pending_items=total,unchecked_items=total-len(current),
        scope='REGISTERED_DOWNLOADED_SHARD_ONLY_NOT_GLOBAL_UNIVERSE',
        evaluated_at=dt.datetime.fromtimestamp(now,dt.timezone.utc).isoformat())
    state['last_slice'] = counters
    persist()
    return counters


def report(state, slice_result):
    # Report only this worker's evidence, never promote historical partial
    # reports into current full-group PASS results.
    return dict(schema=SCHEMA, lane=state.get('lane'), slice=slice_result,
                historical_target='2000-01 through 2026; dataset applicability not approved',
                groups=[dict(id=f'R{i:02}', status='BLOCKED' if i == 7 else 'OPEN',
                             full_acceptance=False) for i in range(1, 9)],
                recorded_outcome_versions=len(state.get('outcomes', {})),
                progress=state.get('progress'),
                progress_recomputed_this_run=slice_result['status']=='SLICE_COMPLETE_NOT_FULL_ACCEPTANCE',
                source_downloads=0, production_writes=0, approved_scopes=[],
                missing_capabilities=['approved historical universe', 'all dataset contracts',
                                      'independent cross-source validation', 'historical PIT evidence',
                                      'full restore and downstream release evidence'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--register', type=Path, default=Path('reports/raw-register/20261027_v1/units'))
    parser.add_argument('--esb-evidence', type=Path, default=Path('reports/raw-acceptance/20261028_esb_contract'))
    parser.add_argument('--clear-auth-hold', action='store_true')
    parser.add_argument('--inventory-only', action='store_true')
    parser.add_argument('--inventory-state', type=Path)
    parser.add_argument('--shard-index', type=int)
    parser.add_argument('--lease', type=Path)
    args = parser.parse_args()
    args.state.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    file = args.state / 'worker.json.gz'
    state = load(file) if file.exists() else dict(schema=SCHEMA)
    if state.get('schema') != SCHEMA:
        raise ValueError('STATE_SCHEMA')
    lane = 'inventory' if args.inventory_only else f'worker-{args.shard_index}'
    if state.get('lane', lane) != lane:
        raise ValueError('STATE_LANE_MISMATCH')
    state['lane'] = lane
    if args.clear_auth_hold:
        state.pop('auth_hold', None)
    def persist():
        save(file, state)
        if args.lease:
            from scripts.v093_acceptance_state import commit
            commit(args.state, args.lease, lane)
    if state.get('auth_hold'):
        result = dict(status='AUTH_HOLD_MANUAL_RESET_REQUIRED', inspected=0, packages=0)
    else:
        try:
            # Only read operations are exposed by this adapter. Existing account
            # credentials may have wider scopes, but no write methods are called.
            from scripts.annual_actual_firstpass import service
            api = service()
        except Exception as exc:
            if 'invalid_grant' in str(exc) or 'invalid_client' in str(exc):
                state['auth_hold'] = True
            persist()
            raise RuntimeError('DRIVE_AUTH_OR_CONNECTION_FAILED_SEE_PROVIDER_SETTINGS') from None
        from scripts.v093_acceptance_remote_inventory import collect, ROOT
        checkpoint = (args.inventory_state or args.state) / 'inventory.json.gz'
        inventory = load(checkpoint) if checkpoint.exists() else None
        if inventory and inventory.get('root') != ROOT:
            raise ValueError('INVENTORY_ROOT_SCOPE')
        # Refresh finished enumeration daily; unfinished generations continue.
        if args.inventory_only and inventory and inventory['phase'] == 'DONE':
            age = time.time() - dt.datetime.fromisoformat(inventory['started_at']).timestamp()
            if age >= 24 * 3600:
                inventory = None
        def list_page(query, token):
            return api.files().list(q=query, pageToken=token, pageSize=1000,
                fields='nextPageToken,files(id,name,mimeType,size,modifiedTime,parents,md5Checksum,version)',
                supportsAllDrives=True, includeItemsFromAllDrives=True).execute(num_retries=0)
        if args.inventory_only:
            temp = args.out / 'inventory'
            resume = None
            if inventory:
                temp.mkdir(parents=True, exist_ok=True)
                resume = temp / 'resume.json'
                resume.write_text(json.dumps(inventory))
            snapshot = collect(list_page, temp, root=ROOT, max_requests=60,
                               max_seconds=90, resume=resume)
            save(checkpoint, json.loads((temp / 'checkpoint.json').read_text()))
            if snapshot['error']:
                snapshot['error'] = 'INVENTORY_READ_FAILED_SEE_RUN_STATUS'
                (temp / 'snapshot.json').write_text(json.dumps(snapshot))
            result = dict(status='INVENTORY_COMPLETE' if snapshot['enumeration_complete']
                          else 'INVENTORY_INCOMPLETE', inspected=0, packages=0,
                          file_metadata_records=snapshot['file_metadata_records'])
            summary = report(state, result)
            (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
            persist()
            if snapshot['error']:
                raise SystemExit(2)
            return
        if args.inventory_state is None or args.shard_index is None:
            raise ValueError('WORKER_REQUIRES_SHARED_INVENTORY_AND_SHARD_INDEX')
        snapshot = dict(enumeration_complete=bool(inventory and inventory['phase'] == 'DONE'),
                        files=list(inventory['files'].values()) if inventory else [])
        from scripts.v093_prelaunch_acceptance_batch import inspect_raw
        from scripts.v093_acceptance_dependencies import checker_signatures
        from scripts.v093_esb_market_evidence import load_evidence
        signatures = checker_signatures(Path(__file__).resolve().parent.parent)
        evidence = load_evidence(args.esb_evidence)
        def read_remote(fid, expected_size):
            from googleapiclient.http import MediaIoBaseDownload
            buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(buffer, api.files().get_media(fileId=fid), chunksize=1024 * 1024)
            done = False
            while not done:
                time.sleep(0.5)  # Bound each read-only worker's Drive request rate.
                _, done = downloader.next_chunk(num_retries=0)
                if buffer.tell() > expected_size:
                    raise ValueError('REMOTE_DOWNLOAD_SIZE_LIMIT')
            meta = api.files().get(fileId=fid,
                fields='id,name,mimeType,size,modifiedTime,parents,md5Checksum,version',
                supportsAllDrives=True).execute(num_retries=0)
            return buffer.getvalue(), meta
        result = work(shard_rows(tasks(args.register), args.shard_index, 3), snapshot, state, read_remote,
                      inspect_raw, signatures, evidence, persist=persist)
    summary = report(state, result)
    (args.out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    (args.out / 'summary.md').write_text(
        '# JARVIS 自動驗收\n\n' +
        f"本輪：{result['status']}；內容檢查 {result['inspected']} 筆。\n\n" +
        '八組完整驗收仍未通過；正式發布核准範圍為0。\n' +
        '此排程只讀既存RAW，保留未知、隔離與缺少檢查器的項目。\n')
    persist()
    print(json.dumps(summary, ensure_ascii=False))
    if result['status'] == 'AUTH_HOLD_MANUAL_RESET_REQUIRED':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
