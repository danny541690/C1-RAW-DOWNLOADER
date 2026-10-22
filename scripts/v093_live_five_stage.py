"""Operational native capture and durable per-unit basic-QA/staging workers.

RAW bytes are immutable; staging outputs never imply numeric, unit, or PIT approval.
Drive state belongs to one stage; GitHub leases and two Actions pools bound writers.
"""
import argparse, collections, datetime as dt, io, json, os, random, time, urllib.error, zipfile
from pathlib import Path
from scripts.annual_actual_firstpass import Drive, service
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_independent_raw import Independent
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r1 import C1
from scripts.v093_five_stage_policy import load_policy, policy_digest
from scripts.v093_five_stage_durable_gate import acquire, commit, _read, LeaseConflict

RUN = 'LIVE_FIVE_STAGE_202610_TO_200001_V1'
MONTHS = [f'{y}-{m:02d}' for y in range(2026,1999,-1) for m in range(12,0,-1) if (y,m)<=(2026,10)]
STAGES = ('RAW','QA1','PRICE','FINANCIAL','CHIP')
STAGING_REVISION = 'R2_ARCHIVE_PROVENANCE'

def emit(**obj):
    print('LIVE_FIVE_STAGE '+json.dumps(obj,ensure_ascii=False,sort_keys=True),flush=True)

def route(category):
    if category.startswith('revenue_') or category in engine.FIN_REPORTS:return 'FINANCIAL'
    if category in ('institutional','margin','lending','foreign_holdings','broker','ownership'):return 'CHIP'
    if category in ('prices','prices_indices','valuation','indices','marketcap','ex_dividend','capital_reduction','par_value_change'):return 'PRICE'
    raise ValueError('UNROUTED_DATASET:'+category)

def dataset_watermarks(state):
    marks={}
    for bucket in ('units','financial_units'):
        for receipt in state.get(bucket,{}).values():
            if receipt.get('status')!='SAVED_BASIC_VERIFIED':continue
            key=receipt['source']+':'+receipt['category']
            marks[key]=max(marks.get(key,''),receipt['period'])
    return marks


def retryable(exc):
    if isinstance(exc,urllib.error.HTTPError):return exc.code in (408,429,500,502,503,504)
    return isinstance(exc,(TimeoutError,ConnectionError,OSError))

def payload(d,receipt,with_archive_hash=False):
    ref=receipt.get('evidence_file')
    if not ref:raise ValueError('MISSING_RAW_FILE_REFERENCE')
    fid,sep,member=ref.partition('/')
    raw=native.read(d,{'id':fid})
    archive_sha=native.sha(raw)
    if receipt.get('archive_sha256') and receipt['archive_sha256']!=archive_sha:raise ValueError('ARCHIVE_READBACK_HASH_MISMATCH')
    if sep:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if z.getinfo(member).file_size>30_000_000:raise ValueError('MEMBER_SIZE_LIMIT')
            raw=z.read(member)
    if native.sha(raw)!=receipt['sha256']:raise ValueError('RAW_READBACK_HASH_MISMATCH')
    return (raw,archive_sha) if with_archive_hash else raw

