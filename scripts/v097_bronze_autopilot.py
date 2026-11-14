#!/usr/bin/env python3
"""JARVIS v0.97 Bronze autonomous evidence gate.
Run INSIDE C1-RAW-DOWNLOADER. Not an assertion that 74,750 files are READY.
Strictly read-only on raw source/destination; writes only scoped QA evidence.
"""
import csv, datetime as dt, hashlib, io, json, os, re, sys, zipfile
from decimal import Decimal, InvalidOperation
from collections import Counter

SOURCES = ('TWSE', 'TPEx', 'MOPS', 'TDCC', 'TAIFEX', 'NDC', 'FinMind')
BASELINE = 'v097_BRONZE_74750_BASELINE_ROWS_43604879456.json'
COHORT = 74750
VERSION = 'autopilot-0.1.1'
CAP = min(800, max(1, int(os.getenv('AUTOPILOT_BATCH', '350'))))
CYCLES = min(8, max(1, int(os.getenv('AUTOPILOT_CYCLES', '3'))))
MAX_RAW_BYTES = 60 * 1024 * 1024
MAX_MEMBER_BYTES = 32 * 1024 * 1024
MAX_EXPANDED = 250 * 1024 * 1024
MAX_MEMBERS = 5000
READY = 'BRONZE_READY_FOR_SILVER'
NDC_VERSION = 'autopilot-0.1.2-ndc-native-excel-cells'
FINMIND_VERSION = 'autopilot-0.1.2-finmind-raw-unit-manifest'

def adapter_version(source):
    return NDC_VERSION if source == 'NDC' else (FINMIND_VERSION if source == 'FinMind' else VERSION)


def source_api():
    from scripts.v097_bronze_first_pipeline import service, common, match, load_json, put_once, upsert, call
    api = service()
    _, control, quality, _ = common(api)
    return api, control, quality, match, load_json, put_once, upsert, call


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def stable_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def date_token(x):
    s = str(x).strip()
    m = re.fullmatch(r'((?:19|20)\d{2})[-/]?(\d{1,2})[-/]?(\d{1,2})', s)
    if m:
        try: return dt.date(*map(int, m.groups())).isoformat()
        except ValueError: return None
    m = re.fullmatch(r'(\d{3})/(\d{1,2})/(\d{1,2})', s)
    if m:
        try: return dt.date(1911+int(m[1]), int(m[2]), int(m[3])).isoformat()
        except ValueError: return None
    return None


def classify_dataset(source, name, payload=None):
    n = name.lower()
    tokens = {
        'TWSE': {'stock': ('stock_day',), 'index': ('mi_index',), 'institution': ('t86', 'institution'), 'margin': ('mi_margn',)},
        'TPEx': {'quotes': ('quotes', 'daily', 'stk'), 'financing': ('margin',)},
        'MOPS': {'finance': ('ifrs', 'balance', 'cashflow', 'financial'), 'revenue': ('revenue', 'monthly'), 'report': ('t187ap', 'mops')},
        'TDCC': {'holdings': ('distribution', 'tdcc', 'holding')},
        'TAIFEX': {'futures': ('fut', 'future', 'daily', 'taifex'), 'options': ('opt', 'option')},
        'NDC': {'business_cycle': ('ndc', 'indicator', 'business', '景氣')},
        'FinMind': {'stock_price': ('taiwanstockprice',), 'financial': ('taiwanstockfinancial',), 'institutional': ('taiwanstockinstitutional',)}
    }
    for dataset, probes in tokens[source].items():
        if any(probe in n for probe in probes): return dataset
    if isinstance(payload, dict):
        if source in ('TWSE', 'TPEx') and isinstance(payload.get('tables'), list):
            titles='|'.join(str(t.get('title','')) for t in payload['tables'] if isinstance(t,dict))
            if source=='TWSE' and '價格指數' in titles and '每日收盤行情' in titles:
                return 'twse_mixed_index_and_stock_quotes'
            if source=='TPEx' and '上櫃股票行情' in titles:return 'tpex_quotes_and_optional_sections'
            return 'official_tables_identity_pending'
        if source == 'FinMind' and payload.get('dataset'): return str(payload['dataset'])
    return None


