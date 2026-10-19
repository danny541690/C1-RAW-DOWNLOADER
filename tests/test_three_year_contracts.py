import ast, pathlib, unittest, json, re, datetime as dt, html, csv, io

src=pathlib.Path('scripts/v093_three_year_repair.py').read_text()
tree=ast.parse(src)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('normdate','actual_date','category','tabular','validate')]
ns={'re':re,'dt':dt,'json':json,'html':html,'csv':csv,'io':io,
    'DAILY':{'TWSE':[('prices_indices','',{}),('margin','',{})],'TPEx':[('prices','',{})]},
    'EVENTS':{'TWSE':[('capital_reduction','')],'TPEx':[]}}
exec(compile(ast.Module(body=nodes,type_ignores=[]),'contracts','exec'),ns)

class Contracts(unittest.TestCase):
 def payload(self,date='20240102',rows=None):
  return json.dumps({'stat':'OK','date':date,'fields':['代號','收盤價'],'data':rows or [[str(1000+i),10] for i in range(300)]}).encode()
 def test_correct_daily_bulk(self):
  self.assertEqual(ns['validate'](self.payload(),'TWSE','prices_indices','2024-01-02')['rows'],300)
 def test_current_response_cannot_impersonate_history(self):
  with self.assertRaisesRegex(ValueError,'DATE_MISMATCH'):ns['validate'](self.payload('20261019'),'TWSE','prices_indices','2024-01-02')
 def test_single_stock_cannot_impersonate_full_market(self):
  with self.assertRaisesRegex(ValueError,'NOT_FULL_MARKET'):ns['validate'](self.payload(rows=[['2330',10]]),'TWSE','prices_indices','2024-01-02')
 def test_row_alignment(self):
  with self.assertRaisesRegex(ValueError,'WIDTH'):ns['validate'](self.payload(rows=[['2330']]),'TWSE','prices_indices','2024-01-02')
 def test_empty_events_not_proof(self):
  with self.assertRaisesRegex(ValueError,'EMPTY_EVENT'):ns['validate'](b'{"stat":"OK","data":[]}','TWSE','capital_reduction','2024-01')
 def test_revenue_month(self):
  raw='<html>113年1月<table><td>2330</td></table></html>'.encode('cp950')
  self.assertEqual(ns['validate'](raw,'MOPS','revenue_sii_0','2024-01')['codes'],['2330'])
  with self.assertRaisesRegex(ValueError,'PERIOD_UNPROVEN'):ns['validate'](raw,'MOPS','revenue_sii_0','2024-02')
 def test_date_formats(self):
  self.assertEqual(ns['normdate']('113/01/02'),'2024-01-02')
  self.assertEqual(ns['normdate']('2024/01/02'),'2024-01-02')
  self.assertIsNone(ns['normdate']('20240231'))
 def test_categories(self):
  self.assertEqual(ns['category']('2024-01-02_HISTORICAL_CORRECTED_R3.json','TPEx'),'prices')
  self.assertEqual(ns['category']('revenue_sii_2025-01_0_abc.raw','MOPS'),'revenue_sii_0')
  self.assertEqual(ns['category']('THREE_YEAR_OFFICIAL_GAPS_20261019_R1_revenue_otc_1_2025-01_abc.html','MOPS'),'revenue_otc_1')
 def test_official_csv_date_and_table(self):
  raw=('113/01/02\n代號,收盤價\n'+''.join(str(1000+i)+',10\n' for i in range(300))).encode('cp950')
  self.assertEqual(ns['validate'](raw,'TPEx','prices','2024-01-02')['rows'],300)
  with self.assertRaisesRegex(ValueError,'DATE_UNPROVEN'):ns['validate'](raw,'TPEx','prices','2024-01-03')

if __name__=='__main__':unittest.main()
