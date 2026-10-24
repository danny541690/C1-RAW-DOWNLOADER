"""Persistent repair frontier election; CAS decides one owner before any RAW write.

Month ownership is sticky across runs. It is not a certification of completeness.
The existing fenced RAW month lease is still required for all data mutations.
"""
import copy
import time
from scripts.v093_five_stage_durable_gate import _read, _put, LeaseConflict

PLAN = 'REPAIR_FOUR_FRONTIERS_20261024_V1'
LANES = {
    'EARLY_ASC': ('2000-01', '2012-12', 'ASC'),
    'EARLY_DESC': ('2000-01', '2012-12', 'DESC'),
    'RECENT_ASC': ('2013-01', '2026-10', 'ASC'),
    'RECENT_DESC': ('2013-01', '2026-10', 'DESC'),
}

def lane_months(lane):
    lower, upper, direction = LANES[lane]
    months = [f'{year}-{month:02d}' for year in range(2000, 2027)
              for month in range(1, 13) if lower <= f'{year}-{month:02d}' <= upper]
    return months if direction == 'ASC' else months[::-1]

def elect(state, lane, month):
    if lane not in LANES or month not in lane_months(lane):
        raise ValueError('INVALID_REPAIR_LANE_OR_MONTH')
    state = copy.deepcopy(state)
    if state.get('plan', PLAN) != PLAN:
        raise ValueError('REPAIR_COORDINATION_PLAN_MISMATCH')
    state['plan'] = PLAN
    workers = state.setdefault('workers', {})
    claims = state.setdefault('months', {})
    worker = workers.setdefault(lane, {})
    if worker.get('status') == 'PAUSED_AT_MEETING':
        return state, False
    holder = claims.get(month)
    if holder and holder['lane'] != lane and workers.get(holder['lane'],{}).get('status')=='PAUSED_AT_MEETING':
        worker.update(status='FRONTIERS_MET_RANGE_VISITED_NOT_CERTIFIED',meeting_month=month,survivor=lane)
        return state,False
    if holder and holder['lane'] != lane:
        worker.update(status='PAUSED_AT_MEETING', meeting_month=month,
                      survivor=holder['lane'])
        # The survivor must resume this month, even across a batch timeout.
        return state, False
    claims.setdefault(month, {'lane': lane, 'status': 'CLAIMED_NOT_CERTIFIED'})
    worker.update(status='ACTIVE', active_month=month)
    return state, True

def claim_month(api, token, lane, month, retries=12):
    for _ in range(retries):
        sha, manifest = _read(api, token)
        state, allowed = elect(manifest['jobs'].get(PLAN, {}), lane, month)
        if state == manifest['jobs'].get(PLAN):
            return allowed, state['workers'][lane]
        manifest['jobs'][PLAN] = state
        if _put(api, token, sha, manifest, 'repair: elect one month owner and persist meeting pause'):
            return allowed, state['workers'][lane]
    raise LeaseConflict('REPAIR_FRONTIER_CAS_EXHAUSTED')

def reserve_source(api, token, source, now=None, interval=3, retries=12):
    """Four repair workers share one nonblocking per-source request window."""
    if source not in ('TWSE','TPEx','MOPS') or interval<=0:
        raise ValueError('INVALID_SOURCE_WINDOW')
    for _ in range(retries):
        instant=time.time() if now is None else now
        sha,manifest=_read(api,token)
        windows=manifest['jobs'].setdefault(PLAN+'_SOURCE_WINDOWS',{})
        if windows.get(source,0)>instant:return False
        windows[source]=instant+interval
        if _put(api,token,sha,manifest,'repair: reserve shared source request window'):return True
    raise LeaseConflict('REPAIR_SOURCE_WINDOW_CAS_EXHAUSTED')


def defer_source(api, token, source, seconds, now=None, retries=12):
    """Share a source error cooldown across workers without shortening it."""
    if source not in ('TWSE','TPEx','MOPS') or not 0 < seconds <= 86400:
        raise ValueError('INVALID_SOURCE_COOLDOWN')
    deadline=(time.time() if now is None else now)+seconds
    for _ in range(retries):
        sha,manifest=_read(api,token)
        windows=manifest['jobs'].setdefault(PLAN+'_SOURCE_WINDOWS',{})
        if windows.get(source,0)>=deadline:return windows[source]
        windows[source]=deadline
        if _put(api,token,sha,manifest,'repair: share source error cooldown across four lanes'):return deadline
    raise LeaseConflict('REPAIR_SOURCE_COOLDOWN_CAS_EXHAUSTED')
