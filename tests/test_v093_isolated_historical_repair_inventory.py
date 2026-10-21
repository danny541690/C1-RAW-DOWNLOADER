import io,json,zipfile,unittest
from unittest.mock import patch
from scripts.v093_isolated_historical_repair_inventory import inspect_zip_bytes,inspect_month,blocked_stages

class HistoricalInventoryTests(unittest.TestCase):
    def test_zip_crc_manifest(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            z.writestr('a.raw','{"x":1}')
            z.writestr('manifest.json',json.dumps({'units':[{'id':1}]}))
        r=inspect_zip_bytes(buf.getvalue())
        self.assertEqual(r['receipt_units'],1)
        self.assertFalse(r['certified'])
        self.assertFalse(r['pit_verified'])
    def test_invalid_zip(self):
        with self.assertRaises(zipfile.BadZipFile):
            inspect_zip_bytes(b'not a zip')
    def test_missing_archives_queue_is_not_certified(self):
        class Drive:pass
        def ls(d,parent):
            if parent=='ROOT':return [{'id':'YEAR','name':'2000','mimeType':'application/vnd.google-apps.folder'}]
            if parent=='YEAR':return [{'id':x,'name':x,'mimeType':'application/vnd.google-apps.folder'} for x in ('TWSE','TPEx','MOPS','FinMind')]
            if parent in ('TWSE','TPEx','MOPS','FinMind'):
                return [{'id':parent+'M','name':'2000-01','mimeType':'application/vnd.google-apps.folder'}]
            return []
        with patch('scripts.v093_isolated_historical_repair_inventory.ROOT','ROOT'),patch('scripts.v093_isolated_historical_repair_inventory.ls',side_effect=ls):
            r=inspect_month(Drive(),'2000-01')
        self.assertEqual(len(r['repair_queue']),4)
        self.assertFalse(r['certified'])
        self.assertTrue(all(x['action']=='INSPECT_OTHER_FORMATS_THEN_BACKFILL' for x in r['repair_queue']))
        self.assertEqual(set(blocked_stages(r)),{'PRICE','FINANCIAL','CHIP'})
if __name__=='__main__':unittest.main()
