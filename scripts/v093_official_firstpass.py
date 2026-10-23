"""Two-ended official-only capture; reuse immutable v0.93 receipts, no FinMind."""
import argparse
import calendar
import collections
import concurrent.futures
import datetime as dt
import json
import re
import time
import urllib.error
from urllib.parse import urlparse, urlencode
from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_replanned_five_stage import Worker as PreviousWorker
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r1 import C1
from scripts.v093_five_stage_durable_gate import commit, LeaseBusy
from scripts.v093_raw_month_coordination import capture_history_month

REVISION='OFFICIAL_ONLY_TWO_ENDS_20261023_V1'
SOURCES=('TWSE','TPEx','MOPS')
HOSTS={'www.twse.com.tw','www.tpex.org.tw','mopsov.twse.com.tw','mopsfin.twse.com.tw'}
SAVED={'SAVED_BASIC_VERIFIED','RAW_DOWNLOADED_UNVERIFIED'}
# Explicit lower bounds returned by the corresponding official endpoints.
LOWER_BOUNDS={('TWSE','prices_indices'):'2004-02-11',
 ('TWSE','institutional'):'2012-05-02',('TWSE','margin'):'2001-01-01',
 ('TWSE','valuation'):'2005-09-02',('TWSE','lending'):'2005-07-01',
 ('TWSE','foreign_holdings'):'2004-02-11'}

def months_through(end):
    return [f'{y}-{m:02d}' for y in range(2000,2027) for m in range(1,13)
            if f'{y}-{m:02d}'<=end]

def is_before_source_start(job):
    earliest=LOWER_BOUNDS.get((job['source'],job['category']))
    return earliest if earliest and job['period']<earliest else None

def assert_official(job):
    if job['source'] not in SOURCES or urlparse(job['url']).hostname not in HOSTS:
        raise ValueError('NON_OFFICIAL_SOURCE_FORBIDDEN')

def firstpass_receipt(raw,job):
    """Classify a response for storage, without numeric/full-market/PIT acceptance."""
    if not raw:raise ValueError('EMPTY_RESPONSE')
    try:obj=json.loads(raw.decode('utf-8-sig'))
    except (ValueError,UnicodeDecodeError):obj=None
    if isinstance(obj,dict):
        status=str(obj.get('stat',obj.get('status',''))).lower()
        rows,codes,_=native.tabular(obj)
        if status not in ('','ok','200') or not rows:
            return dict(status='OFFICIAL_NO_DATA_RETURNED',rows=len(rows),codes_found=[],
                note='Response preserved; empty/status response is not proof of source historical absence')
        return dict(status='RAW_DOWNLOADED_UNVERIFIED',rows=len(rows),codes_found=sorted(codes))
    text=raw.decode('utf-8',errors='replace')
    if '<table' not in text.lower():
        try:text=raw.decode('cp950')
        except UnicodeDecodeError:pass
    if '<table' in text.lower():
        codes=sorted(set(re.findall(r'<td[^>]*>\s*([1-9]\d{3})\s*</td>',text,re.I)))
        return dict(status='RAW_DOWNLOADED_UNVERIFIED',rows=None,codes_found=codes)
    return dict(status='RAW_RESPONSE_REVIEW_HOLD',rows=None,codes_found=[],
        note='Original response preserved; format/content review deferred to later pass')

