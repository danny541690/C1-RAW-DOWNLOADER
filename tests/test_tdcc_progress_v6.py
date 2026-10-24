import json,time,unittest
from scripts import v093_tdcc_independent as m

class PendingBreakdownTests(unittest.TestCase):
 def test_backlog_is_not_a_failure_count(self):
  r={'d|ok':dict(status='SAVED_BASIC_VERIFIED',file_id='f',sha256='s',remote_readback_hash_verified=True),
     'd|empty':dict(status='SKIPPED_SOURCE_EMPTY'),
     'd|failed':dict(status='UNRESOLVED',attempts=1,retry_after_epoch=time.time()+900),
     'd|cap':dict(status='UNRESOLVED',attempts=3),
     'd|intent':dict(status='REQUEST_INTENT',attempts=1)}
  s=m.history_summary('d',['ok','empty','failed','cap','intent','new'],r)
  self.assertEqual((s['saved'],s['source_empty'],s['pending_total']),(1,1,4))
  self.assertEqual((s['not_attempted'],s['failed'],s['interrupted']),(1,2,1))
  self.assertEqual((s['retry_exhausted'],s['retry_cooldown']),(1,1))
  self.assertEqual(s['pending_total'],s['not_attempted']+s['failed']+s['interrupted']+s['other_unverified'])
  self.assertFalse(s['historical_universe_complete'])

class JournalCheckpointTests(unittest.TestCase):
 def worker(self):
  w=object.__new__(m.Worker);w.state=dict(receipts={},history_receipts={},history_receipt_date='20261016')
  w.ctrl='ctrl';w.writes=[];w.write_status=lambda:w.writes.append(('STATUS.json',b''))
  w.d=type('D',(),{})();w.d.put=lambda parent,name,raw,*a,**kw:w.writes.append((name,raw))
  return w
 def test_intent_and_result_durable_with_coalesced_metadata(self):
  w=self.worker();w.state['history_receipts']['d|x']={'status':'REQUEST_INTENT','attempts':1};w.save()
  w.state['history_receipts']['d|x']={'status':'SAVED_BASIC_VERIFIED','file_id':'f','sha256':'s','remote_readback_hash_verified':True};w.save()
  names=[n for n,_ in w.writes]
  self.assertEqual(names.count('HISTORY_20261016.json'),2)
  self.assertEqual(names.count('CURSOR.json'),1);self.assertEqual(names.count('STATUS.json'),1)
  w.save();self.assertEqual(len(w.writes),4)
  # Restart reads the final journal even when CURSOR predates the success.
  state=json.loads(next(raw for name,raw in w.writes if name=='CURSOR.json'))
  raw=[raw for name,raw in w.writes if name=='HISTORY_20261016.json'][-1]
  m.restore_history(state,lambda name:raw)
  self.assertEqual(state['history_receipts']['d|x']['status'],'SAVED_BASIC_VERIFIED')
 def test_snapshot_changes_remain_immediately_durable(self):
  w=self.worker();w.save();w.state['receipts']['snapshot']={'status':'REQUEST_INTENT'};w.save()
  self.assertEqual([n for n,_ in w.writes].count('CURSOR.json'),2)
  self.assertEqual([n for n,_ in w.writes].count('HISTORY_20261016.json'),1)
 def test_date_change_and_final_exit_flush_metadata(self):
  w=self.worker();w.save();w.state['history_receipt_date']='20261008';w.save();w.save(force=True)
  self.assertEqual([n for n,_ in w.writes].count('CURSOR.json'),3)
 def test_failed_write_is_not_cached_as_saved(self):
  w=self.worker();put=w.d.put
  def fail(*args,**kw):raise OSError('write rejected')
  w.d.put=fail
  with self.assertRaises(OSError):w.save()
  self.assertFalse(hasattr(w,'_journal_saved'))
  w.d.put=put;w.save();self.assertEqual(w.writes[0][0],'HISTORY_20261016.json')
 def test_saved_success_still_skips_all_source_requests(self):
  w=self.worker();w.saved=0;w.skipped=0;w.state['history_receipts']['d|ok']={'status':'SAVED_BASIC_VERIFIED','sha256':'keep'}
  w.request=lambda *a:self.fail('successful RAW must not be downloaded')
  self.assertTrue(w.process('d|ok',m.QUERY,'x',date='d',code='ok'))
  self.assertEqual(w.state['history_receipts']['d|ok']['sha256'],'keep');self.assertEqual(w.writes,[])
