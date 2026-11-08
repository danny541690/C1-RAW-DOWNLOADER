#!/usr/bin/env python3
import hashlib,io,json,unittest,zipfile
from scripts.v095_legacy_tdcc_mirror_adapter import records,validate_capture_zip
from scripts.v095_legacy_taifex_csv_adapter import eligible
class NativeSourceAdapterTest(unittest.TestCase):
 def setUp(self):
  self.payload=("資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%\r\n"
     "20260430,00400A,1,0,0,0.00\r\n"
     "20260430,YR43  ,17,5,100,0.20\r\n").encode("utf-8-sig")
 def archive(self,override=None):
  name="01_RAW/2026/TDCC_ARCHIVE/2026-04/2026-04-30.csv"
  rec={"source":"TDCC_ARCHIVE","dataset":"holding_distribution","state":"CAPTURED_ARCHIVE_STRUCTURE",
    "url":"https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots/2026/2026-04-30.csv",
    "file":name,"period":"2026-04-30","bytes":len(self.payload),
    "sha256":hashlib.sha256(self.payload).hexdigest(),"rows":2}
  rec.update(override or {})
  b=io.BytesIO()
  with zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED) as z:
   z.writestr(name,self.payload)
   z.writestr("capture_receipts.json",json.dumps([rec]))
  b.seek(0);return zipfile.ZipFile(b)
 def test_native_tdcc_alpha_codes_and_receipt_sha(self):
  with self.archive() as z:
   result=validate_capture_zip(z,"2026-04")
   self.assertEqual(result[0]["rows"],2)
  data=records(self.payload,"2026-04")
  self.assertEqual(data[0]["stock_id"],"00400A")
  self.assertEqual(data[1]["stock_id"],"YR43")
  self.assertFalse(data[0]["pit_verified"])
  self.assertFalse(data[0]["official_source_verified"])
 def test_bad_sha_fails_closed(self):
  with self.archive({"sha256":"0"*64}) as z:
   with self.assertRaisesRegex(ValueError,"SHA"):validate_capture_zip(z,"2026-04")
 def test_wrong_month_fails_closed(self):
  with self.archive() as z:
   with self.assertRaisesRegex(ValueError,"DATE"):validate_capture_zip(z,"2026-05")
 def test_taifex_only_supported_daily_history_not_tick(self):
  self.assertTrue(eligible("HISTORY_largeTraderFutDown_2026-09_"+"a"*64+".csv","2026-09"))
  self.assertFalse(eligible("TICK_delta_chinese_20260908_csv_"+"a"*64+".csv","2026-09"))
  self.assertFalse(eligible("HISTORY_largeTraderFutDown_2026-10_"+"a"*64+".csv","2026-09"))
  self.assertFalse(eligible("HISTORY_unknown_2026-09_"+"a"*64+".csv","2026-09"))
if __name__=="__main__":unittest.main()
