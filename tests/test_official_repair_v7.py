import copy,time,json,unittest,collections,datetime as dt
from unittest.mock import Mock,patch
from scripts import v093_official_repair as r

class DurableJournalTests(unittest.TestCase):
 def worker(self):
  w=object.__new__(r.RepairWorker);w.journal={'month':'2013-01','units':{}}
  w.monthctrl='month';w.stagectrl='stage';w.pending_index={};w.cursor={};w.owner='run/RAW'
  w.checked=w.repaired=w.downloaded=0;w.source_requests=collections.Counter();w._last_progress=time.monotonic()
  w.writes=[];w.putj=lambda parent,name,obj:w.writes.append((parent,name,copy.deepcopy(obj)));w.save_state=Mock()
  return w
 def test_changed_intent_and_result_durable_but_retry_index_coalesced(self):
  w=self.worker();w.journal['units']['x']={'status':'SOURCE_CHECK_REQUEST_INTENT','attempts':1};w.save_journal()
  w.journal['units']['x'].update(status='CONTENT_CHECK_PASS',complete=True,raw_sha256='sha');w.save_journal();w.save_journal()
  self.assertEqual(sum(n=='OFFICIAL_REPAIR_STATE.json' for p,n,o in w.writes),2)
  self.assertEqual(sum(n=='RETRY_MONTHS.json' for p,n,o in w.writes),1)
  self.assertEqual([o for p,n,o in w.writes if n=='OFFICIAL_REPAIR_STATE.json'][-1]['units']['x']['raw_sha256'],'sha')
 def test_local_state_and_retry_index_force_flushed_at_month_boundary(self):
  w=self.worker();w.save_journal();w._local_state_dirty=True;w.save_journal();w.save_state.assert_not_called()
  w.flush_auxiliary(force=True);w.save_state.assert_called_once();self.assertFalse(w._local_state_dirty)
  self.assertEqual(sum(n=='RETRY_MONTHS.json' for p,n,o in w.writes),2)
 def test_failed_journal_write_never_cached_as_success(self):
  w=self.worker();put=w.putj;w.putj=Mock(side_effect=OSError('remote failed'))
  with self.assertRaises(OSError):w.save_journal()
  self.assertFalse(hasattr(w,'_journal_saved'));w.putj=put;w.save_journal()
  self.assertEqual(sum(n=='OFFICIAL_REPAIR_STATE.json' for p,n,o in w.writes),1)
 def test_pending_full_inventory_marker_survives_partial_month(self):
  w=self.worker();w.pending_index['2013-01']={'inventory_required':True};w.save_journal()
  self.assertTrue(w.pending_index['2013-01']['inventory_required'])
  self.assertEqual(w.pending_index['2013-01']['next_retry_at'],0)
  self.assertIn('2013-01',r.due_months(w.pending_index))
 def test_capture_exception_still_flushes_derived_checkpoints(self):
  w=self.worker();w.capture_month_units=Mock(side_effect=ValueError('parser'));w.flush_auxiliary=Mock();w.publish_unresolved=Mock()
  with self.assertRaises(ValueError):w.capture_month('2013-01')
  w.flush_auxiliary.assert_called_once_with(force=True);w.publish_unresolved.assert_called_once()

class TargetedRetryTests(unittest.TestCase):
 def test_due_queue_rotates_and_leaves_frontier_budget(self):
  w=object.__new__(r.RepairWorker);w.cursor={'last_due_month':'2000-01'};w.save_cursor=Mock();w.putj=Mock();w.stagectrl='stage'
  w.pending_index={m:{'next_retry_at':0,'retry_units':1} for m in ['2000-01','2000-02']};w.until=time.monotonic()+1200;original=w.until;seen=[]
  def capture(worker,month):
   seen.append(month);self.assertTrue(worker._due_only);self.assertLess(worker.until,time.monotonic()+181);return True
  with patch.object(r,'capture_history_month',side_effect=capture):w.run_due_work()
  self.assertEqual(seen,['2000-02','2000-01']);self.assertEqual(w.until,original);self.assertFalse(w._due_only)
 def test_control_gaps_full_inventory_prioritized_and_only_seeded_once(self):
  w=object.__new__(r.RepairWorker);w.lane='RECENT_ASC';w.cursor={};w.pending_index={};w.stagectrl='stage';w.putj=Mock();w.save_cursor=Mock()
  w.seed_control_gaps();self.assertEqual(set(w.pending_index),set(r.CONTROL_GAP_MONTHS));w.seed_control_gaps();self.assertEqual(w.putj.call_count,1)
  w.until=time.monotonic()+600;seen=[]
  def capture(worker,month):seen.append(month);self.assertFalse(worker._due_only);return True
  with patch.object(r,'capture_history_month',side_effect=capture):w.run_due_work()
  self.assertEqual(set(seen),set(r.CONTROL_GAP_MONTHS));self.assertFalse(any(v.get('inventory_required') for v in w.pending_index.values()))
 def test_only_due_existing_rows_are_repaired(self):
  w=object.__new__(r.RepairWorker);w.lane='RECENT_ASC';w._due_only=True;w.roots={'RAW':'raw'};w.d=Mock();w.d.find.return_value={'id':'month'};w.monthctrl='month';w.today=dt.date(2026,10,24)
  jobs=[dict(source='TWSE',category='prices',period='2013-01-'+day,month='2013-01',url='https://www.twse.com.tw/x') for day in ['02','03','04']]
  keys=[r.engine.key(j) for j in jobs];w.state={'units':{k:dict(j,status='SAVED_BASIC_VERIFIED',sha256=k,evidence_file='archive/member') for k,j in zip(keys,jobs)},'financial_units':{}}
  journal={'month':'2013-01','units':{keys[0]:{'status':'UNRESOLVED_SOURCE_BACKOFF','next_retry_at':0},keys[1]:{'status':'CONTENT_CHECK_PASS','terminal':True,'complete':True},keys[2]:{'status':'UNRESOLVED_SOURCE_LIMIT','next_retry_at':time.time()+3600}}}
  w.restore=Mock();w.flags_for=Mock(return_value={});w.save_journal=Mock();w.cursor={};w.until=time.monotonic()+600;w.checked=w.repaired=0;w.source_requests={};w.repair_one=Mock()
  with patch.object(r.engine,'getj',side_effect=[journal,{}]),patch.object(r.native.Audit,'jobs',return_value=jobs):w.capture_month_units('2013-01')
  self.assertEqual(w.repair_one.call_count,1);self.assertEqual(w.repair_one.call_args.args[0]['period'],'2013-01-02')

class GapInventorySafetyTests(unittest.TestCase):
 def test_gap_import_must_finish_before_any_official_request(self):
  w=object.__new__(r.RepairWorker);w.lane='RECENT_ASC';w._control_gap_inventory=True;w.roots={'RAW':'raw'};w.d=Mock();w.d.find.return_value={'id':'month'};w.monthctrl='month';w.restore=Mock();w.inventory_existing=Mock(return_value=False);w.repair_one=Mock()
  with patch.object(r.engine,'getj',return_value={}),patch.object(r.native.Audit,'jobs') as planner:
   self.assertFalse(w.capture_month_units('2014-05'))
  w.inventory_existing.assert_called_once_with(r.SOURCES);planner.assert_not_called();w.repair_one.assert_not_called();self.assertTrue(w.month_incomplete)
