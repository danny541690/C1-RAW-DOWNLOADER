"""Independent targeted official-only repair; original source archives remain immutable."""
import argparse
import os
import collections
import datetime as dt
import json
import re
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
from scripts.v093_repair_coordination import LANES, lane_months, claim_month, reserve_source, defer_source
from scripts.v093_repair_execution import reparse_financial,pending_month,due_months,REPARSE_REVISION

from scripts.v093_official_problem_catalog import problem_summary, unresolved_items

REVISION='OFFICIAL_TARGETED_REPAIR_20261023_V1'
QUALITY_REVISION='OFFICIAL_LOCAL_REPARSE_AND_SOURCE_CHECK_V4'
MAX_RETRY_CYCLES=5
RETRY_COOLDOWN_SECONDS=3600
MAX_POINT_ATTEMPTS=3
MAX_POINT_SECONDS=90
PARAMETER_INCIDENT_MONTH='2026-06'
PRIORITY_RETRY_SECONDS=600
EXECUTION_REVISION='MISSING_FINANCIAL_PLAN_AND_RAW_REPAIR_V8'
PLAN_REVISION='OFFICIAL_CONTENT_ROUTE_RECONCILIATION_20261027_V4'
BACKFILL_PASS='OFFICIAL_DATABASE_BACKFILL_20261027_V2'
AUX_CHECKPOINT_SECONDS=30
CONTROL_GAP_PLAN='RAW_CONTROL_GAPS_20261024_V1'
CONTROL_GAP_MONTHS=('2014-05','2014-06','2014-07','2014-08')
SOURCE_LIMIT_COOLDOWN_SECONDS=3600
TRANSIENT_COOLDOWN_SECONDS=120
SOURCE_EMPTY_COOLDOWN_SECONDS=86400

def reopen_backfill(prior):
    """One authorized retry pass; preserve evidence and successful units."""
    retryable={'UNRESOLVED_RETRY_CYCLES_EXHAUSTED','UNRESOLVED_ATTEMPT_LIMIT',
               'UNRESOLVED_TIME_LIMIT','SOURCE_NO_DATA_UNCONFIRMED','SOURCE_CONTENT_INCOMPLETE'}
    if prior.get('complete') or prior.get('status') not in retryable or prior.get('backfill_pass')==BACKFILL_PASS:
        return prior
    history=list(prior.get('backfill_history',[]))
    history.append({k:prior.get(k) for k in ('status','attempts','retry_cycle','error','next_retry_at')})
    return dict(prior,terminal=False,complete=False,attempts=0,work_seconds=0,retry_cycle=0,
                cycle_had_request=False,next_retry_at=0,backfill_pass=BACKFILL_PASS,
                backfill_history=history,execution_revision=EXECUTION_REVISION)

def missing_financial_jobs(state,planned):
    """Fill never-planned company/report pairs without resetting existing retries.

    Existing requested pairs retain their own identity and retry history. A saved
    file covers only companies actually found; partial missing companies are
    still an explicit quality finding on that original unit, not a fresh cap.
    """
    claimed={}
    for bucket in ('units','financial_units'):
        for receipt in state.get(bucket,{}).values():
            if receipt.get('source')!='MOPS' or receipt.get('category') not in engine.FIN_REPORTS:continue
            pair=(receipt['category'],receipt.get('report_period'),receipt.get('period'))
            codes=set(receipt.get('codes',[]))
            if receipt.get('evidence_file') and receipt.get('sha256') and receipt.get('status') in SAVED:
                codes.update(receipt.get('codes_found',[]))
            claimed.setdefault(pair,set()).update(codes)
    jobs=[];groups={}
    for job in planned:
        pair=(job['category'],job.get('report_period'),job.get('period'))
        codes=[c for c in job.get('codes',[]) if c not in claimed.get(pair,set())]
        if not codes:continue
        template,remaining=groups.setdefault(pair,(job,[]));remaining.extend(codes)
        claimed.setdefault(pair,set()).update(codes)
    for template,codes in groups.values():
        for start in range(0,len(codes),20):
            chunk=codes[start:start+20]
            params=[(k,v) for k,v in template['params'] if k!='companyId']+ [('companyId',c) for c in chunk]
            jobs.append(dict(template,codes=chunk,params=params))
    return jobs

def incident_retry_due(journal,now):
    return any(row.get('quality_revision')==QUALITY_REVISION
        and not row.get('terminal') and not row.get('complete')
        and row.get('status') in ('UNRESOLVED_SOURCE_BACKOFF','UNRESOLVED_SOURCE_LIMIT',
            'UNRESOLVED_ATTEMPT_LIMIT','UNRESOLVED_TIME_LIMIT',
            'SOURCE_NO_DATA_UNCONFIRMED','SOURCE_CONTENT_INCOMPLETE')
        and row.get('next_retry_at',0)<=now
        for row in journal.get('units',{}).values())