def check_table(fields, rows):
    if not isinstance(fields, list) or not isinstance(rows, list) or not fields or not rows:
        return 'HOLD_EMPTY_OR_INVALID_TABLE'
    for row in rows:
        if not isinstance(row, list) or len(row) != len(fields): return 'HOLD_TABLE_WIDTH_CONFLICT'
    important = [i for i, k in enumerate(fields) if any(t in str(k) for t in
                 ('收盤', '開盤', '最高', '最低', '成交股數', '成交金額', '成交筆數'))]
    for row in rows:
        for ix in important:
            val = str(row[ix]).replace(',', '').strip()
            if val in ('', '--', '---', '-', 'X', 'N/A', '不適用', '除息', '除權'): continue
            if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', val): return 'HOLD_NONNUMERIC_MARKET_CELL'
    return 'OK'


def parse_ndc_native(obj, expected_month):
    """NDC v0.93 extract: genuine Excel cells with archive source reference.
    Do NOT mistake {tables:[{cells:...}]} for TWSE {fields,data}.
    Do NOT treat a parsed historical cell as source/numeric/PIT certification.
    """
    if obj.get('source')!='NDC':
        return {'status':'HOLD_NDC_SOURCE_IDENTITY'}
    if obj.get('month')!=expected_month:
        return {'status':'HOLD_NDC_MONTH_CONFLICT','observed_month':obj.get('month')}
    archive=obj.get('source_archive')
    if not isinstance(archive,dict) or not re.fullmatch(r'[a-f0-9]{64}',str(archive.get('sha256',''))):
        return {'status':'HOLD_NDC_SOURCE_ARCHIVE_PROOF'}
    if not archive.get('file_id') or not archive.get('url') or not archive.get('remote_readback_hash_verified'):
        return {'status':'HOLD_NDC_UNVERIFIED_ORIGIN'}
    tables=obj.get('tables')
    if not isinstance(tables,list) or not tables:
        return {'status':'HOLD_NDC_NO_TABLES'}
    fields=0;numeric=0;dates=set()
    for table in tables:
        if not isinstance(table,dict) or not table.get('table') or not isinstance(table.get('cells'),list) or not table['cells']:
            return {'status':'HOLD_NDC_TABLE_CELLS_INVALID'}
        raw_day=table.get('source_date_cell')
        try:
            day=dt.date(1899,12,30)+dt.timedelta(days=int(raw_day))
            dates.add(day.isoformat())
        except (ValueError,TypeError,OverflowError):
            return {'status':'HOLD_NDC_EXCEL_DATE_CELL_INVALID'}
        seen=set()
        for cell in table['cells']:
            if not isinstance(cell,dict) or not cell.get('field') or cell.get('status')!='VALUE_PRESENT':
                return {'status':'HOLD_NDC_CELL_MISSING_OR_INVALID'}
            field=str(cell['field'])
            if field in seen:return {'status':'HOLD_NDC_DUPLICATE_FIELD'}
            seen.add(field);fields+=1
            val=str(cell.get('native_value','')).strip()
            if not val:return {'status':'HOLD_NDC_EMPTY_VALUE'}
            try:
                d=Decimal(val.replace(',',''))
                if not d.is_finite():return {'status':'HOLD_NDC_NONFINITE_VALUE'}
                numeric+=1
            except InvalidOperation:
                # Categorical signals such as 紅 / 黃紅 / 綠 are valid text.
                if not ('信號' in field or '燈號' in field):
                    return {'status':'HOLD_NDC_UNRECOGNIZED_TEXT_VALUE','field':field}
    if len(dates)!=1 or next(iter(dates))[:7]!=expected_month:
        return {'status':'HOLD_NDC_CONTENT_MONTH_CONFLICT','observed_dates':sorted(dates)}
    return {'status':'NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD',
            'dataset':'business_cycle','period':expected_month,'tables':len(tables),
            'cells':fields,'numeric_cells':numeric,'archive_sha256':archive['sha256'],
            'archive_readback_proof_recorded':True,
            'numeric_verified':bool(obj.get('numeric_verified')),
            'pit_verified':bool(obj.get('pit_verified')),
            'coverage_certified':bool(obj.get('coverage_certified'))}


