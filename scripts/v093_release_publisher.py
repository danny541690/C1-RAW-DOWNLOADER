"""Evidence-backed publication. Invoke only within one serialized publisher workflow.

This is a single-writer expected-release check, not a claim of server-side Drive CAS.
"""
import hashlib,json
from scripts.v093_layer02_governance import GateBlocked,gate_release,REQUIRED_QA

def validate_evidence(manifest,read_evidence):
    gate_release(manifest)
    scope=manifest.get('scope',{})
    if not scope.get('markets') or not scope.get('fields') or not scope.get('from') or not scope.get('to'):
        raise GateBlocked('RELEASE_BLOCKED:SCOPE_MISSING')
    if isinstance(scope.get('expected_universe'),bool) or not isinstance(scope.get('expected_universe'),int) or scope['expected_universe']<=0:
        raise GateBlocked('RELEASE_BLOCKED:UNIVERSE_UNKNOWN')
    for gate in REQUIRED_QA:
        ref=manifest.get('evidence',{}).get(gate,{})
        if not ref.get('name') or not ref.get('sha256'):raise GateBlocked('EVIDENCE_MISSING:'+gate)
        raw=read_evidence(ref['name'])
        if not raw or hashlib.sha256(raw).hexdigest()!=ref['sha256']:raise GateBlocked('EVIDENCE_DIGEST:'+gate)
        proof=json.loads(raw)
        if proof.get('passed') is not True or proof.get('gate')!=gate or proof.get('generation_id')!=manifest['generation_id'] or proof.get('input_digests')!=manifest['input_digests'] or proof.get('scope')!=scope:
            raise GateBlocked('EVIDENCE_IDENTITY:'+gate)
        if not proof.get('checker_commit'):raise GateBlocked('EVIDENCE_CHECKER_VERSION:'+gate)
    return True

def publish(d,control,manifest,expected_release):
    validate_evidence(manifest,lambda name:d.read(control,name))
    data=d.read(manifest['data_folder'],manifest['data_name'])
    if not data or hashlib.sha256(data).hexdigest()!=manifest['parquet_sha256']:raise GateBlocked('PAYLOAD_DIGEST')
    current=d.read(control,'ACTIVE_APPROVED_RELEASE.json')
    actual=json.loads(current)['generation_id'] if current else None
    if actual!=expected_release:raise GateBlocked('EXPECTED_RELEASE_CHANGED')
    name='approved_'+manifest['generation_id']+'.json'
    body=json.dumps(manifest,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
    d.put(control,name,body,'application/json',overwrite=False)
    # A shared concurrency group serializes every production caller.
    again=d.read(control,'ACTIVE_APPROVED_RELEASE.json')
    if again!=current:raise GateBlocked('PUBLISHER_CONFLICT')
    pointer=json.dumps({'generation_id':manifest['generation_id'],'manifest':name,'previous_release':expected_release},sort_keys=True).encode()
    d.put(control,'ACTIVE_APPROVED_RELEASE.json',pointer,'application/json',overwrite=True)
    if d.read(control,'ACTIVE_APPROVED_RELEASE.json')!=pointer:raise GateBlocked('POINTER_READBACK')
    return {'status':'PUBLISHED','generation_id':manifest['generation_id']}
