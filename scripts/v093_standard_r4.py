"""Native parser repair R4. Immutable staging with metric dimensions and context.

Structural checks never imply source/unit/PIT/universe approval. No RAW writes.
"""
import argparse, calendar, collections, csv, datetime as dt, decimal, hashlib, io, json, math, os, re, tempfile, time, zipfile
from pathlib import Path
from lxml import html
import pyarrow as pa
import pyarrow.parquet as pq
from scripts.v093_standard_r1 import Drive, service, ROOT, C1, folder, ls, LIMIT_ARCHIVE, LIMIT_MEMBER, MAX_ZIP_UNCOMPRESSED
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_indexed_drive import IndexedDrive,CheckpointThrottle

VERSION = 'NATIVE_R4_20261020_1'
PARSER_REVISION = 'FINMIND_MONTH_SLICE_ROWS_V1'
NATIVE_PARSER_REVISION = 'NATIVE_MATRIX_AND_INDEX_ROWS_V2'
CSV_HEADER_REVISION = 'TPEX_CSV_HEADER_CONTENT_DATE_V1'
SYMBOLS = ('stock_id','SecuritiesCompanyCode','股票代號','證券代號','代號','公司代號','公司代碼','Code','StockCode','stockNo')
DATES = ('date','Date','trade_date','資料日期','日期','年月日')
PERIODS = ('資料年月','營收年月','revenue_month','年月')
SOURCES = ('TWSE','TPEx','MOPS','FinMind')

def day(value):
    s = str(value or '').strip()
    m = re.fullmatch(r'(\d{3,4})[-/年]?(\d{1,2})[-/月]?(\d{1,2})日?', s)
    if not m: return None
    y, mo, d = map(int,m.groups()); y = y+1911 if y < 1911 else y
    try: return dt.date(y,mo,d).isoformat()
    except ValueError: return None

def month(value):
    s = str(value or '').strip()
    m = re.fullmatch(r'(\d{3,4})[-/年]?(\d{1,2})月?',s)
    if not m: return None
    y, mo = map(int,m.groups()); y = y+1911 if y<1911 else y
    try: return dt.date(y,mo,1).strftime('%Y-%m')
    except ValueError: return None

def number(value):
    if value is None or isinstance(value,bool): return None
    s = str(value).strip().replace(',','').replace('−','-')
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',s): return None
    try:
        n = decimal.Decimal(s)
        return str(n) if n.is_finite() else None
    except decimal.InvalidOperation: return None

def decode(raw):
    for enc in ('utf-8-sig','cp950'):
        try: return raw.decode(enc),enc
        except UnicodeDecodeError: pass
    raise ValueError('UNKNOWN_ENCODING')

def basekey(k): return re.sub(r'__col_\d+$','',str(k)).strip()

def positional(fields,row):
    if len(fields)!=len(row): raise ValueError('ROW_WIDTH_MISMATCH')
    return {str(k).strip()+'__col_'+str(i):v for i,(k,v) in enumerate(zip(fields,row))}

def get(vals,keys):
    return next((v for k,v in vals.items() if basekey(k) in keys and str(v).strip()),None)

def html_tables(text):
    """Leaf tables only; expand explicit spans, retain original text and columns."""
    root=html.fromstring(text)
    for ti,t in enumerate(root.xpath('//table[not(.//table)]')):
        pending={}; grid=[]
        for tr in t.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr'):
            row=[]; col=0; new={}
            def advance():
                nonlocal col
                while col in pending:
                    val,left=pending[col];row.append(val)
                    if left>1:new[col]=(val,left-1)
                    col+=1
            advance()
            for cell in tr.xpath('./th|./td'):
                advance(); val=' '.join(cell.text_content().split())
                cs=max(1,min(int(cell.get('colspan','1')),100));rs=max(1,min(int(cell.get('rowspan','1')),100))
                for _ in range(cs):
                    row.append(val)
                    if rs>1:new[col]=(val,rs-1)
                    col+=1
            advance();pending=new;grid.append(row)
        start=next((i for i,r in enumerate(grid) if any(x in SYMBOLS for x in r)),None)
        if start is None:continue
        headers=grid[start]; symbol_col=next(i for i,x in enumerate(headers) if x in SYMBOLS)
        data_start=next((i for i in range(start+1,len(grid)) if len(grid[i])>symbol_col and re.fullmatch(r'[0-9A-Za-z]{4,8}',grid[i][symbol_col])),None)
        if data_start is None:continue
        # Flatten only non-data header rows of the same width; keep column identity.
        for hr in grid[start+1:data_start]:
            if len(hr)==len(headers):
                headers=[h if h==v or h in SYMBOLS else h+' / '+v for h,v in zip(headers,hr)]
        yield 'html_table_'+str(ti),headers,grid[data_start:]