def parse_json(source, name, blob, expected_month):
    try: obj = json.loads(blob.decode('utf-8-sig'))
    except (ValueError, UnicodeError): return {'status':'HOLD_BAD_JSON'}
    dataset = classify_dataset(source, name, obj)
    if source=='NDC' and isinstance(obj,dict) and obj.get('representation')=='EXTRACTED_NATIVE_CELL_TEXT_WITH_SOURCE_ARCHIVE_REFERENCE':
        return parse_ndc_native(obj,expected_month)
    if isinstance(obj, dict):
        date_candidates = [obj[k] for k in ('date', 'Date', '資料日期', '查詢日期') if k in obj]
        tabs = obj.get('tables')
        if isinstance(tabs, list):
            for t in tabs:
                if isinstance(t, dict):
                    date_candidates += [t['date']] if 'date' in t else []
            # Official responses can include empty optional sections (e.g.
            # TPEx 管理股票 table, TWSE trailing metadata); do not call them
            # corruption, but require at least one complete data table.
            eligible=[t for t in tabs if isinstance(t,dict) and
                      isinstance(t.get('fields'),list) and t.get('fields') and
                      isinstance(t.get('data'),list) and t.get('data')]
            table_failures=[check_table(t['fields'],t['data']) for t in eligible]
            if not eligible or any(x != 'OK' for x in table_failures):
                return {'status':'HOLD_TABLE_CONTENT', 'dataset':dataset,
                        'issues':list(set(table_failures)), 'nonempty_tables':len(eligible)}
        elif isinstance(obj.get('fields'), list) and isinstance(obj.get('data'), list):
            t = check_table(obj['fields'], obj['data'])
            if t != 'OK': return {'status':t, 'dataset':dataset}
        elif source == 'FinMind' and isinstance(obj.get('data'), list) and obj['data']:
            row = obj['data'][0]
            if isinstance(row, dict) and 'date' in row: date_candidates.append(row['date'])
        elif source == 'MOPS' and any(k in obj for k in ('營業收入', '申報日期', '公告日期')):
            date_candidates += [obj[k] for k in ('申報日期', '公告日期') if k in obj]
        else: return {'status':'HOLD_UNKNOWN_JSON_DATASET','dataset':dataset}
    elif isinstance(obj, list) and obj and isinstance(obj[0],dict):
        date_candidates = [obj[0][k] for k in ('date', 'Date', '資料日期') if k in obj[0]]
        if source == 'FinMind' and not {'date', 'stock_id'}.issubset(obj[0]):
            return {'status':'HOLD_FINMIND_DATASET_FIELDS','dataset':dataset}
    else: return {'status':'HOLD_UNKNOWN_JSON_SHAPE','dataset':dataset}
    dates = [date_token(d) for d in date_candidates]
    if date_candidates and not all(dates):return {'status':'HOLD_DATE_PARSE','dataset':dataset}
    # Files representing revision snapshots may contain older periods. Such cases
    # need a DATASET-specific temporal policy, never force a month check.
    if dates and any(d[:7] != expected_month for d in dates):
        return {'status':'HOLD_CONTENT_PERIOD_CONFLICT','dataset':dataset,'dates':dates[:4]}
    if not dates:return {'status':'HOLD_DATE_EVIDENCE','dataset':dataset}
    if not dataset:return {'status':'HOLD_DATASET_IDENTITY','dates':dates[:4]}
    # Price/table content can be parsed, but official historical source/published-at
    # still requires per-dataset evidence. Never call weak shape-only evidence READY.
    return {'status':'CONTENT_PARSED_ORIGIN_PIT_HOLD','dataset':dataset,'dates':dates[:4]}


