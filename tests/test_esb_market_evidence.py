import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from scripts.v093_esb_market_evidence import load_evidence,FIELDS
from scripts.v093_prelaunch_acceptance_batch import inspect_raw
class ESBEvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)
  self.obj=dict(stat='ok',date='20260901',tables=[dict(title='興櫃個股歷史行情',date='115年09月',subtitle='115年09月 1269 測試',fields=FIELDS,totalCount=1,data=[['115/09/01','100','1000','12','10','11','1','0','0','0','0','0','0']])])
  self.entry=dict(file='x.json',code='1269',month='2026-09',url='https://www.tpex.org.tw/www/zh-tw/emerging/historical?code=1269&date=2026%2F09%2F01&type=Monthly&response=json')
  self.row=dict(date='2026-09-01',stock_id='1269',open=9,max=12,min=10,close=11,Trading_Volume=100,Trading_money=1000)
  self.task={'來源':'FinMind','資料集':'TaiwanStockPrice','代碼':'1269','月份':'2026-09','原件參照':'file/x.json'}
 def save(self):
  b=json.dumps(self.obj).encode();(self.p/'x.json').write_bytes(b);self.entry['sha256']=hashlib.sha256(b).hexdigest();(self.p/'manifest.json').write_text(json.dumps(dict(inputs=[self.entry])));return load_evidence(self.p)
 def inspect(self,ev=None):return inspect_raw(json.dumps(dict(status=200,data=[self.row])).encode(),self.task,ev)
 def test_proved_esb_routes_raw_only(self):
  e=self.inspect(self.save());self.assertEqual(len(e['esb_raw_only_rows']),1);self.assertEqual(e['ohlc_rows_checked'],0);self.assertFalse(e['analysis_release_approved']);self.assertFalse(e['esb_raw_only_rows'][0]['close_value_verified'])
 def test_no_market_proof_keeps_generic_hold(self):
  with self.assertRaisesRegex(ValueError,'OHLC_RELATIONSHIP'):self.inspect()
 def test_wrong_date_proof_does_not_exempt(self):
  e=self.save();e[('2026-09-02','1269')]=e.pop(('2026-09-01','1269'))
  with self.assertRaisesRegex(ValueError,'OHLC_RELATIONSHIP'):self.inspect(e)
 def test_tampered_native_raw_rejected(self):
  self.save();(self.p/'x.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'ESB_SHA_MISMATCH'):load_evidence(self.p)
 def test_wrong_code_in_content_rejected(self):
  self.obj['tables'][0]['subtitle']='115年09月 1271 測試'
  with self.assertRaisesRegex(ValueError,'ESB_CONTENT_SCOPE'):self.save()
 def test_wrong_month_in_rows_rejected(self):
  self.obj['tables'][0]['data'][0][0]='115/08/31'
  with self.assertRaisesRegex(ValueError,'ESB_ROW_PERIOD'):self.save()
 def test_duplicate_key_rejected(self):
  t=self.obj['tables'][0];t['data']*=2;t['totalCount']=2
  with self.assertRaisesRegex(ValueError,'ESB_DUPLICATE_KEY'):self.save()
 def test_value_mismatch_not_exempted(self):
  e=self.save();self.row['max']=13
  with self.assertRaisesRegex(ValueError,'ESB_OFFICIAL_VALUE_MISMATCH'):self.inspect(e)
 def test_close_outside_range_still_blocked(self):
  e=self.save();self.row['close']=13
  with self.assertRaisesRegex(ValueError,'ESB_LAST_TRADE_RELATIONSHIP'):self.inspect(e)
 def test_outside_system_trade_contract_not_assumed(self):
  self.obj['tables'][0]['data'][0][7]='1';e=self.save()
  with self.assertRaisesRegex(ValueError,'ESB_OUTSIDE_SYSTEM_CONTRACT_REQUIRED'):self.inspect(e)
 def test_url_scope_mismatch_rejected(self):
  self.entry['url']=self.entry['url'].replace('code=1269','code=1271')
  with self.assertRaisesRegex(ValueError,'ESB_SOURCE_SCOPE'):self.save()
 def test_schema_drift_rejected(self):
  self.obj['tables'][0]['fields']=['date']
  with self.assertRaisesRegex(ValueError,'ESB_CONTENT_SCOPE'):self.save()
 def test_batch_keeps_esb_raw_only_and_evidence_change_invalidates_resume(self):
  import csv,gzip
  from scripts.v093_prelaunch_acceptance_batch import run,sha
  self.save();reg=self.p/'reg';reg.mkdir();cache=self.p/'cache';cache.mkdir()
  raw=json.dumps(dict(status=200,data=[self.row])).encode();(cache/'file1').write_bytes(raw)
  r=dict(self.task,單元ID='unit1',原件參照='file1',已下載='1',期間='2026-09',年份='2026',RAW_SHA256=sha(raw))
  with gzip.open(reg/'FinMind_units.csv.gz','wt',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=r);w.writeheader();w.writerow(r)
  first=run(reg,cache,self.p/'out',esb_dir=self.p)
  self.assertEqual(first['counts']['ESB_RAW_ONLY_RULES_OPEN'],1);self.assertEqual(first['approved_scopes'],[])
  second=run(reg,cache,self.p/'next',self.p/'out/checkpoint.json',self.p)
  self.assertEqual(second['counts']['resumed_content_units'],1)
  # Same code/date, changed valid official evidence: cached result must not survive.
  self.obj['tables'][0]['data'][0][3]='13';self.save()
  third=run(reg,cache,self.p/'changed',self.p/'out/checkpoint.json',self.p)
  self.assertEqual(third['counts']['CONTENT_BLOCKED'],1);self.assertEqual(third['counts'].get('resumed_content_units',0),0)
