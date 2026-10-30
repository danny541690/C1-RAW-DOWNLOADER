import copy,unittest
from unittest.mock import Mock,patch
from scripts.v093_dispatch_recovery import reconcile_pending,ActionsEvidence
from scripts.v093_source_coordination import Coordinator

class DispatchRecoveryTests(unittest.TestCase):
 def setup_state(self,status='SENT'):
  self.key='a'*64
  self.state=dict(source='TDCC',tasks={'one':dict(definition=dict(slot='ASC'),status='READY_CHECK',attempts=3)},outbox={self.key:dict(slot='ASC',status=status,run_id='sender')})
  c=Mock();c.source='TDCC';c.clock.return_value=100
  c.store.read.return_value=('revision',self.state)
  c.update.side_effect=lambda f:f(self.state)
  return c
 def test_verified_terminal_receiver_unblocks_without_touching_tasks(self):
  c=self.setup_state();before=copy.deepcopy(self.state['tasks']);api=Mock()
  api.terminal_receivers.return_value={self.key:dict(run_id='42',conclusion='failure')}
  self.assertEqual(reconcile_pending(c,'ASC','workflow',api),'RECONCILED_TERMINAL')
  self.assertEqual(self.state['outbox'][self.key]['status'],'RESOLVED_TERMINAL')
  self.assertEqual(self.state['tasks'],before)
 def test_unknown_and_active_receivers_never_expire_by_time(self):
  for evidence,expected in [(None,'ACTIVE_RECEIVER'),({},'UNKNOWN_RECEIVER_REQUIRES_RECONCILIATION')]:
   c=self.setup_state();before=copy.deepcopy(self.state);api=Mock();api.terminal_receivers.return_value=evidence
   self.assertEqual(reconcile_pending(c,'ASC','workflow',api),expected)
   self.assertEqual(self.state,before);c.update.assert_not_called()
 def test_live_lease_and_recovery_cap_block_dispatch(self):
  c=self.setup_state();api=Mock();api.terminal_receivers.return_value={self.key:dict(run_id='42')}
  self.state['tasks']['one'].update(owner='live',expires=101)
  self.assertEqual(reconcile_pending(c,'ASC','workflow',api),'ACTIVE_LEASE')
  self.state['tasks']['one'].pop('owner');self.state['dispatch_recovery']={'ASC':{'attempts':4}}
  self.assertEqual(reconcile_pending(c,'ASC','workflow',api),'DISPATCH_RECOVERY_LIMIT')
  self.assertEqual(self.state['outbox'][self.key]['status'],'SENT')
 def test_ack_noop_never_pushes_and_contention_backs_off(self):
  store=Mock();state=dict(source='TDCC',tasks={},outbox={});store.read.return_value=('rev',state)
  c=Coordinator(store,'TDCC')
  self.assertEqual(c.update(lambda s:'unchanged'),'unchanged');store.cas.assert_not_called()
  store.cas.side_effect=[False,True]
  with patch('scripts.v093_source_coordination.time.sleep') as sleep:
   c.update(lambda s:s.update(fence=1))
   sleep.assert_called_once()
 def test_receiver_proof_requires_matching_identity_and_terminal_reread(self):
  api=ActionsEvidence('owner/repo','token');api.runs=Mock(return_value=[dict(id=42,status='completed',conclusion='failure')])
  api.get=Mock(side_effect=[{'jobs':[{'id':9,'conclusion':'failure'}]},'CONTINUATION_ID: '+'a'*64,{'status':'in_progress'}])
  self.assertIsNone(api.terminal_receivers('workflow',{'a'*64}))
 def test_wrong_identity_is_not_receiver_proof(self):
  api=ActionsEvidence('owner/repo','token');api.runs=Mock(return_value=[dict(id=42,status='completed',conclusion='failure')])
  api.get=Mock(side_effect=[{'jobs':[{'id':9,'conclusion':'failure'}]},'CONTINUATION_ID: '+'b'*64])
  self.assertEqual(api.terminal_receivers('workflow',{'a'*64}),{})
 def test_metadata_identity_does_not_need_log_download(self):
  key='a'*64;api=ActionsEvidence('owner/repo','token')
  api.runs=Mock(return_value=[dict(id=42,status='completed',conclusion='failure',display_title='worker | production | '+key)])
  api.get=Mock(return_value={'status':'completed','conclusion':'failure'})
  self.assertEqual(api.terminal_receivers('workflow',{key})[key]['run_id'],'42')
  api.get.assert_called_once_with('/actions/runs/42')
 def test_reviewed_legacy_binding_still_requires_current_terminal_status(self):
  key='a'*64;api=ActionsEvidence('owner/repo','token',{'42':dict(workflow='workflow',identity=key,verified_job_id=9)})
  api.runs=Mock(return_value=[dict(id=42,status='completed',conclusion='failure')]);api.get=Mock(return_value={'status':'in_progress'})
  self.assertIsNone(api.terminal_receivers('workflow',{key}))
 def test_unavailable_logs_do_not_release_unknown_dispatch(self):
  api=ActionsEvidence('owner/repo','token');api.runs=Mock(return_value=[dict(id=42,status='completed',conclusion='failure')])
  api.get=Mock(side_effect=[{'jobs':[{'id':9,'conclusion':'failure'}]},RuntimeError('ACTIONS_HTTP_404_LOGS')])
  self.assertEqual(api.terminal_receivers('workflow',{'a'*64}),{})
 def test_late_unacknowledged_receiver_is_fenced_before_source_work(self):
  from scripts.v093_source_continuation import acknowledge
  c=self.setup_state();api=ActionsEvidence('owner/repo','token',fence_unacknowledged=True)
  api.runs=Mock(return_value=[])
  self.assertEqual(reconcile_pending(c,'ASC','workflow',api),'RECONCILED_TERMINAL')
  with self.assertRaisesRegex(ValueError,'OUTBOX_STATUS'):acknowledge(c,'ASC',self.key,'late-run')
  self.assertEqual(self.state['tasks']['one']['attempts'],3)
 def test_source_queue_preserves_other_direction_waiter(self):
  from scripts.v093_source_continuation import continue_slot
  c=self.setup_state();c.source='TDCC';self.state['outbox'][self.key]['slot']='DESC'
  with patch('scripts.v093_source_continuation.stage') as stage:
   self.assertFalse(continue_slot(None,c,None,'ASC','run',Mock()));stage.assert_not_called()
 def test_sender_cannot_resurrect_retired_dispatch_after_race(self):
  state={'source':'TDCC','tasks':{'one':dict(definition=dict(slot='ASC'),status='READY',attempts=0)},'outbox':{},'fence':0}
  c=Mock();c.source='TDCC'
  class Store:
   def read(self,source):return 1,copy.deepcopy(state)
   def cas(self,source,rev,value):state.clear();state.update(copy.deepcopy(value));return True
  coordinator=Coordinator(Store(),'TDCC',clock=lambda:100)
  def late_dispatch(identity):state['outbox'][identity]['status']='RESOLVED_TERMINAL'
  self.assertTrue(coordinator.dispatch_after_save('ASC','sender',late_dispatch))
  self.assertEqual(next(iter(state['outbox'].values()))['status'],'RESOLVED_TERMINAL')
