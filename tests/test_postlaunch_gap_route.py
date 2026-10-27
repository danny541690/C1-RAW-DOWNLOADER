"""Historical route holds remain open while alternate-provider RAW is collected."""
import copy,datetime as dt,io,json,time,unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch
from scripts import v093_official_finmind_gapfill as fm
from scripts import v093_history_reverse as engine

class HistoricalGapIntegration(unittest.TestCase):
 def fixture(self,status='UNRESOLVED_HISTORICAL_COMPARE_SCOPE',**row):
  job=dict(source='MOPS',category='BalanceSheet',period='2010-03-31',codes=['2330','2317'])
  state={'units':{},'financial_units':{}}
  journal={'units':{engine.key(job):dict(status=status,complete=False,**row)}}
  return job,state,journal
 def test_historical_hold_plans_explicit_companies_and_period(self):
  job,state,journal=self.fixture();before=copy.deepcopy((job,state,journal))
  tasks,blocked=fm.plan(state,journal,[job],'2010-03','2026-10-27')
  self.assertEqual([x['stock_id'] for x in tasks],['2317','2330']);self.assertFalse(blocked)
  self.assertTrue(all(x['dataset']=='TaiwanStockBalanceSheet' and x['start_date']=='2010-01-01' and x['end_date']=='2010-03-31' and not x['official_gap_closed'] and not x['historical_universe_verified'] for x in tasks))
  self.assertEqual((job,state,journal),before)
 def test_alternate_task_identity_reuses_prior_provider_receipts(self):
  a,s,j=self.fixture();t=fm.plan(s,j,[a],'2010-03','2026-10-27')[0]
  j['units'][engine.key(a)]['status']='SOURCE_CONTENT_INCOMPLETE'
  u=fm.plan(s,j,[a],'2010-03','2026-10-27')[0]
  self.assertEqual([fm.task_key(x) for x in t],[fm.task_key(x) for x in u])
 def test_completed_or_open_derived_quality_is_not_replanned(self):
  for status in ['CONTENT_CHECK_PASS','LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS','SOURCE_CHECKED_OPEN_QUALITY_ITEMS']:
   a,s,j=self.fixture(status);self.assertEqual(fm.plan(s,j,[a],'2010-03','2026-10-27')[0],[])
  a,s,j=self.fixture();j['units'][engine.key(a)]['complete']=True
  self.assertEqual(fm.plan(s,j,[a],'2010-03','2026-10-27')[0],[])
 def test_invalid_local_raw_headers_do_not_prove_numeric_coverage(self):
  a,s,j=self.fixture(local_error='FINANCIAL_VALUES_ABSENT');s['financial_units'][engine.key(a)]={'codes_found':['2330','2317']}
  self.assertEqual(len(fm.plan(s,j,[a],'2010-03','2026-10-27')[0]),2)
 def test_existing_verified_provider_receipt_does_not_request_again(self):
  a,s,j=self.fixture();tasks=fm.plan(s,j,[a],'2010-03','2026-10-27')[0]
  s['finmind_units']={fm.task_key(t):{'status':'SAVED_BASIC_VERIFIED','remote_readback_hash_verified':True} for t in tasks}
  w=Mock(finmind_enabled=True,state=s,journal=j,active='2010-03',today=dt.date(2026,10,27),owner='test',finmind_metrics={'requests':0,'saved':0,'failed':0})
  with patch.object(fm,'reserve') as reserve,redirect_stdout(io.StringIO()):fm.supplement(w,[a])
  reserve.assert_not_called();self.assertEqual(j['finmind_pending'],0);self.assertFalse(j['units'][engine.key(a)]['complete'])
 def test_matching_financial_quarter_remains_uncertified(self):
  a,s,j=self.fixture();t=fm.plan(s,j,[a],'2010-03','2026-10-27')[0][0]
  raw=json.dumps({'status':200,'data':[{'stock_id':t['stock_id'],'date':'2010-03-31','type':'CashAndCashEquivalents','value':100}]}).encode()
  result=fm.validate(raw,t);self.assertFalse(result['numeric_verified']);self.assertFalse(result['pit_verified']);self.assertFalse(result['official_gap_closed'])
  with self.assertRaises(ValueError):fm.validate(raw.replace(b'2010-03-31',b'2010-06-30'),t)
 def test_compact_console_preserves_full_blocked_evidence_in_report(self):
  a=dict(source='TWSE',category='prices_indices',period='2010-03-01');j={'units':{engine.key(a):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}}
  w=Mock(finmind_enabled=True,state={'units':{}},journal=j,active='2010-03',today=dt.date(2026,10,27),owner='test',finmind_metrics={'requests':0,'saved':0,'failed':0})
  out=io.StringIO()
  with redirect_stdout(out):fm.supplement(w,[a])
  report=w.putj.call_args.args[2];console=json.loads(out.getvalue().split('FINMIND_GAPFILL_STATUS ')[1])
  self.assertEqual(len(report['blocked']),1);self.assertEqual(console['blocked_tasks'],1);self.assertNotIn('blocked',console)
  self.assertEqual(sum(console['blocked_reason_counts'].values()),1);self.assertFalse(console['coverage_certified'])
