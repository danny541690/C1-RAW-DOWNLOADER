"""Read MOPS comparative statement matrices without losing account/period axes.

Only existing RAW is consumed. Values, company columns, statement scope and
native units remain explicit; YTD is never converted to quarterly or PIT.
"""
import calendar
import datetime as dt
import decimal
import hashlib
import io
import re

from lxml import html
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.v093_stage06_ledger import checked_unit

VERSION = 'MOPS_MATRIX_FINANCIAL_REPAIR_V1'
REPORTS = ('IncomeStatement','BalanceSheet','CashflowStatement')
MISSING = {'','--','---','-','－','—','N/A','NA','不適用','無資料','無','尚無資料'}
FIELDS = ('source','dataset','security_id','company_name','period_end','fiscal_year','fiscal_quarter',
    'period_kind','statement_scope','native_unit_text','account_name','row_index','column_index',
    'raw_value','decimal_text','announcement_time')
SCHEMA = pa.schema([(k,pa.int64() if k in ('row_index','column_index') else pa.string()) for k in FIELDS])


def text(node): return ' '.join(node.text_content().split())


def number(value):
    s=value.strip().replace(',','').replace('−','-')
    if s in MISSING:return None
    if re.fullmatch(r'\([0-9]+(?:\.[0-9]+)?\)',s):s='-'+s[1:-1]
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)',s):raise ValueError('UNRECOGNIZED_FINANCIAL_CELL')
    n=decimal.Decimal(s)
    if not n.is_finite():raise ValueError('NONFINITE_FINANCIAL_CELL')
    return str(n)


def structure(raw,unit):
    checked_unit(unit)
    if unit['source']!='MOPS' or unit['dataset'] not in REPORTS or unit['security_id']!='ALL_MARKET':
        raise ValueError('MOPS_FINANCIAL_UNIT_REQUIRED')
    root=html.fromstring(raw.decode('utf-8-sig'))
    periods=set(root.xpath('//input[@name="yearseason"]/@value'))
    if len(periods)!=1:raise ValueError('UNPROVEN_FINANCIAL_PERIOD')
    m=re.fullmatch(r'(20\d{2})Q([1-4])',next(iter(periods)))
    if not m:raise ValueError('UNPROVEN_FINANCIAL_PERIOD')
    year,quarter=map(int,m.groups());mo=quarter*3
    end=dt.date(year,mo,calendar.monthrange(year,mo)[1]).isoformat()
    if unit['period_start']!=end or unit['period_end']!=end:raise ValueError('FINANCIAL_PERIOD_CONFLICT')
    for name,value in (('year',str(year)),('season',str(quarter))):
        observed=set(root.xpath('//input[@name="'+name+'"]/@value'))
        if observed and observed!={value}:raise ValueError('FINANCIAL_PERIOD_CONFLICT')
    names=root.xpath('//input[@name="reportName"]/@value')
    codes=[]
    for name in names:
        match=re.fullmatch(r'([0-9A-Za-z]{4,8})\s+(.+)',name.strip())
        if not match:raise ValueError('COMPANY_IDENTITY_UNPROVEN')
        codes.append(match.group(1))
    if not codes or len(codes)!=len(set(codes)):raise ValueError('COMPANY_COLUMN_AMBIGUOUS')
    heads=root.xpath('//*[@id="headTable"]');bodies=root.xpath('//*[@id="bodyTable"]')
    if len(heads)!=1 or len(bodies)!=1:raise ValueError('FINANCIAL_MATRIX_REQUIRED')
    left=heads[0].xpath('.//tbody/tr');right=bodies[0].xpath('.//tbody/tr')
    if not left or len(left)!=len(right):raise ValueError('ACCOUNT_MATRIX_ROW_MISMATCH')
    headers=bodies[0].xpath('.//thead/tr')
    if len(headers)!=2:raise ValueError('COMPANY_HEADER_REQUIRED')
    scope_cells=headers[0].xpath('./th|./td');company_cells=headers[1].xpath('./th|./td')
    if len(scope_cells)!=len(codes) or len(company_cells)!=len(codes):raise ValueError('COMPANY_HEADER_WIDTH_MISMATCH')
    for i,cell in enumerate(company_cells):
        if not re.match(re.escape(codes[i])+r'\s',text(cell)):raise ValueError('COMPANY_COLUMN_ORDER_CONFLICT')
    scopes=[text(c) for c in scope_cells]
    if any(s not in ('合併','個別','個體') for s in scopes):raise ValueError('STATEMENT_SCOPE_UNPROVEN')
    units=[u.strip() for node in root.xpath('//text()') if '金額單位' in str(node)
           for u in re.findall(r'金額單位\s*[：:]\s*([^()（）]+)',str(node))]
    if len(set(units))!=1:raise ValueError('FINANCIAL_NATIVE_UNIT_UNPROVEN')
    unit_text=units[0].strip()
    labels=[];cells=[]
    for a,b in zip(left,right):
        lab=a.xpath('./th|./td');values=b.xpath('./td|./th')
        if len(lab)!=1 or len(values)!=len(codes):raise ValueError('ACCOUNT_MATRIX_WIDTH_MISMATCH')
        if any(c.get('rowspan','1')!='1' or c.get('colspan','1')!='1' for c in lab+values):raise ValueError('UNPROVEN_FINANCIAL_SPAN')
        label=text(lab[0])
        if not label:raise ValueError('ACCOUNT_LABEL_MISSING')
        labels.append(label);cells.append(values)
    combined=' '.join(labels)
    signatures={
        'CashflowStatement':bool(re.search(r'營業活動.*?淨現金',combined)) and '期末現金' in combined,
        'BalanceSheet':('資產總計' in labels or '資產總額' in labels) and any('負債' in s for s in labels),
        'IncomeStatement':any(re.search(r'營業收入|收益合計|收入合計',s) for s in labels) and any(re.search(r'淨利|淨損',s) for s in labels)}
    if not signatures[unit['dataset']]:raise ValueError('FINANCIAL_STATEMENT_TYPE_UNPROVEN')
    return dict(root=root,codes=codes,names=names,scopes=scopes,cells=cells,labels=labels,
        year=str(year),quarter=str(quarter),period=end,unit=unit_text,
        period_kind='INSTANT' if unit['dataset']=='BalanceSheet' else 'YTD')


