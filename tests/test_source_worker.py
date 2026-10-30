import tempfile,unittest
from pathlib import Path
from test_source_coordination import SQLiteCAS
from test_source_executor import DiskAdapter
from scripts.v093_source_coordination import Coordinator
from scripts.v093_source_worker import run_batch
class WorkerTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.c=Coordinator(SQLiteCAS(self.root/'state'),'TWSE')
  self.c.add([dict(source='TWSE',key=key,slot='DESC',period='2026-10-29') for key in ('z-bad','a-good')])
 def test_bad_first_task_does_not_stop_following_good_task(self):
  def factory(ticket,task):
   a=DiskAdapter(self.root)
   if ticket['key']=='z-bad':a.validate=lambda raw:(_ for _ in ()).throw(ValueError('bad'))
   return a
  r=run_batch(self.c,factory,'DESC','worker')
  self.assertEqual(r['task_status_counts'],dict(CONTENT_BLOCKED=1,RAW_BASIC_VERIFIED=1));self.assertEqual(r['processed'],2)
 def test_invalid_adapter_is_held_without_spending_attempt_and_next_continues(self):
  def factory(ticket,task):
   if ticket['key']=='z-bad':raise ValueError('missing native contract')
   return DiskAdapter(self.root)
  r=run_batch(self.c,factory,'DESC','worker');self.assertEqual(r['task_status_counts'],dict(APPLICABILITY_HOLD=1,RAW_BASIC_VERIFIED=1));self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['z-bad']['attempts'],0)
 def test_unit_budget_keeps_ready_work_for_next_batch(self):
  r=run_batch(self.c,lambda t,s:DiskAdapter(self.root),'DESC','worker',max_units=1)
  self.assertEqual(r['processed'],1);self.assertEqual(r['ready_remaining'],1)
 def test_interrupted_save_is_recovered_without_fetch_and_failure_not_looped(self):
  self.c.update(lambda s:s['tasks'].pop('z-bad'))
  a=DiskAdapter(self.root);a.crash=True
  from scripts.v093_source_executor import Executor
  with self.assertRaises(OSError):Executor(self.c,a).one('DESC','old')
  a.crash=False;a.fetch=lambda:(_ for _ in ()).throw(AssertionError('must not refetch'))
  r=run_batch(self.c,lambda t,s:a,'DESC','new');self.assertEqual(r['task_status_counts'],dict(RAW_BASIC_VERIFIED=1));self.assertTrue(r['outcomes'][0]['recovered'])
 def test_failed_save_recovery_does_not_loop_or_block_next_ready_task(self):
  from scripts.v093_source_executor import Executor
  a=DiskAdapter(self.root);a.crash=True
  with self.assertRaises(OSError):Executor(self.c,a).one('DESC','old')
  def factory(ticket,task):
   adapter=DiskAdapter(self.root)
   if ticket['key']=='z-bad':adapter.read=lambda ref:(_ for _ in ()).throw(OSError('temporary storage outage'))
   return adapter
  r=run_batch(self.c,factory,'DESC','new')
  self.assertEqual(r['processed'],2);self.assertEqual(r['task_status_counts'],dict(RECONCILE=1,RAW_BASIC_VERIFIED=1))
  self.assertEqual(self.c.store.read('TWSE')[1]['tasks']['z-bad']['attempts'],1)
 def test_production_gate_rejects_before_any_git_or_source_access(self):
  import subprocess,sys
  p=subprocess.run([sys.executable,'-m','scripts.v093_source_worker','--source','TWSE','--direction','DESC','--mode','production','--namespace','must-not-start'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('PRODUCTION_RELEASE_BLOCKED',p.stderr)

 def test_read_only_work_is_counted_after_batch_budget_exhausted(self):
  def mark(state):
   for task in state['tasks'].values():task.update(status='READY_CHECK',check_only=True,attempts=4)
  self.c.update(mark)
  def factory(ticket,task):
   adapter=DiskAdapter(self.root)
   # Binding failure isolates one task; the second remains available to continue.
   raise ValueError('contract awaiting approval')
  result=run_batch(self.c,factory,'DESC','worker',max_units=1)
  self.assertEqual(result['ready_remaining'],1)
  self.assertEqual(sum(t['attempts'] for t in self.c.store.read('TWSE')[1]['tasks'].values()),8)
 def test_future_retry_is_not_reported_as_immediately_ready(self):
  self.c.update(lambda state:[t.update(status='RETRY_WAIT',next_at=self.c.clock()+3600) for t in state['tasks'].values()])
  result=run_batch(self.c,lambda t,s:DiskAdapter(self.root),'DESC','worker')
  self.assertEqual(result['processed'],0);self.assertEqual(result['ready_remaining'],0)
