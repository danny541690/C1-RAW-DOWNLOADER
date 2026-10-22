"""Bounded repair hook for the real worker; no runtime binding is enabled here."""
import copy
import time
from dataclasses import dataclass

from scripts.v093_stage06_ledger import StaleClaim
from scripts.v093_stage06_owner_replay import replay_one


class RepairBudgetExhausted(RuntimeError): pass


@dataclass
class RepairRuntime:
    ledger: object
    artifacts: object
    processor_version: str
    rule_version: str
    read_input: object
    transform: object
    validate_output: object
    enabled: bool = False
    test_only: bool = True
    budget_seconds: float = 0
    max_tasks: int = 1
    raw_replay: object = None


def run_pending_repairs(worker, runtime=None, monotonic=time.monotonic):
    runtime = runtime or getattr(worker, 'repair_runtime', None)
    report = dict(status='DISABLED_NOT_CONFIGURED', completed_tasks=[], failed=0, deferred=0, test_only=True)
    if runtime is None or not runtime.enabled:
        return report
    if runtime.test_only is not True:
        raise ValueError('LIVE_WORKER_REPAIR_BINDING_NOT_ACTIVATED')
    if runtime.budget_seconds <= 0 or type(runtime.max_tasks) is not int or runtime.max_tasks <= 0:
        raise ValueError('INVALID_REPAIR_RUNTIME_BUDGET')
    cursor = copy.deepcopy(worker.cursor)
    original_deadline = worker.until
    deadline = min(original_deadline, monotonic() + runtime.budget_seconds)
    store = runtime.ledger.store
    if getattr(store, 'owner_fenced', False):
        if (store.stage, store.owner, store.fence, store.lease_key) != (worker.stage, worker.owner, worker.fence, worker.lock):
            raise ValueError('WORKER_OWNER_FENCE_BINDING_MISMATCH')
    elif getattr(runtime.artifacts, 'requires_owner_fenced_store', False):
        raise ValueError('OWNER_FENCED_LEDGER_REQUIRED')

    def guard():
        worker.owned()
        if worker.cursor != cursor or worker.until != original_deadline:
            raise ValueError('REPAIR_MUST_NOT_CHANGE_PRIMARY_CURSOR_OR_BUDGET')
        if monotonic() >= deadline:
            raise RepairBudgetExhausted('REPAIR_BUDGET_ENDED')

    def defer_unfinished():
        for task in runtime.ledger.snapshot()['tasks'].values():
            if task['status'] == 'CLAIMED' and task['owner'] == worker.stage and task['claim']['worker'] == worker.owner:
                try:
                    runtime.ledger.release(task['task_id'], worker.owner, task['fence'])
                except ValueError as exc:
                    if str(exc) != 'UNRECONCILED_HTTP_INTENT': raise

    report['status'] = 'TEST_REPAIR_ACTIVE'
    for _ in range(runtime.max_tasks):
        if monotonic() >= deadline:
            report['deferred'] += 1; break
        try:
            guard()
            ttl = max(1, min(5400, int(deadline - monotonic()) + 30))
            if worker.stage == 'RAW':
                if runtime.raw_replay is None: raise ValueError('RAW_REPLAY_BINDING_REQUIRED')
                task = runtime.raw_replay(guard, ttl)
            else:
                def routed_input(unit):
                    if worker.stage!='QA1':
                        from scripts.v093_live_five_stage import route
                        if route(unit['dataset'])!=worker.stage:raise ValueError('REPAIR_DATASET_OWNER_MISMATCH')
                    return runtime.read_input(unit)
                task = replay_one(runtime.ledger, worker.stage, worker.owner, runtime.processor_version,
                    runtime.rule_version, routed_input, runtime.transform, runtime.validate_output,
                    runtime.artifacts, guard, ttl=ttl)
            if task is None: break
            if task['status'] == 'DONE': report['completed_tasks'].append(task)
            else: report['deferred'] += 1
        except RepairBudgetExhausted:
            defer_unfinished(); report['deferred'] += 1; break
        except StaleClaim:
            raise
        except OSError:
            # Without an acknowledged native hold, primary RAW work must not
            # proceed after an uncertain intent/persistence/transport failure.
            if worker.stage == 'RAW': raise
            report['deferred'] += 1; break
        except (ValueError, KeyError, TypeError):
            report['failed'] += 1
    if worker.cursor != cursor or worker.until != original_deadline:
        raise ValueError('REPAIR_MUST_NOT_CHANGE_PRIMARY_CURSOR_OR_BUDGET')
    return report
