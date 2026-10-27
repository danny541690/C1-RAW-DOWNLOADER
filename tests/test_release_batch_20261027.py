"""Release regression: actual adapter control flow with synthetic API responses."""
import copy,json,unittest
from unittest.mock import patch,Mock
from scripts.annual_actual_firstpass import Drive
from scripts import v093_repair_execution as e
from scripts import v093_official_repair as r
from scripts.v093_official_content_audit import audit_rows
from tests.test_stage06_financial_repair import sample
from tests import test_repair_execution as helpers
from tests.test_v093_indexed_drive import API,Request

class CreateAPI(API):
 def __init__(self):super().__init__([]);self.lost=False;self.creates=0;self.updates=0
 def create(self,body,media_body,fields):
  def result():
   self.creates+=1;fid='new'+str(self.creates)
   self.items.append(dict(id=fid,name=body['name'],mimeType='application/octet-stream'))
   self.bodies[fid]=media_body.getbytes(0,media_body.size())
   if self.lost:self.lost=False;raise TimeoutError('ACK_LOST_AFTER_COMMIT')
   return {'id':fid}
  return Request(self,'create',result)
 def update(self,**kw):self.updates+=1;raise AssertionError('IMMUTABLE_UPDATE_FORBIDDEN')

class ReparseWithActualDrive(unittest.TestCase):
 def run_reparse(self,d):
  raw=sample();job=dict(source='MOPS',category='CashflowStatement',period='2023-03-31',unit_id='release')
  return e.reparse_financial(raw,job,e.digest(raw),lambda:None,lambda n,b:d.put('parent',n,b,overwrite=False),lambda n:d.read('parent',n))
 def test_two_reparse_calls_create_one_drive_object(self):
  api=CreateAPI();d=Drive(api);a=self.run_reparse(d);b=self.run_reparse(d)
  self.assertEqual(a,b);self.assertEqual(api.creates,1);self.assertEqual(api.updates,0);self.assertFalse(b['complete'])
 def test_lost_create_ack_reconciles_without_second_upload(self):
  api=CreateAPI();api.lost=True
  with patch('scripts.annual_actual_firstpass.time.sleep'):
   receipt=self.run_reparse(Drive(api))
  self.assertTrue(receipt['remote_readback_hash_verified']);self.assertEqual(api.creates,1);self.assertEqual(api.updates,0)
 def test_existing_conflict_never_overwrites(self):
  api=CreateAPI();d=Drive(api);d.put('parent','same',b'old')
  with self.assertRaisesRegex(ValueError,'SHA mismatch'):d.put('parent','same',b'new')
  self.assertEqual(api.creates,1);self.assertEqual(api.updates,0);self.assertEqual(d.read('parent','same'),b'old')
 def test_corruption_between_reparse_runs_blocks_reuse(self):
  api=CreateAPI();d=Drive(api);self.run_reparse(d);api.bodies['new1']=b'corrupt'
  with self.assertRaisesRegex(ValueError,'SHA mismatch'):self.run_reparse(d)
  self.assertEqual(api.creates,1);self.assertEqual(api.updates,0)

