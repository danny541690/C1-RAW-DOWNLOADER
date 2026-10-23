import ast
import collections
import datetime as dt
import json
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from urllib.parse import urlparse
from scripts.v093_five_stage_durable_gate import terminal_owner

source=ast.parse((Path(__file__).resolve().parents[1]/'scripts/v093_official_firstpass.py').read_text())
nodes=[n for n in source.body if not isinstance(n,(ast.Import,ast.ImportFrom)) and not isinstance(n,ast.If)]
ns=dict(PreviousWorker=object,urlparse=urlparse,collections=collections,dt=dt,json=json,time=time,
        engine=SimpleNamespace(getj=Mock(),key=lambda j:j['period']))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'official_worker','exec'),ns)
Worker=ns['OfficialWorker']

class OfficialTests(unittest.TestCase):
    def test_scope_contains_all_months_and_no_future_month(self):
        months=ns['months_through']('2026-10')
        self.assertEqual((months[0],months[-1],len(months)),('2000-01','2026-10',322))
    def test_finmind_and_untrusted_host_are_rejected(self):
        for s,u in [('FinMind','https://api.finmindtrade.com/api/v4/data'),('TWSE','https://example.com')]:
            with self.assertRaises(ValueError):ns['assert_official']({'source':s,'url':u})
    def test_exact_official_earliest_boundary(self):
        job={'source':'TWSE','category':'prices_indices','period':'2004-02-10'}
        self.assertEqual(ns['is_before_source_start'](job),'2004-02-11')
        job['period']='2004-02-11';self.assertIsNone(ns['is_before_source_start'](job))
    def test_existing_saved_unit_never_reaches_source(self):
        w=object.__new__(Worker);w.state={'units':{'2000-01-04':{'status':'SAVED_BASIC_VERIFIED'}}};w.skipped=collections.Counter()
        w.fetch_job({'source':'TWSE','url':'https://www.twse.com.tw/a','period':'2000-01-04'},'units')
        self.assertEqual(w.skipped['already_saved'],1)
    def test_meeting_does_not_skip_unprocessed_shared_month(self):
        w=object.__new__(Worker);w.d=Mock();w.otherctrl='other';w.direction='ASC';w.cursor={}
        months=ns['months_through']('2026-10')[::-1]
        ns['engine'].getj=Mock(return_value={'revision':ns['REVISION'],'upper_month':'2026-10','direction':'DESC','month_index':months.index('2012-03')})
        self.assertTrue(w.may_start('2012-03'))
        self.assertFalse(w.may_start('2012-04'))
    def test_recovery_only_from_completed_matching_workflow(self):
        prefix='https://api.github.com/repos/o/r/contents/.github/live-state/five-stage-leases.json'
        for state,allowed in [('completed',True),('in_progress',False)]:
            with patch('scripts.v093_five_stage_durable_gate.open_json',return_value=({'id':123,'status':state,'path':'.github/workflows/v093-official-only-two-ended.yml'},{})):
                self.assertEqual(terminal_owner(prefix,'x','POOL_RAW_OFFICIAL_ASC_V1',{'owner':'123/RAW'}),allowed)

if __name__=='__main__':unittest.main()
