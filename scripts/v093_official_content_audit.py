"""Row-level official RAW checks; preserve native units and never fabricate cells."""
import html
import json
import re
import hashlib
from decimal import Decimal, InvalidOperation

PRICE={'開盤價':'open','開盤':'open','最高價':'high','最高':'high','最低價':'low','最低':'low','收盤價':'close','收盤':'close'}
NONNEGATIVE={'成交股數','成交金額','成交筆數','買進股數','賣出股數','買進金額','賣出金額','融資今日餘額','融券今日餘額'}
IDENTIFIERS={'代號','股票代號','證券代號','公司代號','公司代碼'}

def label(value):return re.sub(r'\s+','',html.unescape(re.sub('<[^>]+>','',str(value))))

def number(value):
    s=label(value).replace(',','').replace('−','-')
    if s in ('','--','---','-','N/A','不適用'):return None
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',s):raise ValueError('NON_NUMERIC_CELL:'+s[:60])
    try:n=Decimal(s)
    except InvalidOperation:raise ValueError('INVALID_DECIMAL')
    if not n.is_finite():raise ValueError('NON_FINITE_NUMBER')
    return n

def audit_json(raw,job):
    obj=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(obj,dict):raise ValueError('EXPECTED_OFFICIAL_JSON_OBJECT')
    counts=dict(rows_checked=0,numeric_cells_checked=0,ohlc_rows_checked=0,duplicate_keys_checked=0)
    checked=[];unverified=[]
    for ti,table in enumerate(obj.get('tables') or [obj]):
        fields=[label(f) for f in table.get('fields',[])];rows=table.get('data',[])
        if not rows:continue
        if not fields:unverified.append('TABLE_WITHOUT_FIELD_NAMES');continue
        codeidx=next((i for i,f in enumerate(fields) if f in IDENTIFIERS),None)
        pcols={PRICE[f]:i for i,f in enumerate(fields) if f in PRICE}
        ratios={i for i,f in enumerate(fields) if job['category']=='foreign_holdings' and ('持股比率' in f or '持股比例' in f) and '上限' not in f}
        ncols={i for i,f in enumerate(fields) if any(token in f for token in NONNEGATIVE)}|ratios
        seen=set()
        for ri,row in enumerate(rows):
            if not isinstance(row,list) or len(row)!=len(fields):raise ValueError('ROW_WIDTH_MISMATCH')
            counts['rows_checked']+=1
            if codeidx is not None:
                code=label(row[codeidx])
                summary=(not code and job.get('source')=='TWSE' and job['category']=='lending'
                    and fields[:7]==['代號','名稱','前日餘額','賣出','買進','現券','今日餘額']
                    and label(row[1])=='合計' and ri==len(rows)-1)
                if not code and not summary:raise ValueError('EMPTY_SECURITY_IDENTIFIER')
                # These native tables have one row per security; event/financial tables may have multiple events.
                if job['category'] in ('prices','prices_indices','institutional','margin','valuation','foreign_holdings','marketcap'):
                    if code in seen:raise ValueError('DUPLICATE_SECURITY_IN_SAME_TABLE:'+code)
                    seen.add(code);counts['duplicate_keys_checked']+=1
            for ci in ncols:
                value=row[ci]
                if ci in ratios:
                    text=label(value)
                    value=text[:-1] if text.endswith('%') else value
                val=number(value);counts['numeric_cells_checked']+=1
                if val is None:
                    unverified.append('MISSING_NUMERIC_CELL');continue
                if val<0:raise ValueError('NEGATIVE_NONNEGATIVE_FIELD:'+fields[ci])
                if ci in ratios and val>100:raise ValueError('HOLDING_PERCENT_OUT_OF_RANGE')
            if len(pcols)==4 and codeidx is not None and re.fullmatch(r'[1-9]\d{3}',label(row[codeidx])):
                vals={k:number(row[i]) for k,i in pcols.items()}
                if any(v is None or v<=0 for v in vals.values()):
                    unverified.append('NO_VALID_TRADE_PRICE_REQUIRES_REVIEW');continue
                if not vals['low']<=vals['open']<=vals['high'] or not vals['low']<=vals['close']<=vals['high']:
                    raise ValueError('OHLC_RELATIONSHIP_VIOLATION')
                counts['ohlc_rows_checked']+=1
        checked.append('TABLE_'+str(ti)+'_ROW_STRUCTURE')
    if not counts['rows_checked']:raise ValueError('NO_ROWS_AUDITED')
    if job['category'] in ('prices','prices_indices') and not counts['ohlc_rows_checked']:
        unverified.append('OHLC_FIELDS_NOT_RECOGNIZED')
    if not counts['numeric_cells_checked'] and not counts['ohlc_rows_checked']:
        unverified.append('NUMERIC_FIELD_RULES_NOT_COVERED')
    return dict(**counts,checks=checked+['SECURITY_DUPLICATES','RECOGNIZED_NUMERIC_DOMAINS','OHLC_RELATIONSHIPS'],
                unverified=sorted(set(unverified)),units_policy='NATIVE_UNITS_PRESERVED_NO_UNPROVEN_CONVERSION',
                cross_source_verified=False,pit_verified=False)

def audit_html(raw,job):
    text=None
    for enc in ('utf-8-sig','cp950'):
        try:text=raw.decode(enc);break
        except UnicodeDecodeError:pass
    if text is None:raise ValueError('UNKNOWN_HTML_ENCODING')
    rows=[]
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>',text,re.S|re.I):
        cells=[label(c) for c in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',tr,re.S|re.I)]
        if cells:rows.append(cells)
    codes=[];cells_checked=0
    for row in rows:
        if not re.fullmatch(r'[1-9]\d{3}',row[0]):continue
        codes.append(row[0])
        for cell in row[2:]:
            candidate=cell.replace(',','')
            if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',candidate):number(candidate);cells_checked+=1
    if job['category'].startswith('revenue_'):
        if not codes or cells_checked==0:raise ValueError('REVENUE_NUMERIC_COMPANY_ROWS_ABSENT')
        if len(codes)!=len(set(codes)):raise ValueError('DUPLICATE_REVENUE_COMPANY')
    return dict(rows_checked=len(rows),numeric_cells_checked=cells_checked,
        checks=['HTML_TABLE_ROWS','RECOGNIZED_FINITE_NUMBERS','REVENUE_COMPANY_DUPLICATES'],
        unverified=['FINANCIAL_ACCOUNTING_IDENTITIES_AND_ANNOUNCEMENT_TIME_NOT_PROVEN'],
        units_policy='NATIVE_UNITS_PRESERVED_NO_UNPROVEN_CONVERSION',cross_source_verified=False,pit_verified=False)

def audit_rows(raw,job):
    try:json.loads(raw.decode('utf-8-sig'))
    except (ValueError,UnicodeDecodeError):return audit_html(raw,job)
    return audit_json(raw,job)

def value_digest(raw):
    """Compare native table values without treating wrapper timestamps as revisions."""
    try:
        obj=json.loads(raw.decode('utf-8-sig'))
        value=[dict(fields=t.get('fields'),data=t.get('data')) for t in (obj.get('tables') or [obj])]
        normalized=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    except (ValueError,UnicodeDecodeError,AttributeError):
        normalized=raw
    return hashlib.sha256(normalized).hexdigest()
