"""Sticky month/year ownership for opposite full-range TAIFEX repair frontiers."""
import copy
from scripts.v093_five_stage_durable_gate import _read, _put, LeaseConflict

PLAN='TAIFEX_FULL_RANGE_2000_LATEST_20261027_V1'

def group(job):
    if job['kind']=='annual':return 'ANNUAL|'+job['start'][:4]
    if job['kind']=='snapshot':return 'SNAPSHOT|'+job['end']
    return 'MONTH|'+job['start'][:7]

def elect(state,direction,job):
    if direction not in ('ASC','DESC') or not '2000-01-01'<=job['start']<=job['end']:
        raise ValueError('INVALID_FULL_RANGE_JOB')
    state=copy.deepcopy(state);claims=state.setdefault('claims',{});key=group(job)
    prior=claims.get(key)
    if prior:return state,prior['direction']==direction
    claims[key]=dict(direction=direction,status='OWNED_NOT_COMPLETENESS_CERTIFIED')
    return state,True

def claim(api,token,direction,job,cache):
    key=group(job)
    if key in cache:return cache[key]['direction']==direction
    for _ in range(12):
        sha,m=_read(api,token);prior=m['jobs'].get(PLAN,{})
        state,allowed=elect(prior,direction,job)
        if state==prior:
            cache.update(state.get('claims',{}));return allowed
        m['jobs'][PLAN]=state
        if _put(api,token,sha,m,'taifex: elect single historical month owner before source request'):
            cache.update(state['claims']);return allowed
    raise LeaseConflict('TAIFEX_FULL_RANGE_CAS_EXHAUSTED')

def merge_verified(state,peer):
    """Import immutable successful receipts only; never erase a local integrity hold."""
    imported=0
    for key,entry in peer.get('receipts',{}).items():
        old=state.setdefault('receipts',{}).get(key,{})
        if old.get('integrity_hold') or old.get('status')=='SAVED_BASIC_VERIFIED':continue
        if (entry.get('status')!='SAVED_BASIC_VERIFIED' or entry.get('integrity_hold')
                or not entry.get('remote_readback_hash_verified') or not entry.get('file_id') or not entry.get('sha256')):continue
        state['receipts'][key]=copy.deepcopy(entry);imported+=1
    for host,until in peer.get('source_backoff',{}).items():
        backoff=state.setdefault('source_backoff',{});backoff[host]=max(backoff.get(host,0),until)
    return imported
