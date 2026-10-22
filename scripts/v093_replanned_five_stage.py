"""User-authorized split: RAW resumes 2014-04; audit reads 2026-10..2000-01.

No change to immutable source policy. QA owns a separate native RAW index, so
existing historical bytes do not have to pass through the RAW download cursor.
"""
import argparse, collections, copy, datetime as dt, io, json, os, time, zipfile
from pathlib import Path
from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_five_stage_durable_gate import commit,_read
from scripts.v093_raw_month_coordination import capture_history_month

PLAN=json.loads((Path(__file__).resolve().parents[1]/'config/v093_execution_plan_20261021.json').read_text())
REVISION=PLAN['revision']
AUDIT_MONTHS=base.MONTHS
RAW_MONTHS=[m for m in AUDIT_MONTHS if m<=PLAN['raw_history_start']]
LEGACY_MONTHS=[m for m in AUDIT_MONTHS if m<=PLAN['legacy_checkpoint_start']]
assert RAW_MONTHS[0]=='2014-04' and RAW_MONTHS[-1]=='2000-01' and len(RAW_MONTHS)==172

def lease_suffix_for(stage):
    return PLAN.get('stage_lease_suffix',{}).get(stage,PLAN['lease_suffix'])

def lease_ttl_for(minutes):
    # 60-minute consumers have a 75-minute Actions timeout and 90-minute lease.
    return max(3600,int((minutes+30)*60))

class ArchiveCache:
    def __init__(self,limit=64_000_000):self.limit=limit;self.size=0;self.entries=collections.OrderedDict()
    def read(self,d,fid):
        if fid in self.entries:
            raw=self.entries.pop(fid);self.entries[fid]=raw;return raw
        raw=native.read(d,{'id':fid})
        if len(raw)<=self.limit:
            while self.entries and self.size+len(raw)>self.limit:
                _,old=self.entries.popitem(last=False);self.size-=len(old)
            self.entries[fid]=raw;self.size+=len(raw)
        return raw

def cached_payload(d,receipt,cache):
    fid,sep,member=receipt['evidence_file'].partition('/')
    archive=cache.read(d,fid);archive_sha=native.sha(archive)
    if receipt.get('archive_sha256') and receipt['archive_sha256']!=archive_sha:raise ValueError('ARCHIVE_READBACK_HASH_MISMATCH')
    raw=archive
    if sep:
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            if z.getinfo(member).file_size>30_000_000:raise ValueError('MEMBER_SIZE_LIMIT')
            raw=z.read(member)
    if native.sha(raw)!=receipt['sha256']:raise ValueError('RAW_READBACK_HASH_MISMATCH')
    return raw,archive_sha

def merge_attempts(target,old):
    for bucket,ledger in old.get('attempt_ledger',{}).items():
        dest=target.setdefault('attempt_ledger',{}).setdefault(bucket,{})
        for key,count in ledger.items():dest[key]=max(dest.get(key,0),int(count))
    for bucket in ('units','financial_units','finmind_units'):
        dest=target.setdefault('attempt_ledger',{}).setdefault(bucket,{})
        for key,receipt in old.get(bucket,{}).items():dest[key]=max(dest.get(key,0),int(receipt.get('attempts',0)))

def newest_receipts(upstream):
    receipts=[e for b in ('units','financial_units') for e in upstream.get(b,{}).values() if e.get('status')=='SAVED_BASIC_VERIFIED' and e.get('evidence_file')]
    return sorted(receipts,key=lambda e:(e.get('period',''),e.get('category',''),e.get('unit_id','')),reverse=True)

