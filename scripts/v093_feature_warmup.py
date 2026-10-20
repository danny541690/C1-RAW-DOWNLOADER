"""Incremental TWSE price history preparation and feature shadow, never approval.

Input caches retain content hashes and exact close values. Cold inputs are verified
against the R3 receipt before extraction. All output remains explicitly unapproved.
"""
import collections,datetime as dt,decimal,hashlib,io,json,time
import pyarrow as pa,pyarrow.parquet as pq
from scripts.v093_feature_shadow import compute_features
from scripts.v093_standard_r1 import C1,ls
from scripts.v093_standard_r4 import basekey

PERIODS=tuple(['2025-'+str(m).zfill(2) for m in range(9,13)]+['2026-'+str(m).zfill(2) for m in range(1,10)])

def warmup_rows(points,target='2026-09'):
    values=collections.defaultdict(set)
    for p in points:values[(p['stock_id'],p['date'])].add(decimal.Decimal(p['close']))
    conflicts={symbol for (symbol,date),vs in values.items() if len(vs)!=1}
    series=collections.defaultdict(list)
    for (symbol,date),vs in values.items():
        if symbol not in conflicts:series[symbol].append((date,str(next(iter(vs)))))
    output=[]
    for symbol,rows in series.items():
        for row in compute_features(sorted(rows)):
            if row['date'].startswith(target):output.append({**row,'stock_id':symbol,'status':'SHADOW_NOT_APPROVED','price_basis':'UNADJUSTED_NATIVE','window_basis':'VALID_OBSERVATIONS_NOT_VERIFIED_CALENDAR'})
    return output,len(conflicts)

def read_verified_cache(d,parent,name,receipt=None):
    """Identical aliases are safe; conflicting bytes remain blocking, never deleted."""
    try:return d.read(parent,name),[]
    except ValueError as exc:
        if str(exc)!='duplicate remote names':raise
    candidates=sorted((f for f in ls(d,parent) if f['name']==name),key=lambda f:f['id'])
    if not candidates:raise ValueError('CACHE_ALIASES_DISAPPEARED')
    payload=None;digest=None
    for item in candidates:
        body=d.call(lambda:d.api.files().get_media(fileId=item['id']))
        current=hashlib.sha256(body).hexdigest()
        if digest is not None and current!=digest:raise ValueError('CONFLICTING_CACHE_ALIASES')
        if receipt and current!=receipt['cache_sha256']:raise ValueError('FEATURE_CACHE_HASH_MISMATCH')
        payload=body;digest=current
    return payload,[f['id'] for f in candidates]

