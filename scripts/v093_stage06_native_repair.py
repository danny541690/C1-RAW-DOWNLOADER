"""Dataset-specific staging repair; no live parser replacement or RAW writes."""
import datetime as dt
import decimal
import hashlib
import io
import json
import re

import pyarrow as pa
import pyarrow.parquet as pq

from scripts.v093_stage06_ledger import checked_unit

VERSION = 'NATIVE_INDEX_EVENT_REPAIR_V1'
INDEX_METRICS = ('收市指數', '漲跌', '漲跌幅度(%)')
EVENTS = {('TWSE', 'capital_reduction'): ('恢復買賣日期', '股票代號'),
          ('TPEx', 'ex_dividend'): ('除權息日期', '代號')}
MISSING = {'', '--', '---', 'N/A', 'NA', '－'}
SCHEMA = pa.schema([(k, pa.int64() if k in ('table_index', 'row_index', 'column_index') else pa.string()) for k in
    ('source', 'market', 'dataset', 'entity_type', 'security_id', 'native_name', 'series_kind', 'date',
     'date_role', 'table_index', 'row_index', 'column_index', 'native_field', 'raw_value', 'decimal_text')])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def date(value):
    match = re.fullmatch(r'(\d{3,4})[-/]?(\d{2})[-/]?(\d{2})', str(value).strip())
    if not match:
        raise ValueError('INVALID_CONTENT_DATE')
    y, mo, d = map(int, match.groups())
    return dt.date(y + 1911 if y < 1911 else y, mo, d).isoformat()


def number(value):
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ValueError('INVALID_NUMERIC_CELL')
    text = str(value).strip().replace(',', '').replace('−', '-')
    if text in MISSING:
        return None
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', text):
        raise ValueError('INVALID_NUMERIC_CELL')
    n = decimal.Decimal(text)
    if not n.is_finite():
        raise ValueError('INVALID_NUMERIC_CELL')
    return str(n)


def unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('DUPLICATE_JSON_FIELD')
        out[key] = value
    return out


def native(raw, unit):
    checked_unit(unit)
    if unit['market'] != {'TWSE': 'TSE', 'TPEx': 'OTC'}.get(unit['source']) or unit['security_id'] != 'ALL_MARKET':
        raise ValueError('NATIVE_UNIT_SCOPE_MISMATCH')
    obj = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)
    if not isinstance(obj, dict) or str(obj.get('stat', '')).upper() != 'OK':
        raise ValueError('UNSUCCESSFUL_SOURCE_RESPONSE')
    key = (unit['source'], unit['dataset'])
    index = key == ('TPEx', 'indices')
    if not index and key not in EVENTS:
        raise ValueError('UNSUPPORTED_REPAIR_DATASET')
    tables = obj.get('tables') if index or unit['source'] == 'TPEx' else [obj]
    if not isinstance(tables, list) or not tables:
        raise ValueError('NO_NATIVE_TABLES')
    parent_day = date(obj['date']) if index else None
    rows = []
    for ti, table in enumerate(tables):
        fields, data = table.get('fields'), table.get('data')
        if not isinstance(fields, list) or not isinstance(data, list) or len(set(fields)) != len(fields):
            raise ValueError('INVALID_NATIVE_TABLE')
        if 'totalCount' in table and table['totalCount'] != len(data):
            raise ValueError('NATIVE_RECORD_COUNT_MISMATCH')
        if index:
            if fields[0] not in ('指數', '報酬指數') or not all(k in fields for k in INDEX_METRICS):
                raise ValueError('UNPROVEN_INDEX_SCHEMA')
            if date(table.get('date')) != parent_day:
                raise ValueError('TABLE_RESPONSE_DATE_CONFLICT')
        else:
            event_field, code_field = EVENTS[key]
            if event_field not in fields or code_field not in fields:
                raise ValueError('EVENT_IDENTITY_OR_DATE_MISSING')
        for ri, values in enumerate(data):
            if not isinstance(values, list) or len(values) != len(fields):
                raise ValueError('ROW_WIDTH_MISMATCH')
            if index:
                name = str(values[0]).strip()
                if not name:
                    raise ValueError('INDEX_NAME_MISSING')
                security = None
                observed = parent_day
                entity = 'INDEX'
                series = 'TOTAL_RETURN_INDEX' if fields[0] == '報酬指數' else 'PRICE_INDEX'
                role = 'OBSERVATION_DATE'
                columns = [fields.index(k) for k in INDEX_METRICS]
            else:
                observed = date(values[fields.index(event_field)])
                security = str(values[fields.index(code_field)]).strip()
                if not re.fullmatch(r'[0-9A-Za-z]{4,8}', security):
                    raise ValueError('INVALID_NATIVE_SECURITY_ID')
                name = str(values[fields.index('名稱')]).strip() if '名稱' in fields else ''
                entity, series = 'SECURITY', None
                role = 'RESUMPTION_DATE' if key[1] == 'capital_reduction' else 'EX_RIGHT_DIVIDEND_DATE'
                excluded = {event_field, code_field, '名稱', '減資原因', '詳細資料', '權/息'}
                columns = [i for i, field in enumerate(fields) if field not in excluded]
            if not unit['period_start'] <= observed <= unit['period_end']:
                raise ValueError('CONTENT_DATE_OUTSIDE_TASK_SCOPE')
            for ci in columns:
                numeric = number(values[ci])
                if numeric is None:
                    continue
                rows.append(dict(source=unit['source'], market=unit['market'], dataset=unit['dataset'],
                    entity_type=entity, security_id=security, native_name=name, series_kind=series,
                    date=observed, date_role=role, table_index=ti, row_index=ri, column_index=ci,
                    native_field=fields[ci], raw_value=str(values[ci]), decimal_text=numeric))
    if not rows:
        raise ValueError('NO_PARSED_NUMERIC_CELLS')
    return obj, rows


