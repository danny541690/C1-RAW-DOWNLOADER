"""Bounded supplement for explicit official gaps; never closes official evidence."""
import calendar, datetime as dt, hashlib, json, math, os, re, time
import urllib.request, urllib.parse, urllib.error
from collections import Counter
from scripts import v093_history_reverse as engine
from scripts import v093_live_five_stage as base
from scripts.v093_replanned_five_stage import ArchiveCache, cached_payload
from scripts.v093_five_stage_durable_gate import _read, _put, LeaseConflict
from scripts.v093_three_year_finmind_gaps import MAP, financial_rows

REVISION='OFFICIAL_FINMIND_GAPS_20261027_V1'
BUDGET_KEY=REVISION+'_SHARED_BUDGET'
DAILY={'prices_indices':'TaiwanStockPrice','prices':'TaiwanStockPrice',
       'institutional':'TaiwanStockInstitutionalInvestorsBuySell',
       'margin':'TaiwanStockMarginPurchaseShortSale','valuation':'TaiwanStockPER',
       'foreign_holdings':'TaiwanStockShareholding'}
GAPS={'SOURCE_NO_DATA_UNCONFIRMED','SOURCE_CONTENT_INCOMPLETE','UNRESOLVED_RETRY_CYCLES_EXHAUSTED',
      'UNRESOLVED_ATTEMPT_LIMIT','UNRESOLVED_TIME_LIMIT','UNRESOLVED_OFFICIAL_ROUTE',
      'OFFICIAL_ROUTE_NOT_FOUND','OFFICIAL_PERIOD_NOT_PROVIDED','UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE',
      'UNRESOLVED_HISTORICAL_COMPARE_SCOPE'}

def task_key(task):
    return engine.key(task)

def plan(state,journal,jobs,month,today):
    tasks={};blocked={}
    confirmed_dates={r.get('period') for r in state.get('units',{}).values()
                     if r.get('status')=='SAVED_BASIC_VERIFIED' and r.get('category') in ('prices','prices_indices')}
    for job in jobs:
        key=engine.key(job);row=journal.get('units',{}).get(key,{})
        if row.get('complete') or row.get('status') not in GAPS:continue
        cat=job['category'];source=job['source'];period=job.get('period','')
        if period>today:continue
        start=month+'-01';end=min(today,month+'-'+str(calendar.monthrange(int(month[:4]),int(month[5:]))[1]))
        kind='daily';dataset=DAILY.get(cat)
        old=state.get('financial_units' if cat in MAP else 'units',{}).get(key,{})
        if cat in MAP:
            dataset=MAP[cat];kind='financial';end=period
            start=period[:4]+'-'+f'{int(period[5:7])-2:02d}'+'-01'
            codes=set(job.get('codes',[]))-set(old.get('codes_found',[]))
            if not codes and row.get('local_error'):codes=set(job.get('codes',[]))
        else:
            market=source
            if cat.startswith('revenue_'):
                dataset='TaiwanStockMonthRevenue';kind='revenue';market='TWSE' if '_sii_' in cat else 'TPEx'
                yy,mm=map(int,month.split('-'));yy,mm=(yy+1,1) if mm==12 else (yy,mm+1)
                start=f'{yy}-{mm:02d}-01';end=min(today,f'{yy}-{mm:02d}-{calendar.monthrange(yy,mm)[1]:02d}')
            codes=set(state.get('market_codes',{}).get(market,[]))
            for receipt in state.get('units',{}).values():
                if receipt.get('source')==market and receipt.get('status')=='SAVED_BASIC_VERIFIED':
                    codes.update(receipt.get('codes_found',[]))
        if not dataset or not codes or start>end:
            blocked[key]=dict(official_gap=key,reason='UNMAPPED_DATASET_OR_HISTORICAL_UNIVERSE_NOT_PROVEN');continue
        if kind=='daily' and period not in confirmed_dates:
            blocked[key]=dict(official_gap=key,reason='OFFICIAL_TRADING_DATE_NOT_PROVEN_NO_BLIND_STOCK_REQUESTS');continue
        for code in sorted(codes):
            if not re.fullmatch(r'[1-9]\d{3}',str(code)):continue
            t=dict(source='FinMind',category=cat,dataset=dataset,stock_id=str(code),period=month,
                   month=month,kind=kind,start_date=start,end_date=end,official_gaps=[key],
                   expected_dates=[period] if kind=='daily' else [],report_period=period,
                   historical_universe_verified=False,official_gap_closed=False)
            k=task_key(t)
            if k in tasks:
                tasks[k]['official_gaps']=sorted(set(tasks[k]['official_gaps']+[key]))
                tasks[k]['expected_dates']=sorted(set(tasks[k]['expected_dates']+t['expected_dates']))
            else:tasks[k]=t
    return list(tasks.values()),list(blocked.values())

