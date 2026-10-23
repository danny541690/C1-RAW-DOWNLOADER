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
        self.assertEqual(len(w.state['tick_jobs']),270)
        self.assertEqual(w.state['latest_trading_date'],'2026-10-22')
    def test_resume_skips_success_and_exhausted_failure(self):
        w=object.__new__(m.Worker);w.state={'receipts':{'ok':{'status':'SAVED_BASIC_VERIFIED'},'bad':{'attempts':3,'status':'UNRESOLVED'}}}
        self.assertTrue(w.process({'key':'ok'}));self.assertTrue(w.process({'key':'bad'}))
if __name__=='__main__':unittest.main()
