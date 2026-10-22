"""JARVIS v0.93 isolated durable GitHub CAS lease for five-stage cutover.

This protects ownership of a GitHub Contents manifest only. It is NOT an atomic
transaction with Google Drive. Production activation remains blocked.
"""
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from scripts.v093_github_budget import open_json

class LeaseBusy(RuntimeError):
    pass

class LeaseConflict(RuntimeError):
    pass

def _digest(value):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('INVALID_SHA256')
    return value

def _read(api_url,token):
    req=urllib.request.Request(api_url,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
    result,_=open_json(req,30)
    payload=json.loads(base64.b64decode(result['content']))
    if not isinstance(payload.get('jobs'),dict):
        raise ValueError('INVALID_DURABLE_MANIFEST')
    return result['sha'],payload

def _put(api_url,token,sha,payload,message):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    body={'message':message,'sha':sha,'content':base64.b64encode(raw).decode()}
    req=urllib.request.Request(api_url,method='PUT',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            if response.status!=200:
                raise LeaseConflict('UNEXPECTED_HTTP_'+str(response.status))
        return True
    except urllib.error.HTTPError as exc:
        if exc.code in (409,422):
            return False
        raise

def acquire(api_url,token,key,owner,now=None,ttl=900,retries=12):
    if not key or not owner or ttl<=0:
        raise ValueError('INVALID_LEASE_REQUEST')
    for attempt in range(retries):
        sha,payload=_read(api_url,token)
        instant=int(time.time() if now is None else now)
        row=payload['jobs'].get(key,{})
        lease=row.get('lease') or {}
        if lease.get('expires_at',0)>instant:
            raise LeaseBusy(key)
        fence=max(int(lease.get('fence',0)),int(row.get('last_fence',0)))+1
        row['lease']={'owner':owner,'expires_at':instant+ttl,'fence':fence}
        payload['jobs'][key]=row
        if _put(api_url,token,sha,payload,'test: durable lease acquire'):
            return fence
        time.sleep(min(.25*(attempt+1),2))
    raise LeaseConflict('CAS_RETRY_EXHAUSTED')

def commit(api_url,token,key,owner,fence,raw_sha256,now=None,retries=12):
    _digest(raw_sha256)
    for attempt in range(retries):
        sha,payload=_read(api_url,token)
        instant=int(time.time() if now is None else now)
        row=payload['jobs'].get(key,{})
        lease=row.get('lease') or {}
        if lease.get('owner')!=owner or lease.get('fence')!=fence or lease.get('expires_at',0)<=instant:
            raise LeaseConflict('STALE_OR_EXPIRED_OWNER')
        if row.get('certified'):
            raise LeaseConflict('CERTIFICATION_NOT_ALLOWED_BY_COMMIT')
        row.update(status='DATA_PRESENT_PENDING_QA',sha256=raw_sha256,certified=False)
        row['lease']=None
        row['last_fence']=fence
        payload['jobs'][key]=row
        if _put(api_url,token,sha,payload,'test: durable lease commit'):
            return True
        time.sleep(min(.25*(attempt+1),2))
    raise LeaseConflict('CAS_RETRY_EXHAUSTED')

def decide_adapter(stage,raw_receipt,qa_receipt,adapter):
    if stage not in ('PRICE','FINANCIAL','CHIP'):
        raise ValueError('UNKNOWN_ADAPTER_STAGE')
    if not raw_receipt or not qa_receipt or not adapter:
        return 'BLOCKED_MISSING_INPUT_OR_ADAPTER'
    try:
        _digest(raw_receipt.get('sha256'))
        _digest(qa_receipt.get('raw_sha256'))
    except ValueError:
        return 'BLOCKED_INVALID_INPUT_DIGEST'
    if raw_receipt.get('sha256')!=qa_receipt.get('raw_sha256'):
        return 'BLOCKED_RAW_QA_DIGEST_MISMATCH'
    for k in ('schema_ok','unit_ok','date_ok','pit_ok','numeric_ok','universe_ok'):
        if adapter.get(k) is not True:
            return 'BLOCKED_'+k.upper()
    if not adapter.get('approved_version'):
        return 'BLOCKED_UNAPPROVED_ADAPTER'
    return 'ELIGIBLE_FOR_STAGING_NOT_CERTIFIED'
