"""Independent targeted official-only repair; original source archives remain immutable."""
import argparse
import collections
import datetime as dt
import json
import time
from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_independent_raw import price_checks
from scripts.v093_official_firstpass import OfficialWorker, SOURCES, SAVED, months_through, assert_official, is_before_source_start
from scripts.v093_replanned_five_stage import ArchiveCache, cached_payload
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r1 import C1
from scripts.v093_five_stage_durable_gate import commit, LeaseBusy
from scripts.v093_raw_month_coordination import capture_history_month

REVISION='OFFICIAL_TARGETED_REPAIR_20261023_V1'

def needs_review(receipt,flagged):
    if receipt.get('source') not in SOURCES:return False
    if receipt.get('status')=='OFFICIAL_PERIOD_NOT_PROVIDED':return False
    return receipt.get('status')!='SAVED_BASIC_VERIFIED' or receipt.get('unit_id') in flagged

def validate_content(raw,job):
    if job['category'] in engine.FIN_REPORTS:
        holder=object.__new__(native.Audit);holder.year=int(job['month'][:4]);holder.financial={}
        native.Audit.financial_payload(holder,raw,job['category'],'official raw')
        expected=set(job.get('codes',[]))
        found={c for c,r,p in holder.financial if r==job['category'] and p==job['report_period']}
        if not expected or not expected.issubset(found):raise ValueError('FINANCIAL_REQUESTED_COMPANIES_OR_PERIOD_INCOMPLETE')
        return dict(rows=len(found),codes=sorted(found),validation_level='EXPLICIT_COMPANY_REPORT_PERIOD_BASIC_CELLS')
    try:stats=native.validate(raw,job['source'],job['category'],job['period'])
    except ValueError as exc:
        # Historical market size is not a correctness threshold.
        if str(exc)!='NOT_FULL_MARKET_PRICE_TABLE':raise
        obj=json.loads(raw.decode('utf-8-sig'));rows,codes,width=native.tabular(obj)
        if not rows or width or native.actual_date(obj)!=job['period']:raise
        stats=dict(rows=len(rows),codes=sorted(codes),historical_universe_complete=False)
    if job['category'] in ('prices','prices_indices'):
        check=price_checks(raw,job['source'],job['period'])
        if check['ohlc_violations']:raise ValueError('OHLC_RELATIONSHIP_VIOLATION')
        if check['null_cells']:raise ValueError('PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED')
        stats['basic_price_check']=check
    return stats