def validate(raw,task):
    obj=json.loads(raw);rows=obj.get('data')
    if obj.get('status') in (401,402,403,429):raise PermissionError('FINMIND_QUOTA_OR_AUTH:'+str(obj['status']))
    if obj.get('status')!=200 or not isinstance(rows,list):raise ValueError('FINMIND_BAD_ENVELOPE')
    if not rows:raise ValueError('FINMIND_EMPTY_NOT_ABSENCE')
    if any(not isinstance(r,dict) or str(r.get('stock_id',''))!=task['stock_id'] or not task['start_date']<=str(r.get('date',''))<=task['end_date'] for r in rows):raise ValueError('FINMIND_STOCK_OR_DATE_MISMATCH')
    if task['kind']=='financial' and (task['stock_id'],task['dataset'],task['report_period']) not in financial_rows(raw,task['dataset']):raise ValueError('FINMIND_QUARTER_UNPROVEN')
    if task['kind']=='revenue' and any(str(r.get('revenue_year'))!=task['month'][:4] or int(r.get('revenue_month',0))!=int(task['month'][5:]) for r in rows):raise ValueError('FINMIND_REVENUE_MONTH_MISMATCH')
    if task['dataset']=='TaiwanStockPrice':
        for row in rows:
            vals=[float(row[k]) for k in ('open','max','min','close')]
            o,h,l,c=vals
            if not all(math.isfinite(v) for v in vals) or l<0 or l>min(o,c) or h<max(o,c):raise ValueError('FINMIND_OHLC_INVALID')
    covered=sorted(set(str(r['date']) for r in rows)&set(task['expected_dates']))
    if task['kind']=='daily' and not covered:raise ValueError('FINMIND_NO_REQUESTED_GAP_DATE')
    return dict(rows=len(rows),covered_dates=covered,unfilled_dates=sorted(set(task['expected_dates'])-set(covered)),
                numeric_verified=False,pit_verified=False,official_gap_closed=False)

def reserve(api,token,now=None):
    instant=time.time() if now is None else now
    for _ in range(12):
        sha,m=_read(api,token);b=m['jobs'].setdefault(BUDGET_KEY,{})
        recent=[t for t in b.get('requests',[]) if instant-t<3600]
        if b.get('next_at',0)>instant or len(recent)>=200:return False
        b.update(requests=recent+[instant],next_at=instant+18)
        if _put(api,token,sha,m,'finmind: reserve shared bounded gap-only request'):return True
    raise LeaseConflict('FINMIND_SHARED_BUDGET_CAS_EXHAUSTED')

def hold(api,token):
    for _ in range(12):
        sha,m=_read(api,token);b=m['jobs'].setdefault(BUDGET_KEY,{})
        b['next_at']=max(b.get('next_at',0),time.time()+3600)
        if _put(api,token,sha,m,'finmind: share provider auth or quota cooldown'):return
    raise LeaseConflict('FINMIND_PROVIDER_HOLD_CAS_EXHAUSTED')