class Worker(Independent):
    def __init__(self,stage,minutes,lease_suffix="",lease_ttl=3600,isolated=False):
        self.stage=stage
        self.today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
        native.TODAY=self.today
        engine.RUN=RUN
        self.until=time.monotonic()+minutes*60
        self.d=Drive(service())
        # Only the primary RAW worker opts into ID-based readback verification.
        self.d.direct_readback=(stage=='RAW' and not isolated)
        self.control=self.d.folder(native.REPORT_ROOT,RUN)
        if isolated:
            self.primary_control=self.control
            # Each stage creates a different root; parallel starts cannot create
            # duplicate shared WORKERS folders in Drive.
            self.control=self.d.folder(self.d.folder(self.control,'RECONCILE_REPAIR'),'WORKERS_'+stage+'_V2')
        self.stagectrl=self.d.folder(self.control,stage)
        self.registry=FolderRegistry(self.d,self.d.folder(C1,'05_CONTROL'),namespace=('STAGE06_' if isolated else 'LIVE_')+stage)
        self.folders={};self.circuit=collections.Counter();self.request_counts=collections.Counter()
        self.active=None;self.processed=0;self.saved=0
        self.cursor=engine.getj(self.d,self.stagectrl,'CURSOR.json') or {'month_index':0,'run':RUN,'retry_months':[]}
        if self.cursor.get('run')!=RUN:raise ValueError('CURSOR_RUN_MISMATCH')
        self.api='https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+'/contents/.github/live-state/five-stage-leases.json'
        self.token=os.environ['GH_TOKEN'];self.owner=os.environ['GITHUB_RUN_ID']+'/'+stage
        self.lock=('POOL_RAW' if stage=='RAW' else 'POOL_CONSUMER')+lease_suffix
        # TTL exceeds the workflow's hard timeout. No writer can outlive its lease.
        self.fence=acquire(self.api,self.token,self.lock,self.owner,ttl=lease_ttl)
        self.last_lease_check=0

    def owned(self):
        if time.monotonic()-self.last_lease_check<120:return
        _,state=_read(self.api,self.token)
        lease=state['jobs'][self.lock].get('lease') or {}
        if lease.get('owner')!=self.owner or lease.get('fence')!=self.fence or lease.get('expires_at',0)<=time.time():raise LeaseConflict('STALE_WRITER')
        self.last_lease_check=time.monotonic()

    def putj(self,parent,name,obj):
        self.owned();engine.putj(self.d,parent,name,obj)

    def save_state(self):
        self.owned();self.registry.flush()
        self.state['dataset_watermarks']=dataset_watermarks(self.state)
        self.state['updated_utc']=native.stamp()
        self.putj(self.monthctrl,'MONTH_STATE.json',self.state)

    def monthfolder(self,stage,month):
        return self.d.folder(self.d.folder(self.control,stage),month)

    def save_cursor(self):
        self.cursor['updated_utc']=native.stamp()
        self.putj(self.stagectrl,'CURSOR.json',self.cursor)

    def record_payload(self,j,raw,receipt,bucket):
        """Save deterministic archive first, then ledger; inventory reconciles a crash."""
        receipt=dict(receipt,unit_id=engine.key(j),bucket=bucket,month=self.active,
                     numeric_verified=False,pit_verified=False,run=RUN)
        blob=engine.packed([(receipt,raw)])
        # ZIP timestamps and receipt metadata may change while RAW bytes stay equal.
        # Address the full archive so retries preserve older immutable evidence.
        archive_sha=native.sha(blob)
        name=RUN+'_'+receipt['unit_id']+'_'+native.sha(raw)[:20]+'_'+archive_sha+'.zip'
        parent=self.folder(j['source'],self.active) if receipt['status']=='SAVED_BASIC_VERIFIED' else self.d.folder(self.monthctrl,'QUARANTINE')
        self.owned();self.d.put(parent,name,blob,'application/zip',overwrite=False)
        file=self.d.find(parent,name)
        receipt['evidence_file']=file['id']+'/'+receipt['unit_id']+'.raw'
        receipt['archive_sha256']=archive_sha
        self.state[bucket][receipt['unit_id']]=receipt
        if receipt['status']=='SAVED_BASIC_VERIFIED':
            # Drive.put verified these exact archive bytes. Do not re-download
            # our own archive for inventory when this month resumes.
            self.state.setdefault('inventory',{})[file['id']]=dict(
                name=name,source=j['source'],sha256=archive_sha,errors=[],
                checked_utc=native.stamp(),verified_on_write=True)
        self.state['stocks']=sorted(set(self.state['stocks'])|set(receipt.get('codes_found',[])))
        self.save_state()
        if receipt['status']=='SAVED_BASIC_VERIFIED':self.saved+=1
        emit(stage=self.stage,month=self.active,unit=receipt['unit_id'],source=j['source'],dataset=j['category'],status=receipt['status'],bytes=len(raw),sha256=native.sha(raw),remote_readback=True)

    def inspect_payload(self,source,name,raw,meta,file_ref):
        # Only known native v0.93 trees are inventoried; prior versions never imported.
        if 'v0.92' in name.lower() or 'v092' in name.lower():raise ValueError('LEGACY_VERSION_REJECTED')
        if meta.get('run')==RUN and meta.get('status')=='SAVED_BASIC_VERIFIED':
            if meta.get('month')!=self.active or meta.get('source')!=source or native.sha(raw)!=meta.get('sha256'):raise ValueError('RECOVERY_IDENTITY_MISMATCH')
            self.state[meta.get('bucket','units')][engine.key(meta)]=dict(meta,evidence_file=file_ref)
            self.state['stocks']=sorted(set(self.state['stocks'])|set(meta.get('codes_found',[])))
        else:super().inspect_payload(source,name,raw,meta,file_ref)

    def fetch_job(self,j,bucket):
        k=engine.key(j);old=self.state[bucket].get(k,{})
        if old.get('status')=='SAVED_BASIC_VERIFIED':return
        if getattr(self,'stage06_cleanup',False) and old.get('status')=='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED':
            emit(stage='RAW',unit=k,status='STAGE06_UNCERTAIN_REQUEST_RECONCILIATION_REQUIRED');return
        attempts=self.state['attempt_ledger'].setdefault(bucket,{})
        count=attempts.get(k,0)
        max_attempts=getattr(self,'max_source_attempts',4)
        if count>=max_attempts or old.get('permanent_hold') or old.get('next_retry_at',0)>time.time():return
        source=j['source']
        if self.circuit[source]>=2:
            self.state[bucket].setdefault(k,dict(j,unit_id=k,status='SOURCE_CIRCUIT_WAIT',next_retry_at=time.time()+900,numeric_verified=False,pit_verified=False))
            return
        attempts[k]=count+1
        e=dict(j,unit_id=k,attempts=count+1,status='REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED',numeric_verified=False,pit_verified=False)
        self.state[bucket][k]=e;self.save_state()
        raw=None
        try:
            raw=native.request(j['url'],j.get('params'))
            if bucket=='financial_units':
                holder=object.__new__(native.Audit);holder.year=int(self.active[:4]);holder.financial={}
                native.Audit.financial_payload(holder,raw,j['category'],j['url'])
                found=sorted({c for c,r,p in holder.financial if r==j['category'] and p==j['report_period'] and c in j['codes']})
                if not found:raise ValueError('NO_EXPLICIT_COMPANY_QUARTER_NUMERIC_CELLS')
                stats={'rows':len(found),'codes':found}
                e['partial_financial_cells_only']=True
            else:stats=native.validate(raw,source,j['category'],j['period'])
            e.update(status='SAVED_BASIC_VERIFIED',sha256=native.sha(raw),rows=stats['rows'],codes_found=stats['codes'])
            self.circuit[source]=0
        except Exception as exc:
            transient=retryable(exc);self.circuit[source]+=int(transient)
            delay=min(3600,60*2**count)+random.uniform(0,20)
            if isinstance(exc,urllib.error.HTTPError):
                hint=exc.headers.get('Retry-After','') if exc.headers else ''
                try:delay=max(delay,float(hint))
                except ValueError:
                    try:
                        from email.utils import parsedate_to_datetime
                        delay=max(delay,parsedate_to_datetime(hint).timestamp()-time.time())
                    except (TypeError,ValueError):pass
            e.update(status='RETRY_WAIT' if transient and count<max_attempts-1 else 'ISOLATED_MISSING',
                     error=type(exc).__name__+':'+str(exc)[:200],permanent_hold=not transient,
                     next_retry_at=time.time()+delay,retry_exhausted=count>=max_attempts-1)
        if raw is not None:
            e.update(sha256=native.sha(raw),bytes=len(raw));self.record_payload(j,raw,e,bucket)
        else:self.state[bucket][k]=e;self.save_state();emit(stage='RAW',month=self.active,unit=k,status=e['status'],error=e.get('error'))
        self.processed+=1

    def capture_month(self,month,quota=None):
        self.restore(month,self.monthfolder('RAW',month))
        # Crash recovery and legacy per-unit proof always precede a new HTTP request.
        jobs=native.Audit.jobs(object.__new__(native.Audit),month,set())
        # Do not request today's incomplete close-of-day snapshot.
        if month==self.today.strftime('%Y-%m') and dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).hour<18:
            jobs=[j for j in jobs if j['period']!=self.today.isoformat()]
        jobs.sort(key=lambda j:(j['period'],j['category'] in ('prices','prices_indices')),reverse=True)
        for source in ('TWSE','TPEx','MOPS','FinMind'):
            if not self.inventory_existing((source,)):return False
            # Each source hands off independently; FinMind inventory cannot block
            # a confirmed official-source gap from being captured.
            financial=self.financial_jobs() if source=='MOPS' else []
            for bucket,items in (('units',[j for j in jobs if j['source']==source]),('financial_units',financial)):
                for j in items:
                    if time.monotonic()>=self.until:return False
                    if quota is not None and self.processed>=quota:return False
                    self.fetch_job(j,bucket)
        unresolved=[e for b in ('units','financial_units') for e in self.state[b].values() if e.get('status')!='SAVED_BASIC_VERIFIED']
        self.state['missing_queue']=unresolved
        self.state['finmind_alignment_hold']='NO_APPROVED_CROSS_SOURCE_SEMANTIC_EVIDENCE_NO_REQUEST'
        self.state['watermark']=max((e['period'] for e in self.state['units'].values() if e.get('status')=='SAVED_BASIC_VERIFIED'),default=None)
        self.save_state()
        if any(e.get('next_retry_at',0)>0 and not e.get('permanent_hold') and not e.get('retry_exhausted') for e in unresolved):
            self.cursor['retry_months']=sorted(set(self.cursor.get('retry_months',[]))|{month},reverse=True)
        else:self.cursor['retry_months']=[m for m in self.cursor.get('retry_months',[]) if m!=month]
        return True

    def raw(self):
        idx=self.cursor['month_index']
        # Bounded top-up and 10% repair request reservation; never reset the history pointer.
        if idx>0:self.capture_month(MONTHS[0],quota=4)
        repair_end=self.processed+max(1,int(max(1,(self.until-time.monotonic())/20)*.10))
        for month in list(self.cursor.get('retry_months',[]))[:1]:
            if self.processed>=repair_end or time.monotonic()>=self.until:break
            self.capture_month(month,quota=repair_end)
        while self.cursor['month_index']<len(MONTHS) and time.monotonic()<self.until:
            month=MONTHS[self.cursor['month_index']]
            if not self.capture_month(month):break
            self.cursor['month_index']+=1;self.save_cursor()
        self.save_cursor()

    def consume(self):
        # Read durable upstream ledgers. Consumers never modify RAW state or receipts.
        rawroot=self.d.find(self.control,'RAW')
        months=native.listing(self.d,rawroot['id']) if rawroot else []
        for f in sorted(months,key=lambda f:f['name'],reverse=True):
            month=f['name']
            if month not in MONTHS or f['mimeType']!='application/vnd.google-apps.folder':continue
            upstream=engine.getj(self.d,f['id'],'MONTH_STATE.json') or {}
            out=self.monthfolder(self.stage,month)
            ledger=engine.getj(self.d,out,'MONTH_STATE.json') or {'month':month,'units':{}}
            qa_folder=self.d.find(self.d.folder(self.control,'QA1'),month) if self.stage!='QA1' else None
            qa=(engine.getj(self.d,qa_folder['id'],'MONTH_STATE.json') or {}).get('units',{}) if qa_folder else {}
            for receipt in [e for b in ('units','financial_units') for e in upstream.get(b,{}).values()]:
                if time.monotonic()>=self.until:return
                if receipt.get('status')!='SAVED_BASIC_VERIFIED':continue
                if self.stage!='QA1' and route(receipt['category'])!=self.stage:continue
                k=receipt['unit_id']+'_'+receipt['sha256']
                output_key=k if self.stage=='QA1' else k+'_'+STAGING_REVISION
                if output_key in ledger['units']:continue
                if self.stage!='QA1' and qa.get(k,{}).get('status')!='BASIC_QA_PASS':continue
                result={'raw_sha256':receipt['sha256'],'unit_id':receipt['unit_id'],'numeric_verified':False,'pit_verified':False,'stage':self.stage,'checked_utc':native.stamp()}
                try:
                    raw,archive_sha=payload(self.d,receipt,with_archive_hash=True)
                    result['archive_sha256']=archive_sha
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
                        name=receipt['category']+'_'+receipt['period']+'.raw'
                        rows,stats,encoding=parse_member(receipt['source'],name,raw,month)
                        if not rows:raise ValueError('NO_PARSED_NUMERIC_CELLS:'+json.dumps(stats))
                        for row in rows:
                            row.update(native_archive=receipt['evidence_file'].split('/')[0],native_sha256=archive_sha,native_member_sha256=receipt['sha256'])
                        buf=io.BytesIO();pq.write_table(pa.Table.from_pylist(rows,schema=SCHEMA),buf,compression='zstd')
                        blob=buf.getvalue();filename=output_key+'.parquet'
                        self.owned();self.d.put(out,filename,blob,'application/octet-stream',overwrite=False)
                        result.update(status='STAGING_SAVED_NOT_APPROVED',rows=len(rows),sha256=native.sha(blob),parser_stats=stats,output_name=filename)
                except (ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
                    result.update(status='QUARANTINED',error=type(exc).__name__+':'+str(exc)[:400])
                if self.stage!='QA1':
                    result['processor_version']=STAGING_REVISION
                    if k in ledger['units']:ledger['units'][k]['status']='SUPERSEDED_PROVENANCE_REVISION'
                ledger['units'][output_key]=result;self.putj(out,'MONTH_STATE.json',ledger)
                self.processed+=1;self.saved+=int(result['status']!='QUARANTINED')
                emit(stage=self.stage,month=month,unit=receipt['unit_id'],status=result['status'],rows=result.get('rows'))
        self.save_cursor()

    def run(self):
        try:
            self.raw() if self.stage=='RAW' else self.consume()
            report={'stage':self.stage,'run':RUN,'processed_this_run':self.processed,'saved_this_run':self.saved,
                    'status':'ACTIVE' if self.processed else 'WAITING_FOR_AVAILABLE_UPSTREAM_OR_NEXT_BATCH',
                    'updated_utc':native.stamp(),'month_index':self.cursor['month_index'],'scope_months':322,
                    'numeric_verified':False,'pit_verified':False,'policy_sha256':policy_digest()}
            self.putj(self.stagectrl,'STATUS.json',report)
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(json.dumps(report,sort_keys=True).encode()))
            emit(**report)
        except Exception as exc:
            failed={'stage':self.stage,'status':'FAILED_RETRY_NEXT_RUN','error':type(exc).__name__}
            try:commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(json.dumps(failed,sort_keys=True).encode()))
            except Exception:pass
            raise

def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=STAGES,required=True);p.add_argument('--minutes',type=float,default=4)
    args=p.parse_args()
    if not .1<=args.minutes<=26:raise SystemExit('INVALID_BUDGET')
    load_policy()
    request=json.loads(Path('requests/V093_FIVE_STAGE_202610_TO_200001_20261021.json').read_text())
    if request.get('activation_authorized') is not True or request.get('scope',{}).get('months')!=322:raise SystemExit('MISSING_USER_AUTHORIZATION')
    Worker(args.stage,args.minutes).run()

if __name__=='__main__':main()
