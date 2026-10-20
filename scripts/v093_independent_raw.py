"""Independent official-first RAW capture/validation with bounded retries and gap queue."""
import argparse,collections,concurrent.futures,datetime as dt,io,json,os,re,time,urllib.request,zipfile
from decimal import Decimal,InvalidOperation
import scripts.v093_history_reverse as engine
import scripts.v093_three_year_repair as native
from scripts.annual_actual_firstpass import Drive,service
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_three_year_repair import ROOT,REPORT_ROOT,Audit,listing,read,stamp,sha,validate,category,actual_date
from scripts.v093_three_year_finmind_gaps import financial_rows,MAP

RUN='INDEPENDENT_RAW_2026_LATEST_TO_200001_V1'
WORKFLOW='v093-raw-resume.yml'
SOURCES=('TWSE','TPEx','MOPS','FinMind')
PRICE_FIELDS={'開盤價':'open','開盤':'open','最高價':'max','最高':'max','最低價':'min','最低':'min','收盤價':'close','收盤':'close'}

def month_plan(today):
    return [f'{y}-{m:02d}' for y in range(2026,1999,-1) for m in range(12,0,-1) if (y,m)<=(today.year,today.month)]

def price_checks(raw,source,period):
    try:obj=json.loads(raw.decode('utf-8-sig'))
    except (ValueError,UnicodeDecodeError):return {'checked_rows':0,'ohlc_violations':[],'null_cells':[],'status':'FORMAT_REQUIRES_SEPARATE_NUMERIC_CHECK'}
    tables=obj.get('tables') or [obj];bad=[];missing=[];count=0
    for table in tables:
        fields=[str(f).strip() for f in table.get('fields',[])]
        si=next((i for i,f in enumerate(fields) if f in ('代號','股票代號','證券代號','公司代號')),None)
        mapping={i:PRICE_FIELDS[f] for i,f in enumerate(fields) if f in PRICE_FIELDS}
        if si is None or set(mapping.values())!={'open','max','min','close'}:continue
        for row in table.get('data',[]):
            if not isinstance(row,list) or len(row)!=len(fields):continue
            code=str(row[si]).strip()
            if not re.fullmatch(r'[1-9]\d{3}',code):continue
            values={};null=[]
            for i,k in mapping.items():
                try:
                    value=Decimal(str(row[i]).replace(',','').strip())
                    if not value.is_finite() or value<=0:raise InvalidOperation()
                    values[k]=value
                except (InvalidOperation,ValueError):null.append(k)
            if null:missing.append({'source':source,'stock_id':code,'date':period,'fields':null,'meaning':'MISSING_OR_NONTRADING_REQUIRES_REVIEW'});continue
            count+=1
            if not values['min']<=values['open']<=values['max'] or not values['min']<=values['close']<=values['max']:
                bad.append({'stock_id':code,'date':period})
    return {'checked_rows':count,'ohlc_violations':bad,'null_cells':missing,'status':'BASIC_OHLC_CHECK_ONLY_NOT_FULL_NUMERIC_ACCEPTANCE'}

def retry_candidates(jobs,state,ledger):
    return [j for j in jobs if state.get(engine.key(j),{}).get('status')!='SAVED_BASIC_VERIFIED' and ledger.get(engine.key(j),0)<3]