def source_failure(exc,job):
    message=str(exc)
    if message=='OFFICIAL_COMPANY_SELECTOR_REJECTED':
        return dict(status='UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE',terminal=True)
    # Only an explicit official lower-bound response proves historical unavailability.
    match=re.search(r'查詢開始日期小於\s*(\d{2,4})年\s*(\d{1,2})月\s*(\d{1,2})日',message)
    if match:
        year=int(match[1]);year=year+1911 if year<1911 else year
        try:earliest=dt.date(year,int(match[2]),int(match[3])).isoformat()
        except ValueError:earliest=None
        if earliest and job['period']<earliest:
            return dict(status='OFFICIAL_PERIOD_NOT_PROVIDED',terminal=True,source_start=earliest)
    if isinstance(exc,base.urllib.error.HTTPError) and exc.code==404:
        return dict(status='OFFICIAL_ROUTE_NOT_FOUND',terminal=True)
    if any(text in message for text in ('EMPTY_RESPONSE','EMPTY_EVENT','沒有符合條件','查無資料')):
        return dict(status='SOURCE_NO_DATA_UNCONFIRMED',terminal=False)
    if message=='FINANCIAL_REQUESTED_COMPANIES_OR_PERIOD_INCOMPLETE':
        return dict(status='SOURCE_CONTENT_INCOMPLETE',terminal=False)
    return None

def needs_review(receipt,flagged):
    if receipt.get('source') not in SOURCES:return False
    if receipt.get('status')=='OFFICIAL_PERIOD_NOT_PROVIDED':return False
    return receipt.get('status')!='SAVED_BASIC_VERIFIED' or receipt.get('unit_id') in flagged

def validate_content(raw,job):
    if job['category'] in engine.FIN_REPORTS:
        if '至少需要輸入一個正確的股號或股名' in raw.decode('utf-8-sig',errors='replace'):
            raise ValueError('OFFICIAL_COMPANY_SELECTOR_REJECTED')
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
        stats['basic_price_check']=check
    stats['row_audit']=audit_rows(raw,job)
    if stats.get('basic_price_check',{}).get('null_cells'):
        stats['row_audit']['unverified']=sorted(set(stats['row_audit'].get('unverified',[]))|{'PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED'})
    return stats