class OfficialWorker(PreviousWorker):
    def indexed_month(self,month):
        if not hasattr(self,'qa_index_root'):
            qa=self.d.find(self.control,'QA1')
            root=self.d.find(qa['id'],'RAW_INDEX') if qa else None
            self.qa_index_root=root['id'] if root else None
        folder=self.d.find(self.qa_index_root,month) if self.qa_index_root else None
        return folder['id'] if folder else None

    def restore(self,month,ctrl):
        super().restore(month,ctrl)
        indexed=self.indexed_month(month)
        index=engine.getj(self.d,indexed,'MONTH_STATE.json') if indexed else None
        if not index:return
        changed=False
        for bucket in ('units','financial_units'):
            for key,receipt in index.get(bucket,{}).items():
                if (receipt.get('source') in SOURCES and receipt.get('status') in SAVED
                    and receipt.get('sha256') and receipt.get('evidence_file')
                    and self.state[bucket].get(key,{}).get('status') not in SAVED):
                    self.state[bucket][key]=dict(receipt,reused_qa_raw_index=True)
                    changed=True
        for fid,evidence in index.get('inventory',{}).items():
            if evidence.get('source') in SOURCES and fid not in self.state['inventory']:
                self.state['inventory'][fid]=evidence;changed=True
        if changed:
            self.state['stocks']=sorted(set(self.state['stocks'])|{code for bucket in ('units','financial_units')
                for receipt in self.state[bucket].values() if receipt.get('source') in SOURCES
                for code in receipt.get('codes_found',[])})
            self.state['existing_qa_index_reused']=True
            self.save_state()

    def __init__(self,direction,minutes):
        base.Worker.__init__(self,'RAW',minutes,lease_suffix='_OFFICIAL_'+direction+'_V1',lease_ttl=5400)
        try:
            self.direction=direction
            self.stagectrl=self.d.folder(self.control,'OFFICIAL_ONLY_'+direction)
            self.otherctrl=self.d.folder(self.control,'OFFICIAL_ONLY_'+('ASC' if direction=='DESC' else 'DESC'))
            self.registry=FolderRegistry(self.d,self.d.folder(C1,'05_CONTROL'),namespace='OFFICIAL_ONLY_'+direction)
            self.cursor=engine.getj(self.d,self.stagectrl,'CURSOR.json') or {
                'revision':REVISION,'direction':direction,'month_index':0,'retry_months':[],
                'upper_month':min(self.today.strftime('%Y-%m'),'2026-12'),'status':'ACTIVE'}
            if self.cursor.get('revision')!=REVISION:raise ValueError('PLAN_MISMATCH')
            self.months=months_through(self.cursor['upper_month'])
            if direction=='DESC':self.months.reverse()
            self.phase='OFFICIAL_ONLY_FIRST_PASS'
            self.max_source_attempts=3
            self.skipped=collections.Counter()
            self.source_requests=collections.Counter()
        except Exception:
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'INIT_FAILED'))
            raise

    def saved_coverage(self,job,bucket):
        """Reuse source/period/company coverage even when an old batch has another key."""
        exact=self.state[bucket].get(engine.key(job),{})
        if exact.get('status') in SAVED:return True
        entries=[e for e in self.state[bucket].values() if e.get('status') in SAVED
            and e.get('source')==job['source'] and e.get('category')==job['category']
            and e.get('period')==job['period'] and e.get('evidence_file') and e.get('sha256')]
        if bucket!='financial_units':return bool(entries)
        requested=set(job.get('codes',[]))
        covered={c for e in entries if e.get('report_period')==job.get('report_period') for c in e.get('codes_found',[])}
        return bool(requested) and requested.issubset(covered)

    def fetch_job(self,job,bucket):
        assert_official(job)
        key=engine.key(job)
        old=self.state[bucket].get(key,{})
        if self.saved_coverage(job,bucket):
            self.skipped['already_saved']+=1;return
        earliest=is_before_source_start(job)
        if earliest:
            if old.get('status')!='OFFICIAL_PERIOD_NOT_PROVIDED':
                self.state[bucket][key]=dict(old,**job,unit_id=key,
                    status='OFFICIAL_PERIOD_NOT_PROVIDED',earliest_available_date=earliest,
                    availability_evidence='OFFICIAL_ENDPOINT_EXPLICIT_DATE_REJECTION',
                    permanent_hold=True,numeric_verified=False,pit_verified=False)
            self.skipped['before_official_start']+=1;return
        if old.get('status') in ('OFFICIAL_PERIOD_NOT_PROVIDED','OFFICIAL_NO_DATA_RETURNED','OFFICIAL_REVIEW_HOLD'):
            self.skipped[old['status']]+=1;return
        # A prior empty/error response stays visible and is not silently certified.
        if old.get('permanent_hold') or old.get('retry_exhausted'):
            self.skipped['prior_unresolved_hold']+=1;return
        PreviousWorker.fetch_job(self,job,bucket)

    def financial_jobs(self):
        prior=self.state['stocks']
        # FinMind-only codes cannot define an official-source historical universe.
        self.state['stocks']=sorted({code for bucket in ('units','financial_units')
            for entry in self.state[bucket].values()
            if entry.get('source') in SOURCES and entry.get('status') in SAVED
            for code in entry.get('codes_found',[])})
        self.official_financial_universe_count=len(self.state['stocks'])
        try:return engine.History.financial_jobs(self)
        finally:self.state['stocks']=prior

    def inspect_payload(self,source,name,raw,meta,file_ref):
        if meta.get('firstpass_revision')==REVISION and meta.get('status') in SAVED:
            if source not in SOURCES or meta.get('source')!=source or meta.get('month')!=self.active or native.sha(raw)!=meta.get('sha256'):
                raise ValueError('FIRSTPASS_ARCHIVE_IDENTITY_MISMATCH')
            self.state[meta.get('bucket','units')][meta['unit_id']]=dict(meta,evidence_file=file_ref)
            self.state['stocks']=sorted(set(self.state['stocks'])|set(meta.get('codes_found',[])))
            return
        super().inspect_payload(source,name,raw,meta,file_ref)

    def fetch_batch(self,items,bucket):
        """Network threads never touch Drive/state; archive and commit on one thread."""
        pending=[]
        for job in items:
            assert_official(job)
            key=engine.key(job);old=self.state[bucket].get(key,{})
            if self.saved_coverage(job,bucket):
                self.skipped['already_saved']+=1;continue
            if key in self.state.get('protected_legacy_receipts',{}) and old.get('status') not in SAVED:
                self.skipped['prior_saved_receipt_preserved']+=1
                continue
            attempts=self.state['attempt_ledger'].setdefault(bucket,{})
            if old.get('status') not in SAVED and old.get('firstpass_revision')!=REVISION and not is_before_source_start(job):
                # First pass gets one fresh bounded opportunity for previously failed downloads.
                old=dict(old,firstpass_revision=REVISION,permanent_hold=False,retry_exhausted=False,next_retry_at=0)
                attempts[key]=0;self.state[bucket][key]=old
            if (old.get('status') in SAVED or is_before_source_start(job)
                or old.get('permanent_hold') or old.get('retry_exhausted')
                or old.get('status') in ('OFFICIAL_PERIOD_NOT_PROVIDED','OFFICIAL_NO_DATA_RETURNED','RAW_RESPONSE_REVIEW_HOLD')):
                if old.get('status') in SAVED:self.skipped['already_saved']+=1
                elif is_before_source_start(job):self.fetch_job(job,bucket)
                else:self.skipped['deferred_to_later_pass']+=1
                continue
            if attempts.get(key,0)>=3 or old.get('next_retry_at',0)>time.time():continue
            if self.circuit[job['source']]>=2:
                self.state[bucket][key]=dict(job,unit_id=key,status='RETRY_WAIT',
                    next_retry_at=time.time()+900,attempts=attempts.get(key,0),numeric_verified=False,pit_verified=False)
                continue
            attempts[key]=attempts.get(key,0)+1
            receipt=dict(job,unit_id=key,attempts=attempts[key],
                status='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED',numeric_verified=False,pit_verified=False,
                bucket=bucket,month=self.active,run=base.RUN,firstpass_revision=REVISION)
            self.state[bucket][key]=receipt;pending.append((job,receipt))
        if not pending:return
        self.save_state()  # Durable intent precedes all source requests.
        def download(pair):
            job,receipt=pair;receipt=dict(receipt);raw=None
            try:
                raw=native.request(job['url'],job.get('params'))
                receipt.update(firstpass_receipt(raw,job))
            except Exception as exc:
                transient=base.retryable(exc);delay=min(3600,60*2**(receipt['attempts']-1))
                if isinstance(exc,urllib.error.HTTPError) and exc.headers:
                    try:delay=max(delay,float(exc.headers.get('Retry-After','0')))
                    except ValueError:pass
                receipt.update(status='RETRY_WAIT' if transient and receipt['attempts']<3 else 'ISOLATED_MISSING',
                    error=type(exc).__name__+':'+str(exc)[:200],permanent_hold=not transient,
                    next_retry_at=time.time()+delay,retry_exhausted=receipt['attempts']>=3)
            if raw is not None:receipt.update(sha256=native.sha(raw),bytes=len(raw))
            return job,receipt,raw
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(download,pending))
        groups=collections.defaultdict(list)
        for job,receipt,raw in results:
            source=job['source'];self.source_requests[source]+=1;self.processed+=1
            self.circuit[source]=self.circuit[source]+1 if receipt['status']=='RETRY_WAIT' else 0
            if raw is None:self.state[bucket][receipt['unit_id']]=receipt
            else:groups[(source,receipt['status'] in SAVED)].append((receipt,raw))
        for (source,success),entries in groups.items():
            blob=engine.packed(entries);digest=native.sha(blob)
            parent=self.folder(source,self.active) if success else self.d.folder(self.monthctrl,'QUARANTINE')
            name=base.RUN+'_OFFICIAL_BATCH_'+digest+'.zip'
            self.owned();self.d.put(parent,name,blob,'application/zip',overwrite=False)
            file=self.d.find(parent,name)
            for receipt,raw in entries:
                receipt.update(evidence_file=file['id']+'/'+receipt['unit_id']+'.raw',archive_sha256=digest)
                self.state[bucket][receipt['unit_id']]=receipt
                if success:
                    self.saved+=1
                    self.state['stocks']=sorted(set(self.state['stocks'])|set(receipt.get('codes_found',[])))
            if success:self.state['inventory'][file['id']]=dict(name=name,source=source,sha256=digest,
                errors=[],checked_utc=native.stamp(),verified_on_write=True)
        self.save_state()
        print('OFFICIAL_BATCH_SAVED '+json.dumps(dict(month=self.active,source=items[0]['source'],
            requests=len(results),saved=sum(r['status'] in SAVED for _,r,_ in results),
            network_concurrency=2,archive_count=len(groups))),flush=True)

    def capture_month(self,month,quota=None):
        self.restore(month,self.monthfolder('RAW',month))
        jobs=native.Audit.jobs(object.__new__(native.Audit),month,set())
        # Historical Saturday trading must not be lost by the older weekday plan.
        year,mo=map(int,month.split('-'))
        for day in range(1,calendar.monthrange(year,mo)[1]+1):
            date=dt.date(year,mo,day)
            if date.weekday()!=5 or date>self.today:continue
            for source,datasets in native.DAILY.items():
                for category,path,extra in datasets:
                    arg=date.strftime('%Y%m%d' if source=='TWSE' else '%Y/%m/%d')
                    root='https://www.twse.com.tw/' if source=='TWSE' else 'https://www.tpex.org.tw/www/zh-tw/'
                    jobs.append(dict(source=source,category=category,period=date.isoformat(),month=month,
                        url=root+path+'?'+urlencode(dict(date=arg,response='json',**extra))))
        now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        cutoff=self.today if now.hour>=18 else self.today-dt.timedelta(days=1)
        jobs=[j for j in jobs if len(j['period'])!=10 or j['period']<=cutoff.isoformat()]
        jobs.sort(key=lambda j:(j['period'],j['category']),reverse=self.direction=='DESC')
        for source in SOURCES:
            financial=self.financial_jobs() if source=='MOPS' else []
            # Unpublished current-quarter statements are not missing downloads.
            financial=[j for j in financial if dt.date.fromisoformat(j['period'])<=cutoff]
            source_jobs=[j for j in jobs if j['source']==source]
            # Known receipts suffice to skip completed data; inventory only unknown requests.
            unknown=any((engine.key(j) not in self.state[b] or self.state[b][engine.key(j)].get('status')=='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED') and not self.saved_coverage(j,b)
                and engine.key(j) not in self.state.get('protected_legacy_receipts',{}) and not is_before_source_start(j)
                for b,items in (('units',source_jobs),('financial_units',financial)) for j in items)
            if unknown and not self.inventory_existing((source,)):return False
            if source=='MOPS':financial=[j for j in self.financial_jobs() if dt.date.fromisoformat(j['period'])<=cutoff]
            for bucket,items in (('units',[j for j in jobs if j['source']==source]),('financial_units',financial)):
                for offset in range(0,len(items),6):
                    if time.monotonic()>=self.until:return False
                    if quota is not None and self.processed>=quota:return False
                    limit=6 if quota is None else min(6,quota-self.processed)
                    self.fetch_batch(items[offset:offset+limit],bucket)
        records=[e for b in ('units','financial_units') for e in self.state[b].values() if e.get('source') in SOURCES]
        retry=any(e.get('status')=='RETRY_WAIT' and not e.get('retry_exhausted') for e in records)
        waiting=set(self.cursor.get('retry_months',[]))
        if retry:waiting.add(month)
        else:waiting.discard(month)
        self.cursor['retry_months']=sorted(waiting,reverse=self.direction=='DESC')
        self.save_state()
        result={'revision':REVISION,'month':month,'sources':list(SOURCES),'finmind_enabled':False,
            'queue_visited':True,'download_complete':False,'numeric_verified':False,'pit_verified':False,
            'official_financial_universe_count':getattr(self,'official_financial_universe_count',0),
            'historical_universe_complete':False,
            'source_counts':{s:dict(collections.Counter(e['status'] for e in records if e['source']==s)) for s in SOURCES},
            'updated_utc':native.stamp()}
        self.putj(self.monthctrl,'OFFICIAL_FIRSTPASS_RESULT.json',result)
        print('OFFICIAL_MONTH_RESULT '+json.dumps(result,ensure_ascii=False),flush=True)
        return True

    def may_start(self,month):
        other=engine.getj(self.d,self.otherctrl,'CURSOR.json')
        if not other:return True
        if other.get('revision')!=REVISION:raise ValueError('OTHER_PLAN_MISMATCH')
        othermonths=months_through(other['upper_month'])
        if other['direction']=='DESC':othermonths.reverse()
        index=other['month_index']
        frontier=othermonths[index] if index<len(othermonths) else None
        self.cursor['other_next_month']=frontier
        crossed=frontier is None or (month>frontier if self.direction=='ASC' else month<frontier)
        if crossed:self.cursor['status']='PRIMARY_RANGE_VISITED'
        return not crossed

    def run(self):
        try:
            # Retry only transient download failures; no second-round numerical repair.
            for month in list(self.cursor.get('retry_months',[]))[:1]:
                if time.monotonic()>=self.until:break
                capture_history_month(self,month,quota=self.processed+3)
            while self.cursor.get('status')!='PRIMARY_RANGE_VISITED' and time.monotonic()<self.until:
                index=self.cursor['month_index']
                if index>=len(self.months):self.cursor['status']='PRIMARY_RANGE_VISITED';break
                month=self.months[index]
                if not self.may_start(month):break
                self.cursor.update(status='ACTIVE',active_month=month,next_month=month)
                self.save_cursor()
                if not capture_history_month(self,month,can_start=lambda:self.may_start(month)):break
                self.cursor['month_index']+=1
                self.cursor['last_visited_month']=month
                self.save_cursor()
            index=self.cursor['month_index']
            self.cursor['next_month']=self.months[index] if index<len(self.months) else None
            self.cursor['sources']=list(SOURCES)
            self.cursor['finmind_enabled']=False
            self.save_cursor()
            report=dict(self.cursor,processed_this_run=self.processed,saved_this_run=self.saved,
                        skipped_this_run=dict(self.skipped),source_requests_this_run=dict(self.source_requests),
                        network_concurrency_per_end=2,archive_batch_limit=6,
                        run_id=self.owner,updated_utc=native.stamp())
            self.putj(self.stagectrl,'STATUS.json',report)
            print('OFFICIAL_FIRSTPASS '+json.dumps(report,ensure_ascii=False),flush=True)
        finally:
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'OFFICIAL_BATCH_ENDED'))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--direction',choices=('ASC','DESC'),required=True)
    parser.add_argument('--minutes',type=float,default=50)
    args=parser.parse_args()
    if not 1<=args.minutes<=60:raise ValueError('INVALID_BUDGET')
    base.load_policy()
    try:OfficialWorker(args.direction,args.minutes).run()
    except LeaseBusy:print('OFFICIAL_WAIT_EXISTING_OWNER',flush=True)

if __name__=='__main__':main()
