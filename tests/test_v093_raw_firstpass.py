import collections,datetime as dt,time,unittest
from scripts.v093_raw_firstpass import MONTHS,FirstPass,month_policy,key

class FirstPassContracts(unittest.TestCase):
    def test_scope_and_future_current_existing_rules(self):
        self.assertEqual(len(MONTHS),324);self.assertEqual(len(set(MONTHS)),324)
        self.assertEqual(MONTHS[0],'2026-12');self.assertEqual(MONTHS[-1],'2000-01')
        today=dt.date(2026,10,20)
        self.assertEqual(month_policy('2026-12',today,{}),'FUTURE_MONTH_NOT_AVAILABLE')
        self.assertEqual(month_policy('2026-10',today,{}),'NEW_CAPTURE_CURRENT_MONTH_PARTIAL')
        self.assertEqual(month_policy('2024-01',today,{'TWSE':[{'id':'one'}],'TPEx':[]}),'SKIPPED_EXISTING_NO_TOPUP')
    def test_attempt_is_durable_before_http_and_failure_is_not_retried(self):
        h=object.__new__(FirstPass);h.until=time.monotonic()+10;h.state={'units':{}};events=[]
        job={'source':'TWSE','category':'prices','period':'2001-01-02'}
        h.save_state=lambda:events.append(('save',h.state['units'][key(job)]['status']))
        def fetch(j,b):
            self.assertEqual(events[-1][0],'save');events.append(('fetch',None))
            return j,dict(j,unit_id=key(j),status='DEFERRED_MISSING'),None
        h.fetch_one=fetch
        def flush(results,b):
            for j,e,raw in results:h.state[b][key(j)]=e
        h.flush=flush
        self.assertTrue(h.process([job],'units'));self.assertTrue(h.process([job],'units'))
        self.assertEqual(sum(e[0]=='fetch' for e in events),1)
    def test_interrupted_intent_is_not_replayed(self):
        h=object.__new__(FirstPass);h.until=time.monotonic()+10
        j={'source':'TWSE','category':'prices','period':'2001-01-02'}
        h.state={'units':{key(j):{'status':'REQUEST_INTENT_INTERRUPTED_OR_UNCONFIRMED'}}}
        h.fetch_one=lambda *a:self.fail('interrupted request must not be replayed')
        self.assertTrue(h.process([j],'units'))
