import copy
import csv
import io
import json
import unittest
from scripts.v093_prelaunch_acceptance_batch import inspect_raw
from scripts.v093_taifex_monthly_content import FUTURES, LARGE


class SupplementDispatchTests(unittest.TestCase):
    def setUp(self):
        self.row = {'來源': 'FinMind', '資料集': 'TaiwanStockFinancialStatements', '代碼': '1444',
                    '月份': '2010-06', '期間': '2010-06', '原件參照': 'retained.raw'}
        self.financial = dict(status=200, data=[dict(date='2010-06-30', stock_id='1444', type='EPS',
                                                  origin_name='基本每股盈餘', value=-0.6)])

    def inspect(self, obj=None):
        return inspect_raw(json.dumps(obj or self.financial).encode(), self.row)

    def csv(self, header, rows):
        stream=io.StringIO();writer=csv.writer(stream);writer.writerow(header);writer.writerows(rows)
        return stream.getvalue().encode('cp950')

    def taifex(self, payload, dataset='futDataDown', period='2026-06-01'):
        return inspect_raw(payload, {'來源':'TAIFEX','資料集':dataset,'期間':period})

    def test_financial_negative_eps_preserved_and_not_released(self):
        before=copy.deepcopy(self.financial);e=self.inspect()
        self.assertEqual(e['finite_value_cells'],1);self.assertEqual(self.financial,before)
        self.assertFalse(e['analysis_release_approved']);self.assertFalse(e['unit_contract_verified'])
        self.assertFalse(e['quarter_or_halfyear_semantics_verified'])

    def test_financial_noncanonical_type_retains_origin_identity(self):
        a=copy.deepcopy(self.financial);a['data'][0].update(type='-',origin_name='科目甲')
        a['data'].append(dict(a['data'][0],origin_name='科目乙'))
        e=self.inspect(a);self.assertEqual(e['rows'],2);self.assertEqual(e['ambiguous_account_type_keys'],1)
        self.assertFalse(e['canonical_account_key_verified'])

    def test_duplicate_financial_native_key_rejected(self):
        a=copy.deepcopy(self.financial);a['data']*=2
        with self.assertRaisesRegex(ValueError,'DUPLICATE_NATIVE_KEY'):self.inspect(a)

    def test_financial_nonfinite_bool_and_string_values_rejected(self):
        for value in (float('nan'),float('inf'),True,'0.6'):
            with self.subTest(value=value):
                a=copy.deepcopy(self.financial);a['data'][0]['value']=value
                with self.assertRaisesRegex(ValueError,'INVALID_NUMBER'):self.inspect(a)

    def test_wrong_financial_code_month_and_nonquarter_date_rejected(self):
        for changed in ({'stock_id':'2330'},{'date':'2010-09-30'},{'date':'2010-06-29'}):
            a=copy.deepcopy(self.financial);a['data'][0].update(changed)
            with self.assertRaises(ValueError):self.inspect(a)

    def test_financial_error_empty_and_missing_origin_rejected(self):
        for obj in ({'status':400,'data':self.financial['data']},{'status':200,'data':[]}):
            with self.assertRaisesRegex(ValueError,'EMPTY_OR_ERROR'):self.inspect(obj)
        obj=copy.deepcopy(self.financial);del obj['data'][0]['origin_name']
        with self.assertRaisesRegex(ValueError,'SCHEMA'):self.inspect(obj)

    def test_monthly_futures_close_column_ohlc_checked(self):
        row=['2026/06/01','TX','202606','10','12','9','11','1','10%', '5','11','8','','','','','','一般','']
        e=self.taifex(self.csv(FUTURES,[row]));self.assertGreater(e['recognized_numeric_checks'],0)
        self.assertFalse(e['analysis_release_approved']);row[6]='15'
        with self.assertRaisesRegex(ValueError,'OHLC_RELATIONSHIP'):self.taifex(self.csv(FUTURES,[row]))

    def test_monthly_missing_prices_remain_explicit(self):
        row=['2026/06/01','TX','202607','-','-','-','-','-','-', '0','10','0','','','','','','一般','']
        e=self.taifex(self.csv(FUTURES,[row]));self.assertEqual(e['unverified_price_rows'],1)
        self.assertFalse(e['full_numeric_certification'])

    def test_wrong_taifex_schema_and_month_do_not_pass(self):
        payload=self.csv(LARGE,[['2006/05/02','TX','臺指','200605','0','0','0','0','0','0']])
        with self.assertRaisesRegex(ValueError,'SCHEMA_MISMATCH'):self.taifex(payload)
        with self.assertRaisesRegex(ValueError,'OUTSIDE_REQUEST'):self.taifex(payload,'largeTraderFutDown','2006-06-01')

    def test_large_trader_routed_without_claiming_numeric_completeness(self):
        payload=self.csv(LARGE,[['2006/05/02','TX','臺指','200605','0','0','0','0','0','0']])
        e=self.taifex(payload,'largeTraderFutDown','2006-05-01');self.assertEqual(e['rows'],1)
        self.assertEqual(e['recognized_numeric_checks'],0);self.assertFalse(e['full_numeric_certification'])

    def test_grouped_legs_date_inherited_and_missing_legs_rejected(self):
        text='組合式序號,日期,契約數,交易時段\n組合式序號,子序號,契約,到期月份(週別),履約價格,買/賣權,成交價格,成交數量\nC1,2017/04/13,2,一般,\nC1,1,TX,201704,-,-,10,2,\nC1,2,TX,201705,-,-,11,2,\n'
        e=self.taifex(text.encode('cp950'),'combinationOrderDown','2017-04-01');self.assertEqual(e['rows'],2)
        self.assertEqual(e['content_period']['min'],'2017-04-13')
        with self.assertRaisesRegex(ValueError,'LEGS_MISSING'):
            self.taifex(text.rsplit('C1,2',1)[0].encode('cp950'),'combinationOrderDown','2017-04-01')

    def test_unknown_taifex_dataset_still_rejected(self):
        with self.assertRaisesRegex(ValueError,'UNMAPPED_TAIFEX_DATASET'):self.taifex(b'data','not_supported')


if __name__=='__main__':unittest.main()
