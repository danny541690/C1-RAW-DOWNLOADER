"""Isolated cloud CAS test using synthetic metadata; no source downloads."""
import concurrent.futures
import json
import os
import time

from scripts.v093_stage06_ledger import GitHubStore, Ledger, RULES, StaleClaim, digest


def main():
    repo = os.environ['GITHUB_REPOSITORY']
    run = os.environ['GITHUB_RUN_ID'] + '-' + os.environ.get('GITHUB_RUN_ATTEMPT', '1')
    path = '.github/live-state/stage06-canary-' + run + '.json'
    token = os.environ['GH_TOKEN']
    clock = [int(time.time())]
    def client():
        return Ledger(GitHubStore(repo, path, token), lambda: clock[0])
    ledger = client()
    unit = dict(source='SYNTHETIC', market='TEST', dataset='CAS_CANARY', security_id='TEST',
                period_start='2026-10-01', period_end='2026-10-01', native_unit_id='canary-' + run)
    evidence = digest('synthetic input'); proof = digest('synthetic test approval')
    gap = ledger.observe(unit, 'PARSER_MAPPING', 'PRICE', evidence, 'SYNTHETIC_CANARY')
    ledger.approve_version('PRICE', 'SYNTHETIC_TEST_V1', proof)
    task = ledger.enqueue(gap['gap_id'], evidence, 'SYNTHETIC_TEST_V1', 'TEST_RULES_V1')
    same = client().enqueue(gap['gap_id'], evidence, 'SYNTHETIC_TEST_V1', 'TEST_RULES_V1')
    assert same['task_id'] == task['task_id']
    def claim(i):
        return client().claim('PRICE', 'canary-' + str(i), ttl=10)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(claim, range(2)))
    assert sum(x is not None for x in claims) == 1, 'DOUBLE_CLAIM'
    old = next(x for x in claims if x is not None)
    clock[0] += 11
    renewed = client().claim('PRICE', 'canary-restarted', ttl=10)
    assert renewed['fence'] > old['fence']
    def receipt(t):
        return dict(task_id=t['task_id'], owner='PRICE', fence=t['fence'], input_sha256=evidence,
                    processor_version='SYNTHETIC_TEST_V1', output_sha256=digest('synthetic output'),
                    validation_evidence_sha256=proof, checks={k: True for k in RULES['PARSER_MAPPING'][1]})
    try:
        ledger.complete(old['task_id'], old['claim']['worker'], old['fence'], receipt(old))
    except StaleClaim:
        pass
    else:
        raise AssertionError('STALE_OWNER_COMMITTED')
    client().complete(renewed['task_id'], 'canary-restarted', renewed['fence'], receipt(renewed))
    state = client().snapshot()
    assert len(state['tasks']) == 1 and state['gaps'][gap['gap_id']]['status'] == 'RESOLVED'
    print('STAGE06_LEDGER_CANARY ' + json.dumps(dict(result='PASS', isolated_path=path,
          tests=['cloud_cas', 'dedup', 'concurrent_claim', 'expired_fence', 'receipt_closure'],
          live_source_downloads=0, owner_runtime_integrated=False, production_data_approved=False)))


if __name__ == '__main__':
    main()
