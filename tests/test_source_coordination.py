import concurrent.futures,hashlib,json,sqlite3,tempfile,threading,unittest
from pathlib import Path
from scripts.v093_source_coordination import Coordinator,StaleOwner
from scripts.v093_source_partition import COUNTS

class SQLiteCAS:
 """Real transactional local harness; not a remote GitHub runner backend."""
 def __init__(self,path):
  self.path=str(path)
  with sqlite3.connect(self.path) as c:c.execute('CREATE TABLE IF NOT EXISTS state(source TEXT PRIMARY KEY,rev INTEGER,value TEXT)')
 def read(self,source):
  with sqlite3.connect(self.path,timeout=20) as c:r=c.execute('SELECT rev,value FROM state WHERE source=?',(source,)).fetchone()
  return (r[0],json.loads(r[1])) if r else (0,None)
 def cas(self,source,rev,state):
  with sqlite3.connect(self.path,timeout=20) as c:
   if rev==0:
    return c.execute('INSERT OR IGNORE INTO state VALUES(?,?,?)',(source,1,json.dumps(state))).rowcount==1
   return c.execute('UPDATE state SET rev=?,value=? WHERE source=? AND rev=?',(rev+1,json.dumps(state),source,rev)).rowcount==1

class CoordinationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.path=Path(self.tmp.name)/'state.db';self.store=SQLiteCAS(self.path);self.now=[1000]
  self.c=Coordinator(self.store,'TWSE',clock=lambda:self.now[0],ttl=20)
 def add(self,n=1):self.c.add([dict(source='TWSE',key=str(i),slot='DESC',period=f'2026-10-{i+1:02d}') for i in range(n)])
 def test_source_hold_blocks_both_directions_and_previously_leased_request(self):
  self.add();ticket=self.c.claim('DESC','old')
  self.c.add([dict(source='TWSE',key='asc',slot='ASC',period='2000-01')])
  self.c.update(lambda s:s.update(hold='RATE_LIMIT'))
  self.assertIsNone(self.c.claim('ASC','new','ASC'))
  with self.assertRaisesRegex(ValueError,'SOURCE_ON_HOLD'):self.c.begin_request(ticket)
  self.assertEqual(self.store.read('TWSE')[1]['tasks']['0']['attempts'],0)
  self.c.update(lambda s:s.pop('hold'))
  self.assertEqual(self.c.begin_request(ticket),1)
 def test_twelve_simultaneous_workers_never_duplicate_or_cross_sources(self):
  jobs=[];seen=[];lock=threading.Lock()
  for source,count in COUNTS.items():
   c=Coordinator(self.store,source)
   for slot in (['ASC','DESC'] if count==2 else ['DESC']):
    c.add([dict(source=source,key=slot+str(i),slot=slot,period=f'2026-10-{i+1:02d}') for i in range(4)])
    jobs.append((source,slot))
  def work(job):
   source,slot=job;c=Coordinator(SQLiteCAS(self.path),source)
   while True:
    t=c.claim(slot,source+slot,slot)
    if not t:break
    c.begin_request(t);raw=(source+t['key']).encode();sha=hashlib.sha256(raw).hexdigest()
    c.saved(t,sha);c.verified(t,sha,True)
    with lock:seen.append((source,t['key']))
  with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:list(pool.map(work,jobs))
  self.assertEqual(len(seen),48);self.assertEqual(len(set(seen)),48)
  for source in COUNTS:
   _,s=self.store.read(source);self.assertTrue(all(t['status']=='RAW_BASIC_VERIFIED' for t in s['tasks'].values()))
 def test_separate_processes_share_one_durable_claim(self):
  import subprocess,sys
  self.add()
  code="import sys,json;sys.path.insert(0,'tests');from test_source_coordination import SQLiteCAS;from scripts.v093_source_coordination import Coordinator;print(json.dumps(Coordinator(SQLiteCAS(sys.argv[1]),'TWSE').claim('DESC',sys.argv[2])))"
  jobs=[subprocess.Popen([sys.executable,'-c',code,str(self.path),owner],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for owner in ('process-a','process-b')]
  results=[]
  for job in jobs:
   out,err=job.communicate(timeout=30);self.assertEqual(job.returncode,0,err.decode());results.append(json.loads(out))
  self.assertEqual(sum(r is not None for r in results),1)
 def test_two_contenders_same_task_only_one_owner(self):
  self.add();barrier=threading.Barrier(2)
  def claim(owner):barrier.wait();return Coordinator(SQLiteCAS(self.path),'TWSE').claim('DESC',owner)
  # Use current-time leases for both contenders.
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:r=list(pool.map(claim,['one','two']))
  self.assertEqual(sum(x is not None for x in r),1)
 def test_expired_owner_cannot_publish_and_request_intent_requires_reconciliation(self):
  self.add();t=self.c.claim('DESC','old');self.c.begin_request(t);self.now[0]+=21
  self.assertIsNone(self.c.claim('DESC','new'))
  with self.assertRaises(StaleOwner):self.c.saved(t,'a'*64)
  self.assertEqual(self.store.read('TWSE')[1]['tasks']['0']['status'],'RECONCILE')
 def test_unstarted_expired_task_can_be_reclaimed_but_old_fence_rejected(self):
  self.add();t=self.c.claim('DESC','old');self.now[0]+=21;new=self.c.claim('DESC','new')
  self.assertGreater(new['fence'],t['fence'])
  with self.assertRaises(StaleOwner):self.c.begin_request(t)
 def test_attempts_survive_new_coordinator_and_stop_after_four(self):
  self.add()
  for attempt in range(4):
   c=Coordinator(SQLiteCAS(self.path),'TWSE',clock=lambda:self.now[0]);t=c.claim('DESC','run'+str(attempt));self.assertEqual(c.begin_request(t),attempt+1);c.failed(t)
  self.assertIsNone(self.c.claim('DESC','fifth'))
  self.assertEqual(self.store.read('TWSE')[1]['tasks']['0']['attempts'],4)
 def test_readback_failure_does_not_finish_task(self):
  self.add();t=self.c.claim('DESC','one');self.c.begin_request(t);self.c.saved(t,'a'*64)
  with self.assertRaises(ValueError):self.c.verified(t,'b'*64,True)
  self.assertEqual(self.store.read('TWSE')[1]['tasks']['0']['status'],'STORED')
 def test_checkpoint_error_blocks_request_and_dispatch(self):
  self.add();t=self.c.claim('DESC','one')
  class Broken:
   def read(_,source):return self.store.read(source)
   def cas(*args):raise OSError('offline fixture')
  broken=Coordinator(Broken(),'TWSE',clock=lambda:self.now[0])
  with self.assertRaises(OSError):broken.begin_request(t)
  called=[]
  self.assertFalse(broken.dispatch_after_save('ASC','run',called.append)) # No mutation or dispatch for an empty slot.
  self.c.add([dict(source='TWSE',key='asc',slot='ASC',period='2000-01')])
  with self.assertRaises(OSError):broken.dispatch_after_save('ASC','run',called.append)
  self.assertEqual(called,[])
 def test_continuation_is_durable_and_not_duplicated_for_same_run(self):
  self.add();called=[]
  def dispatch(identity):
   self.assertEqual(self.store.read('TWSE')[1]['outbox'][identity]['status'],'INTENT');called.append(identity)
  self.assertTrue(self.c.dispatch_after_save('DESC','run',dispatch))
  self.assertFalse(self.c.dispatch_after_save('DESC','run',dispatch));self.assertEqual(len(called),1)
 def test_fast_receiver_ack_is_not_overwritten_by_sender_completion(self):
  self.c.add([dict(source='TWSE',key='next',slot='DESC',period='2026-10-01')])
  def receiver(identity):
   self.c.update(lambda state:state['outbox'][identity].update(status='RECEIVED',received_run_id='next-run'))
  self.assertTrue(self.c.dispatch_after_save('DESC','run',receiver))
  self.assertEqual(next(iter(self.c.store.read('TWSE')[1]['outbox'].values()))['status'],'RECEIVED')
 def test_saved_interruption_is_dispatched_for_readback_without_new_attempt(self):
  self.c.add([dict(source='TWSE',key='saved',slot='DESC',period='2026-10-01')])
  ticket=self.c.claim('DESC','first');self.c.begin_request(ticket);self.c.prepare_save(ticket,'a'*64,'immutable-locator');self.c.error(ticket,'RECONCILE','STORE','OSError')
  called=[];self.assertTrue(self.c.dispatch_after_save('DESC','recover-run',called.append));self.assertEqual(len(called),1)
  recovered=self.c.recover('DESC','cold');self.assertIsNotNone(recovered);self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['saved']['attempts'],1)
 def test_unrecoverable_saved_locator_is_held_after_four_readback_attempts(self):
  self.c.add([dict(source='TWSE',key='lost',slot='DESC',period='2026-10-01')])
  ticket=self.c.claim('DESC','first');self.c.begin_request(ticket);self.c.prepare_save(ticket,'a'*64,'lost-locator');self.c.error(ticket,'RECONCILE','STORE','OSError')
  for attempt in range(4):
   ticket=self.c.recover('DESC','cold');self.assertIsNotNone(ticket);self.c.error(ticket,'RECONCILE','LOOKUP','OSError')
  self.assertIsNone(self.c.recover('DESC','fifth'));task=self.c.store.read('TWSE')[1]['tasks']['lost']
  self.assertEqual(task['status'],'STORAGE_HOLD');self.assertEqual(task['recovery_attempts'],4);self.assertEqual(task['attempts'],1)
 def test_uncertain_dispatch_is_not_blindly_repeated(self):
  self.add()
  def fail(_):raise TimeoutError('dispatch fixture')
  with self.assertRaises(TimeoutError):self.c.dispatch_after_save('DESC','run',fail)
  self.assertFalse(self.c.dispatch_after_save('DESC','run',lambda _:self.fail('must reconcile')))
 def test_no_continuation_when_only_cooling_down_or_source_hold(self):
  self.add();t=self.c.claim('DESC','one');self.c.begin_request(t);self.c.failed(t,retry_after=300)
  self.assertFalse(self.c.dispatch_after_save('DESC','run',lambda _:self.fail('no ready task')))
 def test_running_owner_is_not_duplicated_by_watchdog(self):
  self.add();self.c.claim('DESC','one')
  self.assertFalse(self.c.dispatch_after_save('DESC','run',lambda _:self.fail('owner active')))