class RepairWorker(OfficialWorker):
    def note_activity(self,kind,key,digest):
        if not hasattr(self,'activity'):self.activity={}
        self.activity.setdefault(kind,set()).add((key,digest))

    def activity_summary(self):
        return dict(execution_revision=EXECUTION_REVISION,**{
            name:len(getattr(self,'activity',{}).get(name,set())) for name in (
                'unchanged_raw_checked_this_run','prior_verified_skipped_this_run',
                'local_reparse_readback_this_run','local_quality_open_this_run')})

    def __init__(self,direction,minutes,lane=None):
        self.finmind_enabled=os.environ.get("FINMIND_GAPFILL_ENABLED")=="1"
        self.backfill_enabled=os.environ.get("OFFICIAL_BACKFILL_PASS")==BACKFILL_PASS
        self.lane=lane
        if lane is not None:direction=LANES[lane][2]
        control_name=lane or direction
        base.Worker.__init__(self,'RAW',minutes,lease_suffix='_OFFICIAL_REPAIR_'+control_name+'_V1',lease_ttl=5400)
        self.direction=direction;self.phase='OFFICIAL_TARGETED_REPAIR'
        self.stagectrl=self.d.folder(self.control,'OFFICIAL_REPAIR_'+control_name)
        self.otherctrl=self.d.folder(self.control,'OFFICIAL_REPAIR_'+('ASC' if direction=='DESC' else 'DESC'))
        self.registry=FolderRegistry(self.d,self.d.folder(C1,'05_CONTROL'),namespace='OFFICIAL_REPAIR_'+control_name)
        self.cursor=engine.getj(self.d,self.stagectrl,'CURSOR.json') or dict(revision=REVISION,
            direction=direction,month_index=0,upper_month=min(self.today.strftime('%Y-%m'),'2026-12'),sweeps=0)
        if self.cursor.get('revision')!=REVISION:raise ValueError('REPAIR_PLAN_MISMATCH')
        if self.cursor.get('quality_revision')!=QUALITY_REVISION:
            self.cursor['prior_quality_checkpoint']=dict(self.cursor)
            self.cursor.update(quality_revision=QUALITY_REVISION,status='ACTIVE')
            self.save_cursor()
        self.months=months_through(self.cursor['upper_month'])
        if direction=='DESC':self.months.reverse()
        if lane is not None:self.months=lane_months(lane)
        self.cache=ArchiveCache();self.checked=0;self.repaired=0;self.downloaded=0;self.source_requests=collections.Counter()
        self.pending_index=engine.getj(self.d,self.stagectrl,'RETRY_MONTHS.json') or {}
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
        for key,items in flags.items():
            flags[key]=list({json.dumps(item,sort_keys=True):item for item in items}.values())
        return flags

    def flush_auxiliary(self,force=False):
        """Keep results durable per unit; coalesce only derived ledgers/indexes."""
        now=time.monotonic()
        month=self.journal.get('month')
        due=(force or month!=getattr(self,'_aux_month',None)
             or now-getattr(self,'_aux_saved_at',float('-inf'))>=AUX_CHECKPOINT_SECONDS)
        if not due:return
        if getattr(self,'_local_state_dirty',False):
            self.save_state()
            self._local_state_dirty=False
        if hasattr(self,'pending_index'):
            self.putj(self.stagectrl,'RETRY_MONTHS.json',self.pending_index)
        self._aux_month=month;self._aux_saved_at=now

    def save_journal(self):
        self.journal['problem_summary']=problem_summary(self.journal)
        snapshot={k:v for k,v in self.journal.items() if k!='updated_utc'}
        fingerprint=(self.monthctrl,native.sha(json.dumps(snapshot,sort_keys=True).encode()))
        if fingerprint!=getattr(self,'_journal_saved',None):
            self.journal['updated_utc']=native.stamp()
            # Every changed send intent/result is readback-verified immediately.
            self.putj(self.monthctrl,'OFFICIAL_REPAIR_STATE.json',self.journal)
            self._journal_saved=fingerprint
        if hasattr(self,'pending_index'):
            month=self.journal['month'];prior=self.pending_index.get(month,{})
            self.pending_index[month]=pending_month(self.journal)
            if self.journal.get('finmind_pending',0):
                self.pending_index[month].update(finmind_gapfill_required=True,next_retry_at=time.time()+60)
            for marker in ('inventory_required','plan_reconciliation_required'):
                if prior.get(marker):self.pending_index[month].update({marker:True,'next_retry_at':0})
        self.flush_auxiliary()
        if time.monotonic()-getattr(self,'_last_progress',0)>=60:
            report=dict(self.cursor,run_id=self.owner,updated_utc=native.stamp(),
                current_work_month=self.journal.get('month'),batch_complete=False,
                finmind_enabled=getattr(self,'finmind_enabled',False),finmind_metrics=getattr(self,'finmind_metrics',{}),
                checked_this_run=self.checked,repaired_this_run=self.repaired,
                source_requests_this_run=dict(self.source_requests),download_responses_this_run=self.downloaded,
                month_result_counts=dict(collections.Counter(row.get('status','UNKNOWN')
                    for row in self.journal.get('units',{}).values())),
                problem_summary=self.journal.get('problem_summary',{}),
                quality_revision=QUALITY_REVISION,numeric_verified=False,pit_verified=False,
                repair_success_definition='VALIDATED_SAVED_AND_REMOTE_READBACK_HASH_CONFIRMED',**self.activity_summary())
            self.putj(self.stagectrl,'STATUS.json',report)
            print('OFFICIAL_REPAIR_PROGRESS '+json.dumps(report),flush=True)
            self._last_progress=time.monotonic()

    def repair_one(self,job,bucket,flags):
        key=engine.key(job);old=self.state[bucket].get(key,{})
        signature=native.sha(json.dumps(dict(quality_revision=QUALITY_REVISION,
            sha=old.get('sha256'),flags=flags),sort_keys=True).encode())
        prior=self.journal['units'].get(key,{})
        if getattr(self,'backfill_enabled',False):
            known=source_failure(ValueError(prior.get('error','')),job)
            if not known or known.get('status')!='OFFICIAL_PERIOD_NOT_PROVIDED':
                prior=reopen_backfill(prior)
        recovery_status=None
        prior_content_pass=prior.get('status') in ('BASIC_CONTENT_PASS','CONTENT_CHECK_PASS')
        retained=bool(old.get('evidence_file') and old.get('sha256') and old.get('status') in SAVED)
        if prior.get('status') in ('BASIC_CONTENT_PASS','CONTENT_CHECK_PASS') and not retained:
            prior=dict(prior,terminal=False,complete=False,next_retry_at=0,attempts=0,work_seconds=0,
                prior_pass_reopened_reason='RAW_RECEIPT_MISSING_OR_INVALID')
        if retained and prior.get('content_audit_revision')=='ROW_AUDIT_V5' and prior.get('status') in ('BASIC_CONTENT_PASS','CONTENT_CHECK_PASS') and prior.get('raw_sha256')==old.get('sha256') and not flags:
            self.note_activity('prior_verified_skipped_this_run',key,old.get('sha256'))
            return  # Preserve previously checked unchanged RAW; no repeat source request.
        # Revisit retained failures once offline. Do not reset source caps,
        # redownload successful RAW, or repeat an already completed local audit.
        if (old.get('evidence_file') and not prior.get('complete')
                and (prior.get('terminal') or prior.get('local_error'))
                and prior.get('status')!='LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS'
                and prior.get('execution_revision')!=EXECUTION_REVISION
                and prior.get('local_recovery_revision')!=EXECUTION_REVISION):
            recovery_status=prior.get('status','UNRESOLVED_RETRY_CYCLES_EXHAUSTED')
            prior=dict(prior,terminal=False,next_retry_at=0,local_recovery_revision=EXECUTION_REVISION)
        elif prior.get('status')=='UNRESOLVED_OFFICIAL_ROUTE' and job.get('url'):
            prior=dict(prior,terminal=False,next_retry_at=0)
        if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature:
            known=source_failure(ValueError(prior.get('error','')),job)
            if known and known['status']=='OFFICIAL_PERIOD_NOT_PROVIDED':
                prior.update(known,complete=False)
                self.save_journal()
                return
        if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature and prior.get('terminal') and (prior.get('status') not in ('BASIC_CONTENT_PASS','CONTENT_CHECK_PASS') or prior.get('content_audit_revision')=='ROW_AUDIT_V5'):
            return
        if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature and prior.get('next_retry_at',0)>time.time():return
        row=prior if prior.get('quality_revision')==QUALITY_REVISION and prior.get('input_signature')==signature else dict(
            unit_id=key,source=job['source'],quality_revision=QUALITY_REVISION,input_signature=signature,
            attempts=0,work_seconds=0,prior_result=prior.get('status'))
        if retained and prior_content_pass:
            for counter in ('attempts','retry_cycle','work_seconds'):
                if counter in prior:row[counter]=prior[counter]
        if row.get('next_retry_at',0) and row['next_retry_at']<=time.time() and not (retained and prior_content_pass):
            row=dict(row,attempts=0,work_seconds=0,cycle_had_request=False,retry_cycle=row.get('retry_cycle',0)+int(row.get('cycle_had_request',False)))
            row.pop('next_retry_at',None)
        row.update(category=job.get('category'),period=job.get('period'),report_period=job.get('report_period'),execution_revision=EXECUTION_REVISION)
        self.journal['units'][key]=row
        if job['source'] not in SOURCES:raise ValueError('NON_OFFICIAL_SOURCE_FORBIDDEN')
        started=time.monotonic()
        requests_before=sum(self.source_requests.values())
        deadline=min(self.until,started+max(0,MAX_POINT_SECONDS-row.get('work_seconds',0)))
        local_raw=None;local_stats=None
        try:
            if old.get('evidence_file') and old.get('status') in SAVED:
                try:
                    local_raw,_=cached_payload(self.d,old,self.cache)
                    local_stats=validate_content(local_raw,job)
                    row.pop('error',None)
                    if row.get('local_error'):row['previous_local_error']=row.pop('local_error')
                    row['local_check']=local_stats;row['content_audit_revision']='ROW_AUDIT_V5';self.checked+=1
                    if flags or local_stats.get('row_audit',{}).get('unverified',[]):
                        if job['category'] in engine.FIN_REPORTS and (row.get('reparse_receipt',{}).get('parser_revision')!=REPARSE_REVISION or row.get('reparse_receipt',{}).get('raw_sha256')!=old['sha256']):
                            try:
                                target=self.d.folder(self.monthctrl,'REPARSE_STAGING')
                                row['reparse_receipt']=reparse_financial(local_raw,dict(job,unit_id=key),old['sha256'],self.owned,
                                    lambda name,data:self.d.put(target,name,data,'application/octet-stream',overwrite=False),
                                    lambda name:self.d.read(target,name))
                                self.note_activity('local_reparse_readback_this_run',key,old['sha256'])
                            except Exception as exc:
                                row.update(status='LOCAL_REPARSE_FAILED',terminal=True,complete=False,
                                    error=type(exc).__name__+':'+str(exc)[:300],next_action='FIX_PARSER_KEEP_RAW')
                                return
                        # Derived/parser/PIT flags are not evidence that source bytes are bad.
                        # Preserve RAW and route the unresolved quality finding to reparse.
                        row.update(status='LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS',terminal=True,
                            complete=False,raw_sha256=old['sha256'],review_flags=flags,
                            open_checks=local_stats.get('row_audit',{}).get('unverified',[]),
                            next_action='VERIFY_ACCOUNTING_UNITS_AND_PIT' if row.get('reparse_receipt') else 'REPARSE_EXISTING_RAW',source_rechecked=False,
                            numeric_verified=False,pit_verified=False)
                        self.note_activity('local_quality_open_this_run',key,old['sha256'])
                        return
                    if not flags and not local_stats.get('row_audit',{}).get('unverified',[]):
                        row.update(status='CONTENT_CHECK_PASS',terminal=True,complete=True,raw_sha256=old['sha256'],
                            checked_utc=native.stamp(),numeric_verified=False,pit_verified=False)
                        self.state[bucket][key]=dict(old,status='SAVED_BASIC_VERIFIED',quality_revision=QUALITY_REVISION,
                            validation_level='ROW_CONTENT_CHECKS_PASSED_SOURCE_RAW_PRESERVED',numeric_verified=False,pit_verified=False)
                        self._local_state_dirty=True
                        self.note_activity('unchanged_raw_checked_this_run',key,old['sha256'])
                        return
                except Exception as exc:row['local_error']=type(exc).__name__+':'+str(exc)[:300]
                if prior_content_pass:
                    row.update(status='LOCAL_REVALIDATION_FAILED_KEEP_RAW',terminal=True,complete=False,
                        next_action='REVIEW_LOCAL_AUDIT_KEEP_PRIOR_RAW_NO_REDOWNLOAD',numeric_verified=False,pit_verified=False)
                    return
            if recovery_status:
                row.update(status=recovery_status,terminal=True,complete=False,
                    next_action='REVIEW_RETAINED_RAW_AND_SOURCE_SCOPE_NO_CAP_RESET')
                return
            if not job.get('url'):
                row.update(status='UNRESOLVED_OFFICIAL_ROUTE',terminal=True,complete=False);return
            # Do not repeatedly send pre-2013 financial statements to the post-IFRS
            # comparison route. This is a routing hold, never evidence of no data.
            # Retained RAW was checked above and remains available for local QA.
            if (job.get('source')=='MOPS' and job.get('category') in engine.FIN_REPORTS
                    and job.get('url')=='https://mopsfin.twse.com.tw/compare/report'
                    and re.fullmatch(r'20(?:0[0-9]|1[0-2])-.*',job.get('period',''))):
                row.update(status='UNRESOLVED_HISTORICAL_COMPARE_SCOPE',terminal=True,complete=False,
                    route_reference='https://mopsfin.twse.com.tw/terms',
                    next_action='VERIFY_LEGACY_ENDPOINT_OR_DOCUMENTED_ADOPTION',
                    numeric_verified=False,pit_verified=False)
                return
            assert_official(job)
            if is_before_source_start(job):
                row.update(status='OFFICIAL_PERIOD_NOT_PROVIDED',terminal=True,complete=False);return
            # Fresh official requests are restricted to unresolved/invalid content, never an unchanged previous pass.
            while row['attempts']<MAX_POINT_ATTEMPTS and time.monotonic()+20<deadline:
                if getattr(self,'_source_cooldowns',{}).get(job['source'],0)>time.time():
                    row.update(status='UNRESOLVED_SOURCE_BACKOFF',terminal=False,complete=False,
                        next_retry_at=self._source_cooldowns[job['source']]);break
                if self.circuit[job['source']]>=2:
                    row.update(status='UNRESOLVED_SOURCE_BACKOFF',terminal=False,complete=False);break
                row.update(status='SOURCE_CHECK_REQUEST_INTENT')
                self.save_journal()
                raw=None
                try:
                    try:native.request_data(job.get('params'))
                    except ValueError as exc:
                        row.update(status='LOCAL_PARAM_ENCODING_ERROR',terminal=True,complete=False,error=str(exc))
                        break
                    if getattr(self,'lane',None) and not reserve_source(self.api,self.token,job['source']):
                        row.update(status='WAIT_SHARED_SOURCE_WINDOW',terminal=False,complete=False,next_retry_at=time.time()+3)
                        break
                    row['attempts']+=1
                    self.save_journal()  # Persist the send intent before the transport call.
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
                    row.pop('error',None)
                    row.update(status='OFFICIAL_VALUES_CONFIRMED' if equal else 'REPLACED_WITH_OFFICIAL_RESPONSE',
                        terminal=True,complete=not bool(open_checks or flags),
                        original_sha256=old.get('sha256'),official_sha256=native.sha(raw),
                        official_value_digest=value_digest(raw),values_equal=equal,validation=stats,
                        open_checks=open_checks,review_flags=flags,numeric_verified=False,pit_verified=False,
                        checked_utc=native.stamp())
                    # A source check never silently closes unresolved derived/PIT findings.
                    if open_checks or flags:row['status']='SOURCE_CHECKED_OPEN_QUALITY_ITEMS'
                    if job.get('category') in engine.FIN_REPORTS:
                        # New RAW must reach the parser now; a terminal source result
                        # must not strand it until a future full scan.
                        try:
                            target=self.d.folder(self.monthctrl,'REPARSE_STAGING')
                            row['reparse_receipt']=reparse_financial(raw,dict(job,unit_id=key),native.sha(raw),self.owned,
                                lambda name,data:self.d.put(target,name,data,'application/octet-stream',overwrite=False),
                                lambda name:self.d.read(target,name))
                            self.note_activity('local_reparse_readback_this_run',key,native.sha(raw))
                            row['next_action']='VERIFY_ACCOUNTING_UNITS_AND_PIT'
                        except Exception as exc:
                            # Valid saved RAW stays retained; parser errors are not
                            # a reason to redownload identical official bytes.
                            row.update(status='LOCAL_REPARSE_FAILED',complete=False,
                                error=type(exc).__name__+':'+str(exc)[:300],next_action='FIX_PARSER_KEEP_RAW')
                    self.circuit[job['source']]=0
                    break
                except Exception as exc:
                    transient=base.retryable(exc);self.circuit[job['source']]+=int(transient)
                    if raw is not None:
                        digest=native.sha(raw);q=self.d.folder(self.monthctrl,'REPAIR_EVIDENCE')
                        self.owned();self.d.put(q,key+'_'+digest+'.raw',raw,'application/octet-stream',overwrite=False)
                        row['last_response_sha256']=digest
                        row['last_response_evidence_file']=str(q)+'/'+key+'_'+digest+'.raw'
                    row.update(status='CHECK_FAILED',error=type(exc).__name__+':'+str(exc)[:300],complete=False)
                    limited=isinstance(exc,base.urllib.error.HTTPError) and exc.code in (403,429)
                    if limited or transient:
                        seconds=SOURCE_LIMIT_COOLDOWN_SECONDS if limited else TRANSIENT_COOLDOWN_SECONDS
                        pause_until=time.time()+seconds
                        if getattr(self,'lane',None):pause_until=defer_source(self.api,self.token,job['source'],seconds)
                        if not hasattr(self,'_source_cooldowns'):self._source_cooldowns={}
                        self._source_cooldowns[job['source']]=pause_until
                        row['next_retry_at']=pause_until
                    disposition=source_failure(exc,job)
                    if disposition:
                        row.update(disposition)
                        if row['status']=='SOURCE_NO_DATA_UNCONFIRMED':row['next_retry_at']=time.time()+SOURCE_EMPTY_COOLDOWN_SECONDS
                        break
                    # Rate limits are retried after a durable cooldown, with a bounded cycle count.
                    if isinstance(exc,base.urllib.error.HTTPError) and exc.code in (403,429):
                        row.update(status='UNRESOLVED_SOURCE_LIMIT',terminal=False);break
            if not row.get('terminal') and row.get('status') not in ('WAIT_SHARED_SOURCE_WINDOW','UNRESOLVED_SOURCE_BACKOFF','UNRESOLVED_SOURCE_LIMIT',
                    'SOURCE_NO_DATA_UNCONFIRMED','SOURCE_CONTENT_INCOMPLETE'):
                row.update(status='UNRESOLVED_ATTEMPT_LIMIT' if row['attempts']>=MAX_POINT_ATTEMPTS else 'UNRESOLVED_TIME_LIMIT',
                           terminal=False,complete=False)
        finally:
            if not row.get('terminal'):
                row['retry_cycle']=row.get('retry_cycle',0)
                if sum(self.source_requests.values())>requests_before and row['retry_cycle']+1>=MAX_RETRY_CYCLES:
                    row.update(status='UNRESOLVED_RETRY_CYCLES_EXHAUSTED',terminal=True,complete=False)
                else:row.setdefault('next_retry_at',time.time()+RETRY_COOLDOWN_SECONDS)
            row['cycle_had_request']=row.get('cycle_had_request',False) or sum(self.source_requests.values())>requests_before
            row['work_seconds']=row.get('work_seconds',0)+time.monotonic()-started
            row['maximum_attempts']=MAX_POINT_ATTEMPTS;row['maximum_seconds']=MAX_POINT_SECONDS
            self.save_journal()

    def publish_unresolved(self):
        report=dict(month=self.journal['month'],run_id=self.owner,execution_revision=EXECUTION_REVISION,
            updated_utc=native.stamp(),summary=problem_summary(self.journal),units=unresolved_items(self.journal),
            complete=False,numeric_verified=False,pit_verified=False)
        self.putj(self.monthctrl,'OFFICIAL_UNRESOLVED_ITEMS.json',report)

    def capture_month(self,month,quota=None):
        try:return self.capture_month_units(month,quota)
        finally:
            if getattr(self,'journal',{}).get('month')==month:
                self.flush_auxiliary(force=True)
                self.publish_unresolved()

    def capture_month_units(self,month,quota=None):
        folder=self.d.find(self.roots['RAW'],month) if self.roots['RAW'] else None
        if not folder:
            if not self.indexed_month(month) and not getattr(self,'lane',None):return True
            folder={'id':self.monthfolder('RAW',month)}
        # Shared month ownership was acquired before loading mutable RAW receipts.
        self.restore(month,folder['id'])
        self.journal=engine.getj(self.d,self.monthctrl,'OFFICIAL_REPAIR_STATE.json') or dict(revision=REVISION,month=month,units={})
        if getattr(self,'_control_gap_inventory',False):
            if not self.inventory_existing(SOURCES):
                self.month_incomplete=True;return False
        flags=self.flags_for(month)
        planned=native.Audit.jobs(object.__new__(native.Audit),month,set())
        financial=[];added=[]
        if month.endswith(('-03','-06','-09','-12')):
            recorded=self.journal.setdefault('financial_plan_jobs',{})
            reserved=dict(self.state,financial_units=dict(recorded,**self.state['financial_units']))
            added=missing_financial_jobs(reserved,self.financial_jobs())
            for job in added:recorded[engine.key(job)]=job
            financial=list(recorded.values())
        self.journal['missing_financial_plan']=dict(revision=PLAN_REVISION,new_units=len(added),planned_units=len(financial),
            official_universe_count=getattr(self,'official_financial_universe_count',0),
            historical_universe_verified=False)
        requests_by_key={engine.key(job):job for job in planned}
        candidates={}
        for bucket in ('units','financial_units'):
            for key,receipt in self.state[bucket].items():
                matching=[f for f in flags.get(key,[]) if not f.get('raw_sha256') or f['raw_sha256']==receipt.get('sha256')]
                if needs_review(receipt,{key:matching} if matching else {}) or (getattr(self,'lane',None) and receipt.get('source') in SOURCES):
                    job=dict(receipt)
                    if not job.get('url') and key in requests_by_key:
                        for field in ('url','params'):
                            if field in requests_by_key[key]:job[field]=requests_by_key[key][field]
                    candidates[key]=(job,bucket,matching)
        visited=engine.getj(self.d,self.monthctrl,'OFFICIAL_FIRSTPASS_RESULT.json') or {}
        if visited.get('queue_visited') or getattr(self,'lane',None):
            now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
            cutoff=self.today if now.hour>=18 else self.today-dt.timedelta(days=1)
            for job in planned+financial:
                key=engine.key(job)
                bucket='financial_units' if job.get('category') in engine.FIN_REPORTS else 'units'
                if len(job['period'])==10 and job['period']>cutoff.isoformat():continue
                if key not in self.state[bucket] and not is_before_source_start(job):candidates[key]=(job,bucket,[])
        if getattr(self,'finmind_enabled',False):
            from scripts.v093_official_finmind_gapfill import supplement
            supplement(self,[item[0] for item in candidates.values()]+planned+financial)
        # Retained financial RAW can be reparsed without a source request; do
        # not bury that work behind hundreds of missing-route/network items.
        ordered=sorted(candidates.values(),key=lambda item:(
            not (item[0].get('category') in engine.FIN_REPORTS and item[0].get('evidence_file')),
            not bool(item[0].get('evidence_file'))))
        for job,bucket,marked in ordered:
            if getattr(self,'_due_only',False):
                row=self.journal['units'].get(engine.key(job),{})
                if not row or row.get('terminal') or row.get('complete') or row.get('next_retry_at',0)>time.time():continue
            if time.monotonic()+25>=self.until:
                self.save_journal();self.month_incomplete=True;return False
            self.repair_one(job,bucket,marked)
            if (getattr(self,'finmind_enabled',False) and time.monotonic()-getattr(self,'_finmind_poll_at',0)>=45
                    and getattr(self,'finmind_metrics',{}).get('requests',0)<40):
                from scripts.v093_official_finmind_gapfill import supplement
                supplement(self,[item[0] for item in candidates.values()]+planned+financial)
        self.save_journal()
        self.cursor.update(last_month=month,flagged_candidates=len(candidates))
        print('OFFICIAL_REPAIR_MONTH '+json.dumps(dict(month=month,candidates=len(candidates),
            checked=self.checked,repaired=self.repaired,source_requests=dict(self.source_requests))),flush=True)
        return True

    def revisit_parameter_incident(self):
        if getattr(self,'lane',None) not in (None,'RECENT_DESC') or self.direction!='DESC':return
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

    def seed_control_gaps(self):
        # Metadata proved four absent controls, not absent RAW. Route these
        # months through normal restore/import before any missing-unit request.
        if getattr(self,'lane',None)!='RECENT_ASC':return
        if self.cursor.get('control_gap_plan')==CONTROL_GAP_PLAN:return
        for month in CONTROL_GAP_MONTHS:
            entry=self.pending_index.setdefault(month,{})
            entry.update(inventory_required=True,next_retry_at=0,
                         reason='MISSING_CONTROL_DIRECTORY_RAW_EXISTENCE_NOT_YET_PROVEN')
        self.putj(self.stagectrl,'RETRY_MONTHS.json',self.pending_index)
        self.cursor['control_gap_plan']=CONTROL_GAP_PLAN
        self.save_cursor()

    def seed_plan_reconciliation(self):
        if self.cursor.get('missing_unit_plan')==PLAN_REVISION:return
        # Revisit only this lane's already visited months; retain the frontier.
        for month in self.months[:self.cursor.get('month_index',0)]:
            entry=self.pending_index.setdefault(month,{})
            entry.update(plan_reconciliation_required=True,next_retry_at=0)
        self.putj(self.stagectrl,'RETRY_MONTHS.json',self.pending_index)
        self.cursor['missing_unit_plan']=PLAN_REVISION
        self.save_cursor()

    def run_due_work(self):
        # A bounded fair queue protects forward progress from stale old retries.
        original=self.until;budget=min(180,max(0,(original-time.monotonic())/6))
        if budget<30:return
        months=due_months(getattr(self,'pending_index',{}))
        last=self.cursor.get('last_due_month')
        if last in months:
            i=months.index(last)+1;months=months[i:]+months[:i]
        months.sort(key=lambda m:not self.pending_index[m].get('inventory_required',False))
        self.until=min(original,time.monotonic()+budget)
        try:
            for month in months:
                if time.monotonic()+30>=self.until:break
                self.cursor['last_due_month']=month;self.save_cursor()
                full_inventory=self.pending_index[month].get('inventory_required',False)
                reconcile=self.pending_index[month].get('plan_reconciliation_required',False) or self.pending_index[month].get('finmind_gapfill_required',False)
                self._due_only=not (full_inventory or reconcile);self._control_gap_inventory=full_inventory;self.month_incomplete=False
                acquired=capture_history_month(self,month)
                if acquired and not self.month_incomplete:
                    if (full_inventory or reconcile) and getattr(self,'journal',{}).get('month')==month:
                        self.pending_index[month]=pending_month(self.journal)
                        if self.journal.get('finmind_pending',0):self.pending_index[month].update(finmind_gapfill_required=True,next_retry_at=time.time()+60)
                    else:
                        for marker in ('inventory_required','plan_reconciliation_required'):
                            self.pending_index.get(month,{}).pop(marker,None)
                    self.putj(self.stagectrl,'RETRY_MONTHS.json',self.pending_index)
        finally:self.until=original;self._due_only=False;self._control_gap_inventory=False

    def run(self):
        try:
            if getattr(self,'lane',None):
                self.seed_control_gaps()
                self.seed_plan_reconciliation()
                self.run_due_work()
            self.revisit_parameter_incident()
            while self.cursor['month_index']<len(self.months) and time.monotonic()<self.until:
                month=self.months[self.cursor['month_index']]
                if getattr(self,'lane',None):
                    allowed,meeting=claim_month(self.api,self.token,self.lane,month)
                    if not allowed:
                        self.cursor.update(meeting);self.save_cursor();break
                self.cursor.update(status='ACTIVE',active_month=month);self.save_cursor()
                # A download owns its active month first; repair skips busy months and revisits next sweep.
                self.month_incomplete=False
                complete=capture_history_month(self,month)
                if self.month_incomplete or (getattr(self,'lane',None) and not complete):break
                self.cursor['month_index']+=1
                self.cursor['last_visited_month']=month
                self.cursor['last_month_busy']=not complete
                self.save_cursor()
            if getattr(self,'lane',None) and self.cursor['month_index']>=len(self.months):
                self.cursor.update(status='RANGE_VISITED_NOT_QUALITY_CERTIFIED')
            elif self.cursor['month_index']>=len(self.months):
                self.cursor.update(month_index=0,sweeps=self.cursor['sweeps']+1,status='SWEEP_ENDED_REVISIT_CHANGED_OR_RETRY_ITEMS')
            report=dict(self.cursor,checked_this_run=self.checked,repaired_this_run=self.repaired,
                source_requests_this_run=dict(self.source_requests),download_responses_this_run=self.downloaded,
                repair_success_definition='VALIDATED_SAVED_AND_REMOTE_READBACK_HASH_CONFIRMED',
                sources=list(SOURCES),finmind_enabled=getattr(self,'finmind_enabled',False),finmind_metrics=getattr(self,'finmind_metrics',{}),
                numeric_verified=False,pit_verified=False,updated_utc=native.stamp(),run_id=self.owner,**self.activity_summary())
            self.save_cursor();self.putj(self.stagectrl,'STATUS.json',report)
            print('OFFICIAL_REPAIR_STATUS '+json.dumps(report),flush=True)
        finally:commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'OFFICIAL_REPAIR_BATCH_ENDED'))

def main():
    p=argparse.ArgumentParser();p.add_argument('--direction',choices=('ASC','DESC'),default='DESC')
    p.add_argument('--lane',choices=tuple(LANES))
    p.add_argument('--minutes',type=float,default=40);a=p.parse_args()
    if not 1<=a.minutes<=50:raise ValueError('INVALID_BUDGET')
    base.load_policy()
    try:RepairWorker(a.direction,a.minutes,lane=a.lane).run()
    except LeaseBusy:print('OFFICIAL_REPAIR_WAIT_EXISTING_OWNER',flush=True)

if __name__=='__main__':main()