class RepairWorker(OfficialWorker):
    def __init__(self,direction,minutes):
        base.Worker.__init__(self,'RAW',minutes,lease_suffix='_OFFICIAL_REPAIR_'+direction+'_V1',lease_ttl=5400)
        self.direction=direction;self.phase='OFFICIAL_TARGETED_REPAIR'
        self.stagectrl=self.d.folder(self.control,'OFFICIAL_REPAIR_'+direction)
        self.otherctrl=self.d.folder(self.control,'OFFICIAL_REPAIR_'+('ASC' if direction=='DESC' else 'DESC'))
        self.registry=FolderRegistry(self.d,self.d.folder(C1,'05_CONTROL'),namespace='OFFICIAL_REPAIR_'+direction)
        self.cursor=engine.getj(self.d,self.stagectrl,'CURSOR.json') or dict(revision=REVISION,
            direction=direction,month_index=0,upper_month=min(self.today.strftime('%Y-%m'),'2026-12'),sweeps=0)
        if self.cursor.get('revision')!=REVISION:raise ValueError('REPAIR_PLAN_MISMATCH')
        self.months=months_through(self.cursor['upper_month'])
        if direction=='DESC':self.months.reverse()
        self.cache=ArchiveCache();self.checked=0;self.repaired=0;self.source_requests=collections.Counter()
        self.roots={}
        for stage in ('RAW','QA1','PRICE','FINANCIAL','CHIP'):
            folder=self.d.find(self.control,stage);self.roots[stage]=folder['id'] if folder else None

    def flags_for(self,month):
        flags={}
        for stage in ('QA1','PRICE','FINANCIAL','CHIP'):
            root=self.roots[stage]
            folder=self.d.find(root,month) if root else None
            ledger=engine.getj(self.d,folder['id'],'MONTH_STATE.json') if folder else None
            if not ledger:continue
            for entry in list(ledger.get('corrections',{}).values())+list(ledger.get('units',{}).values()):
                if entry.get('status')=='QUARANTINED' or entry.get('correction_status')=='PENDING_EVIDENCE_OR_REPAIR':
                    if entry.get('source') in SOURCES and entry.get('unit_id'):
                        flags.setdefault(entry['unit_id'],[]).append(dict(stage=stage,
                            raw_sha256=entry.get('raw_sha256'),error=entry.get('error'),kind=entry.get('correction_kind')))
        return flags

    def save_journal(self):
        self.journal['updated_utc']=native.stamp()
        self.putj(self.monthctrl,'OFFICIAL_REPAIR_STATE.json',self.journal)

    def repair_one(self,job,bucket,flags):
        key=engine.key(job)
        old=self.state[bucket].get(key,{})
        row=self.journal['units'].setdefault(key,dict(unit_id=key,source=job['source'],attempts=0))
        if not job.get('url'):
            row.update(status='OFFICIAL_ROUTE_REQUIRES_REVIEW',error='Receipt has no proven official request URL');return
        assert_official(job)
        signature=native.sha(json.dumps(dict(sha=old.get('sha256'),status=old.get('status'),flags=flags),sort_keys=True).encode())
        if row.get('input_signature')==signature and row.get('status') in ('BASIC_CONTENT_PASS','BASIC_PASS_FLAG_REQUIRES_REVIEW','UNRESOLVED_AFTER_THREE_ATTEMPTS','OFFICIAL_PERIOD_NOT_PROVIDED'):return
        if row.get('next_retry_at',0)>time.time():return
        if is_before_source_start(job):
            row.update(status='OFFICIAL_PERIOD_NOT_PROVIDED',input_signature=signature);return
        if old.get('evidence_file') and old.get('status') in SAVED:
            try:
                raw,_=cached_payload(self.d,old,self.cache);stats=validate_content(raw,job)
                row.update(status='BASIC_PASS_FLAG_REQUIRES_REVIEW' if flags else 'BASIC_CONTENT_PASS',
                    raw_sha256=old['sha256'],input_signature=signature,validation=stats,
                    numeric_verified=False,pit_verified=False,review_flags=flags,checked_utc=native.stamp())
                self.checked+=1
                if not flags and old['status']=='RAW_DOWNLOADED_UNVERIFIED':
                    self.state[bucket][key]=dict(old,status='SAVED_BASIC_VERIFIED',repair_revision=REVISION,
                        validation_level='BASIC_CONTENT_ONLY_NOT_FULL_CORRECTNESS',numeric_verified=False,pit_verified=False)
                    self.save_state()
                return
            except (ValueError,KeyError,TypeError) as exc:row['validation_error']=str(exc)[:300]
        if row['attempts']>=3:
            row.update(status='UNRESOLVED_AFTER_THREE_ATTEMPTS',input_signature=signature);return
        if self.circuit[job['source']]>=2:
            row.update(status='SOURCE_BACKOFF',next_retry_at=time.time()+900);return
        row.update(status='REPAIR_REQUEST_INTENT',attempts=row['attempts']+1,input_signature=signature)
        self.save_journal()  # Attempt limit survives restarts and both directions.
        raw=None
        try:
            self.source_requests[job['source']]+=1
            raw=native.request(job['url'],job.get('params'));stats=validate_content(raw,job)
            receipt=dict(job,unit_id=key,status='SAVED_BASIC_VERIFIED',rows=stats['rows'],codes_found=stats['codes'],
                sha256=native.sha(raw),repair_revision=REVISION,repair_attempt=row['attempts'],
                supersedes_evidence_file=old.get('evidence_file'),supersedes_sha256=old.get('sha256'),
                numeric_verified=False,pit_verified=False,validation_level='BASIC_CONTENT_ONLY_NOT_FULL_CORRECTNESS')
            base.Worker.record_payload(self,job,raw,receipt,bucket)
            row.update(status='SOURCE_REDOWNLOADED_BASIC_PASS',replacement_sha256=receipt['sha256'],
                       original_sha256=old.get('sha256'),review_flags=flags,next_retry_at=0)
            self.repaired+=1;self.circuit[job['source']]=0
        except Exception as exc:
            transient=base.retryable(exc);self.circuit[job['source']]+=int(transient)
            if raw is not None:
                # Keep failed replacement evidence separately; never replace an old RAW receipt with an error page.
                digest=native.sha(raw);q=self.d.folder(self.monthctrl,'REPAIR_EVIDENCE')
                name=key+'_'+digest+'.raw';self.owned();self.d.put(q,name,raw,'application/octet-stream',overwrite=False)
                row['last_response_sha256']=digest
            delay=900 if transient else 3600
            if isinstance(exc,base.urllib.error.HTTPError) and exc.headers:
                try:delay=max(delay,float(exc.headers.get('Retry-After','0')))
                except ValueError:pass
            row.update(status='UNRESOLVED_AFTER_THREE_ATTEMPTS' if row['attempts']>=3 else 'RETRY_LATER',
                error=type(exc).__name__+':'+str(exc)[:300],next_retry_at=time.time()+delay)
        self.save_journal()

    def capture_month(self,month,quota=None):
        folder=self.d.find(self.roots['RAW'],month) if self.roots['RAW'] else None
        if not folder:return True
        # Shared month ownership was acquired before loading mutable RAW receipts.
        self.restore(month,folder['id'])
        self.journal=engine.getj(self.d,self.monthctrl,'OFFICIAL_REPAIR_STATE.json') or dict(revision=REVISION,month=month,units={})
        flags=self.flags_for(month)
        candidates={}
        for bucket in ('units','financial_units'):
            for key,receipt in self.state[bucket].items():
                matching=[f for f in flags.get(key,[]) if not f.get('raw_sha256') or f['raw_sha256']==receipt.get('sha256')]
                if needs_review(receipt,{key:matching} if matching else {}):candidates[key]=(receipt,bucket,matching)
        visited=engine.getj(self.d,self.monthctrl,'OFFICIAL_FIRSTPASS_RESULT.json') or {}
        if visited.get('queue_visited'):
            planned=native.Audit.jobs(object.__new__(native.Audit),month,set())
            now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
            cutoff=self.today if now.hour>=18 else self.today-dt.timedelta(days=1)
            for job in planned:
                key=engine.key(job)
                if len(job['period'])==10 and job['period']>cutoff.isoformat():continue
                if key not in self.state['units'] and not is_before_source_start(job):candidates[key]=(job,'units',[])
        stop=min(self.until,time.monotonic()+90);before=sum(self.source_requests.values())
        for job,bucket,marked in candidates.values():
            if time.monotonic()>=stop or sum(self.source_requests.values())-before>=12:break
            self.repair_one(job,bucket,marked)
        self.save_journal()
        self.cursor.update(last_month=month,flagged_candidates=len(candidates))
        print('OFFICIAL_REPAIR_MONTH '+json.dumps(dict(month=month,candidates=len(candidates),
            checked=self.checked,repaired=self.repaired,source_requests=dict(self.source_requests))),flush=True)
        return True

    def run(self):
        try:
            while self.cursor['month_index']<len(self.months) and time.monotonic()<self.until:
                month=self.months[self.cursor['month_index']]
                self.cursor.update(status='ACTIVE',active_month=month);self.save_cursor()
                # A download owns its active month first; repair skips busy months and revisits next sweep.
                complete=capture_history_month(self,month)
                self.cursor['month_index']+=1
                self.cursor['last_visited_month']=month
                self.cursor['last_month_busy']=not complete
                self.save_cursor()
            if self.cursor['month_index']>=len(self.months):
                self.cursor.update(month_index=0,sweeps=self.cursor['sweeps']+1,status='SWEEP_ENDED_REVISIT_CHANGED_OR_RETRY_ITEMS')
            report=dict(self.cursor,checked_this_run=self.checked,repaired_this_run=self.repaired,
                source_requests_this_run=dict(self.source_requests),sources=list(SOURCES),finmind_enabled=False,
                numeric_verified=False,pit_verified=False,updated_utc=native.stamp(),run_id=self.owner)
            self.save_cursor();self.putj(self.stagectrl,'STATUS.json',report)
            print('OFFICIAL_REPAIR_STATUS '+json.dumps(report),flush=True)
        finally:commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'OFFICIAL_REPAIR_BATCH_ENDED'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--direction',choices=('ASC','DESC'),required=True)
    p.add_argument('--minutes',type=float,default=40);a=p.parse_args()
    if not 1<=a.minutes<=50:raise ValueError('INVALID_BUDGET')
    base.load_policy()
    try:RepairWorker(a.direction,a.minutes).run()
    except LeaseBusy:print('OFFICIAL_REPAIR_WAIT_EXISTING_OWNER',flush=True)

if __name__=='__main__':main()
