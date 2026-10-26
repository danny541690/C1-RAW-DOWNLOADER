"""JARVIS v0.93 isolated durable GitHub CAS lease for five-stage cutover.

This protects ownership of a GitHub Contents manifest only. It is NOT an atomic
transaction with Google Drive. Production activation remains blocked.
"""
import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
import http.client
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
        if exc.code not in (500,502,503,504):raise
    except (TimeoutError, ConnectionError, urllib.error.URLError, http.client.IncompleteRead):
        pass
    # A timed-out PUT may already have committed. Never blindly replay its SHA.
    # Confirm exact content, otherwise let the bounded caller reload and CAS.
    try:
        _, observed = _read(api_url, token)
    except (OSError, http.client.IncompleteRead):
        return False
    return observed == payload


def terminal_owner(api_url, token, key, lease):
    """Only a completed, matching workflow can surrender an unexpired lease."""
    match=re.fullmatch(r'([0-9]+)/(RAW|QA1|PRICE|FINANCIAL|CHIP|RECONCILE)',lease.get('owner',''))
    if not match:return False
    run,stage=match.groups()
    pools={'RAW':'POOL_RAW_REPLAN_201404_V1','QA1':'POOL_CONSUMER_QA1_REPLAN_201404_V1',
           'PRICE':'POOL_CONSUMER_PRICE_REPLAN_201404_V1','FINANCIAL':'POOL_CONSUMER_FINANCIAL_REPLAN_201404_V1',
           'CHIP':'POOL_CONSUMER_CHIP_REPLAN_201404_V1','RECONCILE':'POOL_STAGE06_REPAIR_V1'}
    independent=('POOL_RAW' if stage=='RAW' else 'POOL_CONSUMER')+'_STAGE06_'+stage+'_V1'
    ascending=stage=='RAW' and key=='POOL_RAW_STAGE07_ASCENDING_V1'
    official=stage=='RAW' and key in ('POOL_RAW_OFFICIAL_ASC_V1','POOL_RAW_OFFICIAL_DESC_V1')
    repair=stage=='RAW' and bool(re.fullmatch(r'POOL_RAW_OFFICIAL_REPAIR_(?:ASC|DESC|EARLY_ASC|EARLY_DESC|RECENT_ASC|RECENT_DESC)_V1',key))
    monthly=stage=='RAW' and bool(re.fullmatch(r'RAW_HISTORY_MONTH_20[0-9]{2}_(0[1-9]|1[0-2])',key))
    if key not in (pools[stage],independent) and not ascending and not monthly and not official and not repair:return False
    prefix=api_url.split('/contents/')[0]
    if not re.fullmatch(r'https://api.github.com/repos/[\w.-]+/[\w.-]+',prefix):return False
    request=urllib.request.Request(prefix+'/actions/runs/'+run,headers={
        'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
    try:
        result,_=open_json(request,30)
    except urllib.error.HTTPError as exc:
        if exc.code==404:return False
        raise
    primary={'RAW':'01-raw','QA1':'02-qa','PRICE':'03-price','FINANCIAL':'04-financial','CHIP':'05-chip'}
    allowed={'.github/workflows/v093-v2-06-reconcile-repair.yml'} if not ascending and not monthly else set()
    if ascending or monthly:allowed.add('.github/workflows/v093-v2-07-raw-ascending.yml')
    if monthly:allowed.add('.github/workflows/v093-v2-01-raw.yml')
    if monthly or official:allowed.add('.github/workflows/v093-official-only-two-ended.yml')
    if monthly or repair:allowed.add('.github/workflows/v093-official-only-repair.yml')
    if monthly or repair:allowed.add('.github/workflows/v093-official-four-lane-repair.yml')
    if stage in primary and key==pools[stage]:allowed.add('.github/workflows/v093-v2-'+primary[stage]+'.yml')
    return result.get('id')==int(run) and result.get('status')=='completed' and result.get('path') in allowed


def acquire(api_url,token,key,owner,now=None,ttl=900,retries=12):
    if not key or not owner or ttl<=0:
        raise ValueError('INVALID_LEASE_REQUEST')
    for attempt in range(retries):
        sha,payload=_read(api_url,token)
        instant=int(time.time() if now is None else now)
        row=payload['jobs'].get(key,{})
        lease=row.get('lease') or {}
        if lease.get('expires_at',0)>instant:
            if not terminal_owner(api_url,token,key,lease):
                raise LeaseBusy(key)
            # This CAS also acquires the successor fence. If any writer changed
            # the manifest, reload and revalidate the run instead of stealing it.
            row['recovery']={'previous_owner':lease['owner'],'previous_fence':lease['fence'],
                             'reason':'TERMINAL_WORKFLOW_CONFIRMED_CHECKPOINT_RETAINED'}
            print('STAGE06_TERMINAL_OWNER_RECOVERED '+lease['owner'],flush=True)
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