def parse_html(source, name, blob, month, original_path=''):
    s = blob[:500000].decode('utf-8-sig', errors='replace')
    if not re.search(r'<table\b', s, re.I):return {'status':'HOLD_HTML_NO_TABLE'}
    if source == 'TDCC':
        try:
            from scripts.v097_tdcc_a3_a5_auto import assess
            status, detail = assess(original_path, blob)
            result={'status':'TDCC_'+status,'dataset':'holdings',
                    'content_security_id':detail.get('content_security_id'),
                    'table_qa':detail.get('table_qa',{}).get('status')}
            if status == 'HTML_TOKEN_CONSISTENT_SECURITY_CLASS_AND_ORIGIN_PENDING':
                result['disposition']='EXCLUDED_FROM_ORDINARY_STOCK_SILVER_INPUT'
            return result
        except Exception as e:
            return {'status':'HOLD_TDCC_ADAPTER_EXCEPTION','detail':type(e).__name__}
    if source == 'MOPS':
        # Existing MOPS matrix QA was run separately; cannot automatically infer
        # that this particular file passed without its exact source ID receipt.
        return {'status':'MOPS_MATRIX_RECEIPT_AND_PIT_HOLD','dataset':'finance'}
    return {'status':'HOLD_HTML_SOURCE_ADAPTER', 'dataset':classify_dataset(source,name)}


