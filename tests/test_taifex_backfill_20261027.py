import datetime as dt,unittest,time
from unittest.mock import Mock,patch
from scripts import v093_taifex_independent as m
class Backfill(unittest.TestCase):
 def worker(self):
  w=object.__new__(m.Worker);w.backfill=True;w.direction='ASC';w.today=dt.date(2026,10,27);w.state={'receipts':{},'tick_jobs':{}};w.save=Mock()
  self.old=m.make_job('old','https://www.taifex.com.tw/cht/3/futDataDown','csv',dt.date(2000,1,1),dt.date(2000,1,31),{})
  self.new=dict(self.old,key='new');w.history_jobs=lambda:[self.old,self.new];return w
 def test_missing_plan_added_and_empty_reopened_once(self):
  w=self.worker();w.state['receipts']['old']={'status':'SKIPPED_SOURCE_EMPTY','attempts':2,'request':self.old,'error':'OfficialEmpty:empty','response_sha256':'preserved'}
  w.prepare_backfill();e=w.state['receipts']['old'];self.assertEqual(e['status'],'UNRESOLVED');self.assertEqual(e['attempts'],0);self.assertEqual(e['response_sha256'],'preserved');self.assertEqual(e['offline_recovery_revision'],m.REPAIR_REVISION)
  e['attempts']=1;e['status']='SKIPPED_SOURCE_EMPTY';w.prepare_backfill();self.assertEqual(e['attempts'],1);self.assertEqual(e['status'],'SKIPPED_SOURCE_EMPTY');self.assertEqual(len(e['backfill_history']),1);self.assertIn('new',w.state['receipts'])
 def test_success_and_integrity_hold_untouched(self):
  w=self.worker();a={'status':'SAVED_BASIC_VERIFIED','file_id':'original','sha256':'same','attempts':2};b={'status':'UNRESOLVED','integrity_hold':True,'attempts':3}
  w.state['receipts']={'old':dict(a),'new':dict(b)};w.prepare_backfill();self.assertEqual(w.state['receipts']['old'],a);self.assertEqual(w.state['receipts']['new'],b)
 def test_old_snapshot_never_recreated_and_wrong_partition_ignored(self):
  w=self.worker();w.history_jobs=lambda:[]
  snapshot={'status':'UNRESOLVED','request':dict(self.old,kind='snapshot')};other={'status':'UNRESOLVED','request':dict(self.old,key='other',start='2013-01-01',end='2013-01-31')}
  w.state['receipts']={'snapshot':dict(snapshot),'other':dict(other)};w.prepare_backfill();self.assertEqual(w.state['receipts']['snapshot'],snapshot);self.assertEqual(w.state['receipts']['other'],other)
 def test_unrecorded_job_reaches_source_in_backfill(self):
  w=self.worker();w.recorded_repair_keys=frozenset();w.live=lambda:True;w.eligible=lambda j:True;w.requests=0;w.saved=0;w.request=Mock(return_value=b'raw');w.persist_raw=Mock();w.until=time.monotonic()+100
  with patch.object(m,'validate',return_value={'rows':1}),patch.object(m,'official_csv_mirror',return_value=None):w.process(self.new)
  w.request.assert_called_once();self.assertEqual(w.state['receipts']['new']['backfill_pass'],m.BACKFILL_PASS)
