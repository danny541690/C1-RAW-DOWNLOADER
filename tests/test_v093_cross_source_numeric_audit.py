import unittest
import itertools
from scripts.v093_cross_source_numeric_audit import compare_rows,matches_native_field,is_mapped_native_field
def row(src,field,val,stock="2330",date="2026-09-01"):
 return {"source":src,"date":date,"stock_id":stock,"native_field":field,"numeric_unscaled":val}
class CrossSourceNumericTests(unittest.TestCase):
 def test_conflict_cannot_be_counted_as_agreement_in_any_input_order(self):
  for values in itertools.permutations([100,101,100]):
   with self.subTest(values=values):
    r=compare_rows({'FinMind':[row('FinMind','close',v) for v in values],
                    'TWSE':[row('TWSE','收盤價',100)]})
    self.assertEqual(r['duplicate_conflicts'],1)
    self.assertEqual(r['compared_pairs'],{})
    self.assertEqual(r['within_tolerance'],{})
 def test_conflict_does_not_discard_independent_clean_sources(self):
  r=compare_rows({'FinMind':[row('FinMind','close',100),row('FinMind','close',101)],
                 'TWSE':[row('TWSE','收盤價',100)],'TPEx':[row('TPEx','收盤價',100)]})
  self.assertEqual(r['compared_pairs'],{'TPEx__TWSE':1})
  self.assertEqual(r['duplicate_conflicts'],1)
  self.assertFalse(r['certified'])
 def test_identical_duplicates_do_not_inflate_independent_pairs(self):
  r=compare_rows({'FinMind':[row('FinMind','close',100)]*3,'TWSE':[row('TWSE','收盤價',100)]*2})
  self.assertEqual(r['compared_pairs'],{'FinMind__TWSE':1})
  self.assertEqual(r['duplicate_conflicts'],0)
 def test_bad_keys_cannot_create_false_agreement(self):
  for stock,date in [('2330','2026-02-30'),('2330','20260901'),('','2026-09-01'),('2330!','2026-09-01'),(2330,'2026-09-01')]:
   with self.subTest(stock=stock,date=date):
    r=compare_rows({'FinMind':[row('FinMind','close',100,stock,date)],'TWSE':[row('TWSE','收盤價',100,stock,date)]})
    self.assertEqual(r['compared_pairs'],{})
 def test_nonfinite_negative_and_boolean_tolerance_is_rejected(self):
  for tolerance in [float('nan'),float('inf'),-0.01,True,'0.01']:
   with self.subTest(tolerance=tolerance):
    with self.assertRaisesRegex(ValueError,'INVALID_ABSOLUTE_TOLERANCE'):
     compare_rows({},abs_tol=tolerance)
 def test_positional_field_match_is_exact_not_substring(self):
  self.assertTrue(matches_native_field("收盤價__col_04","收盤價"))
  self.assertTrue(matches_native_field("收盤價","收盤價"))
  self.assertFalse(matches_native_field("除權息前收盤價__col_03","收盤價"))
  self.assertFalse(matches_native_field("收盤價__col_fake","收盤價"))
 def test_tpex_daily_close_alias_not_exdividend(self):
  self.assertTrue(is_mapped_native_field("TPEx","close","收盤__col_02"))
  self.assertTrue(is_mapped_native_field("TPEx","close","收盤價__col_04"))
  self.assertFalse(is_mapped_native_field("TPEx","close","除權息前收盤價__col_03"))
  self.assertFalse(is_mapped_native_field("TWSE","close","收盤__col_02"))
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TPEx":[row("TPEx","收盤__col_02",100)]})
  self.assertEqual(r["compared_pairs"],{"FinMind__TPEx":1})
 def test_cross_source_positional_price(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TPEx":[row("TPEx","收盤價__col_04",100)]})
  self.assertEqual(r["compared_pairs"],{"FinMind__TPEx":1})
 def test_exact_matched_price(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TWSE":[row("TWSE","收盤價",100)]})
  self.assertEqual(r["compared_pairs"],{"FinMind__TWSE":1})
  self.assertEqual(r["within_tolerance"],{"FinMind__TWSE":1})
  self.assertFalse(r["certified"])
 def test_mismatch_and_no_false_join(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TWSE":[row("TWSE","收盤價",101),row("TWSE","收盤價",100,stock="2317")]})
  self.assertEqual(r["mismatch"],{"FinMind__TWSE":1})
  self.assertEqual(len(r["mismatch_examples"]),1)
 def test_no_overlapping_sources_not_pass(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100)],"TPEx":[row("TPEx","投信買賣超",100)]})
  self.assertEqual(r["compared_pairs"],{})
  self.assertFalse(r["independent_numeric_verified"])
 def test_duplicate_source_conflict(self):
  r=compare_rows({"FinMind":[row("FinMind","close",100),row("FinMind","close",101)]})
  self.assertEqual(r["duplicate_conflicts"],1)
 def test_unpadded_parser_field_positions_compare_all_twse_prices(self):
  import json
  from scripts.v093_standard_r4 import parse_member
  raw=json.dumps({'date':'20260901','fields':['證券代號','開盤價','最高價','最低價','收盤價'],'data':[['1101','24.60','26.10','24.60','25.30']]}).encode()
  parsed,stats,encoding=parse_member('TWSE','prices_indices_20260901.raw',raw,'2026-09')
  for r in parsed:r['numeric_unscaled']=float(r['numeric_decimal_text'])
  for metric,value,field in [('open',24.6,'open'),('high',26.1,'max'),('low',24.6,'min'),('close',25.3,'close')]:
   with self.subTest(metric=metric):
    got=compare_rows({'TWSE':parsed,'FinMind':[row('FinMind',field,value,stock='1101')]},metric)
    self.assertEqual(got['within_tolerance'],{'FinMind__TWSE':1});self.assertFalse(got['certified'])
 def test_unpadded_tpex_close_position_is_comparable(self):
  got=compare_rows({'TPEx':[row('TPEx','收盤__col_2',100)],'FinMind':[row('FinMind','close',100)]})
  self.assertEqual(got['compared_pairs'],{'FinMind__TPEx':1})
 def test_malformed_positions_still_do_not_match(self):
  for suffix in ('-1','1x','12345',''):
   self.assertFalse(matches_native_field('收盤價__col_'+suffix,'收盤價'))
 def test_tpex_native_daily_four_price_labels(self):
  import json
  from scripts.v093_standard_r4 import parse_member
  raw=json.dumps({'date':'20260901','fields':['代號','名稱','收盤','漲跌','開盤','最高','最低'],'data':[['1259','測試','25.3','0.9','24.6','26.1','24.6']]}).encode()
  cells,stats,encoding=parse_member('TPEx','prices_20260901.raw',raw,'2026-09')
  for r in cells:r['numeric_unscaled']=float(r['numeric_decimal_text'])
  for metric,field,val in [('open','open',24.6),('high','max',26.1),('low','min',24.6),('close','close',25.3)]:
   got=compare_rows({'TPEx':cells,'FinMind':[row('FinMind',field,val,stock='1259')]},metric)
   self.assertEqual(got['within_tolerance'],{'FinMind__TPEx':1})
 def test_tpex_aliases_exclude_reference_and_event_fields(self):
  for metric,label in [('open','次日開盤參考價'),('high','最高價漲幅'),('low','最低價跌幅'),('close','除權息前收盤')]:
   self.assertFalse(is_mapped_native_field('TPEx',metric,label+'__col_2'))
if __name__=="__main__":unittest.main()
