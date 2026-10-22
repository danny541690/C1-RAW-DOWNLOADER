"""Owner replay boundary for QA1 and transforms; not wired into live workers.

The artifact backend must call guard while holding its own write lock. Production
Drive conditional publication and RAW HTTP replay are intentionally not supplied.
"""
import hashlib
import json
from scripts.v093_stage06_ledger import Ledger, RULES, StaleClaim, digest

def sha(raw):
    if not isinstance(raw,bytes):raise ValueError('ARTIFACT_MUST_BE_BYTES')
    return hashlib.sha256(raw).hexdigest()

def replay_one(ledger,owner,worker,processor_version,rule_version,read_input,transform,
               validate_output,artifacts,assert_owner_lease,ttl=5400):
    if owner not in ('QA1','PRICE','FINANCIAL','CHIP'):raise ValueError('RAW_REQUIRES_DURABLE_HTTP_ADAPTER')
    assert_owner_lease()
    task=ledger.claim(owner,worker,ttl,processor_version=processor_version,rule_version=rule_version,
                      gap_kinds={'BASIC_QA','PARSER_MAPPING'})
    if task is None:return None
    tid=task['task_id'];fence=task['fence']
    def guard():
        assert_owner_lease()
        ledger.owned(ledger.snapshot(),tid,worker,fence,int(ledger.clock()))
    gap=ledger.snapshot()['gaps'][task['gap_id']];unit=gap['unit']
    try:
        guard();raw=read_input(unit)
        if sha(raw)!=task['input_sha256']:raise ValueError('INPUT_READBACK_HASH_MISMATCH')
        guard();output=transform(raw,unit);output_hash=sha(output)
        guard();key='stage06/'+owner+'/'+tid+'/output'
        artifacts.put_immutable(key,output,guard)
        guard();saved=artifacts.read(key)
        if sha(saved)!=output_hash:raise ValueError('OUTPUT_READBACK_HASH_MISMATCH')
        guard();validation=validate_output(raw,saved,unit)
        if not isinstance(validation,dict) or not isinstance(validation.get('evidence'),dict) or not validation['evidence']:
            raise ValueError('VALIDATOR_EVIDENCE_REQUIRED')
        checks=validation.get('checks',{})
        if not all(checks.get(k) is True for k in RULES[gap['kind']][1]):raise ValueError('GAP_SPECIFIC_VALIDATION_REQUIRED')
        proof=dict(task_id=tid,owner=owner,fence=fence,input_sha256=task['input_sha256'],output_sha256=output_hash,
            processor_version=processor_version,rule_version=rule_version,unit=unit,validation=validation)
        proof_bytes=json.dumps(proof,sort_keys=True,separators=(',',':')).encode()
        proof_key='stage06/'+owner+'/'+tid+'/validation-'+str(fence)
        guard();artifacts.put_immutable(proof_key,proof_bytes,guard)
        guard()
        if sha(artifacts.read(proof_key))!=sha(proof_bytes):raise ValueError('VALIDATION_READBACK_HASH_MISMATCH')
        receipt=dict(task_id=tid,owner=owner,fence=fence,input_sha256=task['input_sha256'],
            processor_version=processor_version,rule_version=rule_version,output_sha256=output_hash,
            validation_evidence_sha256=sha(proof_bytes),checks=checks,output_key=key,validation_key=proof_key)
        guard()
        return ledger.complete(tid,worker,fence,receipt)
    except StaleClaim:
        raise
    except (ValueError,KeyError,TypeError) as exc:
        guard()
        code='OWNER_REPLAY_VALIDATION_FAILED'
        ledger.fail(tid,worker,fence,code,digest(dict(error=type(exc).__name__,message=str(exc))))
        raise
