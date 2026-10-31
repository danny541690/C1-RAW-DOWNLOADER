import json,unittest
from pathlib import Path
from scripts.v093_tpex_legacy_prices import validate
from scripts.v093_official_followup import discover,early_2007,eligible,repair_row,EmptyQueryAdapter

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
