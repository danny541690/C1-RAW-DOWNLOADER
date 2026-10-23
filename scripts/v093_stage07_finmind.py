"""FinMind RAW supplementation for ascending historical downloads; no field merging."""
import calendar, datetime as dt, json, math, os, re, time, urllib.error, urllib.parse, urllib.request
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native

# Provider-published earliest availability, not a completeness guarantee.
DATASETS=(
 ('TaiwanStockPrice','prices','1994-10-01'),
 ('TaiwanStockFinancialStatements','IncomeStatement','1990-03-01'),
 ('TaiwanStockMarginPurchaseShortSale','margin','2001-01-01'),
 ('TaiwanStockSecuritiesLending','lending','2001-05-01'),
 ('TaiwanStockMonthRevenue','revenue','2002-02-01'),
 ('TaiwanStockDividendResult','ex_dividend','2003-05-01'),
 ('TaiwanStockShareholding','foreign_holdings','2004-02-01'),
 ('TaiwanStockInstitutionalInvestorsBuySell','institutional','2005-01-01'),
 ('TaiwanStockPER','valuation','2005-10-01'),
 ('TaiwanStockCashFlowsStatement','CashflowStatement','2008-06-01'),
 ('TaiwanStockCapitalReductionReferencePrice','capital_reduction','2011-01-01'),
 ('TaiwanStockBalanceSheet','BalanceSheet','2011-12-01'))
FINANCIAL={'IncomeStatement','BalanceSheet','CashflowStatement'}
TERMINAL={'SAVED_BASIC_VERIFIED','NO_ROWS_RETURNED_NOT_COVERAGE','FINMIND_RETRY_EXHAUSTED'}

class ProviderPause(RuntimeError):pass

def candidate_codes(info,delisted):
    # Historical delistings supplement today's directory. This is a candidate
    # union, never proof of the point-in-time ordinary-share universe.
    codes={str(r.get('stock_id','')) for r in info if r.get('type') in ('twse','tpex')}
    codes.update(str(r.get('stock_id','')) for r in delisted)
    return sorted(c for c in codes if re.fullmatch(r'[1-9][0-9]{3}',c))

def jobs(month,codes):
    year,m=map(int,month.split('-'));end=month+f'-{calendar.monthrange(year,m)[1]:02d}'
    for code in codes:
        for dataset,category,start in DATASETS:
            if end<start:continue
            if category in FINANCIAL and m not in (3,6,9,12):continue
            first=month+'-01';last=end
            if category=='revenue':
                y2,m2=(year+1,1) if m==12 else (year,m+1)
                first=f'{y2}-{m2:02d}-01';last=f'{y2}-{m2:02d}-{calendar.monthrange(y2,m2)[1]:02d}'
            yield dict(source='FinMind',dataset=dataset,category=category,stock_id=code,
                       period=month,month=month,start_date=first,end_date=last,
                       url='https://api.finmindtrade.com/api/v4/data',
                       cross_source_alignment_approved=False)

def validate(raw,job):
    doc=json.loads(raw.decode('utf-8-sig'))
    if doc.get('status') in (401,402,403,429):raise ProviderPause('FINMIND_AUTH_PLAN_OR_RATE_LIMIT')
    if doc.get('status')!=200 or not isinstance(doc.get('data'),list):
        raise ValueError('FINMIND_RESPONSE_NOT_SUCCESS')
    rows=doc['data']
    if not rows:return None
    for row in rows:
        if str(row.get('stock_id',''))!=job['stock_id']:raise ValueError('FINMIND_STOCK_ID_MISMATCH')
        date=str(row.get('date',''))
        dt.date.fromisoformat(date)
        if not job['start_date']<=date<=job['end_date']:raise ValueError('FINMIND_DATE_OUTSIDE_REQUEST')
        if job['category']=='revenue':
            if str(row.get('revenue_year'))!=job['month'][:4] or int(row.get('revenue_month',0))!=int(job['month'][5:]):
                raise ValueError('FINMIND_REVENUE_PERIOD_MISMATCH')
        if job['category']=='prices':
            values={k:float(row[k]) for k in ('open','max','min','close')}
            if any(not math.isfinite(v) or v<0 for v in values.values()):raise ValueError('FINMIND_INVALID_PRICE')
            if all(v>0 for v in values.values()) and not (
                values['min']<=values['open']<=values['max'] and values['min']<=values['close']<=values['max']):
                raise ValueError('FINMIND_OHLC_VIOLATION')
        if job['category'] in FINANCIAL and not math.isfinite(float(row['value'])):
            raise ValueError('FINMIND_NONFINITE_FINANCIAL_CELL')
    return dict(rows=len(rows),codes=[job['stock_id']])

def request(worker,params):
    token=(os.environ.get('FINMIND_TOKEN') or os.environ.get('FINMIND_API_TOKEN') or '').strip()
    limit=480 if token else 240
    recent=[t for t in worker.cursor.get('finmind_requests_utc',[]) if time.time()-t<3600]
    if len(recent)>=limit:
        worker.cursor['finmind_resume_after_epoch']=min(recent)+3601
        worker.save_cursor()
        raise ProviderPause('FINMIND_HOURLY_REQUEST_BUDGET')
    recent.append(time.time());worker.cursor['finmind_requests_utc']=recent
    worker.save_cursor()  # Count intent before source HTTP, including a lost response.
    headers={'User-Agent':'JARVIS-C1-0.93-ascending-raw','Accept':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params),headers=headers)
    try:
        with urllib.request.urlopen(req,timeout=25) as response:
            raw=response.read(18000001)
    except urllib.error.HTTPError as exc:
        if exc.code in (401,402,403,429):raise ProviderPause('FINMIND_AUTH_PLAN_OR_RATE_LIMIT') from exc
        raise
    if len(raw)>18000000:raise ValueError('FINMIND_RESPONSE_SIZE_LIMIT')
    return raw