def transform(raw,unit):
    s=structure(raw,unit);rows=[]
    for ri,cells in enumerate(s['cells']):
        for ci,cell in enumerate(cells):
            value=text(cell);parsed=number(value)
            if parsed is None:continue
            rows.append(dict(source='MOPS',dataset=unit['dataset'],security_id=s['codes'][ci],company_name=s['names'][ci],
                period_end=s['period'],fiscal_year=s['year'],fiscal_quarter=s['quarter'],period_kind=s['period_kind'],
                statement_scope=s['scopes'][ci],native_unit_text=s['unit'],account_name=s['labels'][ri],
                row_index=ri,column_index=ci,raw_value=value,decimal_text=parsed,announcement_time=None))
    if not rows:raise ValueError('NO_NATIVE_FINANCIAL_NUMERIC_CELLS')
    out=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),out,compression='zstd');return out.getvalue()


def validate_output(raw,output,unit):
    s=structure(raw,unit);table=pq.read_table(io.BytesIO(output))
    if table.schema!=SCHEMA:raise ValueError('FINANCIAL_OUTPUT_SCHEMA_MISMATCH')
    rows=table.to_pylist();seen=set()
    for row in rows:
        ri,ci=row['row_index'],row['column_index'];key=(ri,ci)
        if key in seen or not 0<=ri<len(s['cells']) or not 0<=ci<len(s['codes']):raise ValueError('FINANCIAL_CELL_COORDINATE_CONFLICT')
        seen.add(key);native_value=text(s['cells'][ri][ci])
        expected=dict(source='MOPS',dataset=unit['dataset'],security_id=s['codes'][ci],company_name=s['names'][ci],
            period_end=s['period'],fiscal_year=s['year'],fiscal_quarter=s['quarter'],period_kind=s['period_kind'],
            statement_scope=s['scopes'][ci],native_unit_text=s['unit'],account_name=s['labels'][ri],announcement_time=None)
        if any(row[k]!=v for k,v in expected.items()) or row['raw_value']!=native_value:raise ValueError('FINANCIAL_IDENTITY_OR_CONTEXT_MISMATCH')
        expected_number=number(native_value)
        if expected_number is None or decimal.Decimal(row['decimal_text'])!=decimal.Decimal(expected_number):raise ValueError('FINANCIAL_NUMERIC_CELL_MISMATCH')
    required={(ri,ci) for ri,cells in enumerate(s['cells']) for ci,c in enumerate(cells) if number(text(c)) is not None}
    if not required or seen!=required:raise ValueError('FINANCIAL_CELLS_MISSING_OR_EXTRA')
    return dict(checks=dict(hash_readback_ok=True,parser_ok=True,date_ok=True,security_ok=True),evidence=dict(
        parser_version=VERSION,source='MOPS',native_records=len(s['codes']),native_accounts=len(s['labels']),
        cells_compared=len(seen),missing_native_cells=len(s['cells'])*len(s['codes'])-len(seen),
        native_unit_text=s['unit'],period_kind=s['period_kind'],period_end=s['period'],
        input_sha256=hashlib.sha256(raw).hexdigest(),output_sha256=hashlib.sha256(output).hexdigest(),
        numeric_roundtrip_only=True,numeric_semantics_verified=False,pit_verified=False,
        source_coverage_verified=False,announcement_time_inferred=False))