class Worker(base.Worker):
    def __init__(self,stage,minutes,stage06=False):
        suffix='_STAGE06_'+stage+'_V1' if stage06 else lease_suffix_for(stage)
        super().__init__(stage,minutes,lease_suffix=suffix,lease_ttl=lease_ttl_for(minutes),isolated=stage06)
        self.cache=ArchiveCache();self.last_processed_month=None;self.last_processed_period=None
        self.primary_month=None;self.phase='INITIALIZING';self.indexed=0;self.corrections=0
        self.budget_seconds=minutes*60
        if stage=='RAW' and not stage06:
            try:self.initialize_history_cursor()
            except Exception as exc:
                try:commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(type(exc).__name__.encode()))
                except Exception:pass
                raise
        self.cursor.setdefault('audit_month_index',0)

    def initialize_history_cursor(self):
        if self.cursor.get('execution_plan')==REVISION:return
        folder=self.d.find(native.REPORT_ROOT,PLAN['legacy_checkpoint_namespace'])
        if not folder:raise ValueError('LEGACY_CHECKPOINT_NOT_FOUND')
        legacy=engine.getj(self.d,folder['id'],'CURSOR.json')
        if not legacy or legacy.get('version')!=PLAN['legacy_checkpoint_namespace']:raise ValueError('LEGACY_CHECKPOINT_VERSION_MISMATCH')
        index=legacy.get('month_index')
        if type(index) is not int or not 0<=index<len(LEGACY_MONTHS) or LEGACY_MONTHS[index]!=RAW_MONTHS[0]:raise ValueError('LEGACY_CHECKPOINT_NOT_AT_AUTHORIZED_201404')
        snapshot={'old_live_cursor':self.cursor,'legacy_cursor':legacy,'execution_plan':PLAN,'updated_utc':native.stamp()}
        raw=json.dumps(snapshot,ensure_ascii=False,sort_keys=True).encode()
        self.owned();self.d.put(self.stagectrl,'CUTOVER_BACKUP_'+native.sha(raw)[:20]+'.json',raw,'application/json',overwrite=False)
        self.cursor={'run':base.RUN,'execution_plan':REVISION,'month_index':0,'raw_history_start':RAW_MONTHS[0],
                     'raw_history_end':RAW_MONTHS[-1],'retry_months':[],
                     'prior_recent_repairs':self.cursor.get('retry_months',[]),'legacy_resume_month':'2014-04'}
        self.save_cursor()
        base.emit(stage='RAW',event='LEGACY_CURSOR_ADOPTED',primary_next_month='2014-04',history_months=172)

    def restore(self,month,ctrl):
        super().restore(month,ctrl)
        if self.stage=='RAW' and hasattr(self,'primary_control') and not self.state.get('stage06_primary_snapshot'):
            primary_root=self.d.find(self.primary_control,'RAW')
            primary_month=self.d.find(primary_root['id'],month) if primary_root else None
            primary=engine.getj(self.d,primary_month['id'],'MONTH_STATE.json') if primary_month else None
            if primary:
                for bucket in ('units','financial_units','finmind_units'):
                    snapshot=copy.deepcopy(primary.get(bucket,{}))
                    snapshot.update(self.state.get(bucket,{}));self.state[bucket]=snapshot
                merge_attempts(self.state,primary)
                self.state['stocks']=sorted(set(self.state.get('stocks',[]))|set(primary.get('stocks',[])))
            self.state['stage06_primary_snapshot']=True
            self.save_state()
        if self.stage!='RAW' or month not in RAW_MONTHS or self.state.get('legacy_attempts_imported'):return
        oldroot=self.d.find(native.REPORT_ROOT,PLAN['legacy_checkpoint_namespace'])
        oldfolder=self.d.find(oldroot['id'],month) if oldroot else None
        old=engine.getj(self.d,oldfolder['id'],'MONTH_STATE.json') if oldfolder else None
        if old:
            merge_attempts(self.state,old)
            self.state['protected_legacy_receipts']={k:e for b in ('units','financial_units') for k,e in old.get(b,{}).items() if e.get('status')=='SAVED_BASIC_VERIFIED'}
            self.state['stocks']=sorted(set(self.state['stocks'])|set(old.get('stocks',[])))
            self.state['legacy_missing_units']=[e for b in ('units','financial_units') for e in old.get(b,{}).values() if e.get('status')!='SAVED_BASIC_VERIFIED']
        self.state['legacy_attempts_imported']=True
        self.save_state()

    def fetch_job(self,job,bucket):
        if self.phase=='HISTORY_DOWNLOAD' and job['month'] not in RAW_MONTHS:raise ValueError('HISTORY_REQUEST_OUTSIDE_201404_TO_200001')
        key=engine.key(job)
        if key in self.state.get('protected_legacy_receipts',{}) and self.state[bucket].get(key,{}).get('status')!='SAVED_BASIC_VERIFIED':
            self.state[bucket][key]=dict(job,unit_id=key,status='LEGACY_RECEIPT_RECONCILIATION_HOLD',permanent_hold=True,
                                        reason='Prior saved receipt exists; resolve native archive instead of downloading it again',numeric_verified=False,pit_verified=False)
            self.save_state();return
        super().fetch_job(job,bucket)

    def capture_latest(self):
        month=min(self.today.strftime('%Y-%m'),AUDIT_MONTHS[0])
        # This authorized backfill has a fixed 2026-10 upper bound.
        if month!=self.today.strftime('%Y-%m'):return
        parent=self.d.find(self.stagectrl,month)
        if not parent:return
        self.restore(month,parent['id'])
        now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
        latest=self.today if now.hour>=18 else self.today-dt.timedelta(days=1)
        jobs=[j for j in native.Audit.jobs(object.__new__(native.Audit),month,set()) if j['period']==latest.isoformat()]
        count=0
        for source in ('TWSE','TPEx'):
            candidates=[j for j in jobs if j['source']==source and self.state['units'].get(engine.key(j),{}).get('status')!='SAVED_BASIC_VERIFIED']
            if not candidates:continue
            if not self.inventory_existing((source,)):return
            for job in candidates:
                if count>=4 or time.monotonic()>=self.until:return
                before=self.processed;self.fetch_job(job,'units');count+=self.processed-before

    def raw(self):
        final_until=self.until
        reserve=min(90,self.budget_seconds*.10)
        self.until=final_until-reserve
        self.phase='HISTORY_DOWNLOAD'
        for month in list(self.cursor.get('retry_months',[]))[:1]:
            if month not in RAW_MONTHS:continue
            if time.monotonic()>=self.until:break
            self.primary_month=month;capture_history_month(self,month,quota=self.processed+1)
        while self.cursor['month_index']<len(RAW_MONTHS) and time.monotonic()<self.until:
            month=RAW_MONTHS[self.cursor['month_index']];self.primary_month=month
            base.emit(stage='RAW',phase=self.phase,primary_month=month,execution_plan=REVISION)
            if not capture_history_month(self,month):break
            self.cursor['month_index']+=1;self.save_cursor()
        self.save_cursor();self.until=final_until
        self.phase='BOUNDED_LATEST_INCREMENT'
        if time.monotonic()<self.until:self.capture_latest()
        self.phase='HISTORY_DOWNLOAD'

    def input_index(self,month,qa_ledger):
        qa_root=self.d.folder(self.control,'QA1')
        root=self.d.folder(qa_root,'RAW_INDEX')
        folder=self.d.folder(root,month)
        self.restore(month,folder)
        read_control=getattr(self,'primary_control',self.control)
        raw_root=self.d.find(read_control,'RAW');raw_folder=self.d.find(raw_root['id'],month) if raw_root else None
        main=engine.getj(self.d,raw_folder['id'],'MONTH_STATE.json') if raw_folder else None
        if main:
            for bucket in ('units','financial_units'):
                for key,receipt in main.get(bucket,{}).items():
                    if receipt.get('status')=='SAVED_BASIC_VERIFIED' and receipt.get('evidence_file'):
                        self.state[bucket][key]=receipt
            self.state['inventory'].update(main.get('inventory',{}))
        if hasattr(self,'primary_control'):
            primary_qa=self.d.find(self.primary_control,'QA1')
            primary_index=self.d.find(primary_qa['id'],'RAW_INDEX') if primary_qa else None
            primary_month=self.d.find(primary_index['id'],month) if primary_index else None
            indexed=engine.getj(self.d,primary_month['id'],'MONTH_STATE.json') if primary_month else None
            if indexed:
                for bucket in ('units','financial_units'):
                    for key,receipt in indexed.get(bucket,{}).items():
                        if receipt.get('status')=='SAVED_BASIC_VERIFIED' and receipt.get('evidence_file'):
                            self.state[bucket][key]=copy.deepcopy(receipt)
        self.state.setdefault('index_sources_done',[])
        # Consume already indexed units first; do not spend the entire QA budget
        # rescanning a month while verified RAW receipts are already waiting.
        waiting=[r for r in newest_receipts(self.state) if r['unit_id']+'_'+r['sha256'] not in qa_ledger]
        if not waiting and not self.state.get('inventory_complete'):
            limit=self.until;self.until=min(limit,time.monotonic()+min(90,self.budget_seconds*.25))
            before=len(self.state['inventory'])
            try:
                for source in ('TWSE','TPEx','MOPS','FinMind'):
                    if source in self.state['index_sources_done']:continue
                    self.phase='INDEX_EXISTING_RAW'
                    if not self.inventory_existing((source,)):break
                    self.state['index_sources_done'].append(source);self.save_state()
                self.state['inventory_complete']=len(self.state['index_sources_done'])==4
                self.indexed+=len(self.state['inventory'])-before
            finally:self.until=limit
        self.state['input_index_execution_plan']=REVISION
        self.save_state()
        return copy.deepcopy(self.state)

    def indexed_inputs(self):
        qa_root=self.d.find(self.control,'QA1')
        root=self.d.find(qa_root['id'],'RAW_INDEX') if qa_root else None
        if not root:return []
        return sorted([f for f in native.listing(self.d,root['id']) if f['name'] in AUDIT_MONTHS and f['mimeType']=='application/vnd.google-apps.folder'],key=lambda f:f['name'],reverse=True)

    def process_units(self,month,upstream,out,ledger,qa):
        dirty=0
        for receipt in newest_receipts(upstream):
            if time.monotonic()>=self.until:break
            if self.stage!='QA1' and base.route(receipt['category'])!=self.stage:continue
            key=receipt['unit_id']+'_'+receipt['sha256']
            output_key=key if self.stage=='QA1' else key+'_'+base.STAGING_REVISION
            if output_key in ledger['units']:continue
            if self.stage!='QA1' and qa.get(key,{}).get('status')!='BASIC_QA_PASS':continue
            self.phase='QA_CHECK' if self.stage=='QA1' else 'TRANSFORM_AND_CORRECT_STAGING'
            result={'raw_sha256':receipt['sha256'],'unit_id':receipt['unit_id'],'source':receipt['source'],
                    'category':receipt['category'],'period':receipt['period'],'month':month,
                    'stage':self.stage,'execution_plan':REVISION,'checked_utc':native.stamp(),
                    'numeric_verified':False,'pit_verified':False}
            try:
                raw,archive_sha=cached_payload(self.d,receipt,self.cache);result['archive_sha256']=archive_sha
                if self.stage=='QA1':
                    if receipt['category'] not in engine.FIN_REPORTS:native.validate(raw,receipt['source'],receipt['category'],receipt['period'])
                    else:
                        holder=object.__new__(native.Audit);holder.year=int(month[:4]);holder.financial={}
                        native.Audit.financial_payload(holder,raw,receipt['category'],'raw')
                        if not holder.financial:raise ValueError('FINANCIAL_CONTENT_UNPROVEN')
                    result['status']='BASIC_QA_PASS'
                else:
                    from scripts.v093_standard_r4 import parse_member,SCHEMA
                    import pyarrow as pa
                    import pyarrow.parquet as pq
                    rows,stats,_=parse_member(receipt['source'],receipt['category']+'_'+receipt['period']+'.raw',raw,month)
                    if not rows:raise ValueError('NO_PARSED_NUMERIC_CELLS:'+json.dumps(stats))
                    for row in rows:row.update(native_archive=receipt['evidence_file'].split('/')[0],native_sha256=archive_sha,native_member_sha256=receipt['sha256'])
                    buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),buf,compression='zstd')
                    blob=buf.getvalue();filename=output_key+'.parquet'
                    self.owned();self.d.put(out,filename,blob,'application/octet-stream',overwrite=False)
                    result.update(status='STAGING_SAVED_NOT_APPROVED',rows=len(rows),sha256=native.sha(blob),parser_stats=stats,output_name=filename,processor_version=base.STAGING_REVISION)
            except (ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
                result.update(status='QUARANTINED',error=type(exc).__name__+':'+str(exc)[:400])
                kind='STORAGE_RECONCILIATION_REQUIRED' if 'HASH_MISMATCH' in str(exc) else 'PARSER_OR_SEMANTIC_CORRECTION_REQUIRED'
                ledger.setdefault('corrections',{})[output_key]=dict(result,correction_kind=kind,correction_status='PENDING_EVIDENCE_OR_REPAIR',automatic_source_redownload=False)
                self.corrections+=1
            if self.stage!='QA1':
                result['processor_version']=base.STAGING_REVISION
                if key in ledger['units']:ledger['units'][key]['status']='SUPERSEDED_PROVENANCE_REVISION'
            ledger['units'][output_key]=result;dirty+=1
            self.last_processed_month=month;self.last_processed_period=receipt['period']
            self.processed+=1;self.saved+=int(result['status']!='QUARANTINED')
            base.emit(stage=self.stage,month=month,period=receipt['period'],status=result['status'],unit=receipt['unit_id'],rows=result.get('rows'),execution_plan=REVISION)
            if dirty>=8:self.putj(out,'MONTH_STATE.json',ledger);dirty=0
        # Rechecking after a crash is safe; source HTTP attempts remain in RAW's
        # durable ledger. Immutable Parquet writes reconcile by byte hash.
        if dirty:self.putj(out,'MONTH_STATE.json',ledger)

    def consume(self):
        if self.stage=='QA1':
            while self.cursor['audit_month_index']<len(AUDIT_MONTHS) and time.monotonic()<self.until:
                month=AUDIT_MONTHS[self.cursor['audit_month_index']]
                out=self.monthfolder('QA1',month);ledger=engine.getj(self.d,out,'MONTH_STATE.json') or {'month':month,'units':{}}
                upstream=self.input_index(month,ledger['units'])
                self.process_units(month,upstream,out,ledger,{})
                pending=[r for r in newest_receipts(upstream) if r['unit_id']+'_'+r['sha256'] not in ledger['units']]
                if pending:break
                if not upstream.get('inventory_complete'):
                    if time.monotonic()>=self.until:break
                    continue
                ledger['existing_raw_scan_checked']=True
                ledger['inventory_issues_pending_correction']=upstream.get('inventory_errors',[])
                self.putj(out,'MONTH_STATE.json',ledger)
                self.cursor['audit_month_index']+=1;self.save_cursor()
            # A completed sweep is not a completeness certification. New RAW and
            # latest increments are rechecked during subsequent sweeps.
            if self.cursor['audit_month_index']>=len(AUDIT_MONTHS):
                self.cursor['audit_month_index']=0;self.cursor['completed_existing_raw_sweeps']=self.cursor.get('completed_existing_raw_sweeps',0)+1
            self.save_cursor()
        else:
            for folder in self.indexed_inputs():
                if time.monotonic()>=self.until:break
                month=folder['name'];upstream=engine.getj(self.d,folder['id'],'MONTH_STATE.json') or {}
                out=self.monthfolder(self.stage,month);ledger=engine.getj(self.d,out,'MONTH_STATE.json') or {'month':month,'units':{}}
                qa_folder=self.d.find(self.d.folder(self.control,'QA1'),month)
                qa=(engine.getj(self.d,qa_folder['id'],'MONTH_STATE.json') or {}).get('units',{}) if qa_folder else {}
                self.process_units(month,upstream,out,ledger,qa)

    def run(self):
        try:
            from scripts.v093_stage06_worker_bridge import run_pending_repairs
            repair_report=run_pending_repairs(self)
            # Stage six executes its own repairs; primary workers only do their stage.
            live_repair_report={'completed':0,'status':'INDEPENDENT_STAGE06_WORKERS'}
            self.raw() if self.stage=='RAW' else self.consume()
            report={'worker_budget_minutes':self.budget_seconds/60,'lease_ttl_seconds':lease_ttl_for(self.budget_seconds/60),'stage':self.stage,'run':base.RUN,'execution_plan':REVISION,'updated_utc':native.stamp(),
                    'processed_this_run':self.processed,'saved_this_run':self.saved,'indexed_files_this_run':self.indexed,
                    'corrections_queued_this_run':self.corrections,'last_processed_month':self.last_processed_month,
                    'last_processed_period':self.last_processed_period,'primary_active_month':self.primary_month,
                    'primary_next_month':RAW_MONTHS[self.cursor['month_index']] if self.stage=='RAW' and self.cursor['month_index']<len(RAW_MONTHS) else None,
                    'audit_next_month':AUDIT_MONTHS[self.cursor['audit_month_index']] if self.stage=='QA1' else None,
                    'raw_history_start':'2014-04','audit_start':'2026-10','end_month':'2000-01',
                    'status':'HISTORY_ACTIVE' if self.stage=='RAW' and self.primary_month else ('ACTIVE' if self.processed or self.indexed else 'WAITING_FOR_AVAILABLE_UPSTREAM_OR_NEXT_BATCH'),
                    'numeric_verified':False,'pit_verified':False,'full_market_complete':False,'policy_sha256':base.policy_digest(),
                    'stage06_repair':{k:v for k,v in repair_report.items() if k!='completed_tasks'},
                    'stage06_completed_this_run':len(repair_report['completed_tasks'])+live_repair_report.get('completed',0),
                    'stage06_live_repair':live_repair_report}
            self.putj(self.stagectrl,'STATUS.json',report)
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(json.dumps(report,sort_keys=True).encode()))
            base.emit(**report)
        except Exception as exc:
            try:commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(type(exc).__name__.encode()))
            except Exception:pass
            raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=base.STAGES,required=True);p.add_argument('--minutes',type=float,default=4)
    a=p.parse_args()
    if not .1<=a.minutes<=PLAN['worker_budgets_minutes'][a.stage]:raise SystemExit('INVALID_BUDGET')
    base.load_policy()
    request=json.loads(Path('requests/V093_FIVE_STAGE_202610_TO_200001_20261021.json').read_text())
    if request.get('activation_authorized') is not True or request.get('execution_plan',{}).get('revision')!=REVISION:raise SystemExit('MISSING_REPLAN_AUTHORIZATION')
    if a.stage!='RAW' and PLAN.get('parallelism')=='ONE_WORKER_PER_STAGE_FIVE_INDEPENDENT_POOLS':
        url='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/contents/.github/live-state/five-stage-leases.json'
        _,manifest=_read(url,os.environ['GH_TOKEN'])
        if manifest.get('parallel_cutover',{}).get('status')!='READY':raise SystemExit('PARALLEL_CUTOVER_PENDING')
    Worker(a.stage,a.minutes).run()
if __name__=='__main__':main()