def universe(worker):
    cached=engine.getj(worker.d,worker.stagectrl,'FINMIND_CANDIDATE_UNIVERSE.json')
    if cached:return cached['codes']
    lists={}
    for dataset in ('TaiwanStockInfo','TaiwanStockDelisting'):
        name=dataset+'_RAW.json'
        raw=worker.d.read(worker.stagectrl,name)
        if raw is None:
            raw=request(worker,{'dataset':dataset})
            obj=json.loads(raw)
            if obj.get('status') in (401,402,403,429):raise ProviderPause('FINMIND_DIRECTORY_UNAVAILABLE')
            if obj.get('status')!=200 or not isinstance(obj.get('data'),list):
                raise ValueError('FINMIND_DIRECTORY_UNPROVEN')
            worker.owned();worker.d.put(worker.stagectrl,name,raw,'application/json',overwrite=False)
        obj=json.loads(raw);lists[dataset]=obj['data']
    codes=candidate_codes(lists['TaiwanStockInfo'],lists['TaiwanStockDelisting'])
    if not codes:raise ValueError('FINMIND_CANDIDATE_UNIVERSE_EMPTY')
    worker.putj(worker.stagectrl,'FINMIND_CANDIDATE_UNIVERSE.json',
        dict(codes=codes,historical_universe_complete=False,
             reason='CURRENT_LIST_PLUS_AVAILABLE_DELISTINGS_NOT_PIT_CERTIFIED'))
    return codes

def supplement(worker,month):
    worker.state['finmind_alignment_hold']='RAW_ONLY_SEPARATE_SOURCE_NOT_MERGED'
    try:
        codes=universe(worker)
    except ProviderPause as exc:
        worker.state['finmind_download_status']=str(exc);worker.save_state();return False
    worker.state['finmind_candidate_count']=len(codes)
    worker.state['historical_universe_complete']=False
    bucket='finmind_units';worker.state.setdefault(bucket,{})
    attempts=worker.state['attempt_ledger'].setdefault(bucket,{})
    for job in jobs(month,codes):
        key=engine.key(job);old=worker.state[bucket].get(key,{})
        if old.get('status') in TERMINAL:continue
        if attempts.get(key,0)>=3:
            worker.state[bucket][key]=dict(old,status='FINMIND_RETRY_EXHAUSTED')
            continue
        if time.monotonic()>=worker.until-30:return False
        if old.get('status') in ('REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED','FINMIND_UNCERTAIN_RESPONSE_HOLD'):
            # Inventory recovery already ran; preserve uncertainty instead of
            # silently repeating a request whose response may have been saved.
            worker.state[bucket][key]=dict(old,status='FINMIND_UNCERTAIN_RESPONSE_HOLD')
            continue
        attempts[key]=attempts.get(key,0)+1
        receipt=dict(job,unit_id=key,attempts=attempts[key],
                     status='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED',
                     numeric_verified=False,pit_verified=False)
        worker.state[bucket][key]=receipt;worker.save_state()
        raw=None
        try:
            raw=request(worker,{'dataset':job['dataset'],'data_id':job['stock_id'],
                'start_date':job['start_date'],'end_date':job['end_date']})
            stats=validate(raw,job)
            if stats is None:
                receipt.update(status='NO_ROWS_RETURNED_NOT_COVERAGE',sha256=native.sha(raw),bytes=len(raw))
                worker.state[bucket][key]=receipt;worker.save_state()
            else:
                receipt.update(status='SAVED_BASIC_VERIFIED',sha256=native.sha(raw),
                               bytes=len(raw),rows=stats['rows'],codes_found=stats['codes'])
                worker.record_payload(job,raw,receipt,bucket)
        except ProviderPause as exc:
            # Provider rejected the call or our local budget prevented sending.
            # Keep this candidate retryable after the pause, never mark it saved.
            attempts[key]=max(0,attempts[key]-1)
            receipt.update(status='FINMIND_PROVIDER_WAIT',error=str(exc),attempts=attempts[key])
            worker.state[bucket][key]=receipt;worker.save_state();return False
        except (ValueError,KeyError,TypeError,TimeoutError,OSError) as exc:
            receipt.update(status='FINMIND_DOWNLOAD_OR_VALIDATION_HOLD',
                           error=type(exc).__name__+':'+str(exc)[:160])
            worker.state[bucket][key]=receipt;worker.save_state()
        worker.processed+=1
    pending=[r for r in worker.state[bucket].values() if r.get('status') not in TERMINAL]
    saved=sum(r.get('status')=='SAVED_BASIC_VERIFIED' for r in worker.state[bucket].values())
    worker.state.update(finmind_download_status='QUEUE_VISITED_WITH_GAPS' if pending else 'QUEUE_VISITED',
        finmind_saved_units=saved,finmind_unresolved_units=len(pending),
        coverage_certified=False,numeric_verified=False,pit_verified=False)
    worker.save_state()
    return True
