import json,unittest
from scripts.v093_standard_r3 import day,month,number,parse_member

class NativeRepairTests(unittest.TestCase):
 def parse(self,obj,name='prices_20250102.json',period='2025-01'):
  return parse_member('TWSE',name,json.dumps(obj).encode(),period)
 def test_calendar_validation(self):
  self.assertIsNone(day('20250230'));self.assertIsNone(day('114/13/01'))
  self.assertEqual(day('114/1/2'),'2025-01-02');self.assertEqual(day('20250102'),'2025-01-02')
  self.assertEqual(month('114/1'),'2025-01');self.assertIsNone(month('2025-13'))
 def test_precision_and_missing(self):
  self.assertEqual(number('9,007,199,254,740,993'),'9007199254740993')
  for v in ['NaN','inf','--',True,None]:self.assertIsNone(number(v))
 def test_identifiers_not_features(self):
  rows,counts,_=self.parse({'date':'20250102','fields':['證券代號','收盤價'],'data':[['2330','123.5']]})
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['stock_id'],'2330')
 def test_table_date_used(self):
  r,_,_=self.parse({'tables':[{'date':'114/1/3','fields':['證券代號','收盤價'],'data':[['2330','123']]}]},name='quote.json')
  self.assertEqual(r[0]['date'],'2025-01-03');self.assertEqual(r[0]['date_proof'],'RESPONSE')
 def test_content_date_conflict_rejected(self):
  r,c,_=self.parse({'date':'20250102','data':[{'date':'2025-01-03','stock_id':'2330','close':5}]})
  self.assertFalse(r);self.assertEqual(c['ROW_RESPONSE_DATE_CONFLICT'],1)
 def test_filename_never_content_verified(self):
  r,_,_=self.parse([{'stock_id':'2330','close':5}])
  self.assertFalse(r[0]['date_content_verified']);self.assertFalse(r[0]['pit_verified'])
 def test_unpadded_month_csv_is_not_publication_day(self):
  b='出表日期,資料年月,公司代號,營業收入-當月營收\n115/10/16,114/1,2330,1000\n'.encode()
  r,_,_=parse_member('MOPS','revenue.raw',b,'2025-01')
  self.assertEqual(r[0]['observation_period'],'2025-01');self.assertIsNone(r[0]['date'])
  self.assertEqual(len(r),1)
 def test_html_title_not_remark_dates(self):
  s='<html><b>上市公司114年1月份(累計與當月)營業收入統計表</b><table><tr><th>公司代號</th><th>當月營收</th><th>備註</th></tr><tr><td>2330</td><td>1000</td><td>113年12月併購</td></tr></table></html>'
  r,_,_=parse_member('MOPS','revenue_sii.html',s.encode(),'2025-01')
  self.assertEqual(r[0]['observation_period'],'2025-01');self.assertEqual(len(r),1)
 def test_ohlc_failure_is_quarantined(self):
  r,c,_=self.parse([{'date':'2025-01-02','stock_id':'2330','open':11,'max':10,'min':5,'close':8}])
  self.assertEqual(c['OHLC_VIOLATIONS'],1);self.assertTrue(all(x['status']=='QUARANTINE_OHLC' for x in r))
 def test_duplicate_columns_preserved(self):
  r,_,_=self.parse({'date':'20250102','fields':['證券代號','金額','金額'],'data':[['2330','1','2']]})
  self.assertEqual(len(r),2);self.assertNotEqual(r[0]['native_field'],r[1]['native_field'])
 def test_invalid_and_outside_dates_reported(self):
  r,c,_=self.parse([{'date':'2025-02-30','stock_id':'2330','close':5},{'date':'2025-02-01','stock_id':'2330','close':6}])
  self.assertFalse(r);self.assertEqual(c['INVALID_DATE'],1);self.assertEqual(c['OUTSIDE_PARTITION'],1)
 def test_wrapped_finmind_revenue(self):
  o=[{'source_record':{'date':'2025-02-10','stock_id':'2330','revenue_year':2025,'revenue_month':1,'revenue':1000}}]
  r,_,_=parse_member('FinMind','revenue_complement.jsonl',(json.dumps(o[0])+'\n').encode(),'2025-01')
  self.assertEqual(len(r),1);self.assertEqual(r[0]['numeric_decimal_text'],'1000')

if __name__=='__main__':unittest.main()
