"""Replay retained 2003-03 source bytes; no live provider requests."""
import copy,datetime as dt,hashlib,io,pathlib,time,unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch
from scripts import v093_official_finmind_gapfill as fm
from scripts import v093_history_reverse as engine
RAW=(pathlib.Path(__file__).parent/'fixtures/finmind_success_empty_200303.json').read_bytes()
SHA='bd3deae97b9bbf5496db1c19da707df924ec244a8568f606429c0a6532ddca72'

class ActualEmptyReply(unittest.TestCase):
 def fixture(self):
  job=dict(source='MOPS',category='IncomeStatement',period='2003-03-31',codes=['1107'])
  journal={'units':{engine.key(job):{'status':'UNRESOLVED_HISTORICAL_COMPARE_SCOPE','complete':False}}}
  state={'units':{},'financial_units':{}}
  task=fm.plan(state,journal,[job],'2003-03','2026-10-28')[0][0]
  worker=Mock(finmind_enabled=True,state=state,journal=journal,active='2003-03',today=dt.date(2026,10,28),owner='test',finmind_metrics={'requests':0,'saved':0,'failed':0},until=time.monotonic()+100)
  worker.d.folder.return_value='rejected'
  return job,task,worker
 def test_exact_retained_bytes_rejected_despite_success_envelope(self):
  _,task,_=self.fixture();self.assertEqual(len(RAW),40);self.assertEqual(hashlib.sha256(RAW).hexdigest(),SHA)
  with self.assertRaisesRegex(ValueError,'FINMIND_EMPTY_NOT_ABSENCE'):fm.validate(RAW,task)
 def test_empty_response_stays_failed_and_retains_evidence_without_raw_publish(self):
  job,task,w=self.fixture();before=copy.deepcopy(w.state['financial_units']);response=Mock()
  response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False);response.read.return_value=RAW
  with patch.object(fm,'reserve',return_value=True),patch.object(fm.urllib.request,'urlopen',return_value=response) as request,patch.object(fm.base.Worker,'record_payload') as publish,patch.object(fm,'cached_payload') as readback,redirect_stdout(io.StringIO()):
   fm.supplement(w,[job])
  self.assertEqual(request.call_count,1);publish.assert_not_called();readback.assert_not_called()
  row=w.state['finmind_units'][fm.task_key(task)]
  self.assertEqual(row['status'],'FINMIND_GAP_UNRESOLVED');self.assertEqual(row['response_sha256'],SHA)
  self.assertEqual(row['attempts'],1);self.assertFalse(row['official_gap_closed']);self.assertGreater(row['next_retry_at'],time.time())
  self.assertEqual(w.finmind_metrics,{'requests':1,'saved':0,'failed':1});self.assertEqual(w.state['financial_units'],before)
  self.assertFalse(w.journal['units'][engine.key(job)]['complete']);self.assertEqual(w.d.put.call_args.args[2],RAW)
 def test_three_prior_attempts_do_not_send_a_fourth_request(self):
  job,task,w=self.fixture();w.state['finmind_units']={fm.task_key(task):dict(task,status='FINMIND_GAP_UNRESOLVED',attempts=3,next_retry_at=0,error='ValueError:FINMIND_EMPTY_NOT_ABSENCE',response_sha256=SHA)}
  before=copy.deepcopy(w.state['finmind_units'])
  with patch.object(fm,'reserve') as reserve,patch.object(fm.urllib.request,'urlopen') as request,redirect_stdout(io.StringIO()):fm.supplement(w,[job])
  reserve.assert_not_called();request.assert_not_called();self.assertEqual(w.state['finmind_units'],before);self.assertEqual(w.finmind_metrics['saved'],0)
 def test_cooldown_prevents_immediate_replay_of_empty_response(self):
  job,task,w=self.fixture();w.state['finmind_units']={fm.task_key(task):dict(task,status='FINMIND_GAP_UNRESOLVED',attempts=1,next_retry_at=time.time()+3600,error='ValueError:FINMIND_EMPTY_NOT_ABSENCE')}
  with patch.object(fm,'reserve') as reserve,patch.object(fm.urllib.request,'urlopen') as request,redirect_stdout(io.StringIO()):fm.supplement(w,[job])
  reserve.assert_not_called();request.assert_not_called();self.assertEqual(w.journal['finmind_pending'],1);self.assertFalse(w.journal['units'][engine.key(job)]['complete'])