def mops_matrix_rows(name,raw,partition):
    """Use the existing strict matrix adapter, retaining account/company axes."""
    from scripts.v093_stage06_financial_repair import structure,number as financial_number,text as cell_text
    root=html.fromstring(raw.decode('utf-8-sig'))
    periods=set(root.xpath('//input[@name="yearseason"]/@value'))
    if len(periods)!=1:raise ValueError('UNPROVEN_FINANCIAL_PERIOD')
    match=re.fullmatch(r'(20\d{2})Q([1-4])',next(iter(periods)))
    if not match:raise ValueError('UNPROVEN_FINANCIAL_PERIOD')
    year,quarter=map(int,match.groups());mo=quarter*3
    period=dt.date(year,mo,calendar.monthrange(year,mo)[1]).isoformat()
    if period[:7]!=partition:raise ValueError('FINANCIAL_PARTITION_CONFLICT')
    reports=[r for r in ('IncomeStatement','BalanceSheet','CashflowStatement') if r in name]
    if len(reports)!=1:raise ValueError('FINANCIAL_REPORT_NAME_AMBIGUOUS')
    unit=dict(source='MOPS',market='UNKNOWN',dataset=reports[0],security_id='ALL_MARKET',
              period_start=period,period_end=period,native_unit_id=name)
    matrix=structure(raw,unit);out=[]
    for ri,cells in enumerate(matrix['cells']):
        for ci,cell in enumerate(cells):
            original=cell_text(cell);value=financial_number(original)
            if value is None:continue
            context=dict(company=matrix['names'][ci],account=matrix['labels'][ri],
                         report=reports[0],period_kind=matrix['period_kind'],period_end=period)
            out.append(dict(observation_period=period,date=period,stock_id=matrix['codes'][ci],
                source='MOPS',native_member=name,native_table=reports[0],row_index=ri,
                native_field=matrix['codes'][ci],native_metric=matrix['labels'][ri],
                native_type=matrix['period_kind'],native_origin_name=matrix['labels'][ri],
                native_unit=matrix['unit'],statement_scope=matrix['scopes'][ci],
                native_record_json=json.dumps(context,ensure_ascii=False,sort_keys=True),
                raw_value=original,numeric_decimal_text=value,date_proof='EXPLICIT_REPORT_PERIOD',
                date_content_verified=True,unit_verified=False,numeric_semantics_verified=False,
                pit_verified=False,ohlc_violation=False,status='STAGING_UNMAPPED'))
    if not out:raise ValueError('NO_NATIVE_FINANCIAL_NUMERIC_CELLS')
    return out,dict(STAGED_CELLS=len(out),NATIVE_RECORDS=len(matrix['cells']),
                    MOPS_MATRIX_CELLS=len(out)), 'utf-8-sig'

def csv_header_date(source,grid,header_index,filename_day=None):
    """TPEx CSV content date is evidence; filename alone never proves it."""
    if source!='TPEx':return None
    observed=[]
    for row in grid[:header_index]:
        line=' '.join(str(v).strip() for v in row).strip()
        match=re.fullmatch(r'資料日期\s*[:：]\s*(.*?)\s*',line)
        if match:
            value=day(match.group(1))
            if not value:raise ValueError('INVALID_CSV_HEADER_DATE')
            observed.append(value)
    values=set(observed)
    if len(values)>1:raise ValueError('CSV_HEADER_DATE_CONFLICT')
    value=next(iter(values)) if values else None
    if value and filename_day and value!=filename_day:raise ValueError('CSV_HEADER_FILENAME_DATE_CONFLICT')
    return value

