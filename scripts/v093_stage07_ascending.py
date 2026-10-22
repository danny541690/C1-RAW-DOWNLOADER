"""Ascending RAW helper: own cursor, canonical RAW month receipts, stop on meeting."""
import argparse
import json
import time
from pathlib import Path
from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_replanned_five_stage import Worker, RAW_MONTHS, REVISION, lease_ttl_for
from scripts.v093_folder_registry import FolderRegistry
from scripts.v093_standard_r1 import C1
from scripts.v093_five_stage_durable_gate import commit, LeaseBusy
from scripts.v093_raw_month_coordination import capture_history_month

REVISION7='ASCENDING_RAW_200001_MEET_PRIMARY_V1'
MONTHS7=[f'{year}-{month:02d}' for year in range(2000,2013) for month in range(1,13)]
STOPPED={'STOPPED_MET_PRIMARY','STOPPED_PRIMARY_SCOPE_VISITED','STOPPED_UPPER_BOUND'}


def primary_frontier(cursor):
    if cursor.get('execution_plan')!=REVISION:
        raise ValueError('PRIMARY_CURSOR_PLAN_UNPROVEN')
    index=cursor.get('month_index')
    if type(index) is not int or not 0<=index<=len(RAW_MONTHS):
        raise ValueError('PRIMARY_CURSOR_INDEX_UNPROVEN')
    return RAW_MONTHS[index] if index<len(RAW_MONTHS) else None


class AscendingWorker(Worker):
    def __init__(self,minutes):
        base.Worker.__init__(self,'RAW',minutes,lease_suffix='_STAGE07_ASCENDING_V1',
                             lease_ttl=lease_ttl_for(minutes))
        try:
            self.primary_stagectrl=self.stagectrl
            self.stagectrl=self.d.folder(self.control,'RAW_ASCENDING')
            self.registry=FolderRegistry(self.d,self.d.folder(C1,'05_CONTROL'),namespace='LIVE_RAW_ASCENDING')
            self.cursor=engine.getj(self.d,self.stagectrl,'CURSOR.json') or dict(
                revision=REVISION7,month_index=0,status='ACTIVE',
                start_month='2000-01',end_month='2012-12',direction='OLDEST_TO_NEWEST')
            if self.cursor.get('revision')!=REVISION7:
                raise ValueError('ASCENDING_CURSOR_REVISION_MISMATCH')
            index=self.cursor.get('month_index')
            if type(index) is not int or not 0<=index<=len(MONTHS7):
                raise ValueError('ASCENDING_CURSOR_INDEX_UNPROVEN')
            self.phase='HISTORY_DOWNLOAD'
        except Exception:
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'STAGE07_INIT_FAILED'))
            raise

    def may_start(self,month):
        primary=engine.getj(self.d,self.primary_stagectrl,'CURSOR.json')
        if primary is None:raise ValueError('PRIMARY_CURSOR_NOT_FOUND')
        frontier=primary_frontier(primary)
        self.cursor['primary_next_month']=frontier
        if frontier is None:
            self.cursor.update(status='STOPPED_PRIMARY_SCOPE_VISITED',meeting_month=month)
            self.save_cursor()
            return False
        if month>=frontier:
            self.cursor.update(status='STOPPED_MET_PRIMARY',meeting_month=frontier)
            self.save_cursor()
            return False
        return True

    def run(self):
        try:
            # A meeting is durable. Later hourly invocations do no source downloads.
            while self.cursor.get('status') not in STOPPED and time.monotonic()<self.until:
                index=self.cursor['month_index']
                if index>=len(MONTHS7):
                    self.cursor['status']='STOPPED_UPPER_BOUND';break
                month=MONTHS7[index]
                if not self.may_start(month):break
                self.cursor.update(status='ACTIVE',last_month=month)
                self.save_cursor()
                complete=capture_history_month(self,month,can_start=lambda:self.may_start(month))
                if not complete:
                    if self.cursor.get('status') not in STOPPED:
                        self.cursor['status']='PARTIAL_OR_WAITING_MONTH_OWNER'
                    break
                self.cursor['month_index']+=1
                self.cursor['last_visited_month']=month
                self.save_cursor()
            if self.cursor['month_index']>=len(MONTHS7) and self.cursor.get('status') not in STOPPED:
                self.cursor['status']='STOPPED_UPPER_BOUND'
            self.cursor['next_month']=(MONTHS7[self.cursor['month_index']]
                if self.cursor['month_index']<len(MONTHS7) else None)
            self.save_cursor()
            report=dict(self.cursor,worker='STAGE07_RAW_ASCENDING',
                processed_this_run=self.processed,saved_this_run=self.saved,
                numeric_verified=False,pit_verified=False,coverage_certified=False,
                updated_utc=native.stamp(),run_id=self.owner)
            self.putj(self.stagectrl,'STATUS.json',report)
            print('STAGE07_RAW_ASCENDING '+json.dumps(report,sort_keys=True),flush=True)
            return report
        finally:
            commit(self.api,self.token,self.lock,self.owner,self.fence,native.sha(b'STAGE07_BATCH_ENDED'))


def main():
    p=argparse.ArgumentParser();p.add_argument('--minutes',type=float,default=60)
    args=p.parse_args()
    if not 1<=args.minutes<=60:raise ValueError('INVALID_BUDGET')
    plan=json.loads((Path(__file__).resolve().parents[1]/'config/v093_stage07_ascending.json').read_text())
    if (plan.get('enabled') is not True or plan.get('activation_authorized') is not True or
        plan.get('revision')!=REVISION7 or plan.get('start_month')!='2000-01' or
        plan.get('end_month')!='2012-12' or plan.get('stop_when_meeting_primary') is not True):
        raise ValueError('STAGE07_NOT_AUTHORIZED')
    base.load_policy()
    try:AscendingWorker(args.minutes).run()
    except LeaseBusy:print('STAGE07_WAIT_EXISTING_WORKER',flush=True)


if __name__=='__main__':main()