def transform(raw, unit):
    _, rows = native(raw, unit)
    metadata = dict(parser_version=VERSION, input_sha256=sha(raw), unit=unit,
                    numeric_verified=False, pit_verified=False, production_data_approved=False,
                    status='TEST_STAGING_NOT_APPROVED')
    table = pa.Table.from_pylist(rows, schema=SCHEMA).replace_schema_metadata(
        {b'jarvis_stage06': json.dumps(metadata, sort_keys=True).encode()})
    output = io.BytesIO()
    pq.write_table(table, output, compression='zstd')
    return output.getvalue()


def validate_output(raw, output, unit):
    """Reconcile stored cells to native coordinates, without calling transform."""
    checked_unit(unit)
    if unit['market'] != {'TWSE': 'TSE', 'TPEx': 'OTC'}.get(unit['source']) or unit['security_id'] != 'ALL_MARKET':
        raise ValueError('NATIVE_UNIT_SCOPE_MISMATCH')
    table = pq.read_table(io.BytesIO(output))
    if not table.schema.remove_metadata().equals(SCHEMA):
        raise ValueError('OUTPUT_SCHEMA_MISMATCH')
    meta = json.loads((table.schema.metadata or {})[b'jarvis_stage06'])
    if meta['input_sha256'] != sha(raw) or meta['unit'] != unit or meta['parser_version'] != VERSION:
        raise ValueError('OUTPUT_PROVENANCE_MISMATCH')
    if any(meta.get(k) is not False for k in ('numeric_verified', 'pit_verified', 'production_data_approved')):
        raise ValueError('UNSUPPORTED_APPROVAL_CLAIM')
    obj = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)
    if str(obj.get('stat', '')).upper() != 'OK':
        raise ValueError('UNSUCCESSFUL_SOURCE_RESPONSE')
    tables = obj['tables'] if 'tables' in obj else [obj]
    expected = set()
    for ti, tab in enumerate(tables):
        if 'totalCount' in tab and tab['totalCount'] != len(tab['data']):
            raise ValueError('NATIVE_RECORD_COUNT_MISMATCH')
        index = unit['dataset'] == 'indices'
        skip = {'恢復買賣日期', '股票代號', '除權息日期', '代號', '名稱', '減資原因', '詳細資料', '權/息'}
        columns = [i for i, field in enumerate(tab['fields']) if (field in INDEX_METRICS if index else field not in skip)]
        for ri, row in enumerate(tab['data']):
            for ci in columns:
                if str(row[ci]).strip() not in MISSING:
                    expected.add((ti, ri, ci))
    seen = set()
    for row in table.to_pylist():
        coord = row['table_index'], row['row_index'], row['column_index']
        if coord in seen or coord not in expected:
            raise ValueError('EXTRA_OR_DUPLICATE_OUTPUT_CELL')
        seen.add(coord)
        ti, ri, ci = coord
        tab = tables[ti];values = tab['data'][ri];field = tab['fields'][ci]
        if row['source'] != unit['source'] or row['market'] != unit['market'] or row['dataset'] != unit['dataset']:
            raise ValueError('OUTPUT_IDENTITY_MISMATCH')
        if row['native_field'] != field or row['raw_value'] != str(values[ci]):
            raise ValueError('NATIVE_CELL_MISMATCH')
        if decimal.Decimal(row['decimal_text']) != decimal.Decimal(str(values[ci]).strip().replace(',', '').replace('−', '-')):
            raise ValueError('NUMERIC_CELL_MISMATCH')
        if unit['dataset'] == 'indices':
            observed = date(obj['date'])
            series = 'TOTAL_RETURN_INDEX' if tab['fields'][0] == '報酬指數' else 'PRICE_INDEX'
            if (row['entity_type'], row['security_id'], row['native_name'], row['series_kind'], row['date_role']) != (
                    'INDEX', None, str(values[0]).strip(), series, 'OBSERVATION_DATE'):
                raise ValueError('INDEX_IDENTITY_MISMATCH')
            if date(tab['date']) != observed:
                raise ValueError('TABLE_RESPONSE_DATE_CONFLICT')
        else:
            event_field, code_field = EVENTS[(unit['source'], unit['dataset'])]
            observed = date(values[tab['fields'].index(event_field)])
            role = 'RESUMPTION_DATE' if unit['dataset'] == 'capital_reduction' else 'EX_RIGHT_DIVIDEND_DATE'
            if row['entity_type'] != 'SECURITY' or row['security_id'] != str(values[tab['fields'].index(code_field)]).strip() or row['date_role'] != role or row['series_kind'] is not None:
                raise ValueError('EVENT_IDENTITY_MISMATCH')
        if row['date'] != observed or not unit['period_start'] <= observed <= unit['period_end']:
            raise ValueError('OUTPUT_DATE_MISMATCH')
    if not seen or seen != expected:
        raise ValueError('MISSING_OUTPUT_CELLS')
    return {'checks': {'hash_readback_ok': True, 'parser_ok': True, 'date_ok': True, 'security_ok': True},
            'evidence': {'input_sha256': sha(raw), 'output_sha256': sha(output), 'cells_compared': len(seen),
                         'native_records': sum(len(t['data']) for t in tables), 'numeric_roundtrip_only': True,
                         'numeric_semantics_verified': False, 'pit_verified': False,
                         'source_coverage_verified': False, 'parser_version': VERSION}}