def parse_member(source,name,raw,partition):
    if source=='MOPS' and any(r in name for r in ('IncomeStatement','BalanceSheet','CashflowStatement')):
        return mops_matrix_rows(name,raw,partition)
    text,encoding=decode(raw); stats=collections.Counter();records=[]
    filename_days={day(m) for m in re.findall(r'(?<!\d)(20\d{6})(?!\d)',name)}-{None}
    filename_day=next(iter(filename_days)) if len(filename_days)==1 else None
    is_revenue=bool(re.search(r'revenue|t21sc03',name,re.I))
    html_period=None;csv_content_day=None
    if text.lstrip().startswith('<'):
        root=html.fromstring(text)
        titles=[e.text_content() for e in root.xpath('//title|//b|//h1|//h2|//h3') if '營業收入統計表' in e.text_content()]
        matches={month(y+'/'+m) for title in titles for y,m in re.findall(r'(?<!\d)(\d{3,4})\s*年\s*(\d{1,2})\s*月',title)}-{None}
        if is_revenue and len(matches)==1: html_period=next(iter(matches))
        for tab,fields,rows in html_tables(text):
            for i,row in enumerate(rows):
                if len(row)!=len(fields):stats['ROW_WIDTH_MISMATCH']+=1;continue
                records.append((tab,i,positional(fields,row),None))
    elif text.lstrip().startswith(('{','[')) or name.lower().endswith('.jsonl'):
        obj=[json.loads(s) for s in text.splitlines() if s.strip()] if name.lower().endswith('.jsonl') else json.loads(text)
        def add(tab,rows,fields=None,parent=None):
            if not isinstance(rows,list):return
            for i,r in enumerate(rows):
                if isinstance(r,list) and isinstance(fields,list):
                    if len(r)!=len(fields):stats['ROW_WIDTH_MISMATCH']+=1;continue
                    vals=positional(fields,r)
                elif isinstance(r,dict): vals=r
                else:stats['UNSUPPORTED_ROW']+=1;continue
                if isinstance(vals.get('source_record'),dict):
                    vals={**{k:v for k,v in vals.items() if k!='source_record'},**vals['source_record']}
                records.append((tab,i,vals,parent))
        if isinstance(obj,list):add('records',obj)
        elif isinstance(obj,dict):
            response_date=day(get(obj,DATES))
            # Monthly free-download slices retain native API rows under `rows`.
            # Accept only the downloader's explicit envelope, with matching IDs.
            if source=='FinMind' and 'rows' in obj:
                if not isinstance(obj['rows'],list) or not obj.get('dataset') or obj.get('status')!='RAW_MONTH_SLICE_NOT_PIT_VERIFIED':raise ValueError('INVALID_FINMIND_SLICE_ENVELOPE')
                if not re.fullmatch(r'[0-9A-Za-z]{4,8}',str(obj.get('stock_id',''))) or not re.fullmatch(r'[0-9a-f]{64}',str(obj.get('response_sha256',''))):raise ValueError('INVALID_FINMIND_SLICE_PROVENANCE')
                if any(not isinstance(r,dict) or str(r.get('stock_id',''))!=str(obj['stock_id']) for r in obj['rows']):raise ValueError('FINMIND_SLICE_STOCK_SCOPE_MISMATCH')
                if isinstance(obj.get('data'),list) and obj['data']:raise ValueError('AMBIGUOUS_FINMIND_ROW_CONTAINERS')
                add('monthly_slice:'+str(obj['dataset']),obj['rows'])
            add('data',obj.get('data'),obj.get('fields'),response_date)
            add('aaData',obj.get('aaData'),obj.get('fields'),response_date)
            for j,t in enumerate(obj.get('tables') or []):
                if isinstance(t,dict):
                    td=day(get(t,DATES))
                    if td and response_date and td!=response_date:stats['RESPONSE_DATE_CONFLICT']+=1;continue
                    add('table_'+str(j)+':'+str(t.get('title','')),t.get('data'),t.get('fields'),td or response_date)
    else:
        grid=list(csv.reader(io.StringIO(text)));hi=next((i for i,r in enumerate(grid) if any(x.strip() in SYMBOLS for x in r)),None)
        if hi is not None:
            fields=grid[hi];csv_content_day=csv_header_date(source,grid,hi,filename_day)
            for i,row in enumerate(grid[hi+1:],hi+1):
                if len(row)!=len(fields):stats['ROW_WIDTH_MISMATCH']+=1;continue
                records.append(('csv',i,positional(fields,row),csv_content_day))
    out=[]; seen=set()
    for tab,i,vals,response_date in records:
        symbol=str(get(vals,SYMBOLS) or '').strip()
        index_name=get(vals,('指數','指數名稱')) if re.match(r'indices_',name) else None
        if index_name:symbol=None
        elif not re.fullmatch(r'[0-9A-Za-z]{4,8}',symbol):stats['NO_SECURITY_ID']+=1;continue
        rawdate=get(vals,DATES); rd=day(rawdate)
        if rawdate and not rd:stats['INVALID_DATE']+=1;continue
        rp=month(get(vals,PERIODS))
        if is_revenue and not rp:
            ry=get(vals,('revenue_year','營收年度'));rm=get(vals,('revenue_month','營收月份'))
            if ry and rm:rp=month(str(ry)+'/'+str(rm))
        if is_revenue:
            rp=rp or html_period
            if not rp:stats['NO_REPORTED_MONTH']+=1;continue
            observation=rp;proof='REPORTED_MONTH'; obsday=None
        else:
            if rd and response_date and rd!=response_date:stats['ROW_RESPONSE_DATE_CONFLICT']+=1;continue
            obsday=rd or response_date or filename_day
            observation=obsday;proof='ROW' if rd else (('CSV_HEADER' if csv_content_day else 'RESPONSE') if response_date else 'FILENAME_ONLY')
            if not observation:stats['NO_CONTENT_OR_FILENAME_DATE']+=1;continue
        if observation[:7]!=partition:stats['OUTSIDE_PARTITION']+=1;continue
        date_keys={basekey(k) for k in vals if basekey(k) in DATES+PERIODS+SYMBOLS+('revenue_year','營收年度','營收月份','出表日期','年度','季別','year','quarter','season')}
        numeric={k:number(v) for k,v in vals.items() if basekey(k) not in date_keys}
        numeric={k:v for k,v in numeric.items() if v is not None}
        ohlc={};aliases={'open':'o','max':'h','min':'l','close':'c','開盤價':'o','最高價':'h','最低價':'l','收盤價':'c'}
        for k,v in numeric.items():
            if basekey(k) in aliases:ohlc[aliases[basekey(k)]]=decimal.Decimal(v)
        price_fail=len(ohlc)==4 and not (ohlc['l']<=ohlc['o']<=ohlc['h'] and ohlc['l']<=ohlc['c']<=ohlc['h'])
        if len(ohlc)==4:stats['OHLC_CHECKED_ROWS']+=1
        if price_fail:stats['OHLC_VIOLATIONS']+=1
        for k,v in numeric.items():
            key=(tab,i,k)
            if key in seen:stats['DUPLICATE_NATIVE_KEY']+=1;continue
            seen.add(key)
            original=str(vals[k]);nv=decimal.Decimal(v)
            if decimal.Decimal(number(original))!=nv:raise ValueError('NUMERIC_ROUNDTRIP_FAIL')
            native_type='INDEX' if index_name else get(vals,('type','account','account_code','科目','科目代號','會計項目'))
            context=json.dumps(vals,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
            out.append({'observation_period':observation,'date':obsday,'stock_id':symbol,'source':source,'native_member':name,'native_table':tab,'row_index':i,'native_field':str(k),'native_metric':str(native_type) if basekey(k) in ('value','Value','數值','金額') and native_type else basekey(k),'native_type':str(native_type) if native_type is not None else None,'native_origin_name':str(index_name or get(vals,('origin_name','科目名稱','會計項目名稱')) or ''),'native_unit':str(get(vals,('unit','單位')) or ''),'statement_scope':str(get(vals,('statement_scope','report_type','合併個別','報表類型')) or ''),'native_record_json':context,'raw_value':original,'numeric_decimal_text':v,'date_proof':proof,'date_content_verified':proof!='FILENAME_ONLY','unit_verified':False,'numeric_semantics_verified':False,'pit_verified':False,'ohlc_violation':price_fail,'status':'QUARANTINE_OHLC' if price_fail else 'STAGING_UNMAPPED'})
    stats['STAGED_CELLS']=len(out);stats['NATIVE_RECORDS']=len(records)
    if not out:stats['NO_PARSED_NUMERIC_CELLS']+=1
    return out,dict(stats),encoding

SCHEMA=pa.schema([(k,pa.int64() if k=='row_index' else pa.bool_() if k in ('date_content_verified','unit_verified','numeric_semantics_verified','pit_verified','ohlc_violation') else pa.string()) for k in ('observation_period','date','stock_id','source','native_archive','native_sha256','native_member','native_member_sha256','native_table','row_index','native_field','native_metric','native_type','native_origin_name','native_unit','statement_scope','native_record_json','raw_value','numeric_decimal_text','date_proof','date_content_verified','unit_verified','numeric_semantics_verified','pit_verified','ohlc_violation','status')])

def receipt_key(source,raw_sha,name=''):
    # Only affected adapters get a new immutable receipt; unchanged outputs stay valid.
    revision=PARSER_REVISION if source=='FinMind' else ''
    if (source=='MOPS' and any(r in name for r in ('IncomeStatement','BalanceSheet','CashflowStatement'))) or (source in ('TWSE','TPEx') and name.startswith('indices_')):
        revision=NATIVE_PARSER_REVISION
    # A TPEx ZIP can contain CSV alternates: invalidate its staging receipt once,
    # retaining original RAW and all prior immutable output generations.
    if source=='TPEx':revision+=CSV_HEADER_REVISION
    return hashlib.sha256((source+VERSION+revision+raw_sha).encode()).hexdigest()

def run(year,mo,sources=None,max_minutes=20,registry_namespace=None):
    started=time.monotonic();deadline=started+max_minutes*60
    phases=collections.Counter();throttle=CheckpointThrottle()
    def timed(label,fn):
        tick=time.monotonic()
        try:return fn()
        finally:phases[label]+=time.monotonic()-tick
    d=IndexedDrive(service());partition=f'{year}-{mo:02d}'
    strict_folder=globals()['folder']
    qa=strict_folder(d,strict_folder(d,C1,'05_CONTROL'),'STANDARD_QA')
    registry=FolderRegistry(d,qa,namespace=registry_namespace)
    def folder(_d,parent,name,create=False):return registry.folder(parent,name,create)
    base=folder(d,ROOT,str(year))
    dest=folder(d,folder(d,folder(d,folder(d,C1,'02_STANDARD'),str(year),True),partition,True),VERSION,True)
    selected=tuple(sources or SOURCES)
    report={'version':VERSION,'period':partition,'source_scope':list(selected),'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'IN_PROGRESS','archives':[],'standalone_files':[],'sources_missing':[],'quality':{'PIT_PASS':False,'COVERAGE_PASS':False,'NUMERIC_PASS':False,'GOLDEN_COPY_PUBLISHED':False}}
    scope_suffix='' if selected==SOURCES else '_'+('_'.join(selected))
    rname=partition+'_'+VERSION+scope_suffix+'_AUDIT.json'
    def persist(force=False):
        if not throttle.due(force):return
        registry.flush()
        report['performance']={'wall_seconds':time.monotonic()-started,'phase_seconds':dict(phases),'drive':dict(d.stats),'checkpoint_policy':'10_INPUTS_OR_60_SECONDS_PLUS_BOUNDARIES'}
        report['updated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        timed('checkpoint_report_write',lambda:d.put(qa,rname,json.dumps(report,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True))
    persist()
    for source in selected:
        try:files=ls(d,folder(d,folder(d,base,source),partition))
        except FileNotFoundError:report['sources_missing'].append(source);persist();continue
        for f in sorted(files,key=lambda x:x['name']):
            if time.monotonic()>=deadline:
                report['status']='CHECKPOINTED_TIME_BUDGET';persist(force=True);return report
            name=f['name'];iszip=name.lower().endswith('.zip')
            if not iszip and not name.lower().endswith(('.raw','.json','.jsonl','.csv','.html')):continue
            if any(x in name.lower() for x in ('manifest','receipt','checkpoint','metadata','audit','report')):continue
            entry={'source':source,'name':name,'status':'PENDING'}
            report['archives' if iszip else 'standalone_files'].append(entry)
            try:
                if int(f.get('size',0))>LIMIT_ARCHIVE:raise ValueError('ARCHIVE_SIZE_LIMIT')
                raw=timed('raw_download',lambda:d.call(lambda:d.api.files().get_media(fileId=f['id'])));sha=hashlib.sha256(raw).hexdigest()
                key=receipt_key(source,sha,name);receipt_name=key+'.receipt.json'
                saved=timed('receipt_read',lambda:d.read(dest,receipt_name))
                if saved:
                    old=json.loads(saved)
                    if old.get('status')=='NO_STAGED_OUTPUT' and old.get('raw_sha256')==sha and old.get('version')==VERSION:
                        entry.update(old);entry['resumed']=True;persist();continue
                    if old.get('status')=='STRUCTURAL_READBACK_PASS':
                        data=timed('existing_output_readback',lambda:d.read(dest,old['parquet_name'])) if old.get('parquet_name') else None
                        if data is not None and hashlib.sha256(data).hexdigest()==old['parquet_sha256'] and pq.read_metadata(io.BytesIO(data)).num_rows==old['cells']:
                            entry.update(old);entry['resumed']=True;persist();continue
                entry.update({'raw_sha256':sha,'version':VERSION,'members':[],'cells':0})
                seen_members=set(); counters=collections.Counter()
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/'candidate.parquet';writer=None
                    try:
                        z=zipfile.ZipFile(io.BytesIO(raw)) if iszip else None
                        if z:
                            if z.testzip():raise ValueError('ZIP_CRC_FAIL')
                            if sum(i.file_size for i in z.infolist())>MAX_ZIP_UNCOMPRESSED:raise ValueError('EXPANSION_LIMIT')
                            members=z.infolist()
                        else:members=[None]
                        for m in members:
                            mn=m.filename if m else name
                            if m and m.is_dir():continue
                            if any(t in mn.lower() for t in ('manifest','receipt','checkpoint','metadata')):continue
                            if not mn.lower().endswith(('.raw','.json','.jsonl','.csv','.html','.htm')):continue
                            ent={'member':mn};entry['members'].append(ent)
                            try:
                                if (m.file_size if m else len(raw))>LIMIT_MEMBER:raise ValueError('MEMBER_SIZE_LIMIT')
                                payload=z.read(m) if m else raw;mh=hashlib.sha256(payload).hexdigest();ent['sha256']=mh
                                if mh in seen_members:ent['status']='IDENTICAL_BYTES_ALIAS_SKIPPED';continue
                                seen_members.add(mh)
                                rows,counts,enc=timed('native_parse',lambda:parse_member(source,mn,payload,partition));counters.update(counts)
                                ent.update({'status':'STAGED' if rows else 'UNRESOLVED','counts':counts,'encoding':enc})
                                if rows:
                                    for r in rows:r.update(native_archive=name,native_sha256=sha,native_member_sha256=mh)
                                    table=timed('arrow_encode',lambda:pa.Table.from_pylist(rows,schema=SCHEMA))
                                    if writer is None:writer=pq.ParquetWriter(path,SCHEMA,compression='zstd')
                                    timed('parquet_write_local',lambda:writer.write_table(table));entry['cells']+=len(rows)
                            except Exception as exc:ent.update(status='QUARANTINED',reason=str(exc)[:180])
                        if z:z.close()
                    finally:
                        if writer:writer.close()
                    entry['checks']=dict(counters)
                    entry['unresolved_members']=sum(e['status'] in ('UNRESOLVED','QUARANTINED') for e in entry['members'])
                    if path.exists():
                        data=path.read_bytes();assert pq.read_metadata(path).num_rows==entry['cells']
                        pname=source+'_'+key+'.parquet';timed('output_write_and_internal_readback',lambda:d.put(dest,pname,data))
                        readback=timed('explicit_output_readback',lambda:d.read(dest,pname))
                        if hashlib.sha256(readback).digest()!=hashlib.sha256(data).digest() or pq.read_metadata(io.BytesIO(readback)).num_rows!=entry['cells']:raise ValueError('READBACK_FAIL')
                        entry.update(parquet_name=pname,parquet_sha256=hashlib.sha256(data).hexdigest(),status='STRUCTURAL_READBACK_PASS')
                    else:entry['status']='NO_STAGED_OUTPUT'
                timed('receipt_write',lambda:d.put(dest,receipt_name,json.dumps(entry,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True))
            except Exception as exc:entry.update(status='INPUT_ERROR',reason=str(exc)[:180])
            persist(force=entry['status']=='INPUT_ERROR');print(json.dumps({'period':partition,'source':source,'input':name,'status':entry['status'],'cells':entry.get('cells',0),'unresolved':entry.get('unresolved_members',0)},ensure_ascii=False),flush=True)
    entries=report['archives']+report['standalone_files']
    if not entries:
        report['status']='BLOCKED_NO_CONVERTIBLE_INPUTS';persist(force=True)
        raise ValueError('NO_CONVERTIBLE_RAW_INPUTS')
    report['status']='STAGING_NOT_APPROVED'
    report['total_staged_cells']=sum(e.get('cells',0) for e in entries)
    report['unresolved_member_occurrences']=sum(e.get('unresolved_members',0) for e in entries)
    report['input_errors']=sum(e['status']=='INPUT_ERROR' for e in entries)
    report['cross_archive_duplicates']='PRESERVED_WITH_LINEAGE_NOT_APPROVED_OR_MERGED'
    persist(force=True);print(json.dumps({k:v for k,v in report.items() if k not in ('archives','standalone_files')},ensure_ascii=False),flush=True)
    if report['input_errors']:raise SystemExit('PARTIAL_WITH_INPUT_ERRORS; inspect durable monthly report')
    return report

def summarize():
    d=Drive(service());qa=folder(d,folder(d,C1,'05_CONTROL'),'STANDARD_QA')
    result={'version':VERSION,'as_of':dt.datetime.now(dt.timezone.utc).isoformat(),'months':[], 'approved':False}
    for y,m in [(2025,m) for m in range(1,13)]+[(2026,m) for m in range(1,11)]:
        period=f'{y}-{m:02d}';raw=d.read(qa,period+'_'+VERSION+'_AUDIT.json')
        if not raw:result['months'].append({'period':period,'status':'NO_R3_REPORT'});continue
        r=json.loads(raw);es=r.get('archives',[])+r.get('standalone_files',[])
        result['months'].append({'period':period,'status':r['status'],'updated_at':r.get('updated_at'),'cells':sum(e.get('cells',0) for e in es),'parquets':sum(bool(e.get('parquet_name')) for e in es),'unresolved_members':sum(e.get('unresolved_members',0) for e in es),'input_errors':sum(e['status']=='INPUT_ERROR' for e in es),'ohlc_violations':sum(e.get('checks',{}).get('OHLC_VIOLATIONS',0) for e in es),'missing_sources':r.get('sources_missing',[])})
    result['months_finished']=sum(m['status']=='STAGING_NOT_APPROVED' for m in result['months'])
    for k in ('cells','parquets','unresolved_members','input_errors','ohlc_violations'):result[k]=sum(m.get(k,0) for m in result['months'])
    d.put(qa,VERSION+'_2025_2026_SUMMARY.json',json.dumps(result,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('## Layer02 R3 staging audit\n\n```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--year',type=int,choices=(2024,2025,2026));p.add_argument('--month',type=int,choices=range(1,13));p.add_argument('--summary',action='store_true');p.add_argument('--source',action='append',choices=SOURCES)
    a=p.parse_args()
    if a.summary:summarize()
    elif a.year and a.month:run(a.year,a.month,a.source)
    else:p.error('--year and --month required unless --summary')

