import ast
import collections
import datetime as dt
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from scripts.v093_five_stage_durable_gate import terminal_owner

source=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_official_repair.py').read_text())
ns=dict(OfficialWorker=object,SOURCES=('TWSE','TPEx','MOPS'),SAVED={'SAVED_BASIC_VERIFIED','RAW_DOWNLOADED_UNVERIFIED'},
    native=SimpleNamespace(sha=lambda b:'a'*64,stamp=lambda:'now',request=Mock(return_value=b'raw'),request_data=Mock(return_value=None)),engine=SimpleNamespace(key=lambda j:'key'),
    assert_official=Mock(),is_before_source_start=Mock(return_value=None),time=time,json=json)
nodes=[n for n in source.body if not isinstance(n,(ast.Import,ast.ImportFrom,ast.If))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_repair','exec'),ns)
Worker=ns['RepairWorker']

class RepairTests(unittest.TestCase):
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
        self.assertEqual(w.journal['units']['key']['status'],'SOURCE_CHECKED_OPEN_QUALITY_ITEMS')
        self.assertEqual(sum(w.source_requests.values()),1)
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
    def test_exhausted_cooldown_cycles_remain_visible(self):
        w=self.worker();w.circuit['TWSE']=2
        w.journal['units']['key']={'quality_revision':ns['QUALITY_REVISION'],'input_signature':'a'*64,
            'attempts':3,'retry_cycle':3,'next_retry_at':time.time()-1}
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'UNRESOLVED_RETRY_CYCLES_EXHAUSTED')
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
