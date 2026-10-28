import json,unittest
from scripts.v093_standard_r4 import parse_member
from scripts.v093_prelaunch_acceptance_batch import inspect_raw
CSV='上櫃股票行情\n資料日期:115/09/08\n代號,名稱,收盤,漲跌,開盤,最高,最低\n1259,測試,10,0,9,11,8\n'
class NativeSupplementTests(unittest.TestCase):
 def test_csv_content_date_without_filename_proves_period(self):
  cells,stats,encoding=parse_member('TPEx','price.csv',CSV.encode(),'2026-09')
  self.assertTrue(cells);self.assertEqual({r['date'] for r in cells},{'2026-09-08'});self.assertEqual({r['date_proof'] for r in cells},{'CSV_HEADER'});self.assertTrue(all(r['date_content_verified'] for r in cells))
 def test_csv_filename_content_conflict_rejected(self):
  with self.assertRaisesRegex(ValueError,'CSV_HEADER_FILENAME_DATE_CONFLICT'):parse_member('TPEx','prices_20260909.csv',CSV.encode(),'2026-09')
 def test_csv_conflicting_metadata_rejected(self):
  raw=CSV.replace('代號,','資料日期:115/09/09\n代號,')
  with self.assertRaisesRegex(ValueError,'CSV_HEADER_DATE_CONFLICT'):parse_member('TPEx','price.csv',raw.encode(),'2026-09')
 def test_csv_invalid_metadata_rejected(self):
  with self.assertRaisesRegex(ValueError,'INVALID_CSV_HEADER_DATE'):parse_member('TPEx','price.csv',CSV.replace('115/09/08','115/02/30').encode(),'2026-09')
 def test_csv_without_metadata_not_content_verified(self):
  cells,stats,encoding=parse_member('TPEx','prices_20260908.csv',CSV.replace('資料日期:115/09/08\n','').encode(),'2026-09')
  self.assertTrue(cells);self.assertTrue(all(not r['date_content_verified'] for r in cells))
 def test_csv_batch_checks_actual_period(self):
  r={'來源':'TPEx','資料集':'prices','期間':'2026-09-08','原件參照':'file/prices_20260908.csv'}
  ev=inspect_raw(CSV.encode(),r);self.assertEqual(ev['date_proof'],'CSV_HEADER');self.assertEqual(ev['ohlc_rows_checked'],1)
 def row(self):return dict(date='2026-09-08',stock_id='1101',open=9,max=11,min=8,close=10)
 def task(self,ext='jsonl'):return {'來源':'FinMind','資料集':'TaiwanStockPrice','代碼':'1101','月份':'2026-09','原件參照':'file/price.'+ext}
 def test_single_jsonl_partition_is_validated(self):
  b=json.dumps(dict(parent_row_index=2,source_record=self.row())).encode();ev=inspect_raw(b,self.task());self.assertEqual(ev['rows'],1);self.assertFalse(ev['parent_response_sha_readback_verified'])
 def test_jsonl_invalid_provenance_rejected(self):
  for index in (True,-1,'2'):
   with self.subTest(index=index):
    with self.assertRaisesRegex(ValueError,'INVALID_FINMIND_NATIVE_PARTITION'):inspect_raw(json.dumps(dict(parent_row_index=index,source_record=self.row())).encode(),self.task())
 def test_jsonl_duplicate_keys_rejected(self):
  row=json.dumps(dict(parent_row_index=2,source_record=self.row()))
  with self.assertRaisesRegex(ValueError,'DUPLICATE_KEY'):inspect_raw((row+'\n'+row).encode(),self.task())
 def test_month_slice_provenance_required(self):
  obj=dict(dataset='TaiwanStockPrice',stock_id='1101',response_sha256='a'*64,status='RAW_MONTH_SLICE_NOT_PIT_VERIFIED',rows=[self.row()]);ev=inspect_raw(json.dumps(obj).encode(),self.task('json'));self.assertEqual(ev['rows'],1);self.assertFalse(ev['parent_response_sha_readback_verified'])
  obj['stock_id']='2330'
  with self.assertRaisesRegex(ValueError,'INVALID_FINMIND_SLICE_PROVENANCE'):inspect_raw(json.dumps(obj).encode(),self.task('json'))
 def test_jsonl_wrong_period_rejected(self):
  r=self.row();r['date']='2026-08-08'
  with self.assertRaisesRegex(ValueError,'FINMIND_PERIOD_CODE'):inspect_raw(json.dumps(dict(parent_row_index=0,source_record=r)).encode(),self.task())

 def test_tpex_staging_receipt_rebuilt_without_changing_twse(self):
  import hashlib
  from scripts.v093_standard_r4 import receipt_key,VERSION
  digest='a'*64
  old_tpex=hashlib.sha256(('TPEx'+VERSION+digest).encode()).hexdigest()
  old_twse=hashlib.sha256(('TWSE'+VERSION+digest).encode()).hexdigest()
  self.assertNotEqual(receipt_key('TPEx',digest,'archive.zip'),old_tpex)
  self.assertEqual(receipt_key('TWSE',digest,'archive.zip'),old_twse)

 def test_csv_under_raw_extension_still_uses_content_date(self):
  r={'來源':'TPEx','資料集':'prices','期間':'2026-09-08','原件參照':'file/hash.raw'}
  self.assertEqual(inspect_raw(CSV.encode(),r)['date_proof'],'CSV_HEADER')

 def test_csv_metadata_retained_managed_prices_not_certified(self):
  raw=CSV+'管理股票\n1269,管理股,10,0,7,11,8\n註：來源說明\n上櫃家數,2,\n'
  r={'來源':'TPEx','資料集':'prices','期間':'2026-09-08','原件參照':'file/hash.raw'}
  ev=inspect_raw(raw.encode(),r)
  self.assertEqual(ev['managed_codes_not_ohlc_certified'],['1269'])
  self.assertIn('MANAGED_STOCK_PRICE_SEMANTICS_NOT_PROVEN',ev['unverified'])
  self.assertEqual(ev['ohlc_rows_checked'],1);self.assertEqual(len(ev['csv_metadata_rows']),3)
 def test_csv_unknown_truncated_rows_are_blocked(self):
  r={'來源':'TPEx','資料集':'prices','期間':'2026-09-08','原件參照':'file/hash.raw'}
  with self.assertRaisesRegex(ValueError,'CSV_UNRECOGNIZED_NON_DATA_ROW'):inspect_raw((CSV+'1101,broken\n').encode(),r)

 def test_csv_repeated_exact_header_is_metadata_not_numeric_data(self):
  header='代號,名稱,收盤,漲跌,開盤,最高,最低\n'
  r={'來源':'TPEx','資料集':'prices','期間':'2026-09-08','原件參照':'file/hash.raw'}
  ev=inspect_raw((CSV+'管理股票\n'+header+'1269,管理股,10,0,7,11,8\n').encode(),r)
  self.assertEqual(ev['rows_checked'],2);self.assertEqual(ev['ohlc_rows_checked'],1)
