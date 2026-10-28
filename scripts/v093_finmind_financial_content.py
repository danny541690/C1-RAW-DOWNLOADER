"""Partial native financial schema checks. No unit conversion or release proof.

Provider schema: https://finmind.github.io/tutor/TaiwanMarket/Fundamental/
The current provider documentation is not a historical PIT/contract receipt.
"""
import calendar
import datetime
from decimal import Decimal


def inspect_financial(obj, row):
    if row['資料集'] != 'TaiwanStockFinancialStatements':
        raise ValueError('UNMAPPED_FINMIND_FINANCIAL_DATASET')
    records = obj.get('data')
    if obj.get('status') != 200 or not isinstance(records, list) or not records:
        raise ValueError('FINMIND_FINANCIAL_EMPTY_OR_ERROR')
    month = row['月份']
    datetime.date.fromisoformat(month + '-01')
    if row['期間'][:7] != month or not row.get('代碼'):
        raise ValueError('FINMIND_FINANCIAL_TASK_SCOPE')
    keys = set(); type_names = {}; noncanonical = 0
    required = {'date', 'stock_id', 'type', 'origin_name', 'value'}
    for record in records:
        if not isinstance(record, dict) or not required <= record.keys():
            raise ValueError('FINMIND_FINANCIAL_SCHEMA')
        if record['stock_id'] != row['代碼'] or not str(record['date']).startswith(month + '-'):
            raise ValueError('FINMIND_FINANCIAL_PERIOD_CODE')
        day = datetime.date.fromisoformat(record['date'])
        if day.month not in (3, 6, 9, 12) or day.day != calendar.monthrange(day.year, day.month)[1]:
            raise ValueError('FINMIND_FINANCIAL_NOT_QUARTER_END')
        for name in ('type', 'origin_name'):
            if not isinstance(record[name], str) or not record[name].strip():
                raise ValueError('FINMIND_FINANCIAL_ACCOUNT_IDENTITY')
        if type(record['value']) not in (int, float) or not Decimal(str(record['value'])).is_finite():
            raise ValueError('FINMIND_FINANCIAL_INVALID_NUMBER')
        # origin_name is retained: provider type '-' is not a universal account.
        key = tuple(record[k] for k in ('date', 'stock_id', 'type', 'origin_name'))
        if key in keys:
            raise ValueError('FINMIND_FINANCIAL_DUPLICATE_NATIVE_KEY')
        keys.add(key)
        type_names.setdefault(key[:3], set()).add(record['origin_name'])
        noncanonical += int(record['type'] == '-')
    return dict(rows=len(records), finite_value_cells=len(records), retained_native_keys=len(keys),
                ambiguous_account_type_keys=sum(len(names) > 1 for names in type_names.values()),
                noncanonical_type_rows=noncanonical, raw_value_conversion=False,
                canonical_account_key_verified=False, numeric_semantics_verified=False,
                unit_contract_verified=False, quarter_or_halfyear_semantics_verified=False,
                source_coverage_verified=False, pit_verified=False, analysis_release_approved=False,
                validation='NATIVE_FINANCIAL_SCHEMA_PARTIAL_ONLY',
                provider_schema_reference='https://finmind.github.io/tutor/TaiwanMarket/Fundamental/')
