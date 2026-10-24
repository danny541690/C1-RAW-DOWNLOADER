import unittest
from scripts import v093_taifex_independent as m

class APINativeTests(unittest.TestCase):
    def job(self,route='DailyForeignExchangeRates'):
        return dict(kind='snapshot',start='2026-10-25',end='2026-10-25',url='https://openapi.taifex.com.tw/v1/'+route)
    def raw(self):
        return ('\ufeff'+','.join(m.API_CSV_SCHEMAS['DailyForeignExchangeRates'])+'\r\n20261022,'+','.join(['1']*10)+'\r\n').encode()
    def test_csv_preserves_actual_source_date_and_native_format(self):
        ev=m.validate(self.raw(),self.job());self.assertEqual(ev['native_format'],'csv');self.assertEqual(ev['content_period']['max'],'2026-10-22');self.assertFalse(ev['numeric_verified'])
    def test_unknown_route_or_other_host_cannot_use_csv_fallback(self):
        for job in [self.job('Unknown'),dict(self.job(),url='https://evil.test/v1/DailyForeignExchangeRates')]:
            with self.assertRaisesRegex(ValueError,'UNRECOGNIZED'):m.validate(self.raw(),job)
    def test_html_and_swagger_still_rejected(self):
        for raw in [b'<html><title>Swagger UI</title></html>',b'<html>blocked</html>']:
            with self.assertRaises(ValueError):m.validate(raw,self.job())
    def test_bad_schema_width_or_future_date_rejected(self):
        for raw in [self.raw().replace('美元'.encode(),'美元X'.encode(),1),self.raw()+b'20261022,1\n',self.raw().replace(b'20261022',b'20261026')]:
            with self.assertRaises(ValueError):m.validate(raw,self.job())
    def test_json_still_supported_and_unmodified(self):
        ev=m.validate(b'[{"Date":"20261022"}]',self.job());self.assertEqual(ev['native_format'],'json');self.assertEqual(ev['rows'],1)
