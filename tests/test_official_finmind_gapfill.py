import datetime as dt, json, time, unittest
from unittest.mock import patch, Mock
from scripts import v093_official_finmind_gapfill as fm
from scripts import v093_history_reverse as engine

class GapfillTests(unittest.TestCase):
 def job(self,**kw):return dict(source='TWSE',category='prices_indices',period='2020-01-02',**kw)
 def state(self):return dict(units={'calendar':dict(source='TPEx',category='prices',period='2020-01-02',status='SAVED_BASIC_VERIFIED'),'calendar2':dict(source='TPEx',category='prices',period='2020-01-03',status='SAVED_BASIC_VERIFIED')},financial_units={},market_codes={'TWSE':['2330','0050','TSE']})
 def tasks(self,status='SOURCE_NO_DATA_UNCONFIRMED',**row):
  j=self.job();journal={'units':{engine.key(j):dict(status=status,**row)}}
  return fm.plan(self.state(),journal,[j],'2020-01','2026-10-27')
 def test_explicit_gap_only_and_stock_ids(self):
  tasks,blocked=self.tasks();self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['stock_id'],'2330');self.assertFalse(blocked)
  self.assertFalse(fm.plan(self.state(),{'units':{}},[self.job()],'2020-01','2026-10-27')[0])
 def test_valid_and_derived_quality_not_recrawled(self):
  for status in ('CONTENT_CHECK_PASS','LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS','SOURCE_CHECKED_OPEN_QUALITY_ITEMS'):
   self.assertFalse(self.tasks(status)[0])
  self.assertFalse(self.tasks(complete=True)[0])
 def test_future_date_never_requested(self):
  j=dict(source='TWSE',category='prices_indices',period='2026-10-28')
  self.assertFalse(fm.plan(self.state(),{'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}},[j],'2026-10','2026-10-27')[0])
 def test_unknown_historical_universe_explicit(self):
  j=self.job();tasks,blocked=fm.plan({'units':{}},{'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}},[j],'2020-01','2026-10-27')
  self.assertFalse(tasks);self.assertTrue(blocked)
 def test_gap_dates_grouped_and_archive_key_identical(self):
  a=self.job();b=dict(a,period='2020-01-03');journal={'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'} for j in (a,b)}}
  tasks,_=fm.plan(self.state(),journal,[a,b],'2020-01','2026-10-27')
  self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['expected_dates'],['2020-01-02','2020-01-03']);self.assertEqual(fm.task_key(tasks[0]),engine.key(tasks[0]))
 def payload(self,**kw):
  row=dict(stock_id='2330',date='2020-01-02',open=10,max=12,min=9,close=11);row.update(kw)
  return json.dumps({'status':200,'data':[row]}).encode()
 def test_ohlc_gap_evidence_not_official_certification(self):
  task=self.tasks()[0][0];ev=fm.validate(self.payload(),task)
  self.assertEqual(ev['covered_dates'],['2020-01-02']);self.assertFalse(ev['official_gap_closed']);self.assertFalse(ev['numeric_verified'])
  for changes in ({'max':8},{'stock_id':'2317'},{'date':'2020-02-01'},{'close':float('nan')}):
   with self.assertRaises(ValueError):fm.validate(self.payload(**changes),task)
 def test_empty_and_quota_never_success(self):
  task=self.tasks()[0][0]
  with self.assertRaises(ValueError):fm.validate(b'{"status":200,"data":[]}',task)
  with self.assertRaises(PermissionError):fm.validate(b'{"status":402,"data":[]}',task)
 def test_financial_missing_companies_only(self):
  j=dict(source='MOPS',category='IncomeStatement',period='2020-03-31',codes=['2330','2317'])
  state=dict(financial_units={engine.key(j):{'codes_found':['2330']}})
  tasks,_=fm.plan(state,{'units':{engine.key(j):{'status':'SOURCE_CONTENT_INCOMPLETE'}}},[j],'2020-03','2026-10-27')
  self.assertEqual([t['stock_id'] for t in tasks],['2317']);self.assertEqual(tasks[0]['start_date'],'2020-01-01')
 def test_shared_quota_survives_workers_and_provider_hold(self):
  manifest={'jobs':{}};writes=[]
  def write(a,t,sha,m,msg):writes.append(msg);return True
  with patch.object(fm,'_read',return_value=('sha',manifest)),patch.object(fm,'_put',side_effect=write):
   self.assertTrue(fm.reserve('api','token',now=100));self.assertFalse(fm.reserve('api','token',now=101))
   self.assertTrue(fm.reserve('api','token',now=118))
   manifest['jobs'][fm.BUDGET_KEY]['requests']=[119]*200
   self.assertFalse(fm.reserve('api','token',now=140))
 def test_completed_receipt_skips_network(self):
  j=self.job();state=self.state();journal={'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}}
  task=fm.plan(state,journal,[j],'2020-01','2026-10-27')[0][0]
  state['finmind_units']={fm.task_key(task):{'status':'SAVED_BASIC_VERIFIED','remote_readback_hash_verified':True}}
  w=Mock(finmind_enabled=True,state=state,journal=journal,active='2020-01',today=dt.date(2026,10,27),owner='run',finmind_metrics={'requests':0,'saved':0,'failed':0})
  with patch.object(fm,'reserve') as reserve:fm.supplement(w,[j]);reserve.assert_not_called()
  self.assertEqual(w.journal['finmind_pending'],0)
 def test_request_save_readback_then_resume_without_duplicate(self):
  j=self.job();state=self.state();journal={'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}}
  w=Mock(finmind_enabled=True,state=state,journal=journal,active='2020-01',today=dt.date(2026,10,27),owner='run',finmind_metrics={'requests':0,'saved':0,'failed':0},until=time.monotonic()+100)
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read.return_value=self.payload()
  def save(worker,task,raw,receipt,bucket):worker.state[bucket][engine.key(task)]=dict(receipt,evidence_file='file/unit.raw')
  with patch.object(fm,'reserve',return_value=True),patch.object(fm.urllib.request,'urlopen',return_value=response) as request,patch.object(fm.base.Worker,'record_payload',side_effect=save),patch.object(fm,'cached_payload',return_value=(self.payload(),{})):
   fm.supplement(w,[j]);fm.supplement(w,[j]);self.assertEqual(request.call_count,1)
  receipt=next(iter(state['finmind_units'].values()));self.assertTrue(receipt['remote_readback_hash_verified']);self.assertFalse(receipt['official_gap_closed']);self.assertEqual(w.finmind_metrics['saved'],1)
 def test_readback_failure_does_not_count_as_saved(self):
  j=self.job();state=self.state();journal={'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}}
  w=Mock(finmind_enabled=True,state=state,journal=journal,active='2020-01',today=dt.date(2026,10,27),owner='run',finmind_metrics={'requests':0,'saved':0,'failed':0},until=time.monotonic()+100)
  response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read.return_value=self.payload()
  def save(worker,task,raw,receipt,bucket):worker.state[bucket][engine.key(task)]=dict(receipt,evidence_file='file/unit.raw')
  with patch.object(fm,'reserve',return_value=True),patch.object(fm.urllib.request,'urlopen',return_value=response),patch.object(fm.base.Worker,'record_payload',side_effect=save),patch.object(fm,'cached_payload',return_value=(b'wrong',{})):
   fm.supplement(w,[j])
  self.assertEqual(w.finmind_metrics['saved'],0);self.assertIn('SHA_MISMATCH',next(iter(state['finmind_units'].values()))['error'])

class CalendarGapTests(unittest.TestCase):
 def test_unconfirmed_holiday_never_requests_every_stock(self):
  j=dict(source='TWSE',category='prices_indices',period='2014-06-02')
  state=dict(units={},market_codes={'TWSE':['1101','2330']})
  journal={'units':{engine.key(j):{'status':'SOURCE_NO_DATA_UNCONFIRMED'}}}
  tasks,blocked=fm.plan(state,journal,[j,j],'2014-06','2026-10-27')
  self.assertFalse(tasks);self.assertEqual(len(blocked),1);self.assertIn('TRADING_DATE_NOT_PROVEN',blocked[0]['reason'])
