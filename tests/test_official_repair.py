import ast
import collections
import datetime as dt
import json
import re
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from scripts.v093_five_stage_durable_gate import terminal_owner
from scripts.v093_official_problem_catalog import problem_summary, unresolved_items

source=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_official_repair.py').read_text())
ns=dict(problem_summary=problem_summary,unresolved_items=unresolved_items,OfficialWorker=object,SOURCES=('TWSE','TPEx','MOPS'),SAVED={'SAVED_BASIC_VERIFIED','RAW_DOWNLOADED_UNVERIFIED'},
    native=SimpleNamespace(sha=lambda b:'a'*64,stamp=lambda:'now',request=Mock(return_value=b'raw'),request_data=Mock(return_value=None)),engine=SimpleNamespace(key=lambda j:'key',FIN_REPORTS=('CashflowStatement','IncomeStatement','BalanceSheet')),
    assert_official=Mock(),is_before_source_start=Mock(return_value=None),time=time,json=json,re=re,dt=dt)
nodes=[n for n in source.body if not isinstance(n,(ast.Import,ast.ImportFrom,ast.If))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_repair','exec'),ns)
Worker=ns['RepairWorker']

class RepairTests(unittest.TestCase):
    def test_source_rejected_company_is_not_no_data_or_local_parameter_error(self):
        result=ns['source_failure'](ValueError('OFFICIAL_COMPANY_SELECTOR_REJECTED'),dict(period='2026-06-30'))
        self.assertEqual(result,dict(status='UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE',terminal=True))
    def test_financial_selector_error_html_is_rejected_before_parsing(self):
        raw='<table><tr><td>至少需要輸入一個正確的股號或股名!</td></tr></table>'.encode()
        # Resolve the actual function body; fixture workers replace validation elsewhere.
        module=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_official_repair.py').read_text())
        function=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='validate_content')
        local=dict(ns);exec(compile(ast.Module(body=[function],type_ignores=[]),'financial_validator','exec'),local)
        with self.assertRaisesRegex(ValueError,'OFFICIAL_COMPANY_SELECTOR_REJECTED'):
            local['validate_content'](raw,dict(category='CashflowStatement'))
    def test_explicit_historical_bound_is_not_a_transient_failure(self):
        result=ns['source_failure'](ValueError('SOURCE_STATUS:查詢開始日期小於100年1月1日，請重新查詢!'),
            dict(period='2000-07-03'))
        self.assertEqual(result,dict(status='OFFICIAL_PERIOD_NOT_PROVIDED',terminal=True,source_start='2011-01-01'))
        self.assertIsNone(ns['source_failure'](ValueError('查詢開始日期小於92年5月5日'),dict(period='2026-06-01')))

    def test_empty_and_incomplete_source_responses_remain_unresolved(self):
        self.worker()
        for message,status in [('EMPTY_RESPONSE_NOT_COVERAGE','SOURCE_NO_DATA_UNCONFIRMED'),
                ('EMPTY_EVENT_UNPROVEN','SOURCE_NO_DATA_UNCONFIRMED'),
                ('SOURCE_STATUS:很抱歉，沒有符合條件的資料','SOURCE_NO_DATA_UNCONFIRMED'),
                ('FINANCIAL_REQUESTED_COMPANIES_OR_PERIOD_INCOMPLETE','SOURCE_CONTENT_INCOMPLETE')]:
            result=ns['source_failure'](ValueError(message),dict(period='2000-07-03'))
            self.assertEqual(result,dict(status=status,terminal=False))

    def test_official_no_data_response_stops_immediate_repeats_without_counting_repair(self):
        w=self.worker();ns['validate_content']=Mock(side_effect=ValueError('EMPTY_RESPONSE_NOT_COVERAGE'))
        w.repair_one(self.job(),'units',[])
        self.assertEqual(sum(w.source_requests.values()),1)
        self.assertEqual(w.repaired,0)
        row=w.journal['units']['key']
        self.assertEqual(row['status'],'SOURCE_NO_DATA_UNCONFIRMED')
        self.assertFalse(row['complete']);self.assertGreater(row['next_retry_at'],time.time())

    def test_official_historical_bound_is_saved_and_not_retried(self):
        w=self.worker();job=self.job();job['period']='2000-07-03'
        ns['validate_content']=Mock(side_effect=ValueError('SOURCE_STATUS:查詢開始日期小於92年5月5日'))
        w.repair_one(job,'units',[]);w.repair_one(job,'units',[])
        self.assertEqual(sum(w.source_requests.values()),1)
        self.assertEqual(w.repaired,0)
        self.assertEqual(w.journal['units']['key']['status'],'OFFICIAL_PERIOD_NOT_PROVIDED')
        self.assertFalse(w.journal['units']['key']['complete'])

    def test_prior_explicit_bound_reclassified_without_another_network_request(self):
        w=self.worker();job=self.job();job['period']='2000-07-03'
        w.journal['units']['key']=dict(quality_revision=ns['QUALITY_REVISION'],input_signature='a'*64,
            status='UNRESOLVED_ATTEMPT_LIMIT',attempts=3,next_retry_at=time.time()+3600,
            error='ValueError:SOURCE_STATUS:查詢開始日期小於100年1月1日')
        w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'OFFICIAL_PERIOD_NOT_PROVIDED')
        ns['native'].request.assert_not_called()
    def worker(self):
        w=object.__new__(Worker);w.state={'units':{}};w.journal={'units':{}};w.checked=0;w.repaired=0;w.downloaded=0
        w.circuit=collections.Counter();w.source_requests=collections.Counter();w.save_journal=Mock();w.save_state=Mock()
        w.cache=Mock();w.d=Mock();w.monthctrl="month";ns["ArchiveCache"]=Mock;w.until=time.monotonic()+200;w.owned=Mock()
        ns['base']=SimpleNamespace(Worker=SimpleNamespace(record_payload=Mock()),retryable=lambda e:False,urllib=__import__('urllib'))
        ns['value_digest']=lambda raw:raw
        ns['native'].request=Mock(return_value=b'raw')
        return w
    def job(self):
        return dict(source='TWSE',url='https://www.twse.com.tw/a',category='prices_indices',month='2026-10',period='2026-10-22')
    def test_finmind_never_selected(self):
        self.assertFalse(ns['needs_review']({'source':'FinMind','status':'ISOLATED_MISSING'},{}))
    def test_local_parameter_failure_is_not_a_source_call(self):
        w=self.worker()
        with patch.object(ns['native'],'request_data',side_effect=ValueError('INVALID_PARAMS')):
            w.repair_one(self.job(),'units',[])
        row=w.journal['units']['key']
        self.assertEqual(row['status'],'LOCAL_PARAM_ENCODING_ERROR')
        self.assertEqual(row['attempts'],0)
        self.assertEqual(sum(w.source_requests.values()),0)
        ns['native'].request.assert_not_called()

    def test_shared_source_window_wait_does_not_count_attempt(self):
        w=self.worker();w.lane='EARLY_ASC';w.api='api';w.token='token'
        with patch.dict(ns,reserve_source=Mock(return_value=False)):
            w.repair_one(self.job(),'units',[])
        row=w.journal['units']['key']
        self.assertEqual(row['status'],'WAIT_SHARED_SOURCE_WINDOW')
        self.assertEqual(row['attempts'],0)
        self.assertLess(row['next_retry_at'],time.time()+5)
        ns['native'].request.assert_not_called()
    def test_known_unsupported_period_not_selected(self):
        self.assertFalse(ns['needs_review']({'source':'TWSE','status':'OFFICIAL_PERIOD_NOT_PROVIDED'},{}))
    def test_verified_and_unflagged_skipped(self):
        self.assertFalse(ns['needs_review']({'source':'TWSE','status':'SAVED_BASIC_VERIFIED','unit_id':'k'},{}))
        self.assertTrue(ns['needs_review']({'source':'TWSE','status':'SAVED_BASIC_VERIFIED','unit_id':'k'},{'k':['flag']}))
    def test_valid_unverified_raw_is_checked_without_redundant_source_request(self):
        w=self.worker();old=dict(self.job(),status='RAW_DOWNLOADED_UNVERIFIED',sha256='s',evidence_file='f/a')
        w.state['units']['key']=old
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.checked,1);self.assertEqual(sum(w.source_requests.values()),0)
        self.assertEqual(w.journal['units']['key']['status'],'CONTENT_CHECK_PASS')
        self.assertTrue(w.journal['units']['key']['terminal'])
    def test_basic_pass_does_not_clear_semantic_flag(self):
        w=self.worker();w.state['units']['key']=dict(self.job(),status='SAVED_BASIC_VERIFIED',sha256='s',evidence_file='f/a')
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        w.repair_one(self.job(),'units',[{'kind':'PARSER_OR_SEMANTIC_CORRECTION_REQUIRED'}])
        self.assertEqual(w.journal['units']['key']['status'],'LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS')
        self.assertEqual(sum(w.source_requests.values()),0)
        self.assertFalse(w.journal['units']['key']['complete'])
    def test_attempt_cap_survives_new_runner(self):
        w=self.worker();w.journal['units']['key']={'attempts':3,'quality_revision':ns['QUALITY_REVISION'],'input_signature':'a'*64}
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'UNRESOLVED_ATTEMPT_LIMIT')
        self.assertFalse(w.journal['units']['key']['terminal'])
        self.assertGreater(w.journal['units']['key']['next_retry_at'],time.time())
        self.assertEqual(sum(w.source_requests.values()),0)
    def test_missing_route_is_recorded_without_crashing(self):
        w=self.worker();job=self.job();del job['url'];w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'UNRESOLVED_OFFICIAL_ROUTE')
    def test_source_backoff_is_retryable_after_cooldown(self):
        w=self.worker();w.circuit['TWSE']=2
        w.repair_one(self.job(),'units',[])
        row=w.journal['units']['key']
        self.assertEqual(row['status'],'UNRESOLVED_SOURCE_BACKOFF')
        self.assertFalse(row['terminal']);self.assertGreater(row['next_retry_at'],time.time())
        w.circuit.clear();row['next_retry_at']=time.time()-1
        ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        def save(worker,job,raw,receipt,bucket):worker.state[bucket]['key']=dict(receipt,evidence_file='new/a')
        ns['base'].Worker.record_payload=save
        ns['cached_payload']=Mock(return_value=(b'raw','archive'))
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.repaired,1);self.assertTrue(w.journal['units']['key']['readback_verified'])
    def test_readback_failure_never_counts_repair_or_replaces_prior_receipt(self):
        w=self.worker();old=dict(self.job(),status='RAW_DOWNLOADED_UNVERIFIED',sha256='old',evidence_file='old/a')
        w.state['units']['key']=old
        ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        ns['cached_payload']=Mock(side_effect=ValueError('RAW_READBACK_HASH_MISMATCH'))
        def save(worker,job,raw,receipt,bucket):worker.state[bucket]['key']=dict(receipt,evidence_file='new/a')
        ns['base'].Worker.record_payload=save
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.repaired,0);self.assertEqual(w.state['units']['key'],old)
        self.assertFalse(w.journal['units']['key']['complete'])
    def test_previous_content_pass_preserved_across_upgrade(self):
        w=self.worker();w.state['units']['key']={'sha256':'same'}
        w.journal['units']['key']={'status':'CONTENT_CHECK_PASS','raw_sha256':'same','quality_revision':'V2'}
        w.repair_one(self.job(),'units',[])
        ns['native'].request.assert_not_called()
    def test_circuit_wait_does_not_exhaust_download_cycles(self):
        w=self.worker();w.circuit['TWSE']=2
        w.journal['units']['key']={'quality_revision':ns['QUALITY_REVISION'],'input_signature':'a'*64,
            'attempts':3,'retry_cycle':3,'next_retry_at':time.time()-1}
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'UNRESOLVED_SOURCE_BACKOFF')
        self.assertFalse(w.journal['units']['key']['complete'])
    def test_lease_recovery_matches_repair_workflow(self):
        api='https://api.github.com/repos/o/r/contents/.github/live-state/five-stage-leases.json'
        for path,allowed in [('.github/workflows/v093-official-only-repair.yml',True),('.github/workflows/v093-official-only-two-ended.yml',False)]:
            with patch('scripts.v093_five_stage_durable_gate.open_json',return_value=({'id':123,'status':'completed','path':path},{})):
                self.assertEqual(terminal_owner(api,'token','POOL_RAW_OFFICIAL_REPAIR_ASC_V1',{'owner':'123/RAW'}),allowed)

    def test_priority_retry_only_selects_due_unresolved_rows(self):
        row=dict(quality_revision=ns['QUALITY_REVISION'],status='UNRESOLVED_SOURCE_BACKOFF',
                 terminal=False,complete=False,next_retry_at=100)
        def due(**changes):return ns['incident_retry_due']({'units':{'k':dict(row,**changes)}},200)
        self.assertTrue(due())
        self.assertFalse(due(next_retry_at=300))
        self.assertFalse(due(terminal=True))
        self.assertFalse(due(complete=True))
        self.assertFalse(due(status='CONTENT_CHECK_PASS'))
        self.assertFalse(due(quality_revision='V2'))

    def priority_worker(self,direction='DESC'):
        w=self.worker();w.direction=direction;w.roots={'RAW':'raw'}
        w.cursor={'parameter_incident_revisited':ns['QUALITY_REVISION'],'month_index':300}
        w.save_cursor=Mock();w.d.find.return_value={'id':'june'}
        ns['engine'].getj=Mock(return_value={'units':{'k':dict(quality_revision=ns['QUALITY_REVISION'],
            status='UNRESOLVED_SOURCE_BACKOFF',terminal=False,next_retry_at=0)}})
        return w

    def test_expired_incident_revisited_after_migration_without_resetting_cursor(self):
        w=self.priority_worker();deadline=w.until
        def capture(worker,month):
            self.assertEqual(month,'2026-06')
            self.assertLess(worker.until,deadline)
            return True
        with patch.dict(ns,capture_history_month=Mock(side_effect=capture)):
            w.revisit_parameter_incident()
        self.assertEqual(w.until,deadline);self.assertEqual(w.cursor['month_index'],300)

    def test_incident_does_not_revisit_completed_or_cooling_rows(self):
        w=self.priority_worker();ns['engine'].getj.return_value['units']['k']['next_retry_at']=time.time()+3600
        with patch.dict(ns,capture_history_month=Mock()) as env:
            w.revisit_parameter_incident();env['capture_history_month'].assert_not_called()

    def test_asc_leaves_incident_retry_to_desc(self):
        w=self.priority_worker('ASC')
        with patch.dict(ns,capture_history_month=Mock()) as env:
            w.revisit_parameter_incident();env['capture_history_month'].assert_not_called()
        ns['engine'].getj.assert_not_called()

    def test_priority_failure_restores_full_run_deadline(self):
        w=self.priority_worker();deadline=w.until
        with patch.dict(ns,capture_history_month=Mock(side_effect=RuntimeError('read failed'))):
            with self.assertRaisesRegex(RuntimeError,'read failed'):w.revisit_parameter_incident()
        self.assertEqual(w.until,deadline)

    def test_busy_priority_month_preserves_frontier_and_migration_state(self):
        w=self.priority_worker();w.cursor.pop('parameter_incident_revisited');deadline=w.until
        with patch.dict(ns,capture_history_month=Mock(return_value=False)):
            w.revisit_parameter_incident()
        self.assertEqual(w.until,deadline);self.assertEqual(w.cursor['month_index'],300)
        self.assertNotIn('parameter_incident_revisited',w.cursor)
        w.save_cursor.assert_not_called()

