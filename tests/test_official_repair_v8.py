import copy,time,unittest
from unittest.mock import Mock,patch
from scripts import v093_official_repair as r

class MissingFinancialPlanTests(unittest.TestCase):
 def job(self,codes,report='IncomeStatement'):
  return dict(source='MOPS',category=report,period='2013-06-30',report_period='20132',month='2013-06',codes=codes,
   url='https://mopsfin.twse.com.tw/compare/report',params=[('compareItem',report),('ys','20132')]+[('companyId',c) for c in codes])
 def test_never_planned_financial_companies_become_downloads(self):
  state={'units':{},'financial_units':{}}
  jobs=r.missing_financial_jobs(state,[self.job(['2330','2317'])])
  self.assertEqual(jobs,[self.job(['2330','2317'])]);self.assertEqual(state,{'units':{},'financial_units':{}})
 def test_existing_good_and_exhausted_pairs_not_reissued_when_chunks_change(self):
  good=dict(self.job(['2330']),status='SAVED_BASIC_VERIFIED',codes_found=['2330'],sha256='sha',evidence_file='a/raw')
  exhausted=dict(self.job(['2317']),status='RETRY_WAIT',attempts=3,retry_cycle=5)
  state={'units':{},'financial_units':{'good':good,'failed':exhausted}};before=copy.deepcopy(state)
  jobs=r.missing_financial_jobs(state,[self.job(['2330','2317','2454'])])
  self.assertEqual(jobs,[self.job(['2454'])]);self.assertEqual(state,before)
  self.assertNotEqual(r.engine.key(jobs[0]),r.engine.key(self.job(['2330','2317','2454'])))
 def test_company_coverage_is_scoped_to_report_and_quarter(self):
  old=dict(self.job(['2330']),status='SAVED_BASIC_VERIFIED',codes_found=['2330'],sha256='sha',evidence_file='a/raw')
  state={'units':{},'financial_units':{'old':old}}
  job=self.job(['2330'],'BalanceSheet')
  self.assertEqual(r.missing_financial_jobs(state,[job]),[job])
 def test_duplicate_planned_pairs_not_duplicated(self):
  self.assertEqual(len(r.missing_financial_jobs({},[self.job(['2330']),self.job(['2330'])])),1)

 def test_sparse_remaining_companies_rebatched_to_twenty(self):
  planned=[self.job([str(i)]) for i in range(41)]
  jobs=r.missing_financial_jobs({},planned)
  self.assertEqual([len(x['codes']) for x in jobs],[20,20,1])
  reserved={'financial_units':{r.engine.key(j):j for j in jobs}}
  self.assertEqual(r.missing_financial_jobs(reserved,planned),[])

class ReconciliationTests(unittest.TestCase):
 def worker(self):
  w=object.__new__(r.RepairWorker);w.cursor={'month_index':2};w.months=['2013-01','2013-02','2013-03'];w.pending_index={};w.stagectrl='stage';w.putj=Mock();w.save_cursor=Mock();return w
 def test_already_visited_months_requeued_once_without_rewinding(self):
  w=self.worker();w.seed_plan_reconciliation();w.seed_plan_reconciliation()
  self.assertEqual(set(w.pending_index),{'2013-01','2013-02'});self.assertEqual(w.cursor['month_index'],2)
  self.assertTrue(all(x['plan_reconciliation_required'] for x in w.pending_index.values()));w.putj.assert_called_once()
 def test_partial_reconciliation_stays_queued_and_completed_one_clears(self):
  w=self.worker();w.seed_plan_reconciliation();w.until=time.monotonic()+1200
  def capture(worker,month):
   self.assertFalse(worker._due_only)
   worker.journal={'month':month,'units':{}}
   worker.month_incomplete=month=='2013-01'
   return True
  with patch.object(r,'capture_history_month',side_effect=capture):w.run_due_work()
  self.assertTrue(w.pending_index['2013-01']['plan_reconciliation_required'])
  self.assertFalse(w.pending_index['2013-02'].get('plan_reconciliation_required'))

class CaptureIntegrationTests(unittest.TestCase):
 def test_missing_financial_download_is_routed_to_financial_bucket(self):
  import datetime as dt
  w=object.__new__(r.RepairWorker);w.lane='RECENT_ASC';w.roots={'RAW':'raw'};w.d=Mock();w.d.find.return_value={'id':'month'}
  w.monthctrl='month';w.today=dt.date(2026,10,25);w.active='2013-06';w.state={'units':{},'financial_units':{}}
  job=MissingFinancialPlanTests().job(['2330'])
  w.financial_jobs=Mock(return_value=[job]);w.restore=Mock();w.flags_for=Mock(return_value={});w.save_journal=Mock()
  w.cursor={};w.until=time.monotonic()+600;w.checked=w.repaired=0;w.source_requests={};w.repair_one=Mock()
  journal={'month':'2013-06','units':{}}
  with patch.object(r.engine,'getj',side_effect=[journal,{}]),patch.object(r.native.Audit,'jobs',return_value=[]):
   w.capture_month_units('2013-06')
  w.repair_one.assert_called_once_with(job,'financial_units',[])
  self.assertEqual(journal['financial_plan_jobs'],{r.engine.key(job):job})
  self.assertEqual(journal['missing_financial_plan']['new_units'],1)
