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
from scripts.v093_stage06_ledger import FileStore, Ledger, digest, import_quarantine, summary, StaleClaim
from scripts.v093_stage06_native_repair import VERSION, transform, validate_output, EVENTS
from scripts.v093_stage06_owner_replay import replay_one

PLAN_PATH = Path(__file__).resolve().parents[1]/'config/v093_stage06_repair_plan_20261022.json'
DEPLOYMENT = 'USER_AUTHORIZED_STAGE06_LIVE_20261022_V1'
RULE_VERSION = 'LIVE_NATIVE_STAGING_RULES_V1'
POOL = 'POOL_STAGE06_REPAIR_V1'
ROOT_NAME = 'RECONCILE_REPAIR'
SUPPORTED = set(EVENTS) | {('TPEx', 'indices')}


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


def approval():
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
        if stage == 'PRICE': ledger.approve_version('PRICE', VERSION, approval())
        for gap in list(ledger.snapshot()['gaps'].values()):
            if gap['status'] == 'RESOLVED' or gap['task_ids']: continue
            unit = gap['unit']
            if gap['kind'] in ('RAW_MISSING', 'RAW_CORRUPT'):
                # No guessed attempt counts, expected calendar, or automatic
                # cross-source substitution. RAW ownership remains unchanged.
                continue
            supported = stage == 'PRICE' and (unit['source'], unit['dataset']) in SUPPORTED
            version = VERSION if supported else 'UNAPPROVED_'+stage+'_REPAIR_V1'
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
            roots = folders(self.d, self.control)
            self.months = {stage:folders(self.d, roots.get(stage)) for stage in base.STAGES}
            qa_index = self.d.find(roots['QA1'], 'RAW_INDEX') if roots.get('QA1') else None
            self.indices = folders(self.d, qa_index['id'] if qa_index else None)
        except Exception:
            commit(self.lease_url,self.token,POOL,self.owner,self.fence,digest('INITIALIZATION_FAILED'))
            raise

    def store(self, path):
        return FencedGitHubStore(self.repo, path, self.token, 'RECONCILE', POOL, self.owner, self.fence)

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
        registry = []
        for folder in (self.indices.get(month), self.months['RAW'].get(month)):
            if folder: registry.extend(input_records(engine.getj(self.d, folder, 'MONTH_STATE.json') or {}))
        # Identical native index entries across RAW and QA are the same proof.
        registry = list({digest(r):r for r in registry}.values())
        unique = {}
        for r in registry:
            key = r['unit_id']+'_'+r['sha256']
            if key not in unique: unique[key] = r
        registry = list(unique.values())
        reports = {}
        for stage in ('QA1', 'PRICE', 'FINANCIAL', 'CHIP'):
            folder = self.months[stage].get(month)
            if not folder: continue
            self.guard()
            state = engine.getj(self.d, folder, 'MONTH_STATE.json') or {}
            if not any(r.get('status')=='QUARANTINED' for r in state.get('units',{}).values()): continue
            # Input references remain private. The immutable RAW hash is also
            # bound into the public task; a changed locator cannot change bytes.
            self.d.put(self.root, 'INPUTS_'+stage+'_'+month+'.json',
                json.dumps(registry, sort_keys=True).encode(), 'application/json', overwrite=True)
            if stage == 'PRICE': self.artifact_folder(stage, month)
            queue = Ledger(self.store(queue_path(stage, month)))
            def update(doc, now):
                new = reconcile_snapshot(doc, stage, state, registry)
                doc.clear(); doc.update(new)
            queue.transaction(update)
            reports[stage] = summary(queue.snapshot())
        return reports

    def run(self, max_months=0):
        count = 0; last = None
        try:
            index = self.runtime.snapshot().get('control',{}).get('month_index',0)
            if index >= len(base.MONTHS): index = 0
            while index < len(base.MONTHS) and time.monotonic() < self.until-45:
                month = base.MONTHS[index]
                try: result = self.month(month)
                except ReconcileBudgetEnded: break
                index += 1; count += 1; last = month
                control = dict(month_index=index, last_scanned_month=month,
                    next_month=base.MONTHS[index] if index<len(base.MONTHS) else None,
                    updated_utc=native.stamp(), direction='NEWEST_TO_OLDEST',
                    scope_start='2026-10', scope_end='2000-01', run=os.environ['GITHUB_RUN_ID'],
                    last_month_result=result, coverage_certified=False)
                self.runtime.transaction(lambda doc, now: doc.update(control=control))
                print('STAGE06_LIVE_PROGRESS '+json.dumps(control, sort_keys=True), flush=True)
                if max_months and count >= max_months: break
            state = self.runtime.snapshot()
            result = dict(status='LIVE_RECONCILING_AND_APPROVED_REPAIR_QUEUE', months_scanned_this_run=count,
                last_scanned_month=last, control=state.get('control'), production_data_approved=False,
                raw_fetch_binding_enabled=False, supported_repairs=sorted([list(x) for x in SUPPORTED]))
            self.d.put(self.root, 'STATUS.json', json.dumps(result, sort_keys=True).encode(), 'application/json', overwrite=True)
            print('STAGE06_LIVE_RESULT '+json.dumps(result, sort_keys=True), flush=True)
            return result
        finally:
            commit(self.lease_url, self.token, POOL, self.owner, self.fence, digest(dict(months=count,last=last)))


