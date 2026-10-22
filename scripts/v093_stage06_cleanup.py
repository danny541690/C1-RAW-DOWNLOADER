"""Live stage-six cleanup using existing owner pools and native persistence.

Separate cleanup cursors never reset the five primary cursors. A bounded month
visit prevents inventory or unavailable upstream data from pinning the sweep.
"""
import argparse
import copy
import json
import time

from scripts import v093_live_five_stage as base
from scripts import v093_history_reverse as engine
from scripts import v093_three_year_repair as native
from scripts.v093_replanned_five_stage import Worker, newest_receipts
from scripts.v093_stage06_live import authorized, ROOT_NAME
from scripts.v093_five_stage_durable_gate import commit, LeaseBusy


def run(stage, minutes=60):
    authorized()
    try:
        worker = Worker(stage, minutes, stage06=True)
    except LeaseBusy:
        print('STAGE06_CLEANUP_WAIT_EXISTING_OWNER '+stage, flush=True)
        return
    original = copy.deepcopy(worker.cursor)
    deadline = worker.until - 45
    root = worker.d.folder(worker.primary_control, ROOT_NAME)
    filename = 'CLEANUP_'+stage+'_CURSOR.json'
    cursor = engine.getj(worker.d, root, filename) or dict(month_index=0, completed_sweeps=0, visits={})
    revision='INDEPENDENT_STAGE06_20261022_V2'
    if cursor.get('independent_revision')!=revision:
        prior=copy.deepcopy(cursor)
        cursor=dict(month_index=0,completed_sweeps=0,visits={},independent_revision=revision,
                    prior_checkpoint=prior,scope_start='2026-10',scope_end='2000-01')
    worker.max_source_attempts = 5
    worker.stage06_cleanup = True
    def save():
        worker.owned()
        cursor.update(stage=stage, direction='NEWEST_TO_OLDEST', max_attempts=5,
                      updated_utc=native.stamp(), run=worker.owner,
                      next_month=base.MONTHS[cursor['month_index']] if cursor['month_index']<len(base.MONTHS) else None,
                      requests=worker.processed, saved=worker.saved,
                      coverage_certified=False, all_data_repaired=False)
        worker.putj(root, filename, cursor)
        print('STAGE06_CLEANUP_PROGRESS '+json.dumps(cursor,sort_keys=True),flush=True)
    try:
        save()
        while time.monotonic()<deadline:
            if cursor['month_index']>=len(base.MONTHS):
                cursor['completed_sweeps']+=1
                cursor['month_index']=0
                cursor['visits']={}
                save()
                if time.monotonic()+300>=deadline:break
                for _ in range(10):
                    worker.owned();time.sleep(30)
            month=base.MONTHS[cursor['month_index']]
            worker.until=min(deadline,time.monotonic()+120)
            worker.phase='STAGE06_CLEANUP'
            complete=False
            try:
                if stage=='RAW':
                    complete=worker.capture_month(month)
                    unresolved=[r for b in ('units','financial_units') for r in worker.state[b].values()
                                if r.get('status')!='SAVED_BASIC_VERIFIED']
                    cursor['last_unresolved_count']=len(unresolved)
                else:
                    out=worker.monthfolder(stage,month)
                    ledger=engine.getj(worker.d,out,'MONTH_STATE.json') or dict(month=month,units={})
                    if not ledger.get('stage06_primary_snapshot'):
                        primary_stage=worker.d.find(worker.primary_control,stage)
                        primary_month=worker.d.find(primary_stage['id'],month) if primary_stage else None
                        primary=engine.getj(worker.d,primary_month['id'],'MONTH_STATE.json') if primary_month else None
                        units=copy.deepcopy((primary or {}).get('units',{}))
                        units.update(ledger['units']);ledger['units']=units
                        ledger['stage06_primary_snapshot']=True
                    if stage=='QA1':
                        upstream=worker.input_index(month,ledger['units'])
                        qa={}
                    else:
                        qa_root=worker.d.folder(worker.control,'QA1')
                        index_root=worker.d.find(qa_root,'RAW_INDEX')
                        index=worker.d.find(index_root['id'],month) if index_root else None
                        upstream=engine.getj(worker.d,index['id'],'MONTH_STATE.json') if index else {}
                        qa_folder=worker.d.find(qa_root,month)
                        qa=(engine.getj(worker.d,qa_folder['id'],'MONTH_STATE.json') or {}).get('units',{}) if qa_folder else {}
                        primary_qa=worker.d.find(worker.primary_control,'QA1')
                        primary_index=worker.d.find(primary_qa['id'],'RAW_INDEX') if primary_qa else None
                        primary_index_month=worker.d.find(primary_index['id'],month) if primary_index else None
                        primary_upstream=engine.getj(worker.d,primary_index_month['id'],'MONTH_STATE.json') if primary_index_month else None
                        combined=copy.deepcopy(primary_upstream or {})
                        for bucket in ('units','financial_units'):
                            combined.setdefault(bucket,{}).update((upstream or {}).get(bucket,{}))
                        upstream=combined
                        primary_qa_month=worker.d.find(primary_qa['id'],month) if primary_qa else None
                        primary_checks=engine.getj(worker.d,primary_qa_month['id'],'MONTH_STATE.json') if primary_qa_month else None
                        qa={**(primary_checks or {}).get('units',{}),**qa}
                    upstream=upstream or {}
                    counts=ledger.setdefault('stage06_repair_attempts',{})
                    deferred_originals={}
                    for key,row in list(ledger['units'].items()):
                        if row.get('status')!='QUARANTINED' or counts.get(key,0)>=5:continue
                        ledger.setdefault('stage06_quarantine_history',{}).setdefault(key,[]).append(copy.deepcopy(row))
                        counts[key]=counts.get(key,0)+1
                        deferred_originals[key]=copy.deepcopy(row)
                    # Persist retry intent and original quarantine before replay.
                    worker.putj(out,'MONTH_STATE.json',ledger)
                    for key in deferred_originals:del ledger['units'][key]
                    try:
                        worker.process_units(month,upstream,out,ledger,qa)
                    finally:
                        for key,row in deferred_originals.items():ledger['units'].setdefault(key,row)
                        worker.putj(out,'MONTH_STATE.json',ledger)
                    applicable=[r for r in newest_receipts(upstream) if stage=='QA1' or base.route(r['category'])==stage]
                    pending=[r for r in applicable if (r['unit_id']+'_'+r['sha256']+('' if stage=='QA1' else '_'+base.STAGING_REVISION)) not in ledger['units']]
                    complete=not pending and (stage!='QA1' or upstream.get('inventory_complete',False))
                    cursor['last_unresolved_count']=len(pending)+sum(r.get('status')=='QUARANTINED' for r in ledger['units'].values())
                cursor.pop('last_error',None)
            except (ValueError,KeyError,TypeError) as exc:
                cursor['last_error']=type(exc).__name__+':'+str(exc)[:240]
            visits=cursor['visits'].get(month,0)+1
            cursor['visits'][month]=visits
            cursor['last_month']=month
            cursor['last_month_status']='VISITED_WITH_UNRESOLVED' if complete and cursor.get('last_unresolved_count') else 'VISITED' if complete else 'DEFERRED_AFTER_FIVE_VISITS' if visits>=5 else 'PARTIAL'
            if complete or visits>=5:cursor['month_index']+=1
            save()
    finally:
        worker.until=deadline+45
        if worker.cursor!=original:
            # capture_month may update an in-memory retry list; no primary cursor is published.
            worker.cursor=original
        commit(worker.api,worker.token,worker.lock,worker.owner,worker.fence,native.sha(b'STAGE06_CLEANUP_FINISHED'))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=('RAW','QA1','CHIP'),required=True)
    parser.add_argument('--minutes',type=float,default=60)
    args=parser.parse_args()
    if not 1<=args.minutes<=60:raise ValueError('INVALID_BUDGET')
    run(args.stage,args.minutes)
