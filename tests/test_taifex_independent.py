import datetime as dt
import io
import unittest
import zipfile
from scripts import v093_taifex_independent as m
class TAIFEXTests(unittest.TestCase):
    def job(self,kind='csv',start='2000-01-01',end='2000-12-31'):
        return {'kind':kind,'start':start,'end':end}
    def csv(self,date='2000/1/4'):
        return ('交易日期,契約,到期月份,收盤價,交易時段\n'+date+',TX,200001,8843,一般\n').encode('cp950')
    def archive(self,raw):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('2000_fut.csv',raw)
        return b.getvalue()
    def test_annual_actual_row_dates(self):
        ev=m.validate(self.archive(self.csv()),self.job('annual'))
        self.assertEqual(ev['content_period'],{'min':'2000-01-04','max':'2000-01-04'})
        self.assertEqual(ev['rows'],1);self.assertTrue(ev['zip_crc_verified'])
    def test_reject_current_data_in_historical_response(self):
        with self.assertRaisesRegex(ValueError,'OUTSIDE_REQUEST'):m.validate(self.csv('2026/10/22'),self.job())
    def test_html_error_not_download(self):
        with self.assertRaises(ValueError):m.validate(b'<html>blocked</html>',self.job())
    def test_empty_not_absence(self):
        with self.assertRaisesRegex(ValueError,'EMPTY_NOT_PROOF'):m.validate('交易日期,契約\n'.encode('cp950'),self.job())
    def test_archive_wrong_year(self):
        with self.assertRaises(ValueError):m.validate(self.archive(self.csv('2026/10/22')),self.job('annual'))
    def test_tick_content_date_must_match(self):
        with self.assertRaisesRegex(ValueError,'TICK_CONTENT_DATE'):m.validate(self.archive(b'20261022,TX,123\n'),self.job('tick','2026-10-21','2026-10-21'))
    def test_tick_crc_and_content_date(self):
        self.assertTrue(m.validate(self.archive(b'20261022,TX,123\n'),self.job('tick','2026-10-22','2026-10-22'))['zip_crc_verified'])
    def test_snapshot_never_claims_historical_date(self):
        ev=m.validate(b'[{"Date":"20261022"}]',self.job('snapshot'))
        self.assertEqual(ev['content_period'],{'min':'2026-10-22','max':'2026-10-22'})
        self.assertIn('NO_HISTORICAL_PARAMETERS',ev['period_semantics'])
    def test_clamp_retention_boundary(self):
        periods=list(m.months_desc(dt.date(2026,10,22),dt.date(2023,10,22)))
        self.assertEqual(periods[0],(dt.date(2026,10,1),dt.date(2026,10,22)))
        self.assertEqual(periods[-1],(dt.date(2023,10,22),dt.date(2023,10,31)))
    def test_javascript_action_overrides_placeholder_and_all_products(self):
        page=b'''<form action="dailyFXRate"><input name="queryStartDate"><input name="queryEndDate"><input name="firstDate" value="2023/10/22 00:00"><input name="lastDate" value="2026/10/22 00:00"><select name="commodityId"><option value="">ALL</option><option value="TX">TX</option></select></form><script>$('#uForm').attr('action', 'futContractsDateDown');</script>'''
        form=m.forms_from_page(page,'futContractsDateView')[0]
        self.assertEqual(form['action'],'futContractsDateDown');self.assertEqual(form['fields']['commodityId'],'')
        self.assertEqual(form['first'],'2023-10-22');self.assertTrue(form['boundary_confirmed'])
    def test_do_not_silently_select_one_product(self):
        page=b'<form action="someDown"><input name="queryStartDate"><input name="queryEndDate"><select name="product"><option value="TX">TX</option></select></form>'
        self.assertEqual(m.forms_from_page(page,'someView'),[])
    def test_official_html_unavailable_does_not_block_bootstrap(self):
        w=object.__new__(m.Worker);w.today=dt.date(2026,10,23)
        w.state={'receipts':{},'catalog':{},'tick_jobs':{}}
        w.evidence=lambda *args:None;w.save=lambda:None
        w.request=lambda *args,**kwargs: (_ for _ in ()).throw(TimeoutError('offline'))
        w.discover()
        self.assertEqual(len(w.state['api_paths']),135)
        self.assertEqual(len(w.state['tick_jobs']),262)
        self.assertTrue(all(j['end']<='2026-10-23' for j in w.state['tick_jobs'].values()))
        self.assertEqual(w.state['latest_trading_date'],'2026-10-22')
    def test_empty_and_unpublished_skip_once_and_continue(self):
        import urllib.error
        for failure,expected in [
            (m.OfficialEmpty('NO_ROWS'),'SKIPPED_SOURCE_EMPTY'),
            (urllib.error.HTTPError('https://www.taifex.com.tw/missing',404,'missing',{},None),'SKIPPED_NOT_PUBLISHED'),
            (TimeoutError('timeout'),'UNRESOLVED'),
            (ValueError('HTML_ERROR'),'UNRESOLVED')]:
            w=object.__new__(m.Worker);w.state={'receipts':{}};w.saved=0
            w.live=lambda:True;w.save=lambda:None
            def fail(*args):raise failure
            w.request=fail
            job={'key':'missing','url':'https://www.taifex.com.tw/missing','kind':'csv','start':'2000-01-01','end':'2000-01-31'}
            self.assertTrue(w.process(job))
            self.assertEqual(w.state['receipts']['missing']['status'],expected)
            if expected.startswith('SKIPPED'):
                self.assertTrue(w.process(job))
                self.assertEqual(w.state['receipts']['missing']['attempts'],1)
                self.assertFalse(w.state['receipts']['missing']['historical_absence_certified'])
    def test_batch_advances_past_skipped_source_data(self):
        w=object.__new__(m.Worker)
        w.state={'receipts':{'empty':{'status':'SKIPPED_SOURCE_EMPTY'},'gone':{'status':'SKIPPED_NOT_PUBLISHED'}}}
        called=[];w.process=lambda job:called.append(job['key']) or True
        w.batch([{'key':k,'url':m.SITE+'/download'} for k in ('empty','gone','older')],1)
        self.assertEqual(called,['older'])
    def test_resume_skips_success_and_exhausted_failure(self):
        w=object.__new__(m.Worker);w.state={'receipts':{'ok':{'status':'SAVED_BASIC_VERIFIED'},'bad':{'attempts':3,'status':'UNRESOLVED'}}}
        self.assertTrue(w.process({'key':'ok'}));self.assertTrue(w.process({'key':'bad'}))
    def test_official_dos_eof_is_not_a_data_row(self):
        self.assertEqual(m.validate(self.csv()+b'\x1a',self.job())['rows'],1)
        with self.assertRaisesRegex(ValueError,'CSV_ROW_DATE_MISSING'):
            m.validate(self.csv()+b'\x1a\n2000/1/5,TX\n',self.job())
    def test_trade_date_cannot_fall_back_to_expiry(self):
        raw='交易日期,到期日期\ninvalid,2000/01/04\n'.encode('cp950')
        with self.assertRaisesRegex(ValueError,'CSV_ROW_DATE_MISSING'):m.validate(raw,self.job())
    def test_compact_roc_date_and_pre_2000_date(self):
        self.assertEqual(m.parse_date('1151016'),dt.date(2026,10,16))
        self.assertEqual(m.parse_date('19991231'),dt.date(1999,12,31))
    def test_official_no_data_and_swagger_are_distinct(self):
        raw='<html><script>alert("查無資料");</script></html>'.encode()
        with self.assertRaises(m.OfficialEmpty):m.validate(raw,self.job())
        with self.assertRaisesRegex(ValueError,'API_ROUTE_RETURNS_SWAGGER_HTML'):
            m.validate(b'\xef\xbb\xbf<html><title>Swagger UI</title></html>',self.job('snapshot'))
        with self.assertRaises(ValueError):m.validate(b'<html>Access denied</html>',self.job())
    def test_revision_migration_preserves_success_and_is_once_only(self):
        ok={'status':'SAVED_BASIC_VERIFIED','sha256':'keep','attempts':1}
        state={'receipts':{'ok':ok.copy(),'bad':{'status':'UNRESOLVED','error':'CSV_ROW_DATE_MISSING','attempts':3}}}
        m.migrate_repairs(state)
        self.assertEqual(state['receipts']['ok'],ok)
        self.assertEqual(state['receipts']['bad']['attempts'],0)
        state['receipts']['bad']['attempts']=3;m.migrate_repairs(state)
        self.assertEqual(state['receipts']['bad']['attempts'],3)
    def test_cached_raw_recovery_requires_hash_and_no_source_redownload(self):
        raw=self.csv()+b'\x1a'
        job=dict(self.job(),key='annual-test',url=m.SITE+'/test')
        w=object.__new__(m.Worker);w.state={'receipts':{job['key']:{'status':'UNRESOLVED','attempts':3,'error':'CSV_ROW_DATE_MISSING','response_sha256':m.digest(raw)}}}
        m.migrate_repairs(w.state)
        w.live=lambda:True;w.save=lambda:None;w.saved=0
        w.d=type('Drive',(),{'read':lambda *args:raw})();w.ctrl='test'
        w.request=lambda *args:(_ for _ in ()).throw(AssertionError('must not redownload'))
        def persist(job,content,entry,ev):
            self.assertEqual(content,raw);self.assertEqual(ev['rows'],1)
            entry.update(status='SAVED_BASIC_VERIFIED',sha256=m.digest(content))
        w.persist_raw=persist
        self.assertTrue(w.process(job));self.assertTrue(w.state['receipts'][job['key']]['recovered_from_saved_evidence'])
    def test_cooldowns_do_not_block_other_sources(self):
        import time
        w=object.__new__(m.Worker);w.state={'receipts':{},'source_backoff':{'www.taifex.com.tw':time.time()+60}}
        self.assertFalse(w.eligible({'key':'x','url':m.SITE+'/test'}))
        self.assertTrue(w.eligible({'key':'y','url':'https://openapi.taifex.com.tw/v1/DailyMarketReportFut'}))
