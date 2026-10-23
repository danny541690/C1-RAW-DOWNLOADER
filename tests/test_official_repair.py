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
    native=SimpleNamespace(sha=lambda b:'a'*64,stamp=lambda:'now'),engine=SimpleNamespace(key=lambda j:'key'),
    assert_official=Mock(),is_before_source_start=Mock(return_value=None),time=time,json=json)
nodes=[n for n in source.body if not isinstance(n,(ast.Import,ast.ImportFrom,ast.If))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'actual_repair','exec'),ns)
Worker=ns['RepairWorker']

class RepairTests(unittest.TestCase):
    def worker(self):
        w=object.__new__(Worker);w.state={'units':{}};w.journal={'units':{}};w.checked=0;w.repaired=0
        w.circuit=collections.Counter();w.source_requests=collections.Counter();w.save_journal=Mock();w.save_state=Mock()
        w.cache=Mock();w.d=Mock();return w
    def job(self):
        return dict(source='TWSE',url='https://www.twse.com.tw/a',category='prices_indices',month='2026-10',period='2026-10-22')
    def test_finmind_never_selected(self):
        self.assertFalse(ns['needs_review']({'source':'FinMind','status':'ISOLATED_MISSING'},{}))
    def test_known_unsupported_period_not_selected(self):
        self.assertFalse(ns['needs_review']({'source':'TWSE','status':'OFFICIAL_PERIOD_NOT_PROVIDED'},{}))
    def test_verified_and_unflagged_skipped(self):
        self.assertFalse(ns['needs_review']({'source':'TWSE','status':'SAVED_BASIC_VERIFIED','unit_id':'k'},{}))
        self.assertTrue(ns['needs_review']({'source':'TWSE','status':'SAVED_BASIC_VERIFIED','unit_id':'k'},{'k':['flag']}))
    def test_valid_existing_raw_has_no_source_download(self):
        w=self.worker();old=dict(self.job(),status='RAW_DOWNLOADED_UNVERIFIED',sha256='s',evidence_file='f/a')
        w.state['units']['key']=old
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1})
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.checked,1);self.assertEqual(sum(w.source_requests.values()),0)
        self.assertEqual(w.state['units']['key']['status'],'SAVED_BASIC_VERIFIED')
        self.assertFalse(w.state['units']['key']['numeric_verified'])
    def test_basic_pass_does_not_clear_semantic_flag(self):
        w=self.worker();w.state['units']['key']=dict(self.job(),status='SAVED_BASIC_VERIFIED',sha256='s',evidence_file='f/a')
        ns['cached_payload']=Mock(return_value=(b'raw','archive'));ns['validate_content']=Mock(return_value={'rows':1})
        w.repair_one(self.job(),'units',[{'kind':'PARSER_OR_SEMANTIC_CORRECTION_REQUIRED'}])
        self.assertEqual(w.journal['units']['key']['status'],'BASIC_PASS_FLAG_REQUIRES_REVIEW')
        self.assertEqual(sum(w.source_requests.values()),0)
    def test_attempt_cap_survives_new_runner(self):
        w=self.worker();w.journal['units']['key']={'attempts':3}
        w.repair_one(self.job(),'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'UNRESOLVED_AFTER_THREE_ATTEMPTS')
        self.assertEqual(sum(w.source_requests.values()),0)
    def test_missing_route_is_recorded_without_crashing(self):
        w=self.worker();job=self.job();del job['url'];w.repair_one(job,'units',[])
        self.assertEqual(w.journal['units']['key']['status'],'OFFICIAL_ROUTE_REQUIRES_REVIEW')
    def test_lease_recovery_matches_repair_workflow(self):
        api='https://api.github.com/repos/o/r/contents/.github/live-state/five-stage-leases.json'
        for path,allowed in [('.github/workflows/v093-official-only-repair.yml',True),('.github/workflows/v093-official-only-two-ended.yml',False)]:
            with patch('scripts.v093_five_stage_durable_gate.open_json',return_value=({'id':123,'status':'completed','path':path},{})):
                self.assertEqual(terminal_owner(api,'token','POOL_RAW_OFFICIAL_REPAIR_ASC_V1',{'owner':'123/RAW'}),allowed)

if __name__=='__main__':unittest.main()
