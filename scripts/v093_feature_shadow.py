"""One-month price feature rehearsal using verified input bytes, never approval.

Preserves insufficient warmup and rejects conflicting duplicate source values.
"""
import collections,datetime as dt,decimal,hashlib,io,json,statistics
import pyarrow as pa,pyarrow.parquet as pq
from scripts.v093_standard_r1 import C1
from scripts.v093_standard_r4 import basekey

WINDOWS=(5,10,20,60,120,240)
def compute_features(points,windows=WINDOWS):
    """points must be ordered unique observation dates; no missing-value filling."""
    if len({p[0] for p in points})!=len(points) or points!=sorted(points):raise ValueError('UNIQUE_SORTED_DATES_REQUIRED')
    out=[]
    for i,(date,value) in enumerate(points):
        close=decimal.Decimal(value)
        if not close.is_finite() or close<=0:raise ValueError('POSITIVE_FINITE_CLOSE_REQUIRED')
        row={'date':date,'close':str(close),'valid_observations':i+1}
        for n in windows:
            if n<1:raise ValueError('POSITIVE_WINDOW_REQUIRED')
            row['ma_'+str(n)]=str(sum(decimal.Decimal(p[1]) for p in points[i-n+1:i+1])/n) if i+1>=n else None
            row['return_'+str(n)]=str((close/decimal.Decimal(points[i-n][1])-1)*100) if i>=n else None
        out.append(row)
    return out

def pilot(d,registry,qa,period='2026-09'):
    report_name=period+'_NATIVE_R3_20261020_1_AUDIT.json';raw=d.read(qa,report_name)
    if not raw:return {'status':'WAITING_FOR_INPUT','period':period,'approved':False}
    report=json.loads(raw)
    if report.get('status')!='STAGING_NOT_APPROVED':return {'status':'WAITING_FOR_STABLE_INPUT','period':period,'approved':False}
    srcdir=registry.folder(registry.folder(registry.folder(registry.folder(C1,'02_STANDARD'),period[:4]),period),'NATIVE_R3_20261020_1')
    closes=collections.defaultdict(set);digests=[];scanned=0
    # Only documented native close field names; no value/type inference from financial staging.
    for entry in report.get('archives',[])+report.get('standalone_files',[]):
        if entry.get('source')!='TWSE' or not entry.get('parquet_name'):continue
        payload=d.read(srcdir,entry['parquet_name'])
        if not payload:raise ValueError('MISSING_REFERENCED_PARQUET')
        digest=hashlib.sha256(payload).hexdigest();digests.append(digest)
        tab=pq.read_table(io.BytesIO(payload),columns=['date','stock_id','native_field','numeric_decimal_text','date_content_verified','status'])
        for batch in tab.to_batches(max_chunksize=20000):
            cols=batch.to_pydict()
            for j,k in enumerate(cols['native_field']):
                scanned+=1
                if basekey(k) not in ('收盤價','close') or not cols['date_content_verified'][j] or cols['status'][j]!='STAGING_UNMAPPED':continue
                date=cols['date'][j]
                if not date or date[:7]!=period:continue
                v=decimal.Decimal(cols['numeric_decimal_text'][j])
                if v.is_finite() and v>0:closes[(cols['stock_id'][j],date)].add(v)
    series=collections.defaultdict(list);conflicts=[]
    for (symbol,date),values in closes.items():
        if len(values)!=1:conflicts.append({'stock_id':symbol,'date':date,'reason':'SOURCE_VERSION_VALUE_CONFLICT'});continue
        series[symbol].append((date,str(next(iter(values)))))
    output=[]
    conflicted={r['stock_id'] for r in conflicts}
    for symbol,points in series.items():
        if symbol in conflicted:continue
        for row in compute_features(sorted(points)):
            output.append({**row,'stock_id':symbol,'status':'SHADOW_NOT_APPROVED','price_basis':'UNADJUSTED_NATIVE','window_basis':'VALID_OBSERVATIONS_NOT_VERIFIED_CALENDAR'})
    generation=hashlib.sha256(json.dumps({'period':period,'inputs':sorted(digests),'formula_version':'PRICE_SHADOW_V1'},sort_keys=True).encode()).hexdigest()
    featurefolder=registry.folder(registry.folder(registry.folder(registry.folder(C1,'03_FEATURES'),period[:4],True),period,True),'PRICE_SHADOW_V1',True)
    existing=d.read(featurefolder,generation+'.manifest.json')
    if existing:
        saved=json.loads(existing);cached=d.read(featurefolder,generation+'.parquet') if saved['rows'] else None
        if saved['rows'] and (not cached or hashlib.sha256(cached).hexdigest()!=saved.get('feature_sha256') or pq.read_metadata(io.BytesIO(cached)).num_rows!=saved['rows']):raise ValueError('PRIOR_FEATURE_READBACK_FAILED')
        return {**saved,'resumed':True}
    feature_sha=None
    if output:
        buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(output),buf,compression='zstd');body=buf.getvalue()
        name=generation+'.parquet';d.put(featurefolder,name,body)
        back=d.read(featurefolder,name)
        if hashlib.sha256(back).digest()!=hashlib.sha256(body).digest() or pq.read_metadata(io.BytesIO(back)).num_rows!=len(output):raise ValueError('FEATURE_READBACK_FAILED')
        feature_sha=hashlib.sha256(body).hexdigest()
    result={'period':period,'status':'SHADOW_NOT_APPROVED','approved':False,'generation_id':generation,'input_digests':sorted(digests),'feature_sha256':feature_sha,'rows':len(output),'instruments_observed_not_universe':len(series),'duplicate_value_conflicts':len(conflicts),'scanned_numeric_cells':scanned,'warmup_scope':'TARGET_MONTH_ONLY_LONG_WINDOWS_EXPECTED_NULL','blockers':['SOURCE_UNIT_CONTRACT','HISTORICAL_SECURITY_UNIVERSE','VERIFIED_TRADING_CALENDAR','CORPORATE_ACTION_BASIS','INDEPENDENT_GOLDEN','FULL_WARMUP','RELEASE_EVIDENCE'],'updated_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    d.put(featurefolder,generation+'.manifest.json',json.dumps(result,ensure_ascii=False,indent=2).encode(),'application/json')
    reportfolder=registry.folder(C1,'07_REPORTS')
    text='# '+period+' 技術指標試運行\n\n僅驗證讀取→計算→保存流程；不是正式選股結果。\n\n'
    text+='- 已保存候選資料列：'+str(len(output))+'\n- 觀測代碼數（非核准母體）：'+str(len(series))+'\n- 價值衝突日期：'+str(len(conflicts))+'\n'
    text+='- 長窗口暖機不足保留空值；不補零、不用較短窗口替代。\n- 待驗證：單位、歷史母體、交易日、公司行動口徑、獨立Golden、暖機及發布證據。\n'
    d.put(reportfolder,period+'_PRICE_SHADOW_V1.md',text.encode(),'text/markdown',overwrite=True)
    d.put(qa,period+'_PRICE_SHADOW_V1_RESULT.json',json.dumps(result,ensure_ascii=False,indent=2).encode(),'application/json',overwrite=True)
    return result
