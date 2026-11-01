import json,unittest
from pathlib import Path
from scripts.v093_tpex_legacy_prices import validate,validate_archived
from scripts.v093_official_followup import discover,early_2007,archived_html,eligible,repair_row,EmptyQueryAdapter

def fixture(period='2007-01-02',title='96年1月2日',change=None):
 fields=['代號','名稱','收盤','漲跌','開盤','最高','最低','成交股數','成交金額(元)']
 rows=[]
 for i in range(300):
  row=[str(1001+i),'測試公司','10','0','10','11','9','1,000','10,000']
  if i==0 and change:row=change(row)
  rows.append('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>')
 text='<table><tr><th colspan="9">上櫃股票行情 '+title+'</th></tr><tr>'+''.join('<th>'+f+'</th>' for f in fields)+'</tr>'+''.join(rows)+'</table>'
 return json.dumps(dict(stat='ok',date=period.replace('-',''),html=text),ensure_ascii=False).encode()

class LegacyPricesTests(unittest.TestCase):
 def test_management_section_caption_does_not_shift_or_pad_stock_rows(self):
  obj=json.loads(fixture());text=obj['html'].replace('96年1月2日','').replace('<table>','<p>交易日期:93年11月16日</p><table>').replace('<th>漲跌</th>','<th colspan="2">漲跌</th>').replace('<td>0</td>','<td>▽</td><td>0</td>').replace('</table>','<tr><td colspan="10">管理股票</td></tr></table>')
  self.assertEqual(validate_archived(text.encode('cp950'),'2004-11-16')['native']['rows'],300)
 def test_caption_outside_rows_and_split_change_columns_bind_actual_prices(self):
  obj=json.loads(fixture());text=obj['html'];text=text.replace('96年1月2日','').replace('<table>','<p>交易日期:93年10月29日</p><table>').replace('<th>漲跌</th>','<th colspan="2">漲跌</th>').replace('<td>0</td>','<td>▽</td><td>0</td>')
  self.assertTrue(validate_archived(text.encode('cp950'),'2004-10-29')['basic_verified'])
  with self.assertRaisesRegex(ValueError,'WRONG_TITLE_DATE'):validate_archived(text.replace('29日','28日').encode('cp950'),'2004-10-29')
 def test_observed_circle_markers_and_four_dash_quotes_preserve_missing_flags(self):
  obj=json.loads(fixture(title='資料日期：931029',change=lambda r:r[:2]+['⊙10']+r[3:]));result=validate_archived(obj['html'].encode('cp950'),'2004-10-29');self.assertEqual(result['native']['marked_price_cells'],1)
  obj=json.loads(fixture(title='資料日期：931029',change=lambda r:r[:2]+['----']+r[3:]));self.assertEqual(validate_archived(obj['html'].encode('cp950'),'2004-10-29')['native']['missing_price_rows'],1)
 def test_truncated_html_is_never_padded_into_a_complete_row(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_TRUNCATED_HTML'):validate_archived(b'<table><tr><td width="Aria','2004-08-12')
 def test_mixed_replacement_bytes_are_diagnosed_without_ignoring_them(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_MIXED_REPLACEMENT_BYTES'):validate_archived(b'\xff\xef\xbf\xbd','2004-02-13')
 def test_official_error_page_does_not_prove_historical_absence(self):
  with self.assertRaisesRegex(ValueError,'NOT_ABSENCE_PROOF'):validate_archived('<html>您所輸入的網址並不存在</html>'.encode(),'2003-09-11')
 def test_archived_unquoted_ohl_does_not_assume_zero_change(self):
  for change in ('-5.90','-0.29','+1.00'):
   obj=json.loads(fixture(title='資料日期：920815',change=lambda r:r[:3]+[change,'.00','.00','.00']+r[7:]));result=validate_archived(obj['html'].encode('cp950'),'2003-08-15')
   self.assertEqual(result['native']['unquoted_open_high_low_rows'],1);self.assertEqual(result['native']['price_relationship_rows_checked'],299);self.assertFalse(result['numeric_verified'])
 def test_oracle_compact_roc_date_is_bound_to_report_date_not_generation_time(self):
  text=json.loads(fixture(title='資料日期：920801'))['html'];raw=('<!-- generated 2003-08-05 -->'+text).encode('cp950')
  self.assertTrue(validate_archived(raw,'2003-08-01')['basic_verified'])
  with self.assertRaisesRegex(ValueError,'WRONG_TITLE_DATE'):validate_archived(raw,'2003-08-04')
  with self.assertRaisesRegex(ValueError,'WRONG_TITLE_DATE'):validate_archived(raw+'<div>資料日期:920804</div>'.encode('cp950'),'2003-08-01')
 def test_observed_oracle_unquoted_ohl_preserves_positive_close_without_certifying_it(self):
  obj=json.loads(fixture(title='資料日期：920801',change=lambda r:r[:3]+['0','.00','.00','.00']+r[7:]));result=validate_archived(obj['html'].encode('cp950'),'2003-08-01')
  self.assertEqual(result['native']['unquoted_open_high_low_rows'],1);self.assertEqual(result['native']['price_relationship_rows_checked'],299);self.assertFalse(result['numeric_verified'])
 def test_saved_archived_response_promotes_original_without_resetting_attempts(self):
  from test_problem_recovery import retained,sha
  cfg=json.loads(Path('config/v093_official_followup_20261031.json').read_text());task=retained(b'old',source='TPEx',period='2003-08-01',category='prices');task['recovery_archive']=dict(commit='a'*40)
  evidence=dict(reference='quarantine',raw_sha256=sha(b'valid'),stored_sha256=sha(b'zip'),readback_verified=True,accepted_as_raw=False,encoding='gzip')
  proof=dict(kind='OFFICIAL_ARCHIVED_HTML_ROUTE',route=cfg['tpex_archived_html'],raw_sha256=cfg['tpex_archived_html']['query_page_sha256'])
  row=repair_row(task,dict(attempts=2),proof,promotion=dict(reason='VALID_REJECTED_RAW_REQUIRES_PROMOTION',accepted_as_raw=False,raw_sha256=sha(b'valid'),rejected_evidence=evidence))
  self.assertEqual(row['attempts'],2);self.assertTrue(row['local_only']);self.assertEqual(row['execution_contract']['mode'],'PROMOTE');self.assertEqual(row['execution_contract']['promotion_evidence']['reference'],'quarantine')
 def test_native_promotion_saves_same_bytes_at_four_attempts_with_no_http(self):
  import gzip,tempfile
  from unittest.mock import patch
  from test_problem_recovery import retained,sha
  from test_native_repair import FakeDrive
  from test_source_coordination import SQLiteCAS
  from scripts.v093_source_coordination import Coordinator
  from scripts.v093_source_executor import Executor
  cfg=json.loads(Path('config/v093_official_followup_20261031.json').read_text());raw=json.loads(fixture(title='資料日期：920801'))['html'].encode('cp950');compressed=gzip.compress(raw);task=retained(b'old',source='TPEx',period='2003-08-01',category='prices')
  evidence=dict(reference='quarantine',raw_sha256=sha(raw),raw_bytes=len(raw),stored_sha256=sha(compressed),readback_verified=True,accepted_as_raw=False,encoding='gzip')
  row=repair_row(task,dict(attempts=4),dict(kind='OFFICIAL_ARCHIVED_HTML_ROUTE',route=cfg['tpex_archived_html'],raw_sha256=cfg['tpex_archived_html']['query_page_sha256']),promotion=dict(reason='VALID_REJECTED_RAW_REQUIRES_PROMOTION',accepted_as_raw=False,raw_sha256=sha(raw),rejected_evidence=evidence))
  with tempfile.TemporaryDirectory() as tmp:
   c=Coordinator(SQLiteCAS(Path(tmp)/'db'),'TPEx',ttl=600);key=row['definition']['key'];c.update(lambda s:s['tasks'].update({key:row}));c.update(lambda s:s.update(hold='HTTPError_403',cooldown_until=c.clock()+3600));drive=FakeDrive();drive.data['quarantine']=compressed
   adapter=EmptyQueryAdapter(c,drive,dict(source='TPEx',key=key),row)
   with patch.object(adapter,'http',side_effect=AssertionError('must not download')) as http:result=Executor(c,adapter).one('DESC','promote')
   current=c.store.read('TPEx')[1]['tasks'][key];self.assertEqual(current['status'],'RAW_BASIC_VERIFIED');self.assertEqual(current['attempts'],4);http.assert_not_called();self.assertEqual(drive.data[result['reference']],raw);self.assertEqual(drive.data['quarantine'],compressed);self.assertTrue(current['storage_receipt']['readback_verified'])
   self.assertEqual(c.store.read('TPEx')[1]['hold'],'HTTPError_403');self.assertNotIn('http_budget',c.store.read('TPEx')[1])
 def test_promotion_http_is_forbidden_even_without_a_source_hold(self):
  from scripts.v093_source_adapters import NativeAdapter
  adapter=object.__new__(NativeAdapter);adapter.case=dict(mode='PROMOTE')
  with self.assertRaisesRegex(ValueError,'SOURCE_HTTP_FORBIDDEN'):adapter.http('https://www.tpex.org.tw/')
 def test_forged_local_flag_cannot_admit_source_download_under_403(self):
  import tempfile
  from scripts.v093_source_coordination import Coordinator
  from test_source_coordination import SQLiteCAS
  with tempfile.TemporaryDirectory() as tmp:
   c=Coordinator(SQLiteCAS(Path(tmp)/'db'),'TPEx');c.add([dict(source='TPEx',key='a',slot='DESC',period='2003-08-15')]);c.update(lambda s:s.update(hold='HTTPError_403'))
   def forge(s):s['tasks']['a'].update(local_only=True,execution_contract=dict(mode='MISSING'))
   c.update(forge);self.assertIsNone(c.claim('DESC','test'));self.assertEqual(c.store.read('TPEx')[1]['tasks']['a']['attempts'],0)
 def test_only_observed_price_markers_are_parsed_and_original_raw_is_unchanged(self):
  raw=fixture(change=lambda r:r[:2]+['♁10']+r[3:]);before=bytes(raw);result=validate(raw,'2007-01-02');self.assertEqual(raw,before);self.assertEqual(result['native']['marked_price_cells'],1)
  with self.assertRaises(ValueError):validate(fixture(change=lambda r:r[:2]+['?10']+r[3:]),'2007-01-02')
 def test_zero_quotes_require_all_ohlc_zero_and_official_dash_change(self):
  result=validate(fixture(change=lambda r:r[:2]+['0','---','0','0','0']+r[7:]),'2007-01-02');self.assertEqual(result['native']['zero_quote_rows'],1);self.assertEqual(result['native']['price_relationship_rows_checked'],299)
  with self.assertRaisesRegex(ValueError,'OHLC'):validate(fixture(change=lambda r:r[:2]+['0','0','0','0','0']+r[7:]),'2007-01-02')
 def test_source_replacement_characters_cannot_be_accepted_as_correct_raw(self):
  with self.assertRaisesRegex(ValueError,'SOURCE_REPLACEMENT'):validate(fixture(change=lambda r:r[:1]+['安�']+r[2:]),'2007-01-02')
 def test_archived_html_decodes_losslessly_and_requires_payload_date(self):
  raw=json.loads(fixture(title='92年8月1日'))['html'].encode('cp950');self.assertTrue(validate_archived(raw,'2003-08-01')['basic_verified'])
  with self.assertRaisesRegex(ValueError,'WRONG_TITLE_DATE'):validate_archived(raw,'2003-08-04')
  with self.assertRaisesRegex(ValueError,'PERIOD_SCOPE'):validate_archived(raw,'2007-01-02')
 def test_archived_route_is_pinned_to_the_observed_official_filename_rule(self):
  from test_problem_recovery import retained,sha
  cfg=json.loads(Path('config/v093_official_followup_20261031.json').read_text());task=retained(b'old',source='TPEx',period='2003-08-01',category='prices');prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',raw_sha256=sha(b'old'),attempts=1)
  self.assertTrue(archived_html(task,cfg));self.assertTrue(eligible(task,prior,{},cfg))
  row=repair_row(task,prior,dict(kind='OFFICIAL_ARCHIVED_HTML_ROUTE',route=cfg['tpex_archived_html'],raw_sha256=cfg['tpex_archived_html']['query_page_sha256']))
  adapter=object.__new__(EmptyQueryAdapter);adapter.case=row['execution_contract']
  from unittest.mock import Mock
  adapter.http=Mock(return_value=b'raw');self.assertEqual(adapter.fetch(),b'raw');adapter.http.assert_called_once_with('https://hist.tpex.org.tw/Hist/STOCK/AFTERTRADING/DAILY_CLOSE_QUOTES/RSTA3104_920801.HTML')
  cfg['tpex_archived_html']['query_page_sha256']='0'*64;self.assertFalse(archived_html(task,cfg))
 def test_official_html_has_payload_date_numeric_checks_and_original_units(self):
  result=validate(fixture(),'2007-01-02');self.assertTrue(result['basic_verified']);self.assertEqual(result['native']['rows'],300);self.assertEqual(result['native']['price_relationship_rows_checked'],300);self.assertFalse(result['full_acceptance'])
 def test_html_fragment_is_allowed_but_missing_date_is_not(self):
  obj=json.loads(fixture());obj['html']=obj['html'].replace('<table>','').replace('</table>','');self.assertTrue(validate(json.dumps(obj).encode(),'2007-01-02')['basic_verified'])
  obj.pop('date');obj['html']=obj['html'].replace('96年1月2日','')
  with self.assertRaisesRegex(ValueError,'DATE_UNPROVEN'):validate(json.dumps(obj).encode(),'2007-01-02')
 def test_wrong_html_date_cannot_be_hidden_by_echoed_query_date(self):
  with self.assertRaisesRegex(ValueError,'WRONG_TITLE_DATE'):validate(fixture(title='96年1月3日'),'2007-01-02')
  with self.assertRaisesRegex(ValueError,'WRONG_RESPONSE_DATE'):validate(fixture(period='2007-01-03'),'2007-01-02')
 def test_wrong_width_prices_and_negative_volume_stay_blocked(self):
  for change,error in [(lambda r:r[:-1],'ROW_WIDTH'),(lambda r:r[:5]+['8']+r[6:],'OHLC'),(lambda r:r[:7]+['-1']+r[8:],'VOLUME_OR_AMOUNT')]:
   with self.subTest(error=error):
    with self.assertRaisesRegex(ValueError,error):validate(fixture(change=change),'2007-01-02')
 def test_incomplete_market_and_duplicate_codes_are_rejected(self):
  obj=json.loads(fixture());obj['html']=obj['html'].replace('<td>1002</td>','<td>1001</td>')
  with self.assertRaisesRegex(ValueError,'DUPLICATE'):validate(json.dumps(obj).encode(),'2007-01-02')
  with self.assertRaisesRegex(ValueError,'PERIOD_SCOPE'):validate(fixture(),'2007-04-21')
 def test_frame_links_are_discovered_without_executing_scripts(self):
  found=discover('<FRAME SRC="RSTA3104QRY.HTML"><frame src="RSTA3104RES.HTML"><iframe src="https://evil.invalid/x">','https://hist.tpex.org.tw/Hist/STOCK/AFTERTRADING/DAILY_CLOSE_QUOTES/param_3104.html')
  self.assertEqual(len(found['frames']),2);self.assertTrue(all(x.startswith('https://hist.tpex.org.tw/') for x in found['frames']))
 def test_early_route_canary_binds_scope_and_does_not_reset_attempts(self):
  from test_problem_recovery import retained,sha
  cfg=json.loads(Path('config/v093_official_followup_20261031.json').read_text());raw=b'old empty'
  task=retained(raw,source='TPEx',period='2007-01-02',category='prices');task['attempts']=3;prior=dict(status='REVIEW_REQUIRED',reason='OFFICIAL_EMPTY_UNCONFIRMED',raw_sha256=sha(raw),attempts=3)
  self.assertTrue(early_2007(task,cfg));self.assertTrue(eligible(task,prior,{},cfg))
  row=repair_row(task,prior,dict(kind='OFFICIAL_HISTORICAL_ROUTE',raw_sha256=cfg['tpex_early_2007']['page_sha256'],route=cfg['tpex_early_2007']))
  self.assertEqual(row['attempts'],3);self.assertEqual(row['execution_contract']['official_historical_query']['method'],'POST')
  prior['attempts']=4;self.assertFalse(eligible(task,prior,{},cfg))
 def test_live_form_contract_uses_post_and_iso_slash_date(self):
  from unittest.mock import Mock
  adapter=object.__new__(EmptyQueryAdapter);adapter.case=dict(source='TPEx',period='2007-01-02',official_historical_query=dict(endpoint='https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotesHis'));adapter.http=Mock(return_value=b'raw')
  self.assertEqual(adapter.fetch(),b'raw');adapter.http.assert_called_once_with(adapter.case['official_historical_query']['endpoint'],{'date':'2007/01/02'})

if __name__=='__main__':unittest.main()
