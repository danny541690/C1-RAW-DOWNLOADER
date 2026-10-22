"""Known RAW failures and explicit completion conditions across all sources."""
import collections
import copy
import re
import tempfile
from pathlib import Path

from scripts.v093_stage06_ledger import FileStore, Ledger, digest, receipt_unit

SOURCES=('TWSE','TPEx','MOPS','FinMind')


def reconcile_raw_snapshot(snapshot, states):
    with tempfile.TemporaryDirectory() as tmp:
        store=FileStore(Path(tmp)/'raw.json');store.cas(None,copy.deepcopy(snapshot));ledger=Ledger(store)
        for state in states:
            rows=[]
            for bucket in ('units','financial_units','finmind_units'):
                rows.extend((bucket,r) for r in state.get(bucket,{}).values() if isinstance(r,dict))
            rows.extend(('legacy',r) for r in state.get('legacy_missing_units',[]) if isinstance(r,dict))
            for bucket,row in rows:
                if row.get('status')=='SAVED_BASIC_VERIFIED':continue
                try:
                    unit=receipt_unit(row)
                    stock=str(row.get('stock_id') or '')
                    if stock:
                        if not re.fullmatch(r'[0-9A-Za-z]{4,8}',stock):raise ValueError('UNKNOWN_STOCK_SCOPE')
                        unit['security_id']=stock
                    key=row['unit_id'];counts=state.get('attempt_ledger',{}).get(bucket,{})
                    candidates=[n for n in (counts.get(key),row.get('attempts')) if type(n) is int and n>=0]
                    prior=max(candidates) if candidates else None
                    evidence=digest(dict(receipt=row,counter=counts.get(key)))
                    gap=ledger.observe(unit,'RAW_MISSING','RAW',digest(row),'EXISTING_RAW_FAILURE',
                        prior_attempts=prior,attempt_evidence_sha256=evidence if prior is not None else None)
                    hid=digest(['RAW_EXPECTATION',gap['gap_id']])
                    def hold(doc,now):
                        doc.setdefault('import_holds',{}).setdefault(hid,dict(hold_id=hid,stage='RAW',gap_id=gap['gap_id'],
                            unit_id=key,status='EXPECTED_SCOPE_OR_SUPPLEMENT_EVIDENCE_REQUIRED',
                            reason='NO_GUESSED_CALENDAR_AVAILABILITY_OR_CROSS_SOURCE_EQUIVALENCE',first_seen=now))
                    ledger.transaction(hold)
                except (ValueError,KeyError,TypeError):
                    hid=digest(['RAW_IDENTITY',row])
                    def unresolved(doc,now):
                        doc.setdefault('import_holds',{}).setdefault(hid,dict(hold_id=hid,stage='RAW',
                            status='RAW_IDENTITY_REQUIRED',receipt_sha256=digest(row),unit_id=row.get('unit_id'),first_seen=now))
                    ledger.transaction(unresolved)
        return ledger.snapshot()


def coverage_snapshot(registry, issues=None):
    counts=collections.Counter((r.get('source'),r.get('category')) for r in registry)
    return dict(source_receipt_counts={s:sum(n for (source,cat),n in counts.items() if source==s) for s in SOURCES},
        datasets_seen=sorted({str(cat) for (source,cat) in counts}),expected_catalog_complete=False,
        scan_scope='KNOWN_RECEIPTS_AND_RECORDED_FAILURES',coverage_certified=False,
        status='KNOWN_RECEIPTS_ONLY' if registry else 'UPSTREAM_NOT_INDEXED_OR_NO_RECEIPTS_UNVERIFIED',
        issues=issues or [])


def completion_gate(evidence):
    required=('expected_catalog_complete','all_required_sources_checked','all_expected_units_present',
        'all_raw_hashes_verified','all_financial_accounts_verified','all_repairs_validated','unit_semantics_verified',
        'historical_universe_verified','pit_verified')
    missing=[k for k in required if evidence.get(k) is not True]
    unresolved=evidence.get('unresolved_count')
    if type(unresolved) is not int or unresolved!=0:missing.append('unresolved_count_zero')
    return dict(complete=not missing,status='COMPLETE_VERIFIED' if not missing else 'INCOMPLETE',blocked_by=missing)
