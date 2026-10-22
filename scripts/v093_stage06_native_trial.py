"""Replay explicitly supplied existing RAW archives into isolated TEST staging."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from scripts.v093_stage06_artifacts import LocalImmutableArtifacts
from scripts.v093_stage06_ledger import FileStore, Ledger, digest, summary
from scripts.v093_stage06_native_repair import VERSION, transform, validate_output
from scripts.v093_stage06_owner_replay import replay_one


def run_trial(original_ledger, receipts, archives, output_dir):
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    target = root / 'TEST_ONLY_LEDGER.json'
    if target.exists():
        raise ValueError('USE_NEW_ISOLATED_TRIAL_DIRECTORY')
    if original_ledger.get('approved_versions'):
        raise ValueError('EXPECTED_UNAPPROVED_TEST_INPUT')
    archive_hashes = {k: hashlib.sha256(Path(v).read_bytes()).hexdigest() for k, v in archives.items()}
    store = FileStore(target)
    cloned = json.loads(json.dumps(original_ledger))
    cloned.update(test_only=True, owner_runtime_integrated=False, production_data_approved=False)
    if not store.cas(None, cloned):
        raise ValueError('TRIAL_ALREADY_EXISTS')
    ledger = Ledger(store)
    artifacts = LocalImmutableArtifacts(root / 'artifacts')
    proof = dict(scope='ISOLATED_TEST_ONLY', input_snapshot_sha256=digest(original_ledger),
                 processor=VERSION, approval='REGRESSION_AND_NATIVE_CELL_RECONCILIATION_ONLY')
    (root / 'TEST_APPROVAL_EVIDENCE.json').write_text(json.dumps(proof, indent=2))
    ledger.approve_version('PRICE', VERSION, digest(proof))
    originals = {r['unit_id']: r for r in receipts}
    for gap in original_ledger['gaps'].values():
        receipt = originals[gap['unit']['native_unit_id']]
        if receipt['sha256'] != gap['evidence_sha256']:
            raise ValueError('INDEX_LEDGER_HASH_CONFLICT')
        ledger.enqueue(gap['gap_id'], gap['evidence_sha256'], VERSION, 'NATIVE_TEST_RULES_V1')

    def read_input(unit):
        r = originals[unit['native_unit_id']]
        archive, member = r['evidence_file'].split('/', 1)
        with zipfile.ZipFile(archives[archive]) as z:
            if z.getinfo(member).file_size > 30_000_000:
                raise ValueError('RAW_MEMBER_SIZE_LIMIT')
            raw = z.read(member)
        if hashlib.sha256(raw).hexdigest() != r['sha256']:
            raise ValueError('EXISTING_RAW_MEMBER_HASH_MISMATCH')
        return raw

    completed = []
    while True:
        task = replay_one(ledger, 'PRICE', 'isolated-test-owner', VERSION, 'NATIVE_TEST_RULES_V1',
                          read_input, transform, validate_output, artifacts, lambda: None)
        if task is None:
            break
        receipt = task['receipt']
        validation = json.loads(artifacts.read(receipt['validation_key']))
        unit = validation['unit']; unit_id = unit['native_unit_id']
        export = root / 'parquet'; export.mkdir(exist_ok=True)
        (export / (unit_id + '.parquet')).write_bytes(artifacts.read(receipt['output_key']))
        (export / (unit_id + '.validation.json')).write_bytes(artifacts.read(receipt['validation_key']))
        completed.append(dict(unit_id=unit_id, dataset=unit['dataset'], period_start=unit['period_start'],
                              period_end=unit['period_end'], **validation['validation']['evidence']))
    if len(completed) != len(original_ledger['gaps']):
        raise ValueError('INCOMPLETE_ISOLATED_REPLAY')
    for key, path in archives.items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != archive_hashes[key]:
            raise ValueError('RAW_ARCHIVE_CHANGED')
    result = dict(status='ISOLATED_NATIVE_REPAIR_TRIAL_PASS_NOT_DEPLOYED', test_only=True,
                  original_snapshot_sha256=digest(original_ledger), source_http_downloads=0,
                  raw_archives_unchanged=True, units_replayed=len(completed),
                  native_records=sum(r['native_records'] for r in completed),
                  native_cells_compared=sum(r['cells_compared'] for r in completed),
                  numeric_semantics_verified=False, pit_verified=False, production_data_approved=False,
                  owner_runtime_integrated=False, ledger_summary=summary(ledger.snapshot()), units=completed)
    (root / 'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    p = argparse.ArgumentParser()
    for name in ('ledger', 'receipts', 'archives', 'output-dir'):
        p.add_argument('--' + name, required=True)
    a = p.parse_args()
    result = run_trial(json.loads(Path(a.ledger).read_text()), json.loads(Path(a.receipts).read_text()),
                       json.loads(Path(a.archives).read_text()), a.output_dir)
    print(json.dumps({k: v for k, v in result.items() if k != 'units'}, sort_keys=True))


if __name__ == '__main__':
    main()
