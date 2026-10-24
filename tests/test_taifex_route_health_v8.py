import datetime as dt
import time
import unittest
from unittest.mock import Mock, patch
from scripts import v093_taifex_independent as m

class RouteHealthTests(unittest.TestCase):
    def job(self,route='DailyOptionsDelta',day='2026-10-25'):
        return dict(key='API|'+day+'|/'+route,kind='snapshot',start=day,end=day,url='https://openapi.taifex.com.tw/v1/'+route)
    def test_expiry_never_becomes_source_date(self):
        raw='契約,買賣權,到期月份(週別),履約價格,Delta值,契約到期日\nTXO,買權,202611,24000,0.5,20261118\n'.encode()
        ev=m.validate(raw,self.job());self.assertEqual(ev['rows'],1);self.assertIsNone(ev['content_period']);self.assertFalse(ev['publication_date_verified'])
        for bad in [raw.replace(b'0.5',b'NaN'),raw.replace(b'0.5',b'2.0'),raw.replace(b'20261118',b'20261399'),raw+raw.split(b'\n')[1]+b'\n']:
            with self.assertRaises(ValueError):m.validate(bad,self.job())
    def test_date_bearing_mirror_routes_remain_strict(self):
        for route in ['SSFRefferedOpeningPrice','SSFRefferedOpeningPriceAh','productsExemptedAH']:
            self.assertIsNotNone(m.official_csv_mirror(self.job(route),dt.date(2026,10,25)))
            self.assertIsNone(m.official_csv_mirror(self.job(route,'2026-10-24'),dt.date(2026,10,25)))
    def test_later_capture_does_not_close_historical_failure(self):
        old=dict(status='UNRESOLVED',request=self.job(day='2026-10-23'),error='ValueError:API_ROUTE_RETURNS_SWAGGER_HTML')
        new=dict(status='SAVED_BASIC_VERIFIED',request=self.job(),remote_readback_hash_verified=True,file_id='file',sha256='abc')
        receipts={'old':old,'new':new};h=m.snapshot_route_health(receipts)
        self.assertEqual(h['historical_swagger_failure_units'],1);self.assertEqual(h['swagger_failure_units_with_later_verified_capture'],1);self.assertEqual(h['swagger_routes_without_any_verified_capture_count'],0)
        self.assertEqual(old['status'],'UNRESOLVED');self.assertFalse(h['later_verified_captures']['old']['original_capture_recreated'])
        new['remote_readback_hash_verified']=False
        self.assertEqual(m.snapshot_route_health(receipts)['swagger_routes_without_any_verified_capture_count'],1)
    def test_due_transport_jobs_respect_partition_cooldown_and_integrity(self):
        w=object.__new__(m.Worker);w.today=dt.date(2026,10,25);w.direction='ASC';w.state={'receipts':{}}
        for key,year in [('old','2000'),('recent','2015')]:
            j=dict(key=key,kind='csv',start=year+'-02-01',end=year+'-02-28',url=m.SITE+'/cht/3/bargainOrderDown')
            w.state['receipts'][key]=dict(status='UNRESOLVED',error='HTTPError:HTTP Error 520',attempts=1,request=j)
        self.assertEqual([j['key'] for j in w.retry_due_history()],['old'])
        w.state['receipts']['old']['integrity_hold']=True;self.assertEqual(w.retry_due_history(),[])
        w.state['receipts']['old']['integrity_hold']=False;w.state['receipts']['old']['retry_after_epoch']=time.time()+60;self.assertEqual(w.retry_due_history(),[])
    def test_transport_retry_delay_and_real_alias(self):
        w=object.__new__(m.Worker);w.today=dt.date(2026,10,25);w.direction='DESC';w.state={'receipts':{}};w.live=Mock(return_value=True);w.save=Mock();w.evidence=Mock()
        j=dict(key='HISTORY|bargainOrderDown|2015-12',kind='csv',start='2015-12-01',end='2015-12-31',url=m.SITE+'/cht/3/bargainOrderDown',fields={'queryStartDate':'2015/12/01','queryEndDate':'2015/12/31'})
        w.request=Mock(side_effect=TimeoutError('network read timeout'));before=time.time();w.process(j)
        e=w.state['receipts'][j['key']];self.assertLess(e['retry_after_epoch']-before,65)
        e['retry_after_epoch']=0;w.process(j);self.assertTrue(w.request.call_args.args[0].endswith('/dlBargainOrderDown'))

    def test_ccp_exact_header_date_and_official_mapping(self):
        raw='結算會員中文名稱,結算會員類別,日期\n甲銀行,一般,20261023\n'.encode()
        job=self.job('CCP_CMLists');ev=m.validate(raw,job)
        self.assertEqual(ev['rows'],1);self.assertEqual(ev['content_period']['max'],'2026-10-23')
        self.assertIn('data_name=CCP_CMLists',m.official_csv_mirror(job,dt.date(2026,10,25))['url'])
        with self.assertRaises(ValueError):m.validate(raw.replace(b'20261023',b'20261026'),job)

    def test_short_source_cooldown_waits_without_bypassing_or_long_sleep(self):
        w=object.__new__(m.Worker);w.live=Mock(return_value=True);w.state={'source_backoff':{'www.taifex.com.tw':120}}
        with patch.object(m.time,'time',return_value=100),patch.object(m.time,'sleep') as sleep:
            self.assertTrue(w.wait_short_source_cooldown());sleep.assert_called_once_with(5)
            self.assertEqual(w.state['source_backoff']['www.taifex.com.tw'],120)
            w.state['source_backoff']['www.taifex.com.tw']=1000
            self.assertFalse(w.wait_short_source_cooldown())
            w.state['source_backoff']['www.taifex.com.tw']=90
            self.assertFalse(w.wait_short_source_cooldown())
