"""Current unresolved states and actions; never certify absent or unverified data."""
from collections import Counter

def problem(row):
    s=row.get('status','UNKNOWN')
    if row.get('complete') or s in ('CONTENT_CHECK_PASS','BASIC_CONTENT_PASS'):
        return 'CHECKED_CONTENT','PRESERVE_VALIDATED_RAW'
    states={
        'UNRESOLVED_HISTORICAL_COMPARE_SCOPE':('HISTORICAL_FINANCIAL_ROUTE_REVIEW','VERIFY_LEGACY_ENDPOINT_OR_DOCUMENTED_ADOPTION'),
        'LOCAL_REVALIDATION_FAILED_KEEP_RAW':('LOCAL_REVALIDATION_FAILURE','REVIEW_LOCAL_AUDIT_KEEP_PRIOR_RAW_NO_REDOWNLOAD'),
        'WAIT_SHARED_SOURCE_WINDOW':('SHARED_PACING_WAIT','WAIT_WITHOUT_SOURCE_ATTEMPT'),
        'SOURCE_CHECK_REQUEST_INTENT':('REQUEST_IN_FLIGHT_OR_INTERRUPTED','RESUME_DURABLE_INTENT_WITH_CAP'),
        'OFFICIAL_PERIOD_NOT_PROVIDED':('HISTORY_NOT_OFFERED','KEEP_EXPLICIT_BOUND_SEEK_OTHER_OFFICIAL_ARCHIVE'),
        'SOURCE_NO_DATA_UNCONFIRMED':('SOURCE_EMPTY_UNCONFIRMED','CHECK_HOLIDAY_LISTING_EVENT_SCOPE_NO_ABSENCE_CLAIM'),
        'SOURCE_CONTENT_INCOMPLETE':('SOURCE_COVERAGE_INCOMPLETE','VERIFY_COMPANIES_PERIOD_AND_ENDPOINT_SCOPE'),
        'UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE':('COMPANY_ENDPOINT_SCOPE','VERIFY_HISTORICAL_UNIVERSE_AND_SELECTOR'),
        'LOCAL_PARAM_ENCODING_ERROR':('PARAMETER_ENCODING','FIX_REPEATED_KEY_FORM_BEFORE_REQUEST'),
        'UNRESOLVED_SOURCE_LIMIT':('SOURCE_ACCESS_BLOCKED','SHARED_SOURCE_COOLDOWN_THEN_BOUNDED_RETRY'),
        'UNRESOLVED_RETRY_CYCLES_EXHAUSTED':('RETRY_EXHAUSTED','OFFLINE_RECOVER_RETAINED_RAW_NO_CAP_RESET'),
        'UNRESOLVED_SOURCE_BACKOFF':('SOURCE_BACKOFF','WAIT_SOURCE_COOLDOWN_CONTINUE_LOCAL_AUDITS')}
    if s in states:return states[s]
    if s in ('LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS','SOURCE_CHECKED_OPEN_QUALITY_ITEMS'):
        return 'QUALITY_VALIDATION_OPEN','VERIFY_FIELD_RULES_ACCOUNTING_UNITS_AND_PIT'
    if s in ('UNRESOLVED_OFFICIAL_ROUTE','OFFICIAL_ROUTE_NOT_FOUND'):
        return 'OFFICIAL_ROUTE_UNRESOLVED','RECOVER_RETAINED_RAW_OR_VERIFY_CANONICAL_ROUTE'
    error=' '.join(str(row.get(k,'')) for k in ('error','local_error'))
    if any(k in error for k in ('READBACK','SHA_MISMATCH','readback hash')):
        return 'READBACK_OR_HASH_FAILURE','KEEP_PRIOR_RAW_RECEIPT_REVIEW_REMOTE_BYTES'
    if any(k in error for k in ('TimeoutError','URLError','IncompleteRead','HTTP Error 5')):
        return 'TRANSPORT_FAILURE','SHARED_TRANSIENT_COOLDOWN_THEN_BOUNDED_RETRY'
    if s=='LOCAL_REPARSE_FAILED' or row.get('local_error'):
        return 'PARSER_OR_SEMANTIC_FAILURE','FIX_PARSER_FROM_RETAINED_EVIDENCE_PRESERVE_RAW'
    return 'UNRESOLVED_REQUIRES_REVIEW','REVIEW_EVIDENCE_WITHOUT_CERTIFYING'

def problem_summary(journal):
    rows=list(journal.get('units',{}).values())
    return dict(total_units=len(rows),current_problem_counts=dict(Counter(problem(r)[0] for r in rows)),
        open_quality_checks=dict(Counter(k for r in rows if not r.get('complete') for k in r.get('open_checks',[]))),
        unresolved_units=sum(problem(r)[0]!='CHECKED_CONTENT' for r in rows),
        scope='THIS_MONTH_JOURNAL_ONLY_NOT_GLOBAL_COVERAGE',numeric_verified=False,pit_verified=False)

def unresolved_items(journal):
    items=[]
    fields=('unit_id','source','category','period','report_period','status','error','local_error',
        'raw_sha256','original_sha256','official_sha256','last_response_sha256',
        'last_response_evidence_file','saved_evidence_file','readback_verified','reparse_receipt',
        'open_checks','review_flags','route_reference','content_audit_revision','attempts','retry_cycle','next_retry_at','source_start','local_recovery_revision')
    for key,row in journal.get('units',{}).items():
        family,action=problem(row)
        if family=='CHECKED_CONTENT':continue
        item={k:row[k] for k in fields if k in row}
        item.update(unit_id=row.get('unit_id',key),problem_family=family,next_action=action,
                    complete=False,numeric_verified=False,pit_verified=False)
        items.append(item)
    return items
