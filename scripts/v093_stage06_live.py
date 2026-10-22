"""Live reverse-month reconciliation and approved native staging repairs.

The reconciler owns its queue only. PRICE repairs execute under the existing
PRICE pool, and never replace RAW or the original quarantined month receipts.
Unsupported repairs remain blocked; absence alone is not proof of a missing unit.
"""
import argparse
import copy
import json
import os
import re
import urllib.request
import tempfile
import time
from pathlib import Path

from scripts.annual_actual_firstpass import Drive, service
from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_five_stage_durable_gate import acquire, commit, LeaseBusy, _read
from scripts.v093_stage06_drive_artifacts import DriveImmutableArtifacts
from scripts.v093_stage06_fenced_store import FencedGitHubStore
from scripts.v093_stage06_ledger import FileStore, Ledger, digest, import_quarantine, summary, StaleClaim, Conflict
from scripts.v093_stage06_native_repair import VERSION, transform, validate_output, EVENTS
from scripts.v093_stage06_financial_repair import VERSION as FIN_VERSION, transform as fin_transform, validate_output as fin_validate
from scripts.v093_stage06_owner_replay import replay_one
from scripts.v093_stage06_coverage import reconcile_raw_snapshot, coverage_snapshot

PLAN_PATH = Path(__file__).resolve().parents[1]/'config/v093_stage06_repair_plan_20261022.json'
DEPLOYMENT = 'USER_AUTHORIZED_STAGE06_LIVE_20261022_V1'
RULE_VERSION = 'LIVE_NATIVE_STAGING_RULES_V1'
POOL = 'POOL_STAGE06_REPAIR_V1'
ROOT_NAME = 'RECONCILE_REPAIR'
SUPPORTED = set(EVENTS) | {('TPEx', 'indices')}
FIN_SUPPORTED = {('MOPS',report) for report in ('IncomeStatement','BalanceSheet','CashflowStatement')}
ADAPTERS = {'PRICE':(VERSION,transform,validate_output),'FINANCIAL':(FIN_VERSION,fin_transform,fin_validate)}

def supported_version(stage,unit):
    scope = SUPPORTED if stage=='PRICE' else FIN_SUPPORTED if stage=='FINANCIAL' else set()
    return ADAPTERS[stage][0] if (unit['source'],unit['dataset']) in scope else None


class ReconcileBudgetEnded(RuntimeError): pass


def authorized():
    plan = json.loads(PLAN_PATH.read_text())
    if plan.get('enabled') is not True or plan.get('live_deployment_id') != DEPLOYMENT or plan.get('activation_authorized') is not True:
        raise ValueError('LIVE_STAGE06_NOT_AUTHORIZED')
    if plan['scope']['start_month'] != '2026-10' or plan['scope']['end_month'] != '2000-01':
        raise ValueError('LIVE_STAGE06_SCOPE_CHANGED')
    return plan


def queue_path(stage, month):
    if stage not in base.STAGES or month not in base.MONTHS:
        raise ValueError('INVALID_LIVE_QUEUE_SHARD')
    return '.github/live-state/stage06-live-'+stage.lower()+'-'+month+'.json'


class LiveDriveArtifacts(DriveImmutableArtifacts):
    scope = 'LIVE_REPAIR_ONLY'
    backend = 'GOOGLE_DRIVE_IMMUTABLE_LIVE_REPAIR'

    def __init__(self, api, parent):
        authorized()
        meta = api.files().get(fileId=parent, fields='id,mimeType,appProperties').execute(num_retries=0)
        props = meta.get('appProperties', {})
        if meta.get('mimeType') != 'application/vnd.google-apps.folder' or props.get('jarvis_stage06_scope') != self.scope or props.get('deployment') != DEPLOYMENT:
            raise ValueError('AUTHORIZED_LIVE_REPAIR_FOLDER_REQUIRED')
        self.api, self.parent, self.verified = api, parent, {}


def approval(stage='PRICE'):
    if stage=='FINANCIAL':
        return digest(dict(deployment=DEPLOYMENT,processor=FIN_VERSION,scope='NATIVE_FINANCIAL_STAGING_ONLY',
            real_raw_units_validated=14,native_cells_compared=13276,
            validation_evidence_sha256=json.loads(PLAN_PATH.read_text())['financial_validation_evidence_sha256'],analysis_approval=False))
    return digest(dict(deployment=DEPLOYMENT, processor=VERSION, scope='NATIVE_STAGING_ONLY',
        validated_cloud_run=39724099017, analysis_approval=False))


