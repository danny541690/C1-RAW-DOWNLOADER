import datetime as dt
import io
import unittest
import zipfile
from unittest.mock import Mock
from scripts import v093_ndc_independent as n

def fixture():
    return [n.table('景氣指標', [
        ['DATE','領先指標綜合指數','新指標'],
        ['2000-01','1',None],['2000-02','2','3']])]

class NdcTests(unittest.TestCase):
    def test_dates(self):
        for value in ['2000-01','2000/1/1','2000年1月','200001','08901']:
            with self.subTest(value=value):self.assertEqual(n.month(value),'2000-01')
        self.assertIsNone(n.month('2000-13'))
        self.assertIsNone(n.month('DATE'))
        self.assertEqual(n.month('36526',excel=True),'2000-01')

    def test_month_range(self):
        months=n.months_desc('2026-10')
        self.assertEqual((months[0],months[-1],len(months)),('2026-10','2000-01',322))
        self.assertEqual(n.months_desc('2000-01'),['2000-01'])

    def test_actual_series_starts(self):
        a=n.availability(fixture())
        self.assertEqual(a['series'][1]['first'],'2000-02')
        self.assertFalse(a['pit_verified'])

    def test_missing_does_not_become_zero(self):
        p=n.month_payload(fixture(),'2000-01',{'sha256':'test'})
        self.assertEqual(p['gaps'][0]['status'],'BEFORE_SERIES_START')
        self.assertIsNone(p['tables'][0]['cells'][1]['native_value'])
        self.assertFalse(p['coverage_certified'])
        self.assertFalse(p['pit_verified'])

    def test_duplicate_month_rejected(self):
        with self.assertRaisesRegex(ValueError,'DUPLICATE_MONTH'):
            n.table('x',[['DATE','x'],['2000-01',1],['2000-01',2]])

    def test_absent_month_not_invented(self):
        with self.assertRaisesRegex(ValueError,'MONTH_NOT_PRESENT'):
            n.month_payload(fixture(),'2000-03',{})

    def test_csv_native_precision(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('manifest.csv','filename,url\nndc.csv,official\n')
            z.writestr('schema-ndc.csv','name,type\nDATE,string\n')
            z.writestr('ndc.csv','DATE,領先指標綜合指數\n2000-01,123.45678901234567\n')
        self.assertEqual(n.parse_bundle(b.getvalue())[0]['rows']['2000-01'][1],'123.45678901234567')

    def test_wrong_schema_and_html_rejected(self):
        with self.assertRaises(zipfile.BadZipFile):n.parse_bundle(b'<html>blocked</html>')
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('x.csv','DATE,unrelated\n2000-01,1\n')
        with self.assertRaisesRegex(ValueError,'SCHEMA'):n.parse_bundle(b.getvalue())

    def test_excel_sparse_cells_and_date(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="指標" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>DATE</t></is></c><c r="B1" t="inlineStr"><is><t>領先指標綜合指數</t></is></c><c r="C1" t="inlineStr"><is><t>其他</t></is></c></row><row><c r="A2"><v>36526</v></c><c r="B2"><v>10.123456789</v></c></row></sheetData></worksheet>')
        self.assertEqual(n.parse_bundle(b.getvalue())[0]['rows']['2000-01'],['36526','10.123456789',None])

    def test_verified_month_not_rewritten(self):
        w=object.__new__(n.Worker)
        w.today=dt.date(2000,1,31)
        w.state={'receipts':{'2000-01':{'status':'SAVED_RAW_ROWS_READBACK_VERIFIED'}},'availability':{'latest':'2000-01'}}
        w.d=Mock();w.discover=Mock(return_value=(fixture(),{}));w.live=Mock(return_value=True);w.save=Mock()
        w.run()
        w.d.put.assert_not_called()
        self.assertEqual(w.state['status'],'BACKFILL_RANGE_SAVED_WITH_OPEN_ITEMS')

    def test_source_gap_skips_to_older_month(self):
        w=object.__new__(n.Worker)
        w.today=dt.date(2000,3,31)
        w.state={'receipts':{'2000-01':{'status':'SAVED_RAW_ROWS_READBACK_VERIFIED'}},'availability':{'latest':'2000-03'}}
        t=n.table('景氣指標',[['DATE','領先指標'],['2000-01','1'],['2000-03','3']])
        w.discover=Mock(return_value=([t],{'sha256':'a'}));w.live=Mock(return_value=True);w.save=Mock()
        w.saved=0;w.d=Mock();w.d.find.return_value={'id':'new'}
        w.run()
        self.assertEqual(w.state['receipts']['2000-02']['status'],'MONTH_NOT_PRESENT_IN_VERIFIED_SOURCE')
        self.assertEqual(w.state['receipts']['2000-03']['status'],'SAVED_RAW_ROWS_READBACK_VERIFIED')
        self.assertEqual(w.d.put.call_count,1)

if __name__=='__main__':unittest.main()
