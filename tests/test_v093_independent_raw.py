import collections,datetime as dt,json,time,unittest
from scripts.v093_independent_raw import Independent,month_plan,price_checks,retry_candidates
from scripts.v093_history_reverse import key

class IndependentRawContracts(unittest.TestCase):
    def test_no_future_month_and_strict_descending_scope(self):
        months=month_plan(dt.date(2026,10,20))
        self.assertEqual(months[0],'2026-10');self.assertEqual(months[-1],'2000-01');self.assertEqual(len(months),322)
        self.assertEqual(len(months),len(set(months)))
        for a,b in zip(months,months[1:]):
            y,m=map(int,a.split('-'));yy,mm=map(int,b.split('-'));self.assertEqual(y*12+m-yy*12-mm,1)
    def test_price_null_and_violation_stay_distinct(self):
        raw=json.dumps({'fields':['證券代號','開盤價','最高價','最低價','收盤價'],'data':[['2330','10','12','9','11'],['2317','--','12','9','11'],['2454','8','12','9','11']]}).encode()
        result=price_checks(raw,'TWSE','2025-01-02')
        self.assertEqual(result['checked_rows'],2);self.assertEqual(result['null_cells'][0]['stock_id'],'2317');self.assertEqual(result['ohlc_violations'][0]['stock_id'],'2454')
    def test_total_three_attempts_are_durable_and_resume_does_not_reset_them(self):
        h=object.__new__(Independent);h.until=time.monotonic()+10;h.state={'units':{},'attempt_ledger':{},'numeric_checks':{}};calls=[]
        job={'source':'TWSE','category':'margin','period':'2025-01-02'}
        h.save_state=lambda:None
        def fetch(j,b):
            calls.append(h.state['attempt_ledger'][b][key(j)])
            return j,dict(j,unit_id=key(j),status='DEFERRED_MISSING'),None
        h.fetch_one=fetch
        def flush(results,b):
            for j,e,raw in results:h.state[b][key(j)]=e
        h.flush=flush
        self.assertTrue(h.process([job],'units'));self.assertEqual(calls,[1,2,3]);self.assertTrue(h.state['units'][key(job)]['retry_exhausted'])
        self.assertTrue(h.process([job],'units'));self.assertEqual(calls,[1,2,3])
    def test_proven_existing_unit_is_not_downloaded_again(self):
        job={'source':'TWSE','category':'margin','period':'2025-01-02'}
        self.assertEqual(retry_candidates([job],{key(job):{'status':'SAVED_BASIC_VERIFIED'}},{}),[])
    def test_existing_month_filename_cannot_override_wrong_payload_date(self):
        h=object.__new__(Independent);h.active='2025-01';h.state={'numeric_checks':{},'units':{},'inventory_errors':[],'stocks':[],'market_codes':{}}
        raw=json.dumps({'stat':'ok','date':'20250203','fields':['代號','值'],'data':[['2330','1']]}).encode()
        with self.assertRaisesRegex(ValueError,'RESPONSE_DATE_MISMATCH'):
            h.inspect_payload('TWSE','margin_2025-01-02.json',raw,{'category':'margin','period':'2025-01-02'},'raw/file')

class MonthIsolationContracts(unittest.TestCase):
    def test_persistent_month_system_error_advances_after_three_attempts(self):
        from unittest.mock import patch
        h=object.__new__(Independent);h.until=time.monotonic()+5;h.months=['2026-10','2000-01'];h.active='2026-10';h.monthctrl='month';h.d=object()
        h.checkpoint={'month_index':0,'backlog_month_index':0,'finished_months':[]};h.save_cursor=lambda:None;h.progress=lambda:None
        calls=[]
        def run_impl():
            if h.checkpoint['month_index']==1:return 'continued'
            calls.append(1);raise ValueError('ambiguous source folder')
        h._run_impl=run_impl
        with patch('scripts.v093_independent_raw.engine.putj'):
            self.assertEqual(h.run(),'continued')
        self.assertEqual(len(calls),3);self.assertEqual(h.checkpoint['month_index'],1)
