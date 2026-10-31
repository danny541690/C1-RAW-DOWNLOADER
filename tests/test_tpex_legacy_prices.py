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