class WorkerRouteAndRevision(unittest.TestCase):
 def test_legacy_compare_hold_does_not_call_source_or_change_retained_state(self):
  _,w,raw,job,key,old=helpers.ReparseExecutionTests().integration_worker()
  job=dict(job,period='2001-03-31',report_period='20011',month='2001-03');key=r.engine.key(job)
  w.state={'financial_units':{}};w.journal={'units':{}}
  before=copy.deepcopy(w.state)
  with patch.object(r.native,'request') as source:w.repair_one(job,'financial_units',[])
  source.assert_not_called();row=w.journal['units'][key]
  self.assertEqual(row['status'],'UNRESOLVED_HISTORICAL_COMPARE_SCOPE');self.assertFalse(row['complete']);self.assertEqual(row['attempts'],0)
  self.assertEqual(w.state,before);self.assertEqual(sum(w.source_requests.values()),0)
 def test_old_pass_requires_local_audit_but_not_source_redownload(self):
  _,w,raw,job,key,old=helpers.ReparseExecutionTests().integration_worker()
  signature=r.native.sha(json.dumps(dict(quality_revision=r.QUALITY_REVISION,sha=old['sha256'],flags=[]),sort_keys=True).encode())
  w.journal['units'][key]=dict(status='CONTENT_CHECK_PASS',complete=True,terminal=True,raw_sha256=old['sha256'],quality_revision=r.QUALITY_REVISION,input_signature=signature,attempts=2,work_seconds=0)
  with patch.object(r,'cached_payload',return_value=(raw,'archive')) as local,patch.object(r,'validate_content',return_value={'rows':2,'codes':['2330'],'row_audit':{'unverified':['PIT']}}),patch.object(r.native,'request') as source:
   w.repair_one(job,'financial_units',[])
  local.assert_called_once();source.assert_not_called();row=w.journal['units'][key]
  self.assertEqual(row['content_audit_revision'],'ROW_AUDIT_V5');self.assertEqual(row['attempts'],2);self.assertFalse(row['complete'])
 def test_failed_old_pass_revalidation_keeps_receipt_and_source_caps(self):
  _,w,raw,job,key,old=helpers.ReparseExecutionTests().integration_worker()
  w.journal['units'][key]=dict(status='CONTENT_CHECK_PASS',complete=True,raw_sha256=old['sha256'],quality_revision='OLD',attempts=3,retry_cycle=4,work_seconds=90,next_retry_at=1)
  with patch.object(r,'cached_payload',side_effect=TimeoutError('LOCAL_READBACK_TIMEOUT')),patch.object(r.native,'request') as source:w.repair_one(job,'financial_units',[])
  source.assert_not_called();row=w.journal['units'][key]
  self.assertEqual(row['status'],'LOCAL_REVALIDATION_FAILED_KEEP_RAW');self.assertEqual(row['attempts'],3);self.assertEqual(row['retry_cycle'],4);self.assertEqual(w.state['financial_units'][key],old);self.assertFalse(row['complete'])
 def test_current_pass_is_skipped_without_read_or_source(self):
  _,w,raw,job,key,old=helpers.ReparseExecutionTests().integration_worker()
  w.journal['units'][key]=dict(status='CONTENT_CHECK_PASS',complete=True,raw_sha256=old['sha256'],content_audit_revision='ROW_AUDIT_V5')
  with patch.object(r,'cached_payload') as local,patch.object(r.native,'request') as source:w.repair_one(job,'financial_units',[])
  local.assert_not_called();source.assert_not_called()
 def test_existing_legacy_raw_is_checked_locally_before_route_hold(self):
  _,w,raw,job,key,old=helpers.ReparseExecutionTests().integration_worker()
  job=dict(job,period='2001-03-31');key=r.engine.key(job);old=dict(old,**job)
  w.state={'financial_units':{key:old}}
  with patch.object(r,'cached_payload',return_value=(raw,'archive')) as local,patch.object(r,'validate_content',return_value={'rows':2,'codes':['2330'],'row_audit':{'unverified':[]}}),patch.object(r.native,'request') as source:w.repair_one(job,'financial_units',[])
  local.assert_called_once();source.assert_not_called();self.assertEqual(w.state['financial_units'][key]['sha256'],old['sha256'])

class AuditCoverage(unittest.TestCase):
 def raw(self,fields,rows):return json.dumps(dict(fields=fields,data=rows)).encode()
 def test_mixed_zero_code_cannot_silently_pass(self):
  raw=self.raw(['證券代號','開盤價','最高價','最低價','收盤價'],[['2330','100','110','90','105'],['0050','100','50','40','45']])
  out=audit_rows(raw,dict(source='TWSE',category='prices'));self.assertIn('OHLC_SECURITY_OUTSIDE_VALIDATED_SCOPE',out['unverified'])
  with self.assertRaisesRegex(ValueError,'OHLC_RELATIONSHIP'):audit_rows(raw,dict(source='TWSE',category='prices',applicable_security_codes=['2330','0050']))
 def test_margin_short_labels_checked_and_missing_remains_open(self):
  out=audit_rows(self.raw(['代號','資買','券賣','資使用率(%)'],[['2330','1','--','41.67%']]),dict(source='TPEx',category='margin'))
  self.assertEqual(out['numeric_cells_checked'],3);self.assertIn('MISSING_NUMERIC_CELL',out['unverified']);self.assertIn('MARGIN_ACCOUNTING_AND_FULL_SCOPE_NOT_PROVEN',out['unverified']);self.assertNotIn('OHLC_RELATIONSHIPS',out['checks'])
 def test_negative_margin_short_quantity_rejected(self):
  with self.assertRaisesRegex(ValueError,'NEGATIVE_NONNEGATIVE'):audit_rows(self.raw(['代號','資買'],[['2330','-1']]),dict(source='TPEx',category='margin'))
 def test_no_numeric_coverage_is_not_claimed(self):
  out=audit_rows(self.raw(['代號','未知欄'],[['2330','abc']]),dict(source='TPEx',category='unknown'))
  self.assertNotIn('RECOGNIZED_NUMERIC_DOMAINS',out['checks']);self.assertIn('NUMERIC_FIELD_RULES_NOT_COVERED',out['unverified'])

class CatalogRouting(unittest.TestCase):
 def test_route_hold_stays_visible_with_period_and_reference(self):
  from scripts.v093_official_problem_catalog import unresolved_items
  row={'status':'UNRESOLVED_HISTORICAL_COMPARE_SCOPE','source':'MOPS','period':'2001-03-31','route_reference':'https://mopsfin.twse.com.tw/terms','attempts':2}
  items=unresolved_items({'units':{'task':row}})
  self.assertEqual(items[0]['problem_family'],'HISTORICAL_FINANCIAL_ROUTE_REVIEW');self.assertEqual(items[0]['period'],'2001-03-31');self.assertEqual(items[0]['attempts'],2);self.assertIn('route_reference',items[0]);self.assertFalse(items[0]['complete'])
 def test_failed_local_revalidation_is_not_reported_as_content_pass(self):
  from scripts.v093_official_problem_catalog import problem
  self.assertEqual(problem({'status':'LOCAL_REVALIDATION_FAILED_KEEP_RAW','complete':False})[0],'LOCAL_REVALIDATION_FAILURE')