def supplement(w,jobs):
    if not getattr(w,'finmind_enabled',False):return
    w._finmind_poll_at=time.monotonic()
    today=w.today if dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).hour>=18 else w.today-dt.timedelta(days=1)
    tasks,blocked=plan(w.state,w.journal,jobs,w.active,today.isoformat())
    receipts=w.state.setdefault('finmind_units',{})
    metrics=getattr(w,'finmind_metrics',dict(requests=0,saved=0,failed=0))
    w.finmind_metrics=metrics
    attempted=0
    for task in tasks:
        key=task_key(task);old=receipts.get(key,{})
        if old.get('status')=='SAVED_BASIC_VERIFIED' and old.get('remote_readback_hash_verified'):continue
        if old.get('attempts',0)>=3 or old.get('next_retry_at',0)>time.time():continue
        if time.monotonic()+35>=w.until or attempted>=4:break
        if not reserve(w.api,w.token):break
        attempted+=1;row=dict(task,unit_id=key,attempts=old.get('attempts',0)+1,
                             status='FINMIND_REQUEST_INTENT',next_retry_at=time.time()+3600,revision=REVISION)
        receipts[key]=row;w.save_state();raw=None
        try:
            params={k:task[k] for k in ('dataset','start_date','end_date')};params['data_id']=task['stock_id']
            headers={'User-Agent':'JARVIS-official-gaps-only','Accept':'application/json'}
            secret=(os.environ.get('FINMIND_TOKEN') or os.environ.get('FINMIND_API_TOKEN') or '').strip()
            if secret:headers['Authorization']='Bearer '+secret
            req=urllib.request.Request('https://api.finmindtrade.com/api/v4/data?'+urllib.parse.urlencode(params),headers=headers)
            metrics['requests']+=1
            with urllib.request.urlopen(req,timeout=25) as response:raw=response.read(18000001)
            if len(raw)>18000000:raise ValueError('FINMIND_BODY_LIMIT')
            evidence=validate(raw,task)
            receipt=dict(row,**evidence,status='SAVED_BASIC_VERIFIED',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),
                         codes_found=[task['stock_id']],supplement_only=True,remote_readback_hash_verified=False)
            # Store in the separate FinMind native-source tree under the existing month lease.
            base.Worker.record_payload(w,task,raw,receipt,'finmind_units')
            remote,_=cached_payload(w.d,receipts[key],ArchiveCache())
            if hashlib.sha256(remote).hexdigest()!=receipt['sha256']:raise ValueError('FINMIND_REMOTE_SHA_MISMATCH')
            validate(remote,task)
            receipts[key].update(remote_readback_hash_verified=True,supplement_only=True,official_gap_closed=False)
            metrics['saved']+=1
        except Exception as exc:
            metrics['failed']+=1
            row.update(status='FINMIND_GAP_UNRESOLVED',error=type(exc).__name__+':'+str(exc)[:180],official_gap_closed=False)
            receipts[key]=row
            if raw is not None:
                digest=hashlib.sha256(raw).hexdigest();parent=w.d.folder(w.monthctrl,'FINMIND_REJECTED_EVIDENCE')
                w.owned();w.d.put(parent,digest+'.raw',raw,'application/octet-stream',overwrite=False)
                row['response_sha256']=digest
            if isinstance(exc,PermissionError) or isinstance(exc,urllib.error.HTTPError) and exc.code in (401,402,403,429):
                hold(w.api,w.token);w.save_state();break
        w.save_state()
    pending=sum(not receipts.get(task_key(t),{}).get('remote_readback_hash_verified',False) and receipts.get(task_key(t),{}).get('attempts',0)<3 for t in tasks)
    w.journal['finmind_pending']=pending
    report=dict(revision=REVISION,month=w.active,run_id=w.owner,planned_tasks=len(tasks),pending_tasks=pending,blocked=blocked,
                saved_tasks=sum(receipts.get(task_key(t),{}).get('remote_readback_hash_verified',False) for t in tasks),
                run_metrics=metrics,official_gap_closed=False,coverage_certified=False,numeric_verified=False,pit_verified=False)
    w.putj(w.monthctrl,'FINMIND_GAPFILL_STATUS.json',report)
    # Keep full per-task evidence in Drive; repeated console heartbeats need only totals.
    console={k:v for k,v in report.items() if k!='blocked'}
    console['blocked_tasks']=len(blocked)
    console['blocked_reason_counts']=dict(Counter(x['reason'] for x in blocked))
    print('FINMIND_GAPFILL_STATUS '+json.dumps(console),flush=True)