if __name__=='__main__':unittest.main()

class NativeLayoutRepairTests(unittest.TestCase):
    def job(self,start='2022-08-01',end='2022-08-31'):
        return dict(kind='csv',start=start,end=end)
    def test_large_trader_tail_notes_and_no_data_after_footer(self):
        raw='日期,商品(契約),商品名稱(契約名稱),到期月份(週別),交易人類別,前五大交易人買方\n2022/08/01,TX,台指期貨,202208,0,1\n月份類別格式: 999999 為所有契約合計。\n交易人類別格式： 0 為前五大交易人\n-表當日收盤後無週到期期貨契約。\n'.encode()
        self.assertEqual(m.validate(raw,self.job())['rows'],1)
        with self.assertRaisesRegex(ValueError,'DATA_AFTER_FOOTNOTE'):
            m.validate(raw+b'2022/08/02,TX,TX,202208,0,1\n',self.job())
    def test_unknown_tail_and_ordinary_date_error_are_rejected(self):
        raw='日期,商品(契約),商品名稱(契約名稱),到期月份(週別),交易人類別\n2022/08/01,TX,TX,202208,0\nunknown\n'.encode()
        with self.assertRaisesRegex(ValueError,'CSV_ROW_DATE_MISSING'):m.validate(raw,self.job())
    def block(self):
        return '組合式序號,日期,契約數,交易時段\n組合式序號,子序號,契約,到期月份(週別),履約價格,買/賣權,成交價格,成交數量\nC1,2022/08/01,1,一般,\nC1,1,TX,202208,-,-,17225,380,\n'
    def test_block_trade_group_date_is_inherited_by_matched_legs(self):
        ev=m.validate(self.block().encode(),self.job());self.assertEqual(ev['rows'],1);self.assertEqual(ev['groups'],1)
    def test_block_trade_missing_and_unmatched_legs_rejected(self):
        for raw in [self.block().replace('C1,1,TX','C2,1,TX'),self.block().replace(',1,一般',',2,一般')]:
            with self.assertRaises(ValueError):m.validate(raw.encode(),self.job())
    def delta(self):
        return ',,,公布日期時間,2026/10/22 04:35:03 PM\n商品, 買賣權, 到期月份(週別), 履約價格, Delta值, 契約到期日\nTXO,買權,202706,250,0.9,20270616\n'
    def test_delta_publication_timestamp_not_future_expiry(self):
        ev=m.validate(self.delta().encode(),self.job('2026-10-22','2026-10-22'))
        self.assertEqual(ev['rows'],1);self.assertEqual(ev['content_period']['max'],'2026-10-22')
        with self.assertRaisesRegex(ValueError,'PUBLICATION_DATE_OUTSIDE'):
            m.validate(self.delta().encode(),self.job('2026-10-21','2026-10-21'))
    def test_delta_invalid_row_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError,'DELTA_ROW_INVALID'):
            m.validate(self.delta().replace('20270616','invalid').encode(),self.job('2026-10-22','2026-10-22'))
    def test_release_only_resets_fixed_parser_failures(self):
        state=dict(repair_revision='TAIFEX_NATIVE_FORMAT_REPAIR_V2_20261024',receipts={
          'fixed':dict(status='UNRESOLVED',attempts=3,error='ValueError:CSV_ROW_DATE_MISSING'),
          'transport':dict(status='UNRESOLVED',attempts=3,error='HTTPError:HTTP Error 520'),
          'saved':dict(status='SAVED_BASIC_VERIFIED',sha256='preserved')})
        m.migrate_repairs(state)
        self.assertEqual(state['receipts']['fixed']['attempts'],0)
        self.assertEqual(state['receipts']['transport']['attempts'],3)
        self.assertEqual(state['receipts']['saved'],dict(status='SAVED_BASIC_VERIFIED',sha256='preserved'))

    def test_options_large_trader_notes_use_distinct_header(self):
        raw='日期,商品(契約),商品名稱(契約名稱),買賣權,到期月份(週別),交易人類別\n2022/08/01,TXO,台指選擇權,買權,202208,0\n備註一：666666為所有週到期契約合計；yyyymm為近月契約。\n備註二：交易人類別格式：0 為部位排序前五大交易人\n備註三："-"表當日收盤後無週到期選擇權契約。\n'.encode()
        self.assertEqual(m.validate(raw,self.job())['rows'],1)
