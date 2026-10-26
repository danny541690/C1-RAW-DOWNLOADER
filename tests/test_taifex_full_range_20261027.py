import datetime as dt, unittest, copy
from unittest.mock import patch,Mock
from scripts import v093_taifex_full_range as c
from scripts import v093_taifex_independent as m

class FullRangeTests(unittest.TestCase):
 def job(self,year=2000,kind='csv'):
  return dict(key='HISTORY|x|'+str(year),kind=kind,start=f'{year}-01-01',end=f'{year}-01-31',url=m.SITE+'/cht/3/x')
 def test_both_directions_include_old_and_recent(self):
  jobs=[self.job(2000),self.job(2012),self.job(2013),self.job(2026)]
  for direction in ('ASC','DESC'):
   self.assertEqual(m.partition_jobs(jobs,direction,True),jobs)
   self.assertTrue(all(m.assigned_job(j,direction,True) for j in jobs))
 def test_other_frontier_cannot_claim_same_month(self):
  j=self.job();state,ok=c.elect({},'ASC',j);self.assertTrue(ok)
  other=dict(j,key='other dataset',url=m.SITE+'/cht/3/y')
  second,ok=c.elect(state,'DESC',other);self.assertFalse(ok);self.assertEqual(second,state)
  self.assertTrue(c.elect(state,'ASC',other)[1])
 def test_annual_not_confused_with_month_and_snapshots(self):
  self.assertNotEqual(c.group(self.job()),c.group(self.job(kind='annual')))
  self.assertEqual(c.group(self.job(kind='snapshot')),'SNAPSHOT|2000-01-31')
 def test_invalid_direction_or_pre_floor_rejected(self):
  for direction,j in [('wrong',self.job()),('ASC',self.job(1999))]:
   with self.assertRaises(ValueError):c.elect({},direction,j)
 def test_merge_only_verified_and_never_erase_hold_or_valid(self):
  valid=dict(status='SAVED_BASIC_VERIFIED',remote_readback_hash_verified=True,file_id='f',sha256='sha')
  state={'receipts':{'hold':{'integrity_hold':True},'good':dict(valid)}}
  peer={'receipts':{'new':valid,'hold':valid,'good':dict(valid,sha256='different'),'unverified':dict(valid,remote_readback_hash_verified=False)},'source_backoff':{'host':50}}
  self.assertEqual(c.merge_verified(state,peer),1);self.assertEqual(state['receipts']['good']['sha256'],'sha');self.assertTrue(state['receipts']['hold']['integrity_hold'])
  state['receipts']['new']['sha256']='local';self.assertEqual(peer['receipts']['new']['sha256'],'sha')
 def test_claim_cache_avoids_repeated_manifest_reads(self):
  manifest={'jobs':{}};cache={}
  with patch.object(c,'_read',return_value=('sha',manifest)) as read,patch.object(c,'_put',return_value=True):
   self.assertTrue(c.claim('api','token','ASC',self.job(),cache));self.assertTrue(c.claim('api','token','ASC',self.job(),cache));self.assertFalse(c.claim('api','token','DESC',self.job(),cache));self.assertEqual(read.call_count,1)
 def test_batch_does_not_stop_after_peer_owned_first_units(self):
  w=object.__new__(m.Worker);w._peer_owned_keys=set();w.eligible=lambda j:j['key'] not in w._peer_owned_keys
  jobs=[dict(self.job(),key=str(i)) for i in range(8)];done=[]
  def process(j):
   if int(j['key'])<6:w._peer_owned_keys.add(j['key'])
   else:done.append(j['key'])
   return True
  w.process=process;w.batch(jobs,2);self.assertEqual(done,['6','7'])
 def test_full_range_backfill_retains_success_across_old_boundary(self):
  w=object.__new__(m.Worker);w.backfill=True;w.full_range=True;w.direction='DESC';w.today=dt.date(2026,10,27);w.save=Mock()
  a=self.job(2000);b=self.job(2026);w.history_jobs=lambda:[a,b];w.state={'receipts':{a['key']:{'request':a,'status':'SAVED_BASIC_VERIFIED','file_id':'preserve'},b['key']:{'request':b,'status':'SKIPPED_SOURCE_EMPTY'}},'tick_jobs':{}}
  w.prepare_backfill();self.assertEqual(w.state['receipts'][a['key']]['file_id'],'preserve');self.assertEqual(w.state['receipts'][b['key']]['status'],'UNRESOLVED')
 def test_native_price_relationship_volume_and_missing_are_distinct(self):
  header='日期,契約,開盤價,最高價,最低價,最後成交價,成交量\n'
  start=dt.date(2020,1,1);end=dt.date(2020,1,31)
  good=m.csv_evidence((header+'2020/01/02,TX,10,12,9,11,1\n').encode(),start,end)
  self.assertEqual(good['recognized_numeric_checks'],2);self.assertFalse(good['full_numeric_certification'])
  for row in ('2020/01/02,TX,10,8,9,11,1','2020/01/02,TX,10,12,9,11,-1','2020/01/02,TX,10,12,9,11,NaN','2020/01/02,TX,10'):
   with self.assertRaises(ValueError):m.csv_evidence((header+row).encode(),start,end)
  missing=m.csv_evidence((header+'2020/01/02,TX,-,-,-,-,0\n').encode(),start,end)
  self.assertEqual(missing['unverified_price_rows'],1)