def reconcile_snapshot(snapshot, stage, month_state, registry):
    """Batch a producer update locally, then publish it as one fenced CAS."""
    with tempfile.TemporaryDirectory() as tmp:
        store = FileStore(Path(tmp)/'ledger.json'); store.cas(None, copy.deepcopy(snapshot))
        ledger = Ledger(store)
        import_quarantine(ledger, stage, month_state)
        for row in month_state.get('units', {}).values():
            if row.get('status') != 'QUARANTINED': continue
            for hold in list(ledger.snapshot().get('import_holds', {}).values()):
                if hold['status'] != 'IDENTITY_RECONCILIATION_REQUIRED' or hold['receipt_sha256'] != digest(row): continue
                try: ledger.reconcile_identity(hold['hold_id'], row, registry, digest(registry))
                except (ValueError, KeyError, TypeError): pass
        if stage in ADAPTERS: ledger.approve_version(stage, ADAPTERS[stage][0], approval(stage))
        for gap in list(ledger.snapshot()['gaps'].values()):
            if gap['status'] == 'RESOLVED': continue
            unit = gap['unit']
            if gap['kind'] in ('RAW_MISSING', 'RAW_CORRUPT'):
                # No guessed attempt counts, expected calendar, or automatic
                # cross-source substitution. RAW ownership remains unchanged.
                continue
            supported = supported_version(stage,unit)
            if not supported and gap['task_ids']:continue
            version = supported or 'UNAPPROVED_'+stage+'_REPAIR_V1'
            ledger.enqueue(gap['gap_id'], gap['evidence_sha256'], version, RULE_VERSION)
        result = ledger.snapshot()
        result.update(deployment=DEPLOYMENT, test_only=False, production_data_approved=False,
                      expected_coverage='UNKNOWN', raw_fetch_binding_enabled=False)
        return result


def folders(d, parent):
    if not parent: return {}
    return {f['name']:f['id'] for f in native.listing(d, parent) if f['mimeType']=='application/vnd.google-apps.folder'}


def input_records(upstream):
    return [r for bucket in ('units', 'financial_units') for r in upstream.get(bucket, {}).values()
            if r.get('status')=='SAVED_BASIC_VERIFIED' and r.get('evidence_file')]