def prepare(d,registry,qa,ops,minutes=20):
    deadline=time.monotonic()+minutes*60
    cache=registry.folder(ops,'FEATURE_WARMUP_CACHE_V2',True)
    name='FEATURE_WARMUP_V2.json';old=d.read(ops,name)
    state=json.loads(old) if old else {'version':'FEATURE_WARMUP_V2','period':'2026-09','source_scope':['TWSE'],'periods':{},'inputs':{}}
    if state.get('version')!='FEATURE_WARMUP_V2':raise ValueError('FEATURE_STATE_VERSION_CONFLICT')
    def save(status):
        registry.flush();state.update(status=status,approved=False,updated_at=dt.datetime.now(dt.timezone.utc).isoformat(),blockers=['SOURCE_CONTRACT_AND_UNITS','HISTORICAL_UNIVERSE','TRADING_CALENDAR','CORPORATE_ACTION_BASIS','INDEPENDENT_GOLDEN','RELEASE_EVIDENCE'])
        d.put(ops,name,json.dumps(state,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    points=[];digests=[];all_periods=True
    for period in PERIODS:
        if time.monotonic()>=deadline:save('CHECKPOINTED_INPUT_PREPARATION');return {'status':state['status'],'periods_prepared':sum(v=='INPUTS_PREPARED' for v in state['periods'].values()),'total_periods':len(PERIODS),'approved':False}
        raw=d.read(qa,period+'_NATIVE_R3_20261020_1_AUDIT.json')
        report=json.loads(raw) if raw else {}
        if report.get('status')!='STAGING_NOT_APPROVED':state['periods'][period]='WAITING_FOR_STABLE_INPUT';all_periods=False;continue
        entries=[e for e in report.get('archives',[])+report.get('standalone_files',[]) if e.get('source')=='TWSE' and e.get('parquet_name')]
        if not entries:state['periods'][period]='MISSING_PRICE_INPUT';all_periods=False;continue
        src=registry.folder(registry.folder(registry.folder(registry.folder(C1,'02_STANDARD'),period[:4]),period),'NATIVE_R3_20261020_1')
        for entry in entries:
            if time.monotonic()>=deadline:save('CHECKPOINTED_INPUT_PREPARATION');return {'status':state['status'],'periods_prepared':sum(v=='INPUTS_PREPARED' for v in state['periods'].values()),'total_periods':len(PERIODS),'approved':False}
            digest=entry.get('parquet_sha256')
            if not digest or len(digest)!=64:raise ValueError('MISSING_INPUT_HASH')
            key=period+'_'+digest;receipt=state['inputs'].get(key)
            cached,aliases=read_verified_cache(d,cache,key+'.json',receipt)
            if cached and receipt:
                if hashlib.sha256(cached).hexdigest()!=receipt['cache_sha256']:raise ValueError('FEATURE_CACHE_HASH_MISMATCH')
                decoded=json.loads(cached)
                if decoded.get('input_sha256')!=digest:raise ValueError('CACHE_INPUT_BINDING_MISMATCH')
                rows=decoded['points']
                if len(rows)!=receipt['rows']:raise ValueError('CACHE_ROW_COUNT_MISMATCH')
                if aliases:receipt['identical_alias_ids']=aliases
            else:
                payload=d.read(src,entry['parquet_name'])
                if not payload or hashlib.sha256(payload).hexdigest()!=digest:raise ValueError('INPUT_HASH_MISMATCH')
                table=pq.read_table(io.BytesIO(payload),columns=['date','stock_id','native_field','numeric_decimal_text','date_content_verified','status'])
                rows=[]
                for batch in table.to_batches(max_chunksize=20000):
                    for row in batch.to_pylist():
                        if basekey(row['native_field']) not in ('收盤價','close') or not row['date_content_verified'] or row['status']!='STAGING_UNMAPPED':continue
                        if not row['stock_id'] or not row['date'] or not row['date'].startswith(period):continue
                        value=decimal.Decimal(row['numeric_decimal_text'])
                        if value.is_finite() and value>0:rows.append({'stock_id':row['stock_id'],'date':row['date'],'close':str(value)})
                body=json.dumps({'input_sha256':digest,'points':rows},ensure_ascii=False).encode()
                if cached:
                    if hashlib.sha256(cached).digest()!=hashlib.sha256(body).digest():raise ValueError('UNRECEIPTED_CACHE_CONTENT_CONFLICT')
                else:d.put(cache,key+'.json',body,'application/json')
                back,aliases=read_verified_cache(d,cache,key+'.json')
                if not back or hashlib.sha256(back).digest()!=hashlib.sha256(body).digest():raise ValueError('CACHE_READBACK_FAILED')
                state['inputs'][key]={'cache_sha256':hashlib.sha256(body).hexdigest(),'rows':len(rows),'identical_alias_ids':aliases}
                save('PREPARING_INPUTS')
            points.extend(rows);digests.append(digest)
        state['periods'][period]='INPUTS_PREPARED';save('PREPARING_INPUTS')
    if not all_periods:save('WAITING_FOR_INPUTS');return {'status':state['status'],'approved':False}
    rows,conflicts=warmup_rows(points)
    generation=hashlib.sha256(json.dumps({'inputs':sorted(digests),'formula':'FEATURE_WARMUP_V2'},sort_keys=True).encode()).hexdigest()
    output=registry.folder(registry.folder(registry.folder(registry.folder(C1,'03_FEATURES'),'2026',True),'2026-09',True),'PRICE_WARMUP_V2',True)
    state.pop('output_sha256',None)
    if rows:
        buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows),buf,compression='zstd');body=buf.getvalue()
        d.put(output,generation+'.parquet',body);back=d.read(output,generation+'.parquet')
        if not back or hashlib.sha256(back).digest()!=hashlib.sha256(body).digest() or pq.read_metadata(io.BytesIO(back)).num_rows!=len(rows):raise ValueError('FEATURE_READBACK_FAILED')
        state['output_sha256']=hashlib.sha256(body).hexdigest()
    state.update(generation_id=generation,rows=len(rows),conflicting_instruments=conflicts,rows_with_ma240=sum(r['ma_240'] is not None for r in rows),rows_with_return240=sum(r['return_240'] is not None for r in rows),input_digests=sorted(digests))
    save('SHADOW_NOT_APPROVED')
    return {k:state[k] for k in ('status','rows','rows_with_ma240','rows_with_return240','conflicting_instruments','approved')}
