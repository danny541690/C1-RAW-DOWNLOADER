"""Behavioral prelaunch tests; no credentials, source calls or Drive writes."""
import copy
import datetime as dt
import json
import threading
import collections
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from unittest.mock import Mock
from scripts import v093_repair_coordination as c
from scripts import v093_taifex_independent as taifex
from scripts.v093_tdcc_independent import history_summary
from scripts.v093_standard_r4 import parse_member
from tests.test_stage06_financial_repair import sample
from scripts.v093_official_repair import RepairWorker


class MeetingTests(unittest.TestCase):
    def test_source_window_is_shared_and_not_a_waiting_download_attempt(self):
        store={'jobs':{}}
        def read(*args):return 'sha',copy.deepcopy(store)
        def put(api,token,sha,payload,message):store.update(payload);return True
        with patch.object(c,'_read',side_effect=read),patch.object(c,'_put',side_effect=put):
            self.assertTrue(c.reserve_source('api','token','MOPS',now=100))
            self.assertFalse(c.reserve_source('api','token','MOPS',now=101))
            self.assertTrue(c.reserve_source('api','token','TWSE',now=101))
            self.assertTrue(c.reserve_source('api','token','MOPS',now=103))

    def worker(self):
        w=object.__new__(RepairWorker)
        w.lane='EARLY_ASC';w.months=['2000-01'];w.cursor={'month_index':0,'sweeps':0}
        w.until=time.monotonic()+10;w.api='api';w.token='token';w.owner='run/RAW'
        w.lock='lock';w.fence=1;w.stagectrl='control'
        w.checked=w.repaired=w.downloaded=0;w.source_requests=collections.Counter()
        w.save_cursor=Mock();w.putj=Mock();w.pending_index={}
        return w

    def test_worker_resumes_same_month_after_time_budget(self):
        w=self.worker()
        def partial(worker,month):worker.month_incomplete=True;return False
        with patch('scripts.v093_official_repair.claim_month',return_value=(True,{})), \
             patch('scripts.v093_official_repair.capture_history_month',side_effect=partial), \
             patch('scripts.v093_official_repair.commit'):
            w.run()
        self.assertEqual(w.cursor['month_index'],0)

    def test_paused_worker_never_enters_raw_month(self):
        w=self.worker()
        with patch('scripts.v093_official_repair.claim_month',return_value=(False,
                   dict(status='PAUSED_AT_MEETING',meeting_month='2000-01',survivor='EARLY_DESC'))), \
             patch('scripts.v093_official_repair.capture_history_month') as capture, \
             patch('scripts.v093_official_repair.commit'):
            w.run()
        capture.assert_not_called()
        self.assertEqual(w.cursor['month_index'],0)
        self.assertEqual(w.cursor['status'],'PAUSED_AT_MEETING')

    def test_survivor_does_not_pause_both_after_finishing_meeting_month(self):
        state,_=c.elect({},'EARLY_ASC','2006-05')
        state,_=c.elect(state,'EARLY_DESC','2006-06')
        state,allowed=c.elect(state,'EARLY_ASC','2006-06')
        self.assertFalse(allowed)
        state,allowed=c.elect(state,'EARLY_DESC','2006-06')
        self.assertTrue(allowed)
        state,allowed=c.elect(state,'EARLY_DESC','2006-05')
        self.assertFalse(allowed)
        self.assertEqual(state['workers']['EARLY_DESC']['status'],'FRONTIERS_MET_RANGE_VISITED_NOT_CERTIFIED')
        self.assertEqual(state['workers']['EARLY_ASC']['status'],'PAUSED_AT_MEETING')

    def test_first_owner_finishes_and_other_stays_paused_across_restart(self):
        state,allowed=c.elect({},'EARLY_ASC','2006-06')
        self.assertTrue(allowed)
        state,allowed=c.elect(state,'EARLY_DESC','2006-06')
        self.assertFalse(allowed)
        self.assertEqual(state['workers']['EARLY_DESC']['survivor'],'EARLY_ASC')
        state,allowed=c.elect(json.loads(json.dumps(state)),'EARLY_DESC','2006-05')
        self.assertFalse(allowed)
        state,allowed=c.elect(state,'EARLY_ASC','2006-06')
        self.assertTrue(allowed)

    def test_all_322_months_have_exactly_one_owner(self):
        state={};positions={lane:0 for lane in c.LANES};paused=set()
        for _ in range(200):
            for lane in c.LANES:
                months=c.lane_months(lane)
                if lane in paused or positions[lane]>=len(months):continue
                month=months[positions[lane]]
                state,allowed=c.elect(state,lane,month)
                if allowed:positions[lane]+=1
                else:paused.add(lane)
        self.assertEqual(len(state['months']),322)
        self.assertTrue(all(v['status']=='CLAIMED_NOT_CERTIFIED' for v in state['months'].values()))

    def test_real_cas_retry_prevents_two_winners(self):
        lock=threading.Lock();store={'sha':0,'jobs':{}}
        def read(*args):
            with lock:return str(store['sha']),{'jobs':copy.deepcopy(store['jobs'])}
        def put(api,token,sha,payload,message):
            with lock:
                if sha!=str(store['sha']):return False
                store.update(sha=store['sha']+1,jobs=copy.deepcopy(payload['jobs']))
                return True
        with patch.object(c,'_read',side_effect=read),patch.object(c,'_put',side_effect=put):
            with ThreadPoolExecutor(2) as pool:
                results=list(pool.map(lambda lane:c.claim_month('api','token',lane,'2006-06'),
                                      ['EARLY_ASC','EARLY_DESC']))
        self.assertEqual(sum(allowed for allowed,_ in results),1)

    def test_invalid_scope_and_plan_fail_closed(self):
        with self.assertRaises(ValueError):c.elect({},'RECENT_ASC','2000-01')
        with self.assertRaises(ValueError):c.elect({'plan':'other'},'EARLY_ASC','2000-01')