class Reconciler:
    def __init__(self, minutes=60):
        self.plan = authorized(); self.until = time.monotonic()+minutes*60
        self.repo, self.token = os.environ['GITHUB_REPOSITORY'], os.environ['GH_TOKEN']
        self.owner = os.environ['GITHUB_RUN_ID']+'/RECONCILE'
        self.lease_url = 'https://api.github.com/repos/'+self.repo+'/contents/.github/live-state/five-stage-leases.json'
        self.fence = acquire(self.lease_url, self.token, POOL, self.owner, ttl=5400)
        try:
            self.d = Drive(service()); self.control = self.d.folder(native.REPORT_ROOT, base.RUN)
            self.root = self.d.folder(self.control, ROOT_NAME)
            self.runtime = Ledger(self.store('.github/live-state/stage06-live-control.json'))
            self.refresh_inputs()
        except Exception:
            commit(self.lease_url,self.token,POOL,self.owner,self.fence,digest('INITIALIZATION_FAILED'))
            raise

    def store(self, path):
        return FencedGitHubStore(self.repo, path, self.token, 'RECONCILE', POOL, self.owner, self.fence,read_cache_seconds=30)

    def refresh_inputs(self):
        roots = folders(self.d, self.control)
        self.months = {stage:folders(self.d, roots.get(stage)) for stage in base.STAGES}
        qa_index = self.d.find(roots['QA1'], 'RAW_INDEX') if roots.get('QA1') else None
        self.indices = folders(self.d, qa_index['id'] if qa_index else None)

    def wait_for_recheck(self, seconds):
        """Bounded polling interval under the same lease; never spin empty months."""
        if time.monotonic()+seconds >= self.until-45:
            return False
        wake = time.monotonic()+seconds
        while time.monotonic() < wake:
            self.guard()
            delay=max(0,min(30, wake-time.monotonic()))
            if delay:time.sleep(delay)
        return time.monotonic() < self.until-45

    def guard(self):
        if time.monotonic() >= self.until-45: raise ReconcileBudgetEnded('RECONCILER_BUDGET_ENDED')
        self.runtime.snapshot()

    def artifact_folder(self, stage, month):
        name = 'ARTIFACTS_'+stage+'_'+month
        old = self.d.find(self.root, name)
        if old:
            LiveDriveArtifacts(self.d.api, old['id']); return old['id']
        self.guard()
        return self.d.api.files().create(body=dict(name=name, parents=[self.root],
            mimeType='application/vnd.google-apps.folder', appProperties=dict(
                jarvis_stage06_scope='LIVE_REPAIR_ONLY', deployment=DEPLOYMENT)), fields='id').execute(num_retries=0)['id']

    def month(self, month):
        registry = [];raw_states=[]
        for folder in (self.indices.get(month), self.months['RAW'].get(month)):
            if folder:
                raw_state=engine.getj(self.d,folder,'MONTH_STATE.json') or {}
                raw_states.append(raw_state);registry.extend(input_records(raw_state))
        # Identical native index entries across RAW and QA are the same proof.
        registry = list({digest(r):r for r in registry}.values())
        unique = {}
        for r in registry:
            key = r['unit_id']+'_'+r['sha256']
            if key not in unique: unique[key] = r
        registry = list(unique.values())
        issues=[{'kind':'RAW_INVENTORY_PENDING','count':len(st.get('inventory_errors',[]))} for st in raw_states if st.get('inventory_errors')]
        if month[-2:] in ('03','06','09','12'):
            for report_type in ('IncomeStatement','BalanceSheet','CashflowStatement'):
                if not any(r.get('source')=='MOPS' and r.get('category')==report_type for r in registry):
                    issues.append({'kind':'FINANCIAL_DATASET_NOT_INDEXED_SCOPE_UNVERIFIED','dataset':report_type})
        reports = {'_coverage':coverage_snapshot(registry,issues)}
        if any(st.get('legacy_missing_units') for st in raw_states) or any(any(r.get('status')!='SAVED_BASIC_VERIFIED' for r in st.get(b,{}).values()) for st in raw_states for b in ('units','financial_units','finmind_units')):
            raw_queue=Ledger(self.store(queue_path('RAW',month)))
            def raw_update(doc,now):
                new=reconcile_raw_snapshot(doc,raw_states);doc.clear();doc.update(new)
            raw_queue.transaction(raw_update);reports['RAW']=summary(raw_queue.snapshot())
        for stage in ('QA1', 'PRICE', 'FINANCIAL', 'CHIP'):
            folder = self.months[stage].get(month)
            if not folder: continue
            self.guard()
            state = engine.getj(self.d, folder, 'MONTH_STATE.json') or {}
            if not any(r.get('status')=='QUARANTINED' for r in state.get('units',{}).values()): continue
            # Input references remain private. The immutable RAW hash is also
            # bound into the public task; a changed locator cannot change bytes.
            input_name='INPUTS_'+stage+'_'+month+'.json'
            if engine.getj(self.d,self.root,input_name) != registry:
                self.d.put(self.root, input_name,
                    json.dumps(registry, sort_keys=True).encode(), 'application/json', overwrite=True)
            if stage in ADAPTERS: self.artifact_folder(stage, month)
            queue = Ledger(self.store(queue_path(stage, month)))
            def update(doc, now):
                new = reconcile_snapshot(doc, stage, state, registry)
                doc.clear(); doc.update(new)
            queue.transaction(update)
            reports[stage] = dict(summary(queue.snapshot()),owner_runtime_integrated=stage in ADAPTERS,
                snapshot_scope='AT_IMPORT_NOT_LIVE_TASK_COUNT')
        return reports

    def run(self, max_months=0, continuous=False, recheck_seconds=300):
        if not 30 <= recheck_seconds <= 900:
            raise ValueError('INVALID_RECHECK_INTERVAL')
        count = 0; last = None;control=None;last_saved=0
        cycles = 0
        try:
            revision='INDEPENDENT_STAGE06_20261022_V2'
            previous=self.runtime.snapshot().get('control',{})
            if previous.get('independent_revision')!=revision:
                def restart(doc,now):
                    doc['prior_independent_checkpoint']=copy.deepcopy(doc.get('control',{}))
                    doc['control']=dict(month_index=0,independent_revision=revision)
                self.runtime.transaction(restart)
            index = self.runtime.snapshot().get('control',{}).get('month_index',0)
            if index >= len(base.MONTHS): index = 0
            while time.monotonic() < self.until-45:
                if self.runtime.store.remaining is not None and self.runtime.store.remaining<200:break
                if index >= len(base.MONTHS):
                    if not continuous:break
                    control = dict(self.runtime.snapshot().get('control',{}),
                        phase='WAITING_RECHECK', continuous=True, next_month=base.MONTHS[0],
                        recheck_seconds=recheck_seconds, cycles_completed_this_run=cycles,
                        updated_utc=native.stamp(), run=os.environ['GITHUB_RUN_ID'])
                    self.runtime.transaction(lambda doc,now:doc.update(control=control))
                    self.d.put(self.root, 'STATUS.json',json.dumps(dict(status='WAITING_RECHECK',
                        control=control,production_data_approved=False),sort_keys=True).encode(),
                        'application/json',overwrite=True)
                    print('STAGE06_LIVE_WAIT_RECHECK '+json.dumps(control,sort_keys=True),flush=True)
                    if not self.wait_for_recheck(recheck_seconds):break
                    self.refresh_inputs()
                    index = 0
                month = base.MONTHS[index]
                try: result = self.month(month)
                except ReconcileBudgetEnded: break
                except Conflict:
                    # Another independent writer won the branch. Retry this month
                    # from fresh receipts; never advance its persistent cursor.
                    print('STAGE06_CAS_CONTENTION_RETRY_SAME_MONTH '+month,flush=True)
                    time.sleep(5)
                    continue
                index += 1; count += 1; last = month
                if index == len(base.MONTHS):cycles += 1
                control = dict(month_index=index, last_scanned_month=month,independent_revision=revision,
                    next_month=base.MONTHS[index] if index<len(base.MONTHS) else (base.MONTHS[0] if continuous else None),
                    phase='SWEEP_COMPLETE' if index==len(base.MONTHS) else 'SCANNING',
                    continuous=continuous,recheck_seconds=recheck_seconds,
                    cycles_completed_this_run=cycles,
                    updated_utc=native.stamp(), direction='NEWEST_TO_OLDEST',
                    scope_start='2026-10', scope_end='2000-01', run=os.environ['GITHUB_RUN_ID'],
                    last_month_result=result, coverage_certified=False)
                material=any(stage in result for stage in base.STAGES)
                if material or index%12==0 or index==len(base.MONTHS) or (max_months and count>=max_months):
                    self.runtime.transaction(lambda doc,now:doc.update(control=control));last_saved=count
                print('STAGE06_LIVE_PROGRESS '+json.dumps(control, sort_keys=True), flush=True)
                if max_months and count >= max_months: break
            if control and count!=last_saved:self.runtime.transaction(lambda doc,now:doc.update(control=control))
            state = self.runtime.snapshot()
            result = dict(status='LIVE_RECONCILING_AND_APPROVED_REPAIR_QUEUE', months_scanned_this_run=count,
                continuous=continuous,cycles_completed_this_run=cycles,
                last_scanned_month=last, control=state.get('control'), production_data_approved=False,
                raw_fetch_binding_enabled=False, supported_repairs=sorted([list(x) for x in SUPPORTED|FIN_SUPPORTED]),
                ultimate_goal='ALL_DATABASE_DATA_RECONCILED_REPAIRED_AND_VERIFIED',scope_is_not_limited_to_supported_adapters=True)
            self.d.put(self.root, 'STATUS.json', json.dumps(result, sort_keys=True).encode(), 'application/json', overwrite=True)
            print('STAGE06_LIVE_RESULT '+json.dumps(result, sort_keys=True), flush=True)
            return result
        finally:
            commit(self.lease_url, self.token, POOL, self.owner, self.fence, digest(dict(months=count,last=last)))


