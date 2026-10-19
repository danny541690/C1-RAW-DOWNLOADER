import ast, collections, concurrent.futures, datetime as dt, hashlib, io, json, math, os, pathlib, re, time, unittest, zipfile

source=pathlib.Path('scripts/v093_history_reverse.py').read_text()
tree=ast.parse(source)
ns=globals().copy();ns.update(RUN='HISTORY_202312_TO_201401_R1',ROOT='raw',REPORT_ROOT='reports',OTHER_FINMIND_CONTROL='other',FIN_REPORTS=('IncomeStatement','BalanceSheet','CashflowStatement'),MAP={'IncomeStatement':'TaiwanStockFinancialStatements','BalanceSheet':'TaiwanStockBalanceSheet','CashflowStatement':'TaiwanStockCashFlowsStatement'},sha=lambda b:hashlib.sha256(b).hexdigest(),stamp=lambda:'test')
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MONTHS' for t in n.targets))]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'history','exec'),ns)
H=ns['History'];key=ns['key'];packed=ns['packed']

class HistoryContracts(unittest.TestCase):
 def test_exact_120_month_descending_sequence(self):
  months=ns['MONTHS']
  self.assertEqual(len(months),120);self.assertEqual(len(set(months)),120)
  self.assertEqual(months[:3],['2023-12','2023-11','2023-10']);self.assertEqual(months[-1],'2014-01')
  for a,b in zip(months,months[1:]):
   y,m=map(int,a.split('-'));yy,mm=map(int,b.split('-'));self.assertEqual(12*y+m-12*yy-mm,1)
 def test_native_response_bytes_and_receipt_roundtrip(self):
  raw=b'{"native": "unchanged", "date":"20231201"}\r\n'
  receipt={'unit_id':'abc','sha256':ns['sha'](raw),'source':'TWSE','month':'2023-12','bucket':'units'}
  with zipfile.ZipFile(io.BytesIO(packed([(receipt,raw)]))) as z:
   self.assertIsNone(z.testzip());self.assertEqual(z.read('abc.raw'),raw)
   self.assertEqual(json.loads(z.read('manifest.json'))['units'][0]['sha256'],ns['sha'](raw))
 def test_financial_groups_and_nonquarter(self):
  h=object.__new__(H);h.active='2023-12';h.state={'stocks':[str(1000+i) for i in range(41)]}
  jobs=h.financial_jobs();self.assertEqual(len(jobs),9)
  self.assertTrue(all(j['report_period']=='20234' and j['period']=='2023-12-31' for j in jobs))
  h.active='2023-11';self.assertEqual(h.financial_jobs(),[])
 def test_finmind_only_explicit_financial_gaps(self):
  h=object.__new__(H);h.active='2023-12';h.state={'financial_units':{'x':{'codes':['2330','2317'],'codes_found':['2330'],'category':'IncomeStatement','period':'2023-12-31','unit_id':'x'}},'units':{},'market_codes':{}}
  tasks=h.fm_plan([]);self.assertEqual(len(tasks),1);self.assertEqual(tasks[0]['stock_id'],'2317')
 def test_multiple_missing_dates_collapse_to_one_stock_month_request(self):
  h=object.__new__(H);h.active='2023-12';h.state={'financial_units':{},'units':{},'market_codes':{'TWSE':['2330']}}
  jobs=[{'source':'TWSE','category':'prices_indices','period':d} for d in ['2023-12-01','2023-12-04']]
  tasks=h.fm_plan(jobs);self.assertEqual(len(tasks),1);self.assertEqual(len(tasks[0]['official_missing_dates']),2)
 def test_recovery_from_archive_before_checkpoint_write(self):
  h=object.__new__(H);h.d=object();h.folder=lambda s,m:s
  raw=b'original';r={'source':'TWSE','unit_id':'abc','month':'2023-12','bucket':'units','status':'SAVED_BASIC_VERIFIED','sha256':ns['sha'](raw),'codes_found':['2330']}
  archive=packed([(r,raw)]);f={'name':ns['RUN']+'_test.zip','id':'f'}
  old={k:ns.get(k) for k in ('getj','listing','read')}
  try:
   ns['getj']=lambda *args:None;ns['listing']=lambda d,p:[f] if p=='TWSE' else [];ns['read']=lambda d,f:archive
   h.restore('2023-12','ctrl')
   self.assertIn('abc',h.state['units']);self.assertEqual(h.state['stocks'],['2330']);self.assertEqual(len(h.state['archives']),1)
  finally:ns.update(old)
 def test_source_specific_task_identity(self):
  a={'source':'TWSE','category':'institutional','period':'2023-12-01'}
  self.assertEqual(key(a),key(dict(a,url='different transport URL')))
  self.assertNotEqual(key(a),key(dict(a,source='TPEx')))

if __name__=='__main__':unittest.main()