def repair_owner(worker, minutes=6):
    """Called by PRICE's real worker, under its existing owner/fence only."""
    plan = json.loads(PLAN_PATH.read_text())
    report = dict(status='DISABLED_OR_UNSUPPORTED_OWNER', completed=0, failed=0, deferred=0)
    if not plan.get('enabled') or worker.stage != 'PRICE': return report
    authorized()
    from scripts.v093_replanned_five_stage import cached_payload
    original_cursor = copy.deepcopy(worker.cursor); original_until = worker.until
    limit = min(worker.until-45, time.monotonic()+minutes*60)
    root = worker.d.find(worker.control, ROOT_NAME)
    if not root: return report
    available = folders(worker.d, root['id'])
    report['status'] = 'LIVE_OWNER_REPAIR_ACTIVE'
    for month in base.MONTHS:
        name = 'ARTIFACTS_PRICE_'+month
        if name not in available or time.monotonic() >= limit: continue
        ledger = Ledger(FencedGitHubStore(os.environ['GITHUB_REPOSITORY'], queue_path('PRICE',month),
            worker.token, 'PRICE', worker.lock, worker.owner, worker.fence))
        artifacts = LiveDriveArtifacts(worker.d.api, available[name])
        records = engine.getj(worker.d, root['id'], 'INPUTS_PRICE_'+month+'.json') or []
        records = {r['unit_id']+'_'+r['sha256']:r for r in records}
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
            try:
                task = replay_one(ledger, 'PRICE', worker.owner, VERSION, RULE_VERSION,
                    read_input, transform, validate_output, artifacts, guard,
                    ttl=max(1,min(5400,int(limit-time.monotonic())+30)))
                if task is None: break
                report['completed'] += int(task['status']=='DONE')
                print('STAGE06_LIVE_OWNER_RECEIPT '+json.dumps(dict(month=month,task_id=task['task_id'],
                    status=task['status'], output_sha256=task['receipt']['output_sha256'])), flush=True)
            except (ValueError, KeyError, TypeError) as exc:
                report['failed'] += 1
                print('STAGE06_LIVE_OWNER_HOLD '+json.dumps(dict(month=month,error=type(exc).__name__+':'+str(exc)[:180])),flush=True)
            except TimeoutError:
                report['deferred'] += 1; break
    if worker.cursor != original_cursor or worker.until != original_until: raise ValueError('PRIMARY_CURSOR_OR_BUDGET_CHANGED')
    print('STAGE06_LIVE_OWNER_RESULT '+json.dumps(report,sort_keys=True),flush=True)
    return report



def cutover_price():
    """One-time authorized restart: only retire a lease after its run is terminal."""
    authorized()
    repo,token=os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN']
    url='https://api.github.com/repos/'+repo+'/contents/.github/live-state/five-stage-leases.json'
    from scripts.v093_replanned_five_stage import lease_suffix_for
    key='POOL_CONSUMER'+lease_suffix_for('PRICE')
    _,state=_read(url,token);lease=state.get('jobs',{}).get(key,{}).get('lease') or {}
    if not lease:return
    owner=lease.get('owner','')
    if not re.fullmatch(r'[0-9]+/PRICE',owner):raise ValueError('UNRECOGNIZED_PRICE_OWNER_NO_CUTOVER')
    run=owner.split('/')[0]
    def api(method,path):
        req=urllib.request.Request('https://api.github.com/repos/'+repo+path,method=method,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=30) as response:
            body=response.read();return json.loads(body) if body else {}
    current=api('GET','/actions/runs/'+run)
    if current.get('path')!='.github/workflows/v093-v2-03-price.yml':raise ValueError('PRICE_WORKFLOW_IDENTITY_MISMATCH')
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
    p.add_argument('--cutover-price',action='store_true')
    a = p.parse_args()
    if not .1 <= a.minutes <= 60 or a.max_months < 0: raise ValueError('INVALID_BUDGET')
    if a.owner_price:
        if a.cutover_price: cutover_price()
        from scripts.v093_replanned_five_stage import Worker
        try: worker = Worker('PRICE', a.minutes)
        except LeaseBusy:
            print('STAGE06_LIVE_OWNER_WAIT_EXISTING_PRICE_WORKER',flush=True); return
        try: repair_owner(worker, a.minutes)
        finally: commit(worker.api,worker.token,worker.lock,worker.owner,worker.fence,digest('STAGE06_OWNER_RUN_FINISHED'))
    else:
        try: Reconciler(a.minutes).run(a.max_months)
        except LeaseBusy: print('STAGE06_LIVE_WAIT_EXISTING_RECONCILER',flush=True)


if __name__=='__main__': main()
