"""Separate staging from analysis approval. Unknown evidence never means PASS."""
import io
import re

import pyarrow.parquet as pq
from scripts.v093_stage06_native_repair import validate_output


def read_repaired_staging(raw, output, unit):
    validate_output(raw, output, unit)
    rows = pq.read_table(io.BytesIO(output)).to_pylist()
    streams = {'indices': [], 'securities': []}
    for row in rows:
        if row['entity_type'] == 'INDEX':
            if row['security_id'] is not None or row['series_kind'] not in ('PRICE_INDEX', 'TOTAL_RETURN_INDEX'):
                raise ValueError('INVALID_INDEX_CONSUMER_IDENTITY')
            streams['indices'].append(row)
        elif row['entity_type'] == 'SECURITY':
            if not re.fullmatch('[0-9A-Za-z]{4,8}', row['security_id'] or ''):
                raise ValueError('INVALID_SECURITY_CONSUMER_IDENTITY')
            streams['securities'].append(row)
        else:
            raise ValueError('UNSUPPORTED_ENTITY_STREAM')
    return dict(status='STAGING_ONLY', streams=streams, approved_for_analysis=False,
                numeric_verified=False, pit_verified=False, universe_verified=False)


def analysis_gate(evidence):
    required = ('schema_ok', 'source_identity_ok', 'numeric_semantics_ok', 'unit_ok',
                'pit_ok', 'universe_ok', 'scope_complete', 'approved_processor')
    missing = [key for key in required if evidence.get(key) is not True]
    return dict(approved_for_analysis=not missing, blocked_by=missing)


def expected_unit_decision(evidence):
    """Only explicit catalog evidence can authorize a missing-unit download."""
    required = ('source_scope_verified', 'calendar_verified', 'universe_verified', 'availability_verified')
    if any(evidence.get(k) is not True for k in required):
        return 'IDENTITY_OR_EXPECTATION_HOLD'
    if evidence.get('applicable') is False:
        return 'NOT_APPLICABLE'
    if evidence.get('applicable') is not True:
        return 'IDENTITY_OR_EXPECTATION_HOLD'
    return 'EXPECTED'
