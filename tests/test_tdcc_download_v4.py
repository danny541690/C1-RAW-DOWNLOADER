import json,time,unittest
from scripts import v093_tdcc_independent as m

def page(date='20261016',code='2330'):
 rows=''.join('<tr><td>'+str(i)+'</td><td>級距</td><td>1</td><td>1000</td><td>1</td></tr>' for i in range(1,16))
 rows+='<tr><td>16</td><td>差異數調整（說明4）</td><td></td><td>-1,000</td><td>-0.00</td></tr>'
 return ('<form></form>證券代號：'+code+' 資料日期：'+date+'<table><tr><th>序</th><th>持股/單位數分級</th><th>人數</th><th>股數/單位數</th><th>比例</th></tr>'+rows+'</table>').encode()

class DownloadV4Tests(unittest.TestCase):
 def worker(self):
  w=object.__new__(m.Worker);w.state={'receipts':{},'history_receipts':{}};w.saved=0;w.skipped=0;w.until=time.monotonic()+300;w.save=lambda:None;w.ctrl='control'
  w.d=type('Drive',(),{'put':lambda *args,**kwargs:None})()
  return w
 def test_official_signed_adjustment_accepted(self):self.assertEqual(m.validate_history(page(),'20261016','2330'),16)
 def test_other_negative_counts_rejected(self):
  with self.assertRaisesRegex(ValueError,'NONNEGATIVE'):m.validate_history(page().replace(b'<td>1</td><td>1000',b'<td>-1</td><td>1000',1),'20261016','2330')
 def test_echoed_form_date_is_not_result_proof(self):
  raw=page('20261008').replace(b'<form>',b'<form>20261016')
  with self.assertRaisesRegex(ValueError,'DATE_NOT_CONFIRMED'):m.validate_history(raw,'20261016','2330')
 def test_no_data_not_parser_failure(self):
  raw='<form></form><table><tr><th>持股/單位數分級 股數</th></tr><tr><td>查無此資料</td></tr></table>'.encode()
  with self.assertRaises(m.SourceEmpty):m.validate_history(raw,'20261016','1516O')
 def test_hidden_fields_not_attribute_order_or_quote_dependent(self):
  fields=m.query_fields("<input value='a&amp;b' type='hidden' name='token'><input name='radio' value='wrong' type='radio'>",'20261016','2330')
  self.assertEqual(fields['token'],'a&b');self.assertNotIn('radio',fields);self.assertEqual(fields['stockNo'],'2330')
 def test_empty_response_is_terminal_without_false_success(self):
  w=self.worker();w.request=lambda *args:b'[]'
  w.process('empty','https://openapi.tdcc.com.tw/v1/opendata/4-10','4-10')
  e=w.state['receipts']['empty'];self.assertEqual(e['status'],'SKIPPED_SOURCE_EMPTY');self.assertFalse(e['historical_absence_certified'])
  w.request=lambda *args:self.fail('empty must not immediately redownload')
  w.process('empty','url','4-10')
 def test_transient_retry_is_delayed_and_success_preserved(self):
  w=self.worker();calls=[]
  def fail(*args):calls.append(1);raise TimeoutError('offline')
  w.request=fail
  w.process('bad','https://openapi.tdcc.com.tw/v1/opendata/4-10','x');w.process('bad','url','x')
  self.assertEqual(len(calls),1);self.assertEqual(w.state['receipts']['bad']['attempts'],1)
  w.state['receipts']['ok']={'status':'SAVED_BASIC_VERIFIED','sha256':'keep'}
  w.process('ok','url','x');self.assertEqual(w.state['receipts']['ok']['sha256'],'keep');self.assertEqual(len(calls),1)
 def test_legacy_empty_reclassified_only_after_matching_hash(self):
  w=self.worker();raw=b'[]';entry=dict(status='UNRESOLVED',error='ValueError:EMPTY_NOT_PROOF_OF_NO_DATA',quarantine_file='raw',response_sha256=m.sha(raw))
  w.state['receipts']={'old':entry,'bad':dict(entry,response_sha256='wrong')}
  w.d.read=lambda *args:raw
  w.reclassify_retained_errors()
  self.assertEqual(w.state['receipts']['old']['status'],'SKIPPED_SOURCE_EMPTY');self.assertEqual(w.state['receipts']['bad']['status'],'UNRESOLVED')

if __name__=='__main__':unittest.main()

class TimeoutResumeTests(unittest.TestCase):
 def test_due_failed_codes_precede_new_candidates(self):
  r={'20251031|2404':dict(status='UNRESOLVED',attempts=1,retry_after_epoch=10),
     '20251031|2478':dict(status='UNRESOLVED',attempts=1,retry_after_epoch=99)}
  codes=m.ordered_history_codes('20251031',['2330','2404','2478','0050'],r,now=20)
  self.assertEqual(codes[0],'2404');self.assertEqual(codes[1:3],['0050','2330'])
 def test_exhausted_and_saved_receipts_are_not_due(self):
  r={'20251031|2404':dict(status='UNRESOLVED',attempts=3),
     '20251031|2478':dict(status='SAVED_BASIC_VERIFIED',sha256='keep')}
  self.assertEqual(m.ordered_history_codes('20251031',['2404','2330','2478'],r,now=20)[0],'2330')
  self.assertEqual(r['20251031|2478']['sha256'],'keep')
 def test_timeout_retry_preserves_cap_and_records_phase(self):
  w=DownloadV4Tests().worker();w.state['history_receipts']['20251031|2404']=dict(status='UNRESOLVED',attempts=1,repair_revision=m.REPAIR_REVISION)
  def fail(*args):raise TimeoutError('read timed out')
  w.request=fail
  w.process('20251031|2404',m.QUERY,'distribution_20251031_2404','html','20251031','2404')
  e=w.state['history_receipts']['20251031|2404'];self.assertEqual(e['attempts'],2)
  self.assertEqual(e['request_phase'],'GET_QUERY_FORM');self.assertEqual(e['error_class'],'TRANSPORT_ERROR')
  self.assertEqual(e['status'],'UNRESOLVED');self.assertGreater(e['retry_after_epoch'],time.time())
 def test_insufficient_run_budget_does_not_spend_attempt(self):
  w=DownloadV4Tests().worker();w.until=time.monotonic()+90
  w.request=lambda *args:self.fail('no request within reserved shutdown budget')
  self.assertFalse(w.process('new',m.QUERY,'new'))
  self.assertNotIn('new',w.state['receipts'])
 def test_transport_release_does_not_restart_history_frontiers(self):
  s=dict(history_completion_revision=m.REPAIR_REVISION,visited_dates=['20261022'],completed_dates=['20261022'])
  self.assertFalse(m.migrate_history(s));self.assertEqual(s['visited_dates'],['20261022'])