class Independent(engine.History):
    def __init__(self,minutes):
        self.today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
        engine.RUN=RUN;engine.MONTHS=month_plan(self.today);native.TODAY=self.today
        super().__init__(minutes)
        plan=engine.getj(self.d,self.control,'PLAN.json')
        self.months=plan['months'] if plan else month_plan(self.today)
        if not self.months or self.months[-1]!='2000-01' or len(self.months)!=len(set(self.months)):raise ValueError('MONTH_PLAN_CONFLICT')
        self.batch_alerts=[]
        self.registry=FolderRegistry(self.d,'10_k6r3pRGKYUp5YbyD3UA1oWw6DngHlO',namespace='INDEPENDENT_RAW')
    def folder(self,source,month):
        k=(source,month)
        if k not in self.folders:
            year=self.registry.folder(ROOT,month[:4],True)
            source_root=self.registry.folder(year,source,True)
            self.folders[k]=self.registry.folder(source_root,month,True)
        return self.folders[k]
    def save_state(self):
        self.registry.flush();super().save_state()
    def restore(self,month,ctrl):
        self.state=engine.getj(self.d,ctrl,'MONTH_STATE.json') or {'month':month,'units':{},'financial_units':{},'finmind_units':{},'finmind_tasks':[],'phase':'INVENTORY','stocks':[],'market_codes':{},'archives':[],'started_utc':stamp()}
        self.active=month;self.monthctrl=ctrl
        for name,default in (('inventory',{}),('inventory_errors',[]),('attempt_ledger',{}),('fm_attempts',{}),('numeric_checks',{}),('existing_finmind',[])):
            self.state.setdefault(name,default)
    def inspect_payload(self,source,name,payload,meta,file_ref):
        cat=meta.get('category') or category(name,source)
        period=meta.get('period') or meta.get('date') or meta.get('effective_date')
        if source=='FinMind':
            try:
                obj=json.loads(payload.decode('utf-8-sig'));rows=obj.get('data',obj.get('rows',[]));dataset=obj.get('dataset') or next((d for d in list(MAP.values())+['TaiwanStockPrice','TaiwanStockMonthRevenue','TaiwanStockInstitutionalInvestorsBuySell','TaiwanStockMarginPurchaseShortSale','TaiwanStockPER','TaiwanStockShareholding'] if d in name),'')
                if not dataset or not isinstance(rows,list) or not rows:raise ValueError('FINMIND_DATASET_OR_ROWS_UNPROVEN')
                if dataset in MAP.values() and not financial_rows(payload,dataset):raise ValueError('FINMIND_FINANCIAL_NUMERIC_UNPROVEN')
                dates=collections.defaultdict(set)
                for row in rows:
                    code=str(row.get('stock_id',''));date=str(row.get('date',''))
                    if not re.fullmatch(r'[1-9]\d{3}',code):raise ValueError('FINMIND_STOCK_ID_UNPROVEN')
                    if dataset=='TaiwanStockMonthRevenue':
                        if str(row.get('revenue_year'))!=self.active[:4] or int(row.get('revenue_month',0))!=int(self.active[5:]):raise ValueError('FINMIND_REVENUE_MONTH_UNPROVEN')
                    elif date[:7]!=self.active:raise ValueError('FINMIND_DATE_MONTH_UNPROVEN')
                    dates[code].add(date)
                if dataset=='TaiwanStockPrice':
                    for row in rows:
                        values={k:Decimal(str(row[k])) for k in ('open','max','min','close')}
                        if any(not v.is_finite() or v<=0 for v in values.values()) or not values['min']<=values['open']<=values['max'] or not values['min']<=values['close']<=values['max']:raise ValueError('FINMIND_EXISTING_OHLC_UNVERIFIED')
                for code,ds in dates.items():self.state['existing_finmind'].append({'dataset':dataset,'stock_id':code,'dates':sorted(ds),'file':file_ref,'sha256':sha(payload)})
                return
            except Exception as exc:raise ValueError('FINMIND_EXISTING_UNVERIFIED:'+str(exc))
        if not cat:raise ValueError('UNMAPPED_NATIVE_DATASET')
        if not period:
            try:period=actual_date(json.loads(payload.decode('utf-8-sig')))
            except (ValueError,UnicodeDecodeError):pass
        if not period and (cat.startswith('revenue_') or cat in ('ex_dividend','capital_reduction','par_value_change')):period=self.active
        if not period or period[:7]!=self.active:raise ValueError('CONTENT_PERIOD_UNPROVEN')
        if cat in engine.FIN_REPORTS:
            holder=object.__new__(Audit);holder.year=int(self.active[:4]);holder.financial={}
            Audit.financial_payload(holder,payload,cat,file_ref)
            quarter=str(int(period[:4]))+str((int(period[5:7])-1)//3+1)
            codes=meta.get('codes') or []
            found=[code for code,report,q in holder.financial if report==cat and q==quarter and code in codes]
            if not codes or set(found)!=set(codes):raise ValueError('EXISTING_FINANCIAL_GROUP_INCOMPLETE')
            bucket='financial_units';stats={'rows':len(found),'codes':found}
        else:
            bucket='units';stats=validate(payload,source,cat,period)
        unit=dict(meta,source=source,category=cat,period=period,month=self.active)
        k=engine.key(unit)
        if cat in ('prices','prices_indices'):
            checks=price_checks(payload,source,period);self.state['numeric_checks'][k]=checks
            if checks['ohlc_violations']:raise ValueError('EXISTING_OHLC_VIOLATION')
        old=self.state[bucket].get(k)
        if old and old.get('raw_sha256',old.get('sha256'))!=sha(payload):
            self.state['inventory_errors'].append({'file':file_ref,'status':'SOURCE_UNIT_REVISION_OR_CONFLICT','unit_id':k,'new_sha256':sha(payload),'prior_sha256':old.get('sha256')})
            return
        self.state[bucket][k]=dict(unit,unit_id=k,status='SAVED_BASIC_VERIFIED',sha256=sha(payload),rows=stats['rows'],codes_found=stats['codes'],reused_existing=True,evidence_file=file_ref,numeric_verified=False,pit_verified=False)
        self.state['stocks']=sorted(set(self.state['stocks'])|set(stats['codes']))
        if source in ('TWSE','TPEx'):self.state['market_codes'][source]=sorted(set(self.state['market_codes'].get(source,[]))|set(stats['codes']))
    def inventory_existing(self):
        for source in SOURCES:
            for f in listing(self.d,self.folder(source,self.active)):
                if time.monotonic()>=self.until:return False
                if f['mimeType']=='application/vnd.google-apps.folder' or f['id'] in self.state['inventory']:continue
                name=f['name'];ext=name.lower().rsplit('.',1)[-1]
                if ext not in ('zip','raw','json','jsonl','csv','html','htm'):continue
                if any(w in name.lower() for w in ('manifest','receipt','checkpoint','audit','report','metadata')):continue
                errors=[];digest=None
                try:
                    if int(f.get('size',0))>250_000_000:raise ValueError('ARCHIVE_SIZE_LIMIT')
                    raw=read(self.d,f);digest=sha(raw)
                    if ext=='zip':
                        with zipfile.ZipFile(io.BytesIO(raw)) as z:
                            if sum(m.file_size for m in z.infolist())>700_000_000:raise ValueError('ZIP_EXPANSION_LIMIT')
                            if z.testzip():raise ValueError('ZIP_CRC_FAILED')
                            manifest=json.loads(z.read('manifest.json')) if 'manifest.json' in z.namelist() else {}
                            receipts={u.get('file'):u for u in manifest.get('units',[])}
                            for member in z.infolist():
                                if member.is_dir() or any(w in member.filename.lower() for w in ('manifest','receipt','checkpoint','metadata')):continue
                                try:
                                    if member.file_size>30_000_000:raise ValueError('MEMBER_SIZE_LIMIT')
                                    payload=z.read(member);meta=receipts.get(member.filename,{})
                                    if meta.get('source',source)!=source:raise ValueError('SOURCE_PATH_MISMATCH')
                                    if meta.get('sha256') and sha(payload)!=meta['sha256']:raise ValueError('MEMBER_SHA_MISMATCH')
                                    self.inspect_payload(source,member.filename,payload,meta,f['id']+'/'+member.filename)
                                except Exception as exc:errors.append({'member':member.filename,'reason':type(exc).__name__+':'+str(exc)[:160]})
                    else:self.inspect_payload(source,name,raw,{},f['id'])
                except Exception as exc:errors.append({'reason':type(exc).__name__+':'+str(exc)[:160]})
                self.state['inventory'][f['id']]={'name':name,'source':source,'sha256':digest,'errors':errors,'checked_utc':stamp()}
                if errors:self.state['inventory_errors'].append({'file_id':f['id'],'name':name,'issues':errors})
                self.save_state()
        return True
    def flush(self,results,bucket):
        if bucket=='finmind_units':
            for task,e,raw in results:
                if e.get('status')=='SAVED_BASIC_VERIFIED' and task.get('dataset')=='TaiwanStockPrice':
                    try:
                        rows=json.loads(raw)['data']
                        for row in rows:
                            values={k:Decimal(str(row[k])) for k in ('open','max','min','close')}
                            if any(not v.is_finite() or v<=0 for v in values.values()):raise ValueError('MISSING_OR_INVALID_PRICE')
                            if not values['min']<=values['open']<=values['max'] or not values['min']<=values['close']<=values['max']:raise ValueError('OHLC_RELATIONSHIP_VIOLATION')
                    except Exception as exc:e.update(status='FINMIND_PRICE_QUARANTINED',error=str(exc)[:160])
        super().flush(results,bucket)
    def fetch_one(self,j,bucket):
        scope=(j['source'],j['category'],j['period'][:4]);self.circuit[scope]=0
        job,e,raw=super().fetch_one(j,bucket)
        if e['status']=='SAVED_BASIC_VERIFIED' and j['category'] in ('prices','prices_indices'):
            checks=price_checks(raw,j['source'],j['period']);e['price_checks']=checks
            if checks['ohlc_violations']:e.update(status='OHLC_QUARANTINED',error='OHLC_RELATIONSHIP_VIOLATION')
        return job,e,raw
    def process(self,jobs,bucket):
        ledger=self.state['attempt_ledger'].setdefault(bucket,{})
        while True:
            pending=retry_candidates(jobs,self.state[bucket],ledger)
            if not pending:return True
            if time.monotonic()>=self.until:return False
            part=pending[:6]
            for j in part:
                k=engine.key(j);ledger[k]=ledger.get(k,0)+1
                self.state[bucket][k]=dict(j,unit_id=k,status='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED',attempts=ledger[k])
            self.save_state()
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda j:self.fetch_one(j,bucket),part))
            for j,e,raw in results:
                e['attempts']=ledger[engine.key(j)]
                if e['status']!='SAVED_BASIC_VERIFIED' and e['attempts']>=3:e['retry_exhausted']=True
                if e.get('price_checks'):self.state['numeric_checks'][engine.key(j)]=e.pop('price_checks')
            self.flush(results,bucket)
    def gap_plan(self,core):
        tasks={engine.key(t):t for t in self.fm_plan(core)}
        for checks in self.state['numeric_checks'].values():
            for gap in checks.get('null_cells',[]):
                t={'source':'FinMind','category':'prices','dataset':'TaiwanStockPrice','stock_id':gap['stock_id'],'period':self.active,'month':self.active,'kind':'daily_month','official_missing_dates':[gap['date']],'null_field_review':gap['fields'],'raw_only_not_cross_source_aligned':True}
                tasks.setdefault(engine.key(t),t)
        return list(tasks.values())
    def supplement(self,max_tasks):
        completed=0
        while completed<max_tasks and time.monotonic()<self.until:
            pending=[t for t in self.state['finmind_tasks'] if self.state['finmind_units'].get(engine.key(t),{}).get('status')!='SAVED_BASIC_VERIFIED' and self.state['fm_attempts'].get(engine.key(t),0)<3]
            if not pending:return True
            task=pending[0];k=engine.key(task)
            # Reuse a verified existing supplement only when stock, dataset and required dates match.
            existing=next((e for e in self.state['existing_finmind'] if e['dataset']==task['dataset'] and e['stock_id']==task['stock_id'] and
                           ((task['kind']=='daily_month' and set(task.get('official_missing_dates',[])).issubset(e['dates'])) or
                            (task['kind']=='financial' and task['period'] in e['dates']) or task['kind']=='revenue')),None)
            if existing:
                self.state['finmind_units'][k]=dict(task,unit_id=k,status='SAVED_BASIC_VERIFIED',reused_existing=True,evidence=existing,numeric_verified=False,pit_verified=False);self.save_state();completed+=1;continue
            budget,_,_=self.quota()
            if budget<=0:return False
            self.state['fm_attempts'][k]=self.state['fm_attempts'].get(k,0)+1;self.save_state()
            prior_tasks=self.state['finmind_tasks'];self.state['finmind_tasks']=[task]
            self.state['finmind_units'].pop(k,None)
            try:super().finmind(1)
            finally:self.state['finmind_tasks']=prior_tasks
            e=self.state['finmind_units'].get(k)
            if e is None:self.state['finmind_units'][k]=dict(task,unit_id=k,status='PROVIDER_LIMIT_OR_UNCONFIRMED',attempts=self.state['fm_attempts'][k])
            else:e['attempts']=self.state['fm_attempts'][k]
            self.save_state();completed+=1
        return False
    def report(self,core):
        records=list(self.state['units'].values())+list(self.state['financial_units'].values())+list(self.state['finmind_units'].values())
        failures=[e for e in records if e.get('status')!='SAVED_BASIC_VERIFIED']
        pending=[t for t in self.state['finmind_tasks'] if self.state['finmind_units'].get(engine.key(t),{}).get('status')!='SAVED_BASIC_VERIFIED' and self.state['fm_attempts'].get(engine.key(t),0)<3]
        result={'version':RUN,'month':self.active,'updated_utc':stamp(),'phase':self.state['phase'],'as_of_date':self.today.isoformat(),
                'expected_core_units':len(core),'state_counts':dict(collections.Counter(e['status'] for e in records)),
                'reused_units':sum(bool(e.get('reused_existing')) for e in records),'inventory_files':len(self.state['inventory']),
                'inventory_issues':self.state['inventory_errors'],'failed_or_unverified_units':failures,'finmind_pending':len(pending),
                'numeric_checks':self.state['numeric_checks'],'archives':self.state['archives'],
                'source_priority':['TWSE','TPEx','MOPS','FinMind_FREE_GAP_ONLY'],'source_native_separate_no_silent_patch':True,
                'calendar_verified':False,'historical_universe_verified':False,'field_unit_contract_verified':False,
                'full_market_complete':False,'numeric_verified':False,'pit_verified':False,'production_ready':False}
        engine.putj(self.d,self.monthctrl,'RESULT.json',result)
        engine.putj(self.d,self.monthctrl,'MISSING_AND_PENDING.json',{'month':self.active,'failed_or_unverified':failures,'finmind_pending':pending,'inventory_issues':self.state['inventory_errors'],'no_automatic_retry_after_three_attempts':True})
        summary={'month':self.active,'phase':self.state['phase'],'units':len(records),'failed_or_unverified':len(failures),'inventory_issues':len(self.state['inventory_errors']),'finmind_pending':len(pending),'report_folder_id':self.monthctrl}
        if failures or self.state['inventory_errors'] or pending:self.batch_alerts.append(summary);print('INDEPENDENT_RAW_ALERT '+json.dumps(summary),flush=True)
        return summary
    def progress(self):
        idx=self.checkpoint['month_index'];result={'version':RUN,'updated_utc':stamp(),'start_month':self.months[0],'end_month':'2000-01','as_of_date':self.today.isoformat(),'total_months':len(self.months),'primary_processed_months':idx,'active_month':self.active,'next_primary_month':self.months[idx] if idx<len(self.months) else None,'mode':self.checkpoint['mode'],'finmind_backlog_index':self.checkpoint['backlog_month_index'],'done':self.checkpoint.get('done',False),'production_ready':False,'numeric_verified':False,'full_market_complete':False}
        engine.putj(self.d,self.control,'PROGRESS.json',result);return result
    def _run_impl(self):
        if not engine.getj(self.d,self.control,'PLAN.json'):
            engine.putj(self.d,self.control,'PLAN.json',{'version':RUN,'months':self.months,'started_as_of_date':self.today.isoformat(),'sources':['TWSE','TPEx','MOPS','FinMind_FREE_GAP_ONLY'],'retry_limit_total_attempts':3,'existing_data':'VALIDATE_ACTUAL_BYTES_REUSE_ONLY_PROVEN_UNITS','source_raw_immutable':True,'legacy_imports':0,'future_months_excluded':True})
        self.active=None
        while self.checkpoint['month_index']<len(self.months) and time.monotonic()<self.until:
            month=self.months[self.checkpoint['month_index']];ctrl=self.d.folder(self.control,month);self.restore(month,ctrl)
            if self.state['phase']=='INVENTORY':
                if not self.inventory_existing():self.report([]);break
                self.state['phase']='OFFICIAL_CORE';self.save_state()
            core=Audit.jobs(object.__new__(Audit),month,set())
            if self.state['phase']=='OFFICIAL_CORE':
                if not self.process(core,'units'):self.report(core);break
                self.state['phase']='OFFICIAL_FINANCIAL';self.save_state()
            if self.state['phase']=='OFFICIAL_FINANCIAL':
                if not self.process(self.financial_jobs(),'financial_units'):self.report(core);break
                self.state['finmind_tasks']=self.gap_plan(core);self.state['phase']='FINMIND_SUPPLEMENT';self.save_state()
            if self.state['phase']=='FINMIND_SUPPLEMENT':
                self.supplement(30);self.state['phase']='PRIMARY_SAVED_WITH_EXPLICIT_GAPS';self.save_state()
            summary=self.report(core)
            self.checkpoint['finished_months'].append(summary);self.checkpoint['month_index']+=1;self.save_cursor();self.progress()
        if self.checkpoint['month_index']>=len(self.months):
            self.checkpoint['mode']='FINMIND_BACKLOG'
            while self.checkpoint['backlog_month_index']<len(self.months) and time.monotonic()<self.until:
                index=self.checkpoint['backlog_month_index'];month=self.months[index];self.restore(month,self.d.folder(self.control,month))
                done=self.supplement(240);self.report(Audit.jobs(object.__new__(Audit),month,set()))
                if not done:break
                self.checkpoint['backlog_month_index']+=1;self.save_cursor()
            if self.checkpoint['backlog_month_index']>=len(self.months):self.checkpoint.update(done=True,mode='FINISHED_WITH_EXPLICIT_GAPS')
        self.save_cursor();progress=self.progress();print('INDEPENDENT_RAW_BATCH_SUMMARY '+json.dumps({'progress':progress,'alerts':self.batch_alerts}),flush=True)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write('```json\n'+json.dumps({'progress':progress,'alerts':self.batch_alerts},ensure_ascii=False,indent=2)+'\n```\n')
        if self.checkpoint.get('done'):self.disable_finished_schedule()
    def run(self):
        while time.monotonic()<self.until:
            try:return self._run_impl()
            except Exception as exc:
                month=self.active
                if month not in self.months:raise
                ledger=self.checkpoint.setdefault('month_system_errors',{})
                item=ledger.setdefault(month,{'attempts':0,'errors':[]})
                item['attempts']+=1;item['errors'].append(type(exc).__name__+':'+str(exc)[:200])
                engine.putj(self.d,self.monthctrl,'SYSTEM_ERROR.json',dict(item,month=month,production_ready=False))
                print('INDEPENDENT_RAW_ALERT '+json.dumps({'month':month,'system_error':item,'report_folder_id':self.monthctrl}),flush=True)
                if item['attempts']>=3:
                    if self.checkpoint['month_index']<len(self.months):
                        self.checkpoint['finished_months'].append({'month':month,'status':'SYSTEM_ERROR_EXHAUSTED','report_folder_id':self.monthctrl})
                        self.checkpoint['month_index']+=1
                    else:self.checkpoint['backlog_month_index']+=1
                self.save_cursor();self.progress()
    def disable_finished_schedule(self):
        req=urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/actions/workflows/'+WORKFLOW+'/disable',data=b'',method='PUT',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=20):pass

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=40);a=p.parse_args();Independent(a.minutes).run()
