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
from scripts.v093_official_content_audit import audit_rows, value_digest
from scripts.v093_official_firstpass import OfficialWorker, SOURCES, SAVED, months_through, assert_official, is_before_source_start
from scripts.v093_replanned_five_stage import ArchiveCache, cached_payload
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r1 import C1
from scripts.v093_five_stage_durable_gate import commit, LeaseBusy
from scripts.v093_raw_month_coordination import capture_history_month

REVISION='OFFICIAL_TARGETED_REPAIR_20261023_V1'
QUALITY_REVISION='OFFICIAL_ROW_AND_SOURCE_CHECK_V3'
MAX_RETRY_CYCLES=5
RETRY_COOLDOWN_SECONDS=3600
MAX_POINT_ATTEMPTS=3
MAX_POINT_SECONDS=90
PARAMETER_INCIDENT_MONTH='2026-06'
PRIORITY_RETRY_SECONDS=600

def incident_retry_due(journal,now):
    return any(row.get('quality_revision')==QUALITY_REVISION
        and not row.get('terminal') and not row.get('complete')
        and row.get('status') in ('UNRESOLVED_SOURCE_BACKOFF','UNRESOLVED_SOURCE_LIMIT',
            'UNRESOLVED_ATTEMPT_LIMIT','UNRESOLVED_TIME_LIMIT')
        and row.get('next_retry_at',0)<=now
        for row in journal.get('units',{}).values())

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
        return dict(rows=len(found),codes=sorted(found),row_audit=audit_rows(raw,job),validation_level='EXPLICIT_COMPANY_REPORT_PERIOD_AND_ROW_CHECKS')
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
    stats['row_audit']=audit_rows(raw,job)
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
        if self.cursor.get('quality_revision')!=QUALITY_REVISION:
            self.cursor['prior_quality_checkpoint']=dict(self.cursor)
            self.cursor.update(quality_revision=QUALITY_REVISION,status='ACTIVE')
            self.save_cursor()
        self.months=months_through(self.cursor['upper_month'])
        if direction=='DESC':self.months.reverse()
        self.cache=ArchiveCache();self.checked=0;self.repaired=0;self.downloaded=0;self.source_requests=collections.Counter()
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
        key=engine.key(job);old=self.state[bucket].get(key,{})
        signature=native.sha(json.dumps(dict(quality_revision=QUALITY_REVISION,
            sha=old.get('sha256'),flags=flags),sort_keys=True).encode())
        prior=self.journal['units'].get(key,{})
        if prior.get('status') in ('BASIC_CONTENT_PASS','CONTENT_CHECK_PASS') and prior.get('raw_sha256')==old.get('sha256') and not flags:
            return  # Preserve previously checked unchanged RAW; no repeat source request.
        if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature and prior.get('terminal'):
            return
        if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature and prior.get('next_retry_at',0)>time.time():return
        row=prior if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature else dict(
            unit_id=key,source=job['source'],quality_revision=QUALITY_REVISION,input_signature=signature,
            attempts=0,work_seconds=0,prior_result=prior.get('status'))
        if row.get('next_retry_at',0) and row['next_retry_at']<=time.time():
            row=dict(row,attempts=0,work_seconds=0,retry_cycle=row.get('retry_cycle',0)+1)
            row.pop('next_retry_at',None)
        row.update(category=job.get('category'),period=job.get('period'),report_period=job.get('report_period'))
        self.journal['units'][key]=row
        if not job.get('url'):
            row.update(status='UNRESOLVED_OFFICIAL_ROUTE',terminal=True,complete=False);self.save_journal();return
        assert_official(job)
        if is_before_source_start(job):
            row.update(status='OFFICIAL_PERIOD_NOT_PROVIDED',terminal=True,complete=False);self.save_journal();return
        started=time.monotonic()
        deadline=min(self.until,started+max(0,MAX_POINT_SECONDS-row.get('work_seconds',0)))
        local_raw=None;local_stats=None
        try:
            if old.get('evidence_file') and old.get('status') in SAVED:
                try:
                    local_raw,_=cached_payload(self.d,old,self.cache)
                    local_stats=validate_content(local_raw,job)
                    row['local_check']=local_stats;self.checked+=1
                    if not flags and not local_stats.get('row_audit',{}).get('unverified',[]):
                        row.update(status='CONTENT_CHECK_PASS',terminal=True,complete=True,raw_sha256=old['sha256'],
                            checked_utc=native.stamp(),numeric_verified=False,pit_verified=False)
                        self.state[bucket][key]=dict(old,status='SAVED_BASIC_VERIFIED',quality_revision=QUALITY_REVISION,
                            validation_level='ROW_CONTENT_CHECKS_PASSED_SOURCE_RAW_PRESERVED',numeric_verified=False,pit_verified=False)
                        self.save_state()
                        return
                except Exception as exc:row['local_error']=type(exc).__name__+':'+str(exc)[:300]
            # Fresh official requests are restricted to unresolved/invalid content, never an unchanged previous pass.
            while row['attempts']<MAX_POINT_ATTEMPTS and time.monotonic()+20<deadline:
                if self.circuit[job['source']]>=2:
                    row.update(status='UNRESOLVED_SOURCE_BACKOFF',terminal=False,complete=False);break
                row.update(status='SOURCE_CHECK_REQUEST_INTENT',attempts=row['attempts']+1)
                self.save_journal()
                raw=None
                try:
                    native.request_data(job.get('params'))  # Reject local encoding failures before counting sends.
                    self.source_requests[job['source']]+=1
                    raw=native.request(job['url'],job.get('params'))
                    self.downloaded+=1
                    stats=validate_content(raw,job)
                    equal=local_raw is not None and value_digest(local_raw)==value_digest(raw)
                    open_checks=stats.get('row_audit',{}).get('unverified',[])
                    if not equal or local_stats is None:
                        receipt=dict(job,unit_id=key,status='SAVED_BASIC_VERIFIED',rows=stats['rows'],codes_found=stats['codes'],
                            sha256=native.sha(raw),repair_revision=REVISION,quality_revision=QUALITY_REVISION,
                            supersedes_evidence_file=old.get('evidence_file'),supersedes_sha256=old.get('sha256'),
                            numeric_verified=False,pit_verified=False,validation_level='ROW_CHECK_AND_FRESH_OFFICIAL_SOURCE_COMPARISON')
                        base.Worker.record_payload(self,job,raw,receipt,bucket)
                        try:
                            readback,_=cached_payload(self.d,self.state[bucket][key],ArchiveCache())
                            if native.sha(readback)!=native.sha(raw):raise ValueError('REPAIR_READBACK_HASH_MISMATCH')
                            validate_content(readback,job)
                        except Exception:
                            # Preserve a previously valid receipt if remote readback cannot confirm the replacement.
                            if old:self.state[bucket][key]=old
                            else:self.state[bucket].pop(key,None)
                            self.save_state()
                            raise
                        row['saved_evidence_file']=self.state[bucket][key]['evidence_file']
                        row['readback_verified']=True
                        self.repaired+=1
                    row.update(status='OFFICIAL_VALUES_CONFIRMED' if equal else 'REPLACED_WITH_OFFICIAL_RESPONSE',
                        terminal=True,complete=not bool(open_checks or flags),
                        original_sha256=old.get('sha256'),official_sha256=native.sha(raw),
                        official_value_digest=value_digest(raw),values_equal=equal,validation=stats,
                        open_checks=open_checks,review_flags=flags,numeric_verified=False,pit_verified=False,
                        checked_utc=native.stamp())
                    # A source check never silently closes unresolved derived/PIT findings.
                    if open_checks or flags:row['status']='SOURCE_CHECKED_OPEN_QUALITY_ITEMS'
                    self.circuit[job['source']]=0
                    break
                except Exception as exc:
                    transient=base.retryable(exc);self.circuit[job['source']]+=int(transient)
                    if raw is not None:
                        digest=native.sha(raw);q=self.d.folder(self.monthctrl,'REPAIR_EVIDENCE')
                        self.owned();self.d.put(q,key+'_'+digest+'.raw',raw,'application/octet-stream',overwrite=False)
                        row['last_response_sha256']=digest
                    row.update(status='CHECK_FAILED',error=type(exc).__name__+':'+str(exc)[:300],complete=False)
                    # Rate limits are retried after a durable cooldown, with a bounded cycle count.
                    if isinstance(exc,base.urllib.error.HTTPError) and exc.code in (403,429):
                        row.update(status='UNRESOLVED_SOURCE_LIMIT',terminal=False);break
            if not row.get('terminal') and row.get('status') not in ('UNRESOLVED_SOURCE_BACKOFF','UNRESOLVED_SOURCE_LIMIT'):
                row.update(status='UNRESOLVED_ATTEMPT_LIMIT' if row['attempts']>=MAX_POINT_ATTEMPTS else 'UNRESOLVED_TIME_LIMIT',
                           terminal=False,complete=False)
        finally:
            if not row.get('terminal'):
                row['retry_cycle']=row.get('retry_cycle',0)
                if row['retry_cycle']+1>=MAX_RETRY_CYCLES:
                    row.update(status='UNRESOLVED_RETRY_CYCLES_EXHAUSTED',terminal=True,complete=False)
                else:row['next_retry_at']=time.time()+RETRY_COOLDOWN_SECONDS
            row['work_seconds']=row.get('work_seconds',0)+time.monotonic()-started
            row['maximum_attempts']=MAX_POINT_ATTEMPTS;row['maximum_seconds']=MAX_POINT_SECONDS
            self.save_journal()

    def capture_month(self,month,quota=None):
        folder=self.d.find(self.roots['RAW'],month) if self.roots['RAW'] else None
        if not folder:
            if not self.indexed_month(month):return True
            folder={'id':self.monthfolder('RAW',month)}
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
        for job,bucket,marked in candidates.values():
            if time.monotonic()+25>=self.until:
                self.save_journal();self.month_incomplete=True;return False
            self.repair_one(job,bucket,marked)
        self.save_journal()
        self.cursor.update(last_month=month,flagged_candidates=len(candidates))
        print('OFFICIAL_REPAIR_MONTH '+json.dumps(dict(month=month,candidates=len(candidates),
            checked=self.checked,repaired=self.repaired,source_requests=dict(self.source_requests))),flush=True)
        return True

    def revisit_parameter_incident(self):
        if self.direction!='DESC':return
        first_visit=self.cursor.get('parameter_incident_revisited')!=QUALITY_REVISION
        if not first_visit:
            folder=self.d.find(self.roots['RAW'],PARAMETER_INCIDENT_MONTH) if self.roots['RAW'] else None
            journal=engine.getj(self.d,folder['id'],'OFFICIAL_REPAIR_STATE.json') if folder else {}
            if not incident_retry_due(journal or {},time.time()):return
        # Cooldown expiry must revisit this month even after the one-time migration.
        # Reserve most of the run for the normal historical frontier.
        run_deadline=self.until
        budget=min(PRIORITY_RETRY_SECONDS,max(0,(run_deadline-time.monotonic())/3))
        if budget<30:return
        self.month_incomplete=False
        self.until=min(run_deadline,time.monotonic()+budget)
        try:
            revisited=capture_history_month(self,PARAMETER_INCIDENT_MONTH)
        finally:
            self.until=run_deadline
        if revisited and not self.month_incomplete:
            self.cursor['parameter_incident_revisited']=QUALITY_REVISION
            self.save_cursor()
        print('OFFICIAL_REPAIR_PRIORITY_REVISIT '+json.dumps(dict(
            month=PARAMETER_INCIDENT_MONTH,acquired=bool(revisited),
            month_incomplete=self.month_incomplete,budget_seconds=budget)),flush=True)

    def run(self):
        try:
            self.revisit_parameter_incident()
            while self.cursor['month_index']<len(self.months) and time.monotonic()<self.until:
                month=self.months[self.cursor['month_index']]
                self.cursor.update(status='ACTIVE',active_month=month);self.save_cursor()
                # A download owns its active month first; repair skips busy months and revisits next sweep.
                self.month_incomplete=False
                complete=capture_history_month(self,month)
                if self.month_incomplete:break
                self.cursor['month_index']+=1
                self.cursor['last_visited_month']=month
                self.cursor['last_month_busy']=not complete
                self.save_cursor()
            if self.cursor['month_index']>=len(self.months):
                self.cursor.update(month_index=0,sweeps=self.cursor['sweeps']+1,status='SWEEP_ENDED_REVISIT_CHANGED_OR_RETRY_ITEMS')
            report=dict(self.cursor,checked_this_run=self.checked,repaired_this_run=self.repaired,
                source_requests_this_run=dict(self.source_requests),download_responses_this_run=self.downloaded,
                repair_success_definition='VALIDATED_SAVED_AND_REMOTE_READBACK_HASH_CONFIRMED',
                sources=list(SOURCES),finmind_enabled=False,
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
