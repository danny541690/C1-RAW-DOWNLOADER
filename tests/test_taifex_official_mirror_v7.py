import datetime as dt
import unittest
from unittest.mock import Mock
from scripts import v093_taifex_independent as m

class OfficialMirrorTests(unittest.TestCase):
    def job(self,route='AcceptableCollateralGovernmentBonds',day='2026-10-25'):
        return dict(key='API|'+day+'|/'+route,kind='snapshot',start=day,end=day,
                    url='https://openapi.taifex.com.tw/v1/'+route)
    def test_official_catalog_mapping_and_current_capture_only(self):
        j=self.job();mirror=m.official_csv_mirror(j,dt.date(2026,10,25))
        self.assertEqual(mirror['url'],'https://www.taifex.com.tw/data_gov/taifex_open_data.asp?data_name=AcceptableCollateralGovernmentBonds')
        self.assertFalse(mirror['historical_reconstruction'])
        for other in [self.job(day='2026-10-24'),self.job('Unknown'),dict(j,fields={'date':'20261025'}),dict(j,url=j['url']+'?date=20261025'),dict(j,url=j['url'].replace('openapi.taifex.com.tw','evil.test'))]:
            self.assertIsNone(m.official_csv_mirror(other,dt.date(2026,10,25)))
    def test_actual_dates_and_exact_schema(self):
        raw='日期,公債代號,公債名稱,交易幣別\r\n20261023,A00102,100央債甲2,TWD\r\n'.encode()
        ev=m.validate(raw,self.job());self.assertEqual(ev['content_period']['max'],'2026-10-23');self.assertEqual(ev['rows'],1)
        for bad in [raw.replace(b'20261023',b'20261026'),raw.replace('公債代號'.encode(),'股票代號'.encode()),raw+b'20261023,A\n',b'<html><title>Swagger UI</title></html>']:
            with self.assertRaises(ValueError):m.validate(bad,self.job())
    def test_process_records_actual_mirror_and_preserves_native_bytes(self):
        runner=object.__new__(m.Worker)
        runner.today=dt.date(2026,10,25);runner.state={'receipts':{}};runner.eligible=Mock(return_value=True);runner.live=Mock(return_value=True);runner.save=Mock()
        raw='商品別,結算保證金,維持保證金,原始保證金,日期\r\n臺股期貨,519000,538000,701000,20261022\r\n'.encode()
        runner.request=Mock(return_value=raw);runner.persist_raw=Mock()
        j=self.job('IndexFuturesAndOptionsMargining');runner.process(j)
        self.assertIn('data_gov/taifex_open_data.asp?',runner.request.call_args.args[0])
        self.assertEqual(runner.persist_raw.call_args.args[1],raw)
        self.assertEqual(runner.state['receipts'][j['key']]['request'],j)
        self.assertTrue(runner.state['receipts'][j['key']]['source_request']['latest_only'])
    def test_verified_receipt_never_refetched(self):
        runner=object.__new__(m.Worker);j=self.job();runner.state={'receipts':{j['key']:{'status':'SAVED_BASIC_VERIFIED'}}};runner.request=Mock()
        self.assertTrue(runner.process(j));runner.request.assert_not_called()

    def test_mirror_uses_separate_route_cooldown_but_respects_real_host(self):
        import time
        runner=object.__new__(m.Worker);runner.today=dt.date(2026,10,25)
        j=self.job();runner.state={'receipts':{},'route_backoff':{j['url']:time.time()+86400}}
        self.assertTrue(runner.eligible(j))
        runner.state['source_backoff']={'www.taifex.com.tw':time.time()+900}
        self.assertFalse(runner.eligible(j))