def repair_owner(worker, minutes=6, only_month=None):
    """Called by PRICE's real worker, under its existing owner/fence only."""
    plan = json.loads(PLAN_PATH.read_text())
    report = dict(status='DISABLED_OR_UNSUPPORTED_OWNER', completed=0, failed=0, deferred=0)
    if not plan.get('enabled') or worker.stage not in ADAPTERS: return report
    stage=worker.stage; version,transform_fn,validate_fn=ADAPTERS[stage]
    authorized()
    from scripts.v093_replanned_five_stage import cached_payload
    original_cursor = copy.deepcopy(worker.cursor); original_until = worker.until
    limit = min(worker.until-45, time.monotonic()+minutes*60)
    read_control=getattr(worker,'primary_control',worker.control)
    root = worker.d.find(read_control, ROOT_NAME)
    if not root: return report
    listing = native.listing(worker.d,root['id'])
    available = {f['name']:f['id'] for f in listing if f['mimeType']=='application/vnd.google-apps.folder'}
    input_months = {f['name'][len('INPUTS_'+stage+'_'):-5] for f in listing if f['name'].startswith('INPUTS_'+stage+'_') and f['name'].endswith('.json')}
    report['status'] = 'LIVE_OWNER_REPAIR_ACTIVE'
    for month in base.MONTHS:
        if only_month and month!=only_month:continue
        if time.monotonic() >= limit:break
        name = 'ARTIFACTS_'+stage+'_'+month
        if name not in available and month not in input_months:continue
        ledger = Ledger(FencedGitHubStore(os.environ['GITHUB_REPOSITORY'], queue_path(stage,month),
            worker.token, stage, worker.lock, worker.owner, worker.fence,read_cache_seconds=30))
        records_list = engine.getj(worker.d, root['id'], 'INPUTS_'+stage+'_'+month+'.json') or []
        # The owner can upgrade previously blocked tasks with the tested version.
        # This does not move the reconciler or primary worker cursor.
        source_stage=worker.d.find(read_control,stage)
        source_folder=worker.d.find(source_stage['id'],month) if source_stage else None
        source_state=engine.getj(worker.d,source_folder['id'],'MONTH_STATE.json') if source_folder else {}
        def upgrade(doc,now):
            new=reconcile_snapshot(doc,stage,source_state or {},records_list);doc.clear();doc.update(new)
        ledger.transaction(upgrade)
        if name not in available:
            worker.owned()
            available[name]=worker.d.api.files().create(body=dict(name=name,parents=[root['id']],
                mimeType='application/vnd.google-apps.folder',appProperties=dict(jarvis_stage06_scope='LIVE_REPAIR_ONLY',deployment=DEPLOYMENT)),fields='id').execute(num_retries=0)['id']
        artifacts = LiveDriveArtifacts(worker.d.api, available[name])
        records = {r['unit_id']+'_'+r['sha256']:r for r in records_list}
        def guard():
            worker.owned()
            if worker.cursor != original_cursor or worker.until != original_until: raise ValueError('PRIMARY_CURSOR_OR_BUDGET_CHANGED')
            if time.monotonic() >= limit: raise TimeoutError('LIVE_REPAIR_BUDGET_ENDED')
        def read_input(unit):
            matches = [g for g in ledger.snapshot()['gaps'].values() if g['unit']==unit and g['status']!='RESOLVED']
            expected = {g['evidence_sha256'] for g in matches}
            if len(expected)!=1: raise ValueError('RAW_HASH_IDENTITY_AMBIGUOUS')
            receipt = records[unit['native_unit_id']+'_'+next(iter(expected))]
            return cached_payload(worker.d, receipt, worker.cache)[0]
        while time.monotonic() < limit:
            if ledger.store.remaining is not None and ledger.store.remaining<120:
                report['deferred']+=1;break
            try:
                task = replay_one(ledger, stage, worker.owner, version, RULE_VERSION,
                    read_input, transform_fn, validate_fn, artifacts, guard,
                    ttl=max(1,min(5400,int(limit-time.monotonic())+30)))
                if task is None: break
                report['completed'] += int(task['status']=='DONE')
                print('STAGE06_LIVE_OWNER_RECEIPT '+json.dumps(dict(month=month,task_id=task['task_id'],
                    status=task['status'], output_sha256=task['receipt']['output_sha256'])), flush=True)
            except (ValueError, KeyError, TypeError) as exc:
                report['failed'] += 1
                print('STAGE06_LIVE_OWNER_HOLD '+json.dumps(dict(month=month,error=type(exc).__name__+':'+str(exc)[:180])),flush=True)
            except TimeoutError:
                for pending in ledger.snapshot()['tasks'].values():
                    if pending['status']=='CLAIMED' and pending.get('claim',{}).get('worker')==worker.owner:
                        try:ledger.release(pending['task_id'],worker.owner,pending['fence'])
                        except StaleClaim:pass
                report['deferred'] += 1; break
            except Conflict:
                # A stored candidate/claim may exist. Preserve it for exact replay.
                # The ledger never turns a conflicted publication into DONE.
                report['deferred'] += 1
                print('STAGE06_LIVE_OWNER_DEFER_CAS_CONFLICT '+json.dumps(dict(month=month)),flush=True)
                report['status']='DEFERRED_CAS_CONTENTION'
                print('STAGE06_LIVE_OWNER_RESULT '+json.dumps(report,sort_keys=True),flush=True)
                return report
    if worker.cursor != original_cursor or worker.until != original_until: raise ValueError('PRIMARY_CURSOR_OR_BUDGET_CHANGED')
    print('STAGE06_LIVE_OWNER_RESULT '+json.dumps(report,sort_keys=True),flush=True)
    return report