if __name__=='__main__':unittest.main()

class LegacyRouteAndProgressTests(unittest.TestCase):
    def test_saved_raw_without_url_is_checked_before_route_resolution(self):
        fixture=RepairTests();w=fixture.worker();job=fixture.job();job.pop('url')
        w.state['units']['key']=dict(job,status='SAVED_BASIC_VERIFIED',sha256='same',evidence_file='saved/member')
        w.journal['units']['key']=dict(status='UNRESOLVED_OFFICIAL_ROUTE',terminal=True,complete=False,quality_revision=ns['QUALITY_REVISION'],input_signature='a'*64)
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'CONTENT_CHECK_PASS')
        self.assertEqual(w.activity_summary()['unchanged_raw_checked_this_run'],1)
        self.assertEqual(w.state['units']['key']['sha256'],'same');self.assertEqual(w.repaired,0)
        ns['native'].request.assert_not_called()
    def test_valid_local_raw_does_not_need_a_live_source_window(self):
        fixture=RepairTests();w=fixture.worker();job=fixture.job();job.pop('url')
        w.state['units']['key']=dict(job,status='SAVED_BASIC_VERIFIED',sha256='same',evidence_file='saved/member')
        w.circuit['TWSE']=2
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':['PIT']}})
        w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS')
        self.assertFalse(w.journal['units']['key']['complete']);ns['native'].request.assert_not_called()
    def test_activity_is_deduplicated_by_unit_and_sha(self):
        w=RepairTests().worker()
        w.note_activity('unchanged_raw_checked_this_run','unit','sha');w.note_activity('unchanged_raw_checked_this_run','unit','sha')
        self.assertEqual(w.activity_summary()['unchanged_raw_checked_this_run'],1)
    def test_parser_fix_rechecks_retained_bytes_without_resetting_source_cap(self):
        fixture=RepairTests();w=fixture.worker();job=fixture.job()
        w.state['units']['key']=dict(job,status='SAVED_BASIC_VERIFIED',sha256='same',evidence_file='saved/member')
        w.journal['units']['key']=dict(status='UNRESOLVED_ATTEMPT_LIMIT',attempts=3,terminal=True,quality_revision=ns['QUALITY_REVISION'],input_signature='a'*64,local_error='ValueError:NON_NUMERIC_CELL:97.24%',next_retry_at=time.time()+3600)
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1,'codes':['2330'],'row_audit':{'unverified':[]}})
        w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'CONTENT_CHECK_PASS')
        self.assertEqual(w.journal['units']['key']['attempts'],3);ns['native'].request.assert_not_called()

