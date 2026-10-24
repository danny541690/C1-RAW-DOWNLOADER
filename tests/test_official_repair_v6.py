import copy,json,time,unittest
from unittest.mock import Mock,patch
from scripts import v093_official_repair as r
from scripts import v093_repair_coordination as c
from scripts.v093_official_problem_catalog import problem,problem_summary,unresolved_items

class SharedCooldownTests(unittest.TestCase):
 def test_four_lanes_share_cooldown_and_other_sources_continue(self):
  store={'jobs':{}}
  def read(*a):return 'sha',copy.deepcopy(store)
  def put(api,token,sha,state,message):store.clear();store.update(state);return True
  with patch.object(c,'_read',side_effect=read),patch.object(c,'_put',side_effect=put):
   self.assertEqual(c.defer_source('api','token','TPEx',3600,now=100),3700)
   self.assertFalse(c.reserve_source('api','token','TPEx',now=200))
   self.assertTrue(c.reserve_source('api','token','TWSE',now=200))
   self.assertEqual(c.defer_source('api','token','TPEx',120,now=200),3700)
   self.assertTrue(c.reserve_source('api','token','TPEx',now=3700))
 def test_reject_invalid_cooldown(self):
  for source,seconds in [('FinMind',120),('MOPS',0),('MOPS',86401)]:
   with self.assertRaises(ValueError):c.defer_source('api','token',source,seconds)

class OfflineRecoveryTests(unittest.TestCase):
 def worker(self):
  from tests.test_repair_execution import ReparseExecutionTests
  _,w,raw,job,key,old=ReparseExecutionTests().integration_worker()
  sig=r.native.sha(json.dumps(dict(quality_revision=r.QUALITY_REVISION,sha=old['sha256'],flags=[]),sort_keys=True).encode())
  w.journal['units'][key]=dict(unit_id=key,source='MOPS',quality_revision=r.QUALITY_REVISION,input_signature=sig,
   execution_revision='V5',status='UNRESOLVED_RETRY_CYCLES_EXHAUSTED',attempts=3,retry_cycle=4,work_seconds=90,
   terminal=True,complete=False,error='TimeoutError:read timed out',next_retry_at=time.time()+3600)
  return w,raw,job,key,old
 def test_offline_recovery_preserves_caps_raw_and_deduplicates(self):
  w,raw,job,key,old=self.worker()
  with patch.object(r,'cached_payload',return_value=(raw,'archive')),patch.object(r,'validate_content',return_value={'rows':2,'codes':['2330','2317'],'row_audit':{'unverified':['PIT']}}),patch.object(r.native,'request') as network:
   w.repair_one(job,'financial_units',[]);w.repair_one(job,'financial_units',[])
  network.assert_not_called();row=w.journal['units'][key]
  self.assertTrue(row['reparse_receipt']['remote_readback_hash_verified'])
  self.assertEqual((row['attempts'],row['retry_cycle']),(3,4));self.assertEqual(w.state['financial_units'][key],old)
  self.assertEqual(w.activity_summary()['local_reparse_readback_this_run'],1)
 def test_invalid_retained_raw_does_not_reset_source_cap(self):
  w,raw,job,key,old=self.worker()
  with patch.object(r,'cached_payload',return_value=(raw,'archive')),patch.object(r,'validate_content',side_effect=ValueError('SOURCE_COMPANIES_MISSING')),patch.object(r.native,'request') as network:
   w.repair_one(job,'financial_units',[]);w.repair_one(job,'financial_units',[])
  network.assert_not_called();row=w.journal['units'][key]
  self.assertEqual(row['status'],'UNRESOLVED_RETRY_CYCLES_EXHAUSTED');self.assertEqual((row['attempts'],row['retry_cycle']),(3,4))
  self.assertFalse(row['complete'])
 def test_prior_pass_never_reopened(self):
  w,raw,job,key,old=self.worker();w.journal['units'][key].update(status='CONTENT_CHECK_PASS',raw_sha256=old['sha256'],complete=True)
  with patch.object(r,'cached_payload') as local,patch.object(r.native,'request') as network:w.repair_one(job,'financial_units',[])
  local.assert_not_called();network.assert_not_called()
 def test_completed_local_quality_audit_not_repeated_on_new_revision(self):
  w,raw,job,key,old=self.worker();w.journal['units'][key].update(status='LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS')
  with patch.object(r,'cached_payload') as local,patch.object(r.native,'request') as network:w.repair_one(job,'financial_units',[])
  local.assert_not_called();network.assert_not_called()

class ProblemCatalogTests(unittest.TestCase):
 def test_stale_error_on_pass_not_a_live_failure(self):
  self.assertEqual(problem(dict(status='CONTENT_CHECK_PASS',complete=True,error='HTTP Error 403'))[0],'CHECKED_CONTENT')
 def test_no_data_bounds_scope_pacing_and_limits_separate(self):
  states=['SOURCE_NO_DATA_UNCONFIRMED','OFFICIAL_PERIOD_NOT_PROVIDED','UNRESOLVED_COMPANY_OR_ENDPOINT_SCOPE','WAIT_SHARED_SOURCE_WINDOW','UNRESOLVED_SOURCE_LIMIT']
  self.assertEqual(len({problem(dict(status=s))[0] for s in states}),len(states))
 def test_quality_and_evidence_preserved_without_certification(self):
  row=dict(unit_id='x',status='LOCAL_CONTENT_CHECKED_OPEN_QUALITY_ITEMS',terminal=True,complete=False,raw_sha256='sha',open_checks=['PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED','PIT'])
  j={'units':{'x':row}};before=copy.deepcopy(j);s=problem_summary(j);items=unresolved_items(j)
  self.assertEqual(s['unresolved_units'],1);self.assertIn('PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED',s['open_quality_checks'])
  self.assertFalse(items[0]['pit_verified']);self.assertEqual(items[0]['raw_sha256'],'sha');self.assertEqual(j,before)
 def test_hash_failure_distinct_from_parser(self):
  self.assertEqual(problem(dict(status='LOCAL_REPARSE_FAILED',error='REPARSE_OUTPUT_READBACK_SHA_MISMATCH'))[0],'READBACK_OR_HASH_FAILURE')