def cutover_price(stage='PRICE'):
    """One-time authorized restart: only retire a lease after its run is terminal."""
    authorized()
    if stage not in ADAPTERS:raise ValueError('UNSUPPORTED_CUTOVER_STAGE')
    repo,token=os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN']
    url='https://api.github.com/repos/'+repo+'/contents/.github/live-state/five-stage-leases.json'
    from scripts.v093_replanned_five_stage import lease_suffix_for
    key='POOL_CONSUMER'+lease_suffix_for(stage)
    _,state=_read(url,token);lease=state.get('jobs',{}).get(key,{}).get('lease') or {}
    if not lease:return
    owner=lease.get('owner','')
    if not re.fullmatch(r'[0-9]+/'+stage,owner):raise ValueError('UNRECOGNIZED_PRICE_OWNER_NO_CUTOVER')
    run=owner.split('/')[0]
    def api(method,path):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,method=method,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            body=response.read();return json.loads(body) if body else {}
    current=api('GET','/actions/runs/'+run)
    expected_workflow={'PRICE':'.github/workflows/v093-v2-03-price.yml','FINANCIAL':'.github/workflows/v093-v2-04-financial.yml'}[stage]
    if current.get('path')!=expected_workflow:raise ValueError('PRICE_WORKFLOW_IDENTITY_MISMATCH')
    if current['status']!='completed':
        api('POST','/actions/runs/'+run+'/cancel')
        for _ in range(24):
            time.sleep(5)
            current=api('GET','/actions/runs/'+run)
            if current['status']=='completed':break
    if current['status']!='completed':raise ValueError('OLD_PRICE_RUN_NOT_TERMINAL_LEASE_PRESERVED')
    _,latest=_read(url,token);active=latest.get('jobs',{}).get(key,{}).get('lease') or {}
    if active!=lease:return  # A successor or the old worker already released it.
    if lease['expires_at']>time.time():
        commit(url,token,key,owner,lease['fence'],digest(dict(reason='USER_STAGE06_LIVE_CUTOVER',old_run=run)))
    print('STAGE06_PRICE_CUTOVER_TERMINAL_CONFIRMED '+run,flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--minutes',type=float,default=60)
    p.add_argument('--max-months',type=int,default=0); p.add_argument('--owner-price',action='store_true')
    p.add_argument('--cutover-price','--cutover-owner',dest='cutover_price',action='store_true')
    p.add_argument('--continuous',action='store_true')
    p.add_argument('--recheck-seconds',type=int,default=300)
    p.add_argument('--owner-stage',choices=sorted(ADAPTERS));p.add_argument('--owner-month',choices=base.MONTHS)
    a = p.parse_args()
    if not .1 <= a.minutes <= 60 or a.max_months < 0: raise ValueError('INVALID_BUDGET')
    if not 30 <= a.recheck_seconds <= 900:raise ValueError('INVALID_RECHECK_INTERVAL')
    if a.owner_price or a.owner_stage:
        stage=a.owner_stage or 'PRICE'
        if a.cutover_price: cutover_price(stage)
        from scripts.v093_replanned_five_stage import Worker
        try: worker = Worker(stage, a.minutes, stage06=True)
        except LeaseBusy:
            print('STAGE06_LIVE_OWNER_WAIT_EXISTING_PRICE_WORKER',flush=True); return
        try: repair_owner(worker, a.minutes, a.owner_month)
        finally: commit(worker.api,worker.token,worker.lock,worker.owner,worker.fence,digest('STAGE06_OWNER_RUN_FINISHED'))
    else:
        try: Reconciler(a.minutes).run(a.max_months,a.continuous,a.recheck_seconds)
        except LeaseBusy: print('STAGE06_LIVE_WAIT_EXISTING_RECONCILER',flush=True)


if __name__=='__main__': main()
