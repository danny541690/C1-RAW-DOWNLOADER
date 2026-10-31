import copy,gzip,hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v093_problem_recovery import exception_evidence,historical_candidate,historical_query,recheck,RecheckAdapter,promotion_task,RecoveryPromotionAdapter
from scripts.v093_three_year_repair import validate
from scripts.v093_source_coordination import Coordinator
from test_source_coordination import SQLiteCAS
from test_source_executor import DiskAdapter

def sha(raw):return hashlib.sha256(raw).hexdigest()
def retained(raw,source='MOPS',period='2012-10',category='revenue_otc_0'):
 key=source+'|'+period+'|test';reference='original-file'
 case=dict(source=source,key=key,period=period,category=category,mode='RETAINED',reference=reference,sha256=sha(raw))
 return dict(definition=dict(source=source,key=key,period=period,slot='DESC'),status='CONTENT_BLOCKED',attempts=3,execution_contract=case,legacy_review=dict(source=source,task_key=key,attempts=3,provenance=[dict(period=period,raw_reference=reference,sha256=sha(raw))]),recovery_archive=dict(commit='a'*40),error=dict(phase='VALIDATE',code='ValueError'))

class ProblemRecoveryTests(unittest.TestCase):
 def setUp(self):
  self.plan=json.loads(Path('config/v093_problem_recovery_20261031.json').read_text())
 def test_plan_is_frozen_to_unique_4008_held_keys(self):
  records=[t for group in self.plan['archives'] for t in group['held']]
  self.assertEqual(len(records),4008);self.assertEqual(len({t['key'] for t in records}),4008)
  self.assertEqual(sum(self.plan['baseline_source_counts'].values()),4008)
 def test_big5_extension_is_lossless_and_period_stays_required(self):
  raw='公司101年10月份'.encode('cp950')+b'<table><tr><td>1234</td><td>\xfa\x41</td></tr></table>'
  stats=validate(raw,'MOPS','revenue_otc_0','2012-10')
  self.assertEqual(stats['encoding'],'big5hkscs');self.assertEqual(stats['rows'],1)
  with self.assertRaisesRegex(ValueError,'REVENUE_PERIOD'):validate(raw,'MOPS','revenue_otc_0','2012-11')
 def test_invalid_bytes_never_receive_lossy_acceptance(self):
  raw='公司101年10月份'.encode('cp950')+b'<table><td>1234</td>\xff</table>'
  with self.assertRaisesRegex(ValueError,'REVENUE_ENCODING'):validate(raw,'MOPS','revenue_otc_0','2012-10')
 def test_empty_company_table_remains_blocked(self):
  with self.assertRaisesRegex(ValueError,'NO_COMPANY_ROWS'):validate('公司98年12月份<table>查無資料</table>'.encode('cp950'),'MOPS','revenue_sii_1','2009-12')
 def test_twse_range_exception_needs_matching_official_body(self):
  task=retained(b'',source='TWSE',period='2000-01-04',category='prices_indices')
  body=json.dumps({'stat':'查詢日期小於93年2月11日，請重新查詢!'},ensure_ascii=False).encode()
  self.assertEqual(exception_evidence(task,self.plan,body)['reason'],'BEFORE_ENDPOINT_START')
  self.assertIsNone(exception_evidence(task,self.plan,b'{"stat":"ok","data":[]}'))
 def test_taifex_boundary_is_dataset_specific_and_end_inclusive(self):
  task=retained(b'',source='TAIFEX',period='2004-04-01');task['execution_contract']['native_job']=dict(url='https://www.taifex.com.tw/cht/3/dlLargeTraderFutDown',start='2004-04-01',end='2004-04-30')
  self.assertEqual(exception_evidence(task,self.plan)['reason'],'BEFORE_DATASET_START')
  task['execution_contract']['native_job']['url']='https://www.taifex.com.tw/cht/3/futDataDown'
  self.assertIsNone(exception_evidence(task,self.plan))
  task['execution_contract']['native_job'].update(url='https://www.taifex.com.tw/cht/3/dlLargeTraderFutDown',end='2004-07-01')
  self.assertIsNone(exception_evidence(task,self.plan))
 def test_official_holiday_needs_empty_payload_and_matching_tpex_date(self):
  task=retained(b'',source='TPEx',period='2026-09-28',category='prices')
  raw=json.dumps(dict(date='20260928',stat='ok',tables=[dict(fields=['代號'],data=[])])).encode()
  self.assertEqual(exception_evidence(task,self.plan,raw)['reason'],'OFFICIAL_NONTRADING_DATE')
  obj=json.loads(raw);obj['tables'][0]['data']=[['1234']]
  self.assertIsNone(exception_evidence(task,self.plan,json.dumps(obj).encode()))
  obj['date']='20260929';obj['tables'][0]['data']=[]
  self.assertIsNone(exception_evidence(task,self.plan,json.dumps(obj).encode()))
 def test_twse_saturday_rule_is_dated_and_does_not_apply_to_tpex(self):
  raw=json.dumps({'stat':'很抱歉，沒有符合條件的資料!'},ensure_ascii=False).encode()
  task=retained(raw,source='TWSE',period='2026-05-30',category='prices_indices')
  self.assertEqual(exception_evidence(task,self.plan,raw)['reason'],'OFFICIAL_SATURDAY_NONTRADING')
  task['definition']['period']='2000-01-08';self.assertIsNone(exception_evidence(task,self.plan,raw))
  task['definition'].update(source='TPEx',period='2026-05-30');self.assertIsNone(exception_evidence(task,self.plan,raw))
 def test_retained_recheck_preserves_attempts_hash_and_raw(self):
  raw='公司101年10月份<table><td>1234</td></table>'.encode('cp950');task=retained(raw);original=copy.deepcopy(task)
  with patch.object(RecheckAdapter,'read',return_value=raw):result=recheck(task,self.plan,None,{})
  self.assertEqual(result['status'],'RAW_BASIC_VERIFIED');self.assertEqual(result['attempts'],3)
  self.assertEqual(result['source_requests'],0);self.assertEqual(result['raw_writes'],0)
  self.assertEqual(task,original);self.assertFalse(result['full_acceptance'])
 def test_receipt_error_is_rebound_only_after_sha_and_validation(self):
  raw='公司101年10月份<table><td>1234</td></table>'.encode('cp950');task=retained(raw);task['error']=dict(phase='RECEIPT_BINDING',code='Conflict')
  with patch.object(RecheckAdapter,'read',return_value=raw):result=recheck(task,self.plan,None,{})
  self.assertTrue(result['receipt_binding_revalidated'])
  with patch.object(RecheckAdapter,'read',return_value=raw+b'changed'):result=recheck(task,self.plan,None,{})
  self.assertEqual(result['status'],'REVIEW_REQUIRED');self.assertEqual(result['reason'],'RECOVERY_RETAINED_SHA')
 def test_historical_probe_never_replaces_retained_or_foreign_partition(self):
  task=retained(b'',period='2008-05',category='revenue_sii_0');task['execution_contract'].update(mode='MISSING',reference=None);task['error']=dict(code='HTTPError_404')
  self.assertEqual(historical_candidate(task),'https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_97_5.html')
  task['execution_contract']['category']='revenue_sii_1';self.assertIsNone(historical_candidate(task))
  task['execution_contract'].update(category='revenue_sii_0',mode='RETAINED');self.assertIsNone(historical_candidate(task))
 def test_historical_executor_keeps_final_request_number_and_caps_four(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);coordinator=Coordinator(SQLiteCAS(root/'db'),'MOPS',ttl=600)
   task=retained(b'',period='2008-05',category='revenue_sii_0');task['execution_contract'].update(mode='MISSING',reference=None);task['error']=dict(code='HTTPError_404')
   adapter=DiskAdapter(root)
   with patch('scripts.v093_problem_recovery.HistoricalAdapter',return_value=adapter):result=historical_query(task,coordinator,None,'campaign')
   self.assertEqual(result['status'],'RAW_BASIC_VERIFIED');self.assertEqual(result['attempts'],4);self.assertEqual(result['source_requests'],1)
   self.assertEqual(adapter.fetches,1)
   # A restart observes the existing durable result, with no fifth request.
   with patch('scripts.v093_problem_recovery.HistoricalAdapter',return_value=adapter):again=historical_query(task,coordinator,None,'campaign')
   self.assertEqual(adapter.fetches,1);self.assertEqual(again['attempts'],4)
 def test_quarantine_promotion_is_lossless_local_and_does_not_reset_requests(self):
  from test_native_repair import FakeDrive
  raw='公司101年10月份<table><td>1234</td></table>'.encode('cp950');compressed=gzip.compress(raw)
  task=retained(raw);task['execution_contract'].update(mode='MISSING',reference=None,sha256=None);task['attempts']=4;task['legacy_review']['attempts']=4
  evidence=dict(reason='VALID_REJECTED_RAW_REQUIRES_PROMOTION',accepted_as_raw=False,raw_sha256=sha(raw),rejected_evidence=dict(reference='quarantine',stored_sha256=sha(compressed),raw_sha256=sha(raw),raw_bytes=len(raw),encoding='gzip',accepted_as_raw=False,readback_verified=True))
  with tempfile.TemporaryDirectory() as folder:
   coordinator=Coordinator(SQLiteCAS(Path(folder)/'db'),'MOPS',ttl=600);drive=FakeDrive();drive.data['quarantine']=compressed
   result=historical_query(task,coordinator,drive,'campaign',promotion=evidence)
   self.assertEqual(result['status'],'RAW_BASIC_VERIFIED');self.assertEqual(result['attempts'],4)
   self.assertEqual(result['source_requests'],0);self.assertEqual(result['materializations'],1)
   self.assertEqual(drive.data[result['raw_reference']],raw);self.assertEqual(drive.data['quarantine'],compressed)
   self.assertTrue(result['storage_receipt']['readback_verified'])

if __name__=='__main__':unittest.main()
