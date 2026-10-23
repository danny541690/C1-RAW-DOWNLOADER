"""Two-ended official-only capture; reuse immutable v0.93 receipts, no FinMind."""
import argparse
import calendar
import collections
import datetime as dt
import json
import re
import time
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

class OfficialWorker(PreviousWorker):
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
        except Exception:
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'INIT_FAILED'))
            raise

    def fetch_job(self,job,bucket):
        assert_official(job)
        key=engine.key(job)
        old=self.state[bucket].get(key,{})
        if old.get('status')=='SAVED_BASIC_VERIFIED':
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
            if entry.get('source') in SOURCES and entry.get('status')=='SAVED_BASIC_VERIFIED'
            for code in entry.get('codes_found',[])})
        self.official_financial_universe_count=len(self.state['stocks'])
        try:return engine.History.financial_jobs(self)
        finally:self.state['stocks']=prior

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
            if not self.inventory_existing((source,)):return False
            financial=self.financial_jobs() if source=='MOPS' else []
            # Unpublished current-quarter statements are not missing downloads.
            financial=[j for j in financial if dt.date.fromisoformat(j['period'])<=cutoff]
            for bucket,items in (('units',[j for j in jobs if j['source']==source]),('financial_units',financial)):
                for job in items:
                    if time.monotonic()>=self.until:return False
                    if quota is not None and self.processed>=quota:return False
                    self.fetch_job(job,bucket)
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
                self.cursor.update(status='ACTIVE',active_month=month)
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
                        skipped_this_run=dict(self.skipped),run_id=self.owner,updated_utc=native.stamp())
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
