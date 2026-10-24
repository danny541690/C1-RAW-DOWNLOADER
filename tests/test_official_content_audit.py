import json
import unittest
from scripts.v093_official_content_audit import audit_rows,value_digest

class RowAuditTests(unittest.TestCase):
    def raw(self,rows=None,extra=None):
        obj={'stat':'OK','fields':['證券代號','開盤價','最高價','最低價','收盤價','成交股數'],
             'data':rows or [['2330','100','110','90','105','1000']]}
        obj.update(extra or {});return json.dumps(obj).encode()
    def job(self):return {'category':'prices_indices'}
    def test_price_rows_and_quantity_are_actually_checked(self):
        out=audit_rows(self.raw(),self.job())
        self.assertEqual(out['ohlc_rows_checked'],1);self.assertEqual(out['numeric_cells_checked'],1)
    def test_invalid_price_relationship_is_rejected(self):
        with self.assertRaises(ValueError):audit_rows(self.raw([['2330','100','95','90','105','1000']]),self.job())
    def test_negative_volume_is_rejected(self):
        with self.assertRaises(ValueError):audit_rows(self.raw([['2330','100','110','90','105','-1']]),self.job())
    def test_duplicate_security_is_rejected(self):
        row=['2330','100','110','90','105','1000']
        with self.assertRaises(ValueError):audit_rows(self.raw([row,row]),self.job())
    def test_nontrade_prices_are_not_accepted_as_verified(self):
        out=audit_rows(self.raw([['2330','--','--','--','--','0']]),self.job())
        self.assertIn('NO_VALID_TRADE_PRICE_REQUIRES_REVIEW',out['unverified'])
    def test_wrapper_timestamp_does_not_create_false_value_revision(self):
        self.assertEqual(value_digest(self.raw(extra={'updated':'a'})),value_digest(self.raw(extra={'updated':'b'})))
    def test_changed_source_value_is_detected(self):
        self.assertNotEqual(value_digest(self.raw()),value_digest(self.raw([['2330','100','110','90','104','1000']])))

if __name__=='__main__':unittest.main()

class NativePercentageTests(unittest.TestCase):
    def raw(self,value):
        return json.dumps(dict(fields=['證券代號','僑外資及陸資持股比率(E=C/A)'],data=[['2330',value]])).encode()
    def test_official_percent_suffix_is_valid_in_holding_ratio_only(self):
        self.assertEqual(audit_rows(self.raw('97.24%'),{'category':'foreign_holdings'})['numeric_cells_checked'],1)
        for value in ['101%','-1%','97%%']:
            with self.assertRaises(ValueError):audit_rows(self.raw(value),{'category':'foreign_holdings'})
    def test_price_percent_suffix_remains_invalid(self):
        with self.assertRaises(ValueError):audit_rows(RowAuditTests().raw([['2330','100%','110','90','105','1000']]),{'category':'prices_indices'})
    def test_nontrading_raw_is_preserved_as_open_quality_not_refetched(self):
        from scripts.v093_official_repair import validate_content
        obj=dict(stat='OK',date='20261022',fields=['證券代號','開盤價','最高價','最低價','收盤價','成交股數'],data=[['2330','--','--','--','--','0']])
        ev=validate_content(json.dumps(obj).encode(),dict(source='TWSE',category='prices_indices',period='2026-10-22'))
        self.assertIn('PRICE_MISSING_OR_NONTRADING_REVIEW_REQUIRED',ev['row_audit']['unverified'])

class OfficialSummaryRowTests(unittest.TestCase):
    def payload(self,rows):
        return json.dumps(dict(fields=['代號','名稱','前日餘額','賣出','買進','現券','今日餘額'],data=rows)).encode()
    def test_twse_lending_final_named_total_is_not_empty_security(self):
        rows=[['2330','台積電','1','1','1','1','1'],['','合計','1','1','1','1','1']]
        out=audit_rows(self.payload(rows),dict(source='TWSE',category='lending'))
        self.assertEqual(out['rows_checked'],2)
        for bad in [rows[::-1],[rows[0],['','unknown','1','1','1','1','1']]]:
            with self.assertRaisesRegex(ValueError,'EMPTY_SECURITY'):
                audit_rows(self.payload(bad),dict(source='TWSE',category='lending'))
    def test_per_thousand_subscription_field_is_not_a_percent(self):
        raw=json.dumps(dict(fields=['代號','按持股比例仟股認購'],data=[['2330','1200']])).encode()
        out=audit_rows(raw,dict(source='TPEx',category='ex_dividend'))
        self.assertIn('NUMERIC_FIELD_RULES_NOT_COVERED',out['unverified'])