class ParserAndCoverageTests(unittest.TestCase):
    def test_existing_financial_raw_reparses_three_statement_types(self):
        for report in ('IncomeStatement','BalanceSheet','CashflowStatement'):
            rows,stats,_=parse_member('MOPS',report+'_2023-03-31.raw',sample(report),'2023-03')
            self.assertEqual(stats['STAGED_CELLS'],3)
            self.assertEqual([r['numeric_decimal_text'] for r in rows],['1234.50','-20','-30'])
            self.assertTrue(all(r['native_metric'] and r['statement_scope'] for r in rows))
            self.assertTrue(all(not r['pit_verified'] and not r['numeric_semantics_verified'] for r in rows))

    def test_financial_wrong_period_is_not_patched(self):
        with self.assertRaisesRegex(ValueError,'PARTITION_CONFLICT'):
            parse_member('MOPS','IncomeStatement.raw',sample('IncomeStatement'),'2023-06')

    def test_index_rows_do_not_invent_stock_ids(self):
        raw=json.dumps(dict(date='20260601',fields=['指數','收盤指數'],
            data=[['發行量加權股價指數','20,000.25']]),ensure_ascii=False).encode()
        rows,_,_=parse_member('TWSE','indices_2026-06-01.raw',raw,'2026-06')
        self.assertEqual(len(rows),1)
        self.assertIsNone(rows[0]['stock_id'])
        self.assertEqual(rows[0]['native_type'],'INDEX')
        self.assertEqual(rows[0]['native_origin_name'],'發行量加權股價指數')

    def test_tdcc_visited_or_exhausted_is_not_complete(self):
        summary=history_summary('20261016',['2330'],{'20261016|2330':dict(status='UNRESOLVED',attempts=3)})
        self.assertFalse(summary['candidate_set_complete'])
        self.assertEqual(summary['unresolved'],1)
        self.assertFalse(history_summary('20261016',[],{})['candidate_set_complete'])

    def test_tdcc_requires_remote_readback_not_status_alone(self):
        receipts={'20261016|2330':dict(status='SAVED_BASIC_VERIFIED',file_id='f',sha256='s')}
        self.assertFalse(history_summary('20261016',['2330'],receipts)['candidate_set_complete'])
        receipts['20261016|2330']['remote_readback_hash_verified']=True
        self.assertTrue(history_summary('20261016',['2330'],receipts)['candidate_set_complete'])

    def test_compact_roc_and_padded_dates(self):
        for value in ('1151016','20261016','2026/ 10/ 16','115/10/16'):
            self.assertEqual(taifex.parse_date(value),dt.date(2026,10,16))
        self.assertIsNone(taifex.parse_date('1150230'))

    def test_expiry_cannot_replace_missing_trade_date(self):
        raw='交易日期,到期日期,價格\n,2026/10/16,100\n'.encode()
        with self.assertRaisesRegex(ValueError,'CSV_ROW_DATE_MISSING'):
            taifex.csv_evidence(raw,dt.date(2026,10,1),dt.date(2026,10,31))


if __name__=='__main__':unittest.main()
