"""RAW repair protocol. Transport and native-counter persistence must be bound
by the RAW owner; no provider request is made by default or by import.
"""
import hashlib
import json
import re
from urllib.parse import urlsplit

from scripts.v093_stage06_admission import expected_unit_decision
from scripts.v093_stage06_ledger import RULES, checked_hash, digest

VERSION = 'RAW_REPAIR_CONTRACT_V1'
OFFICIAL = ('TWSE', 'TPEx', 'MOPS')
HOSTS = {'TWSE': {'www.twse.com.tw', 'openapi.twse.com.tw'},
         'TPEx': {'www.tpex.org.tw'},
         'MOPS': {'mops.twse.com.tw'}, 'FinMind': {'api.finmindtrade.com'}}


def sha(raw):
    if not isinstance(raw, bytes): raise ValueError('RAW_RESPONSE_MUST_BE_BYTES')
    return hashlib.sha256(raw).hexdigest()


class RawReplayBinding:
    def __init__(self, ledger, worker, artifacts, expected, transport, native_bridge, validate_saved,
                 rule_version='RAW_TEST_RULES_V1'):
        if worker.stage != 'RAW': raise ValueError('RAW_OWNER_REQUIRED')
        if getattr(artifacts, 'requires_owner_fenced_store', False):
            store = ledger.store
            if not getattr(store, 'owner_fenced', False) or (store.stage, store.owner, store.fence, store.lease_key) != (
                    worker.stage, worker.owner, worker.fence, worker.lock): raise ValueError('OWNER_FENCED_RAW_LEDGER_REQUIRED')
        self.ledger, self.worker, self.artifacts = ledger, worker, artifacts
        self.expected, self.transport, self.native = expected, transport, native_bridge
        self.validate_saved, self.rule_version = validate_saved, rule_version

    def catalog(self, gap):
        unit = gap['unit']; spec = self.expected(unit)
        if spec.get('unit') != unit or digest(spec) != gap['expected_evidence_sha256']:
            raise ValueError('EXPECTED_CATALOG_EVIDENCE_MISMATCH')
        if expected_unit_decision(spec.get('evidence', {})) != 'EXPECTED':
            raise ValueError('EXPECTED_UNIT_NOT_PROVEN')
        source = unit['source']; job = spec.get('job', {})
        parsed = urlsplit(job.get('url', ''))
        if source not in HOSTS or parsed.scheme != 'https' or parsed.hostname not in HOSTS[source] or parsed.username or parsed.password:
            raise ValueError('SOURCE_ENDPOINT_NOT_ALLOWLISTED')
        if job.get('source') != source: raise ValueError('REQUEST_SOURCE_MISMATCH')
        if source == 'FinMind':
            proof = spec.get('supplement', {})
            checked_hash(proof.get('official_gap_evidence_sha256'))
            dimensions = ('official_gap_verified', 'definition_compatible', 'unit_compatible',
                          'sign_compatible', 'frequency_compatible', 'availability_compatible')
            if unit['security_id'] == 'ALL_MARKET' or not re.fullmatch('[0-9A-Za-z]{4,8}', unit['security_id']) or any(proof.get(k) is not True for k in dimensions):
                raise ValueError('FINMIND_VERIFIED_STOCK_GAP_REQUIRED')
        return spec

    def valid(self, raw, unit):
        result = self.validate_saved(raw, unit)
        if not isinstance(result.get('evidence'), dict) or not result['evidence'] or not all(
                result.get('checks', {}).get(k) is True for k in RULES['RAW_MISSING'][1]):
            raise ValueError('RAW_BASIC_VALIDATION_REQUIRED')
        return result

    def __call__(self, guard, ttl):
        # Existing successful bytes are validated first, even after four attempts.
        snapshot = self.ledger.snapshot()
        for task in snapshot['tasks'].values():
            if task['owner'] != 'RAW' or task['processor_version'] != VERSION or task['rule_version'] != self.rule_version or task['status'] in (
                    'CLAIMED', 'RECONCILE_REQUIRED', 'DONE', 'CANCELLED_SUPERSEDED', 'FAILED_PERMANENT'):
                continue
            gap = snapshot['gaps'][task['gap_id']]
            try: self.catalog(gap)
            except (ValueError,KeyError,TypeError): continue
            guard()
            native = self.native.current(gap['unit'])
            if native.get('saved_payload') is not None:
                try: self.valid(native['saved_payload'], gap['unit']); checked_hash(native['evidence_sha256'])
                except (ValueError,KeyError,TypeError): continue
                self.ledger.reuse_saved_raw(task['task_id'], sha(native['saved_payload']), native['evidence_sha256'])
        task = self.ledger.claim('RAW', self.worker.owner, ttl, processor_version=VERSION,
            rule_version=self.rule_version, gap_kinds={'RAW_MISSING', 'RAW_CORRUPT'}, unit_sources=OFFICIAL)
        if task is None:
            task = self.ledger.claim('RAW', self.worker.owner, ttl, processor_version=VERSION,
                rule_version=self.rule_version, gap_kinds={'RAW_MISSING', 'RAW_CORRUPT'}, unit_sources={'FinMind'})
        if task is None: return None
        tid, fence = task['task_id'], task['fence']; gap = self.ledger.snapshot()['gaps'][task['gap_id']]; unit = gap['unit']
        def owned():
            guard(); self.ledger.owned(self.ledger.snapshot(), tid, self.worker.owner, fence, int(self.ledger.clock()))
        try:
            spec = self.catalog(gap); current = self.native.current(unit)
            if type(current.get('used')) is not int or current['used'] < 0: raise ValueError('NATIVE_ATTEMPT_EVIDENCE_REQUIRED')
            checked_hash(current.get('evidence_sha256'))
            if current.get('saved_payload') is not None and not task.get('validation_only'):
                self.valid(current['saved_payload'],unit)
                raise ValueError('EXISTING_NATIVE_RAW_REQUIRES_RECONCILIATION')
            self.ledger.observe(unit, gap['kind'], 'RAW', gap['evidence_sha256'], gap['reason_code'],
                prior_attempts=current['used'], attempt_evidence_sha256=current['evidence_sha256'])
            response_key = 'stage06/RAW/' + tid + '/response'
            if task.get('validation_only'):
                raw = current.get('saved_payload')
                if raw is None: raw = self.artifacts.read(response_key)
                if sha(raw) != task['recovered_output_sha256']: raise ValueError('SAVED_RESPONSE_HASH_MISMATCH')
            else:
                request_id = 'request-' + tid[:24] + '-' + str(fence)
                owned(); intent = self.ledger.begin_request(tid, self.worker.owner, fence, request_id)
                if not intent['send_allowed']: return self.ledger.snapshot()['tasks'][tid]
                # Native persistence must hold the unit and retain the attempt
                # before any network call. Unknown results cannot be auto-retried.
                self.native.record_intent(unit, intent['record']['attempt'], request_id)
                owned(); raw = self.transport(spec['job'])
                owned(); self.artifacts.put_immutable(response_key, raw, owned)
                if self.artifacts.read(response_key) != raw: raise ValueError('RAW_READBACK_MISMATCH')
                self.ledger.end_request(tid, self.worker.owner, fence, request_id, sha(raw))
            owned(); validation = self.valid(raw, unit)
            self.artifacts.put_immutable(response_key, raw, owned)
            if self.artifacts.read(response_key) != raw: raise ValueError('RAW_READBACK_MISMATCH')
            proof = dict(task_id=tid, source=unit['source'], unit=unit, response_sha256=sha(raw),
                         expected_catalog_sha256=digest(spec), validation=validation, test_only=True)
            proof_key = 'stage06/RAW/' + tid + '/validation-' + str(fence)
            proof_raw = json.dumps(proof, sort_keys=True).encode()
            self.artifacts.put_immutable(proof_key, proof_raw, owned)
            if self.artifacts.read(proof_key) != proof_raw: raise ValueError('RAW_VALIDATION_READBACK_MISMATCH')
            owned(); self.native.finish(unit, sha(raw), validation)
            receipt = dict(task_id=tid, owner='RAW', fence=fence, input_sha256=task['input_sha256'],
                processor_version=VERSION, rule_version=self.rule_version, output_sha256=sha(raw),
                validation_evidence_sha256=sha(proof_raw), checks=validation['checks'], output_key=response_key,
                validation_key=proof_key)
            owned(); return self.ledger.complete(tid, self.worker.owner, fence, receipt)
        except (ValueError, KeyError, TypeError) as exc:
            # An unconfirmed HTTP intent intentionally remains claimed/held.
            try:
                self.ledger.fail(tid, self.worker.owner, fence, 'RAW_REPAIR_CONTRACT_FAILED',
                                 digest(str(exc)), retryable=False)
            except ValueError as pending:
                if str(pending) != 'UNRECONCILED_HTTP_INTENT': raise
            raise