def parse_finmind_unit_archive(blob, expected_month):
    """FinMind unit .raw + manifest.json, exact hash/row/dataset evidence.
    It is a supplement and does NOT certify original provider or publication PIT.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if z.testzip() is not None:return {'status':'HOLD_FINMIND_ZIP_CRC'}
            names={i.filename for i in z.infolist() if not i.is_dir()}
            if 'manifest.json' not in names:return None
            manifest=json.loads(z.read('manifest.json'))
            units=manifest.get('units')
            if not isinstance(units,list) or not units:return None
            declared={'manifest.json'}
            total_rows=0;datasets=set();missing_proof=0
            for unit in units:
                if not isinstance(unit,dict) or unit.get('source')!='FinMind':
                    return {'status':'HOLD_FINMIND_MANIFEST_IDENTITY'}
                filename=unit.get('file')
                if not isinstance(filename,str) or not re.fullmatch(r'[a-zA-Z0-9_.-]+\\.raw',filename):
                    return {'status':'HOLD_FINMIND_MEMBER_NAME'}
                if filename not in names:return {'status':'HOLD_FINMIND_MISSING_MEMBER'}
                if filename in declared:return {'status':'HOLD_FINMIND_DUPLICATE_MEMBER'}
                declared.add(filename)
                data=z.read(filename)
                if len(data)>MAX_MEMBER_BYTES:return {'status':'HOLD_FINMIND_MEMBER_TOO_LARGE'}
                if digest(data)!=unit.get('sha256') or len(data)!=unit.get('bytes'):
                    return {'status':'HOLD_FINMIND_MEMBER_SHA_SIZE'}
                if unit.get('month')!=expected_month:
                    return {'status':'HOLD_FINMIND_MEMBER_MONTH_CONFLICT',
                            'observed':unit.get('month')}
                try:content=json.loads(data)
                except (ValueError,UnicodeError):return {'status':'HOLD_FINMIND_RAW_JSON_INVALID'}
                if not isinstance(content,dict) or not isinstance(content.get('data'),list):
                    return {'status':'HOLD_FINMIND_RAW_DATASET_SHAPE'}
                rows=content['data']
                if len(rows)!=unit.get('rows') or not rows:
                    return {'status':'HOLD_FINMIND_ROW_COUNT_CONFLICT'}
                sid=str(unit.get('stock_id',''))
                for row in rows:
                    if not isinstance(row,dict) or str(row.get('stock_id',''))!=sid:
                        return {'status':'HOLD_FINMIND_STOCK_ID_CONFLICT'}
                    d=date_token(row.get('date'))
                    if d is None or d[:7]!=expected_month:
                        return {'status':'HOLD_FINMIND_ROW_PERIOD_CONFLICT'}
                    if 'value' in row and isinstance(row['value'],(int,float)):
                        from math import isfinite
                        if not isfinite(row['value']):
                            return {'status':'HOLD_FINMIND_NONFINITE_NUMERIC'}
                total_rows+=len(rows)
                if not unit.get('remote_readback_hash_verified') or not unit.get('numeric_verified') or not unit.get('pit_verified'):
                    missing_proof+=1
                datasets.add(str(unit.get('dataset') or 'UNDECLARED'))
            if names != declared:return {'status':'HOLD_FINMIND_UNDECLARED_ARCHIVE_MEMBERS'}
            return {'status':'FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD',
                    'dataset_ids':sorted(datasets),'unit_count':len(units),
                    'rows_checked':total_rows,'members_verified':len(declared),
                    'units_missing_source_numeric_or_pit_proof':missing_proof,
                    'manifest_numeric_verified':bool(manifest.get('numeric_verified')),
                    'manifest_pit_verified':bool(manifest.get('pit_verified'))}
    except (ValueError,zipfile.BadZipFile,KeyError,RuntimeError) as exc:
        return {'status':'HOLD_FINMIND_ARCHIVE_EXCEPTION','error':type(exc).__name__}


def parse_zip(source, name, blob, month, original_path):
    if source=='FinMind':
        special=parse_finmind_unit_archive(blob,month)
        if special is not None:return special
    results=[];expanded=0
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos=z.infolist()
            if not infos or len(infos)>MAX_MEMBERS:return {'status':'HOLD_ZIP_MEMBER_LIMIT'}
            for member in infos:
                if member.is_dir():continue
                if member.flag_bits & 0x1:return {'status':'HOLD_ZIP_ENCRYPTED'}
                if member.filename.startswith('/') or '..' in member.filename.split('/'):
                    return {'status':'HOLD_ZIP_UNSAFE_PATH'}
                expanded += member.file_size
                if member.file_size>MAX_MEMBER_BYTES or expanded>MAX_EXPANDED:
                    return {'status':'HOLD_ZIP_EXPANSION_LIMIT'}
                if member.filename.lower().endswith(('.zip','.xlsx','.xls','.pdf')):
                    results.append({'member':member.filename,'status':'HOLD_NESTED_OR_BINARY_MEMBER'});continue
                raw = z.read(member)
                member_result = parse_content(source,member.filename,raw,month,original_path,allow_zip=False)
                results.append({'member':member.filename,'sha256':digest(raw),**member_result})
    except Exception as e:
        return {'status':'HOLD_ZIP_ERROR','error':type(e).__name__}
    if not results:return {'status':'HOLD_ZIP_EMPTY'}
    states=Counter(x['status'] for x in results)
    # Parent zip not automatically released when children have valid SHA only.
    return {'status':'ZIP_MEMBERS_AUDITED_ORIGIN_HOLD','member_count':len(results),
            'member_states':dict(states),'members':results}


def parse_content(source, name, blob, month, original_path='',allow_zip=True):
    n=name.lower()
    if not blob:return {'status':'HOLD_EMPTY_BYTES'}
    if n.endswith('.json'):return parse_json(source,name,blob,month)
    if n.endswith('.jsonl'):
        try:
            lines=blob.splitlines()
            if not lines:return {'status':'HOLD_EMPTY_JSONL'}
            for raw in lines:
                if not isinstance(json.loads(raw),dict):return {'status':'HOLD_JSONL_SHAPE'}
            return {'status':'JSONL_FULLY_PARSED_DATASET_HOLD','lines':len(lines)}
        except Exception:return {'status':'HOLD_JSONL_PARSE'}
    if n.endswith('.csv'):
        try:
            content=blob.decode('utf-8-sig')
            dialect=csv.Sniffer().sniff(content[:4096],delimiters=',;\t')
            reader=csv.reader(io.StringIO(content),dialect)
            header=next(reader,[])
            if len(header)<2:return {'status':'HOLD_CSV_HEADER'}
            count=0
            for row in reader:
                if row and len(row)!=len(header):return {'status':'HOLD_CSV_WIDTH'}
                if row:count+=1
            if not count:return {'status':'HOLD_CSV_NO_DATA'}
            return {'status':'CSV_FULLY_PARSED_DATASET_HOLD','headers':header[:40],'rows':count}
        except Exception:return {'status':'HOLD_CSV_PARSE_OR_ENCODING'}
    if n.endswith(('.html','.htm')):return parse_html(source,name,blob,month,original_path)
    if n.endswith('.zip') and allow_zip:return parse_zip(source,name,blob,month,original_path)
    if n.endswith('.pdf'):
        return {'status':'PDF_PRESERVED_NEEDS_DATASET_SPECIFIC_TEXT_TABLE_QA' if blob.startswith(b'%PDF-') else 'HOLD_BAD_PDF'}
    return {'status':'HOLD_UNRECOGNIZED_EXTENSION'}


def frozen_partitions(api, control, quality, match, load_json, put_once):
    f=match(api,quality,BASELINE)
    if not f:raise RuntimeError('NO_FROZEN_74750_BASELINE')
    data=load_json(api,f['id'])
    by_source={s:[] for s in SOURCES}
    seen=set()
    for r in data['rows']:
        fid=r['source_id']
        if fid in seen:raise RuntimeError('DUPLICATE_FROZEN_SOURCE_ID')
        seen.add(fid)
        source=r['source']
        if source not in by_source:raise RuntimeError('UNKNOWN_SOURCE_'+str(source))
        by_source[source].append(r)
    if len(seen)!=COHORT:raise RuntimeError('FROZEN_COHORT_NOT_74750')
    for source,rows in by_source.items():
        put_once(api,quality,'v097_AP_INPUT_'+source+'.json',
                 {'schema':'autopilot_input_1','origin_baseline':BASELINE,'source':source,'rows':rows})
    print('INITIALIZED',COHORT,{s:len(rows) for s,rows in by_source.items()},flush=True)


def worker(api, control, quality, match, load_json, put_once, upsert, call, source):
    if source not in SOURCES:raise RuntimeError('INVALID_SOURCE')
    f=match(api,quality,'v097_AP_INPUT_'+source+'.json')
    if not f:raise RuntimeError('RUN_INIT_BEFORE_WORKERS')
    candidates=load_json(api,f['id'])['rows']
    chk_name='v097_AP_CHECKPOINT_'+source+'.json'
    current_version=adapter_version(source)
    for cycle in range(CYCLES):
        f=match(api,control,chk_name)
        ck=load_json(api,f['id']) if f else {'schema':'autopilot_ck_1','version':VERSION,'done':{}}
        done=ck['done']
        def needs_work(row):
            prior=done.get(row['source_id'])
            if not prior:return True
            if prior.get('adapter_version')!=current_version:return True
            return prior.get('status')=='HOLD_READ_OR_SHA' and prior.get('retries',0)<3
        batch=[x for x in candidates if needs_work(x)][:CAP]
        if not batch:
            print('SOURCE_IDLE',source,'checkpointed',len(done),flush=True)
            return
        ids=[r['source_id'] for r in batch]
        attempts=[done.get(fid,{}).get('retries',0) for fid in ids]
        # Stable retry-scoped signature makes batch receipts replayable and
        # avoids conflicts when a formerly failed read succeeds later.
        signature=digest((current_version+'|'+source+'|'+','.join(
                    '%s:%d'%(fid,k) for fid,k in zip(ids,attempts))).encode())[:16]
        receipt_name='v097_AP_RECEIPT_'+source+'_'+signature+'.json'
        prior_receipt=match(api,quality,receipt_name)
        if prior_receipt:
            receipt=load_json(api,prior_receipt['id'])
            receipts=receipt['rows']
            if [r['source_id'] for r in receipts]!=ids:
                raise RuntimeError('REPLAY_IDS_CONFLICT')
        else:
            receipts=[]
            for row in batch:
                fid=row['source_id']
                record={'source_id':fid,'source':source,'destination_id':row['dest_id'],
                        'source_sha256':row['sha'],'adapter_version':current_version,
                        'source_path':row['source_path']}
                try:
                    blob=call(lambda:api.files().get_media(fileId=row['dest_id']))
                    if not blob or len(blob)>MAX_RAW_BYTES:raise ValueError('BYTES_EMPTY_OR_OVER_LIMIT')
                    if digest(blob)!=row['sha']:raise ValueError('DEST_SHA_MISMATCH')
                    result=parse_content(source,row['source_path'].rsplit('/',1)[-1],blob,
                                         row['year']+'-'+row['month'],row['source_path'])
                    record.update(result)
                    record['dest_sha256']=digest(blob)
                except Exception as e:
                    # Distinguish permanent SHA mismatch from transient Drive IO.
                    error=str(e)
                    record.update(status='HOLD_DEST_SHA_CHANGED' if 'SHA_MISMATCH' in error else 'HOLD_READ_OR_SHA',
                                  error=type(e).__name__+':'+error[:160])
                receipts.append(record)
            put_once(api,quality,receipt_name,
                     {'schema':'autopilot_receipt_1','adapter_version':current_version,
                      'source':source,'rows':receipts})
        # The checkpoint is advanced only after immutable receipt commit.
        # If interrupted between the two writes, next run replays the receipt.
        for item in receipts:
            previous=done.get(item['source_id'],{})
            retries=previous.get('retries',0)
            if item['status']=='HOLD_READ_OR_SHA':retries+=1
            done[item['source_id']]={'status':item['status'],
                                     'adapter_version':current_version,'receipt':receipt_name,
                                     'retries':retries}
        # Durable checkpoint and heartbeat; one writer per source.
        upsert(api,control,chk_name,{'schema':'autopilot_ck_1','version':current_version,'source':source,
                 'done':done,'last_run':os.getenv('GITHUB_RUN_ID','manual'),
                 'last_success_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        print('SOURCE_BATCH',source,len(receipts),len(done),'/',len(candidates),
              dict(Counter(x['status'] for x in receipts)),flush=True)


def finalize(api, control, quality, match, load_json, put_once):
    all_states=Counter();by_source={};completed=0
    for source in SOURCES:
        f=match(api,quality,'v097_AP_INPUT_'+source+'.json')
        if not f:raise RuntimeError('UNINITIALIZED_'+source)
        expected=load_json(api,f['id'])['rows']
        cf=match(api,control,'v097_AP_CHECKPOINT_'+source+'.json')
        done=load_json(api,cf['id'])['done'] if cf else {}
        expected_ids={x['source_id'] for x in expected}
        if not set(done)<=expected_ids:raise RuntimeError('CHECKPOINT_ORPHAN_'+source)
        statuses=Counter(r['status'] for r in done.values())
        # Any parser-version update requeues stale evidence.
        stale=sum(r.get('adapter_version')!=adapter_version(source) for r in done.values())
        retry_pending=sum(v.get('status')=='HOLD_READ_OR_SHA' and v.get('retries',0)<3 for v in done.values())
        by_source[source]={'total':len(expected),'processed':len(done),
                           'stale':stale,'retry_pending':retry_pending,'states':dict(statuses)}
        completed+=len(done)-stale-retry_pending
        all_states.update(statuses)
    total=sum(x['total'] for x in by_source.values())
    if total!=COHORT:raise RuntimeError('FINAL_COHORT_MISMATCH')
    ready=all_states[READY]
    unresolved=sum(v for k,v in all_states.items() if k!=READY and not k.startswith('EXCLUDED_'))
    # Explicit release cannot be inferred from JSON shape or a matching filename.
    # Integrate evidence-based source/published-at adapter attestations in the
    # next production validation before enabling READY issuance.
    report={'schema':'autopilot_bronze_acceptance_1','run':os.getenv('GITHUB_RUN_ID','manual'),
            'cohort':COHORT,'processed_current_version':completed,'remaining':COHORT-completed,
            'by_source':by_source,'states':dict(all_states),'silver_ready':ready,
            'fully_examined':completed==COHORT,
            'fully_dispositioned':completed==COHORT and unresolved==0,
            'unresolved_holds':unresolved,
            'silver_gold_executed':False,
            'release_approved':False,
            'release_blockers':['SOURCE_AND_DATASET_SPECIFIC_ORIGIN_CERTIFICATION',
                                'PIT_PUBLICATION_PROVENANCE_FOR_BACKTESTS',
                                'FINAL_READY_MANIFEST_NOT_CERTIFIED']}
    # Current run immutable; latest status can update only after produced.
    put_once(api,quality,'v097_AP_REPORT_'+report['run']+'.json',report)
    print('AUTOPILOT_REPORT',stable_json(report),flush=True)


def selftest():
    assert date_token('113/07/15')=='2024-07-15'
    assert date_token('2024-07-15')=='2024-07-15'
    assert date_token('2024-02-31') is None
    p='2024/TPEx/2024-09/TPEx_BULK_2024-09-10.json'
    bad='{"date":"20261016","tables":[{"fields":["代號","名稱","收盤"],"data":[["1234","abc","10"]]}]}'.encode('utf-8')
    assert parse_content('TPEx','TPEx_BULK_2024-09-10.json',bad,'2024-09',p)['status']=='HOLD_CONTENT_PERIOD_CONFLICT'
    good='{"date":"20240910","tables":[{"fields":["代號","名稱","收盤"],"data":[["1234","abc","10"]]}]}'.encode('utf-8')
    assert parse_content('TPEx','TPEx_BULK_2024-09-10.json',good,'2024-09',p)['status']=='CONTENT_PARSED_ORIGIN_PIT_HOLD'
    ndc={'source':'NDC','month':'2021-04',
         'representation':'EXTRACTED_NATIVE_CELL_TEXT_WITH_SOURCE_ARCHIVE_REFERENCE',
         'source_archive':{'file_id':'sample','url':'https://ws.ndc.gov.tw/x','sha256':'a'*64,
                           'remote_readback_hash_verified':True},
         'tables':[{'table':'景氣指標','source_date_cell':'44287',
                    'cells':[{'field':'指數','native_value':'102.25','status':'VALUE_PRESENT'},
                             {'field':'景氣對策信號','native_value':'紅','status':'VALUE_PRESENT'}]}],
         'numeric_verified':False,'pit_verified':False}
    assert parse_json('NDC','NDC_SOURCE_ROWS.json',json.dumps(ndc,ensure_ascii=False).encode(),'2021-04')['status']=='NDC_NATIVE_CELL_SCHEMA_PASS_NUMERIC_ORIGIN_PIT_HOLD'
    ndc['month']='2021-05'
    assert parse_json('NDC','NDC_SOURCE_ROWS.json',json.dumps(ndc,ensure_ascii=False).encode(),'2021-04')['status']=='HOLD_NDC_MONTH_CONFLICT'
    fin_raw=b'{"msg":"success","status":200,"data":[{"date":"2009-03-31","stock_id":"1236","value":2.0}]}'
    fin_unit={'source':'FinMind','dataset':'TaiwanStockFinancialStatements',
        'file':'unit.raw','sha256':digest(fin_raw),'bytes':len(fin_raw),
        'month':'2009-03','stock_id':'1236','rows':1,
        'numeric_verified':False,'pit_verified':False,'remote_readback_hash_verified':False}
    import zipfile
    bf=io.BytesIO()
    with zipfile.ZipFile(bf,'w') as zz:
        zz.writestr('unit.raw',fin_raw)
        zz.writestr('manifest.json',json.dumps({'units':[fin_unit]}))
    assert parse_zip('FinMind','financial.zip',bf.getvalue(),'2009-03','x')['status']=='FINMIND_UNIT_MEMBER_SHA_ROWS_PASS_SOURCE_PIT_HOLD'
    zbuf=io.BytesIO()
    with zipfile.ZipFile(zbuf,'w') as z:z.writestr('TPEx_BULK_2024-09-10.json',good)
    assert parse_zip('TPEx','q.zip',zbuf.getvalue(),'2024-09',p)['member_count']==1
    print('AUTOPILOT_SELFTEST_PASS')


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('selftest','init','worker','finalize'))
    parser.add_argument('--source',choices=SOURCES)
    args=parser.parse_args()
    if args.mode=='selftest':return selftest()
    api,control,quality,match,load_json,put_once,upsert,call=source_api()
    if args.mode=='init':return frozen_partitions(api,control,quality,match,load_json,put_once)
    if args.mode=='worker':
        if not args.source:parser.error('--source required for worker')
        return worker(api,control,quality,match,load_json,put_once,upsert,call,args.source)
    if args.mode=='finalize':return finalize(api,control,quality,match,load_json,put_once)


if __name__=='__main__':main()