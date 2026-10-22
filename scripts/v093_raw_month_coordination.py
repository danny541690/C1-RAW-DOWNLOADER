"""Coordinate opposite RAW history workers without sharing their cursors."""
import re
from scripts.v093_five_stage_durable_gate import acquire, commit, LeaseBusy


def capture_history_month(worker, month, quota=None, can_start=None):
    if not re.fullmatch(r'20[0-9]{2}-(0[1-9]|1[0-2])',month):
        raise ValueError('INVALID_HISTORY_MONTH')
    key='RAW_HISTORY_MONTH_'+month.replace('-','_')
    try:
        fence=acquire(worker.api,worker.token,key,worker.owner,ttl=5400)
    except LeaseBusy:
        return False
    try:
        # The opposing frontier may have moved while the lease was acquired.
        if can_start is not None and not can_start():return False
        return worker.capture_month(month,quota=quota)
    finally:
        commit(worker.api,worker.token,key,worker.owner,fence,'0'*64)
