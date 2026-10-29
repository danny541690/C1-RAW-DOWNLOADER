"""Verify old receipts before reuse. Caller supplies the retained-RAW read adapter.

This module neither downloads market data nor writes production state. A caller
must durably save the returned manifest before advancing a migration generation.
"""
import hashlib,json
from collections import defaultdict

SUCCESS={'SAVED_BASIC_VERIFIED','SAVED_RAW_ROWS_READBACK_VERIFIED','RAW_DOWNLOADED_UNVERIFIED'}

def migrate(receipts,read_retained,source):
    grouped=defaultdict(list)
    for row in receipts:
        if row.get('source')!=source:continue
        if not isinstance(row.get('task_key'),str) or not row['task_key']:raise ValueError('MIGRATION_TASK_KEY_MISSING')
        if not isinstance(row.get('status','UNKNOWN'),str):raise ValueError('MIGRATION_STATUS_SCHEMA')
        attempts=row.get('attempts',0)
        if type(attempts) is not int or attempts<0:raise ValueError('INVALID_ATTEMPT_COUNT')
        grouped[row['task_key']].append(row)
    reusable={};pending={};blocked={};cache={}
    for key,versions in sorted(grouped.items()):
        attempts=max(v.get('attempts',0) for v in versions)
        success=[v for v in versions if v.get('status') in SUCCESS]
        digests={v.get('sha256') for v in success if isinstance(v.get('sha256'),str) and v['sha256']}
        base=dict(task_key=key,source=source,attempts=attempts,retry_budget_reset=False)
        if len(digests)>1:
            blocked[key]=dict(base,reason='CONFLICTING_RAW_VERSIONS_REVIEW_REQUIRED',sha256=sorted(digests));continue
        if not success:
            pending[key]=dict(base,reason='NO_REUSABLE_RAW_RECEIPT',prior_statuses=sorted({v.get('status','UNKNOWN') for v in versions}));continue
        verified=[];errors=[]
        for row in success:
            ref=row.get('raw_reference');expected=row.get('sha256')
            if not ref or not isinstance(expected,str) or len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
                errors.append('RAW_REFERENCE_OR_SHA_MISSING');continue
            try:
                if ref not in cache:
                    raw=read_retained(ref)
                    if not isinstance(raw,bytes):raise ValueError('MIGRATION_RAW_MISSING')
                    cache[ref]=hashlib.sha256(raw).hexdigest()
                if cache[ref]!=expected:
                    raise ValueError('MIGRATION_RAW_SHA_MISMATCH')
                verified.append(dict(raw_reference=ref,sha256=expected))
            except Exception as exc:
                # Do not persist OAuth/API exception text.
                errors.append(type(exc).__name__)
        if verified:
            # Other failed references remain visible; a same-SHA verified copy
            # can be reused, but failed storage references are not silently fixed.
            reusable[key]=dict(base,status='RETAINED_RAW_READBACK_VERIFIED',references=verified,
                reference_errors=errors,numeric_verified=False,pit_verified=False,full_acceptance=False)
        else:blocked[key]=dict(base,reason='READBACK_OR_RECEIPT_VERIFICATION_FAILED',errors=errors)
    result=dict(schema='JARVIS_SOURCE_RECEIPT_MIGRATION_V1',source=source,
        total_tasks=len(grouped),reusable=reusable,pending=pending,blocked=blocked,
        counts=dict(reusable=len(reusable),pending=len(pending),blocked=len(blocked)),
        migration_review_complete=not blocked,ready_for_production_cutover=False,
        retry_counts_scope='MAX_RECORDED_COUNT_NOT_RESET; divergent attempt histories require reconciliation',
        market_downloads=0,production_writes=0)
    result['manifest_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
