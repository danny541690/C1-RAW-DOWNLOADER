"""Recheck the exact frozen blocker list against retained bytes, without repairs."""
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from scripts.v093_prelaunch_acceptance_batch import inspect_raw
from scripts.v093_acceptance_dependencies import checker_signatures


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def run(targets, register, cache, out, download=None):
    targets = Path(targets); register = Path(register); cache = Path(cache); out = Path(out)
    with targets.open(encoding='utf-8-sig') as stream:
        selected = list(csv.DictReader(stream))
    wanted = {(r['source'], r['task_id']): r for r in selected}
    if not selected or len(wanted) != len(selected) or len(selected) > 100:
        raise ValueError('INVALID_BOUNDED_TARGET_SET')
    rows = {}; register_sha = {}
    for file in sorted(register.glob('*_units.csv.gz')):
        if file.name.split('_units.csv.gz')[0] not in {r['source'] for r in selected}:
            continue
        register_sha[file.name] = sha(file.read_bytes())
        with gzip.open(file, 'rt', encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                key = row['來源'], row['單元ID']
                if key not in wanted:
                    continue
                if key in rows:
                    raise ValueError('DUPLICATE_REGISTER_TASK')
                old = wanted[key]
                if row.get('已下載') != '1' or row['資料集'] != old.get('dataset', row['資料集']) or row['原件參照'] != old['raw_reference'] or row['RAW_SHA256'] != old['raw_sha256'] or row['期間'] != old['period']:
                    raise ValueError('TARGET_REGISTER_CONTEXT_CHANGED')
                rows[key] = row
    if rows.keys() != wanted.keys():
        raise ValueError('TARGETS_NOT_FOUND_IN_FROZEN_REGISTER')
    cache.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    packages = {}; failures = {}; results = []
    for old in selected:
        fid = old['raw_reference'].partition('/')[0]
        if not re.fullmatch('[A-Za-z0-9_-]+', fid):
            raise ValueError('UNSAFE_PACKAGE_ID')
        if fid in packages or fid in failures:
            continue
        try:
            file = cache / fid
            raw = file.read_bytes() if file.exists() else download(fid) if download else None
            if raw is None:
                raise ValueError('RETAINED_PACKAGE_NOT_IN_CACHE')
            if len(raw) > 16 * 1024 * 1024 or sha(raw) != old['package_sha256']:
                raise ValueError('RETAINED_PACKAGE_SHA_OR_SIZE_MISMATCH')
            packages[fid] = raw
            if not file.exists():
                file.write_bytes(raw)
        except Exception as exc:
            failures[fid] = type(exc).__name__  # Do not publish provider auth error text.
    for key, row in rows.items():
        old = wanted[key]; fid, sep, member = row['原件參照'].partition('/')
        result = dict(source=key[0], task_id=key[1], dataset=row['資料集'], period=row['期間'],
                      raw_reference=row['原件參照'], previous_error=old['error'], raw_sha256=row['RAW_SHA256'],
                      status='CONTENT_BLOCKED')
        raw = None
        try:
            if fid in failures:
                raise ValueError('RETAINED_PACKAGE_READ_FAILED:' + failures[fid])
            raw = packages[fid]
            if sha(raw) != old['package_sha256']:
                raise ValueError('RETAINED_PACKAGE_SHA_MISMATCH')
            if sep:
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    info = archive.getinfo(member)
                    if info.file_size > 16 * 1024 * 1024:
                        raise ValueError('RAW_MEMBER_SIZE_LIMIT')
                    raw = archive.read(member)
            if sha(raw) != row['RAW_SHA256']:
                raise ValueError('REGISTER_RAW_SHA_MISMATCH')
            result['raw_sha_verified'] = True
            result['content'] = inspect_raw(raw, row)
            result['status'] = 'PARTIAL_CONTENT_NOT_RELEASED'
        except Exception as exc:
            result['error'] = type(exc).__name__ + ':' + str(exc)[:240]
            if row['來源'] == 'MOPS' and raw:
                from lxml import html
                try:
                    root = html.fromstring(raw.decode('utf-8-sig'))
                    result['native_matrix_rows'] = dict(accounts=len(root.xpath('//*[@id="headTable"]//tbody/tr')),
                                                       values=len(root.xpath('//*[@id="bodyTable"]//tbody/tr')))
                except Exception:
                    result['native_matrix_rows'] = 'UNREADABLE_NOT_ASSUMED_EMPTY'
        results.append(result)
    summary = dict(version='EXACT_BLOCKER_FOLLOWUP_V1', target_csv_sha256=sha(targets.read_bytes()),
                   register_sha256=register_sha,
                   checker_signatures=checker_signatures(Path(__file__).resolve().parents[1]),
                   target_units=len(selected), unique_retained_packages=len(packages), package_read_errors=failures,
                   counts=dict(collections.Counter(r['status'] for r in results)),
                   raw_sha_verified_units=sum(r.get('raw_sha_verified', False) for r in results),
                   unmapped_errors=sum('UNMAPPED_' in r.get('error', '') for r in results),
                   source_market_downloads=0, production_writes=0, closed_quality_tasks=0, approved_scopes=[],
                   results=results)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--targets', type=Path, default=Path('reports/raw-acceptance/20261028_scheduler_live_readiness/blocked_units.csv'))
    parser.add_argument('--register', type=Path, default=Path('reports/raw-register/20261027_v1/units'))
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--read-existing-drive', action='store_true')
    args = parser.parse_args()
    download = None
    if args.read_existing_drive:
        from scripts.annual_actual_firstpass import service
        from googleapiclient.http import MediaIoBaseDownload
        api = service()
        def download(fid):
            meta = api.files().get(fileId=fid, fields='id,size', supportsAllDrives=True).execute(num_retries=0)
            limit = int(meta.get('size', 0))
            if not 0 < limit <= 16 * 1024 * 1024:
                raise ValueError('RETAINED_PACKAGE_SIZE_LIMIT')
            buffer = io.BytesIO(); reader = MediaIoBaseDownload(buffer, api.files().get_media(fileId=fid), chunksize=1024*1024)
            done = False
            while not done:
                _, done = reader.next_chunk(num_retries=0)
                if buffer.tell() > limit:
                    raise ValueError('RETAINED_PACKAGE_SIZE_CHANGED')
            if buffer.tell() != limit:
                raise ValueError('RETAINED_PACKAGE_SIZE_CHANGED')
            return buffer.getvalue()
    summary = run(args.targets, args.register, args.cache, args.out, download)
    if summary['package_read_errors'] or summary['raw_sha_verified_units'] != summary['target_units'] or summary['unmapped_errors']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