class FourLaneLeaseRecoveryTests(unittest.TestCase):
    def test_completed_new_workflow_can_release_only_matching_raw_keys(self):
        api='https://api.github.com/repos/o/r/contents/.github/live-state/five-stage-leases.json'
        reply={'id':123,'status':'completed','path':'.github/workflows/v093-official-four-lane-repair.yml'}
        with patch('scripts.v093_five_stage_durable_gate.open_json',return_value=(reply,{})):
            self.assertTrue(terminal_owner(api,'token','POOL_RAW_OFFICIAL_REPAIR_RECENT_DESC_V1',{'owner':'123/RAW'}))
            self.assertTrue(terminal_owner(api,'token','RAW_HISTORY_MONTH_2026_08',{'owner':'123/RAW'}))
            self.assertFalse(terminal_owner(api,'token','POOL_RAW_OFFICIAL_ASC_V1',{'owner':'123/RAW'}))
        reply['status']='in_progress'
        with patch('scripts.v093_five_stage_durable_gate.open_json',return_value=(reply,{})):
            self.assertFalse(terminal_owner(api,'token','POOL_RAW_OFFICIAL_REPAIR_RECENT_DESC_V1',{'owner':'123/RAW'}))

class RecentLaneIncidentTests(unittest.TestCase):
    def test_recent_desc_revisits_june_without_resetting_frontier(self):
        w=RepairTests().priority_worker();w.lane='RECENT_DESC'
        ns['engine'].getj.return_value={'units':{'k':dict(quality_revision=ns['QUALITY_REVISION'],status='UNRESOLVED_SOURCE_BACKOFF',terminal=False,next_retry_at=0)}}
        with patch.dict(ns,capture_history_month=Mock(return_value=True)) as env:
            w.revisit_parameter_incident();env['capture_history_month'].assert_called_once_with(w,'2026-06')
        self.assertEqual(w.cursor['month_index'],300)
    def test_early_desc_does_not_visit_other_lanes_month(self):
        w=RepairTests().priority_worker();w.lane='EARLY_DESC'
        with patch.dict(ns,capture_history_month=Mock()) as env:
            w.revisit_parameter_incident();env['capture_history_month'].assert_not_called()
