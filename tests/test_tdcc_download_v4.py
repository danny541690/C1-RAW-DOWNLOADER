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
