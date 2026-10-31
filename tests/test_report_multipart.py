import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts.v093_acceptance_publish import collect,encode,DriveArchive
from scripts.v093_source_state_pages import pack
from test_native_repair import FakeDrive

class MultipartReportTests(unittest.TestCase):
 def test_large_unicode_report_is_lossless_and_git_pages_are_bounded(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp);raw=('中文測試😀\\"\n'*120000).encode();(path/'report.json').write_bytes(raw);files=collect(path)
   manifest=json.loads(files['__report_parts_manifest__.json']['text'])['originals']['report.json']
   restored=''.join(files[key]['text'] for key in manifest['parts']).encode()
   self.assertEqual(restored,raw);self.assertEqual(manifest['sha256'],hashlib.sha256(raw).hexdigest())
   self.assertTrue(all(len(encode(v))<=600000 for v in files.values()))
   pack(dict(source='TWSE',tasks=files))
 def test_small_reports_keep_existing_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp);(path/'a.json').write_text('{}');self.assertEqual(set(collect(path)),{'a.json'})
 def test_total_limit_is_kept_and_invalid_utf8_is_not_dropped(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp);(path/'bad.log').write_bytes(b'\xff')
   with self.assertRaises(UnicodeDecodeError):collect(path)
   (path/'bad.log').write_bytes(b'x'*10000001)
   with self.assertRaisesRegex(ValueError,'TOTAL_SIZE'):collect(path)
 def test_drive_parts_reconstruct_exact_record_and_retry_reuses_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp);(path/'report.json').write_text('資料與數據"\n'*130000);record=dict(schema='test',metadata={'job':'large'},files=collect(path));raw=encode(record);drive=FakeDrive()
   with patch('scripts.annual_actual_firstpass.Drive',return_value=drive),patch('scripts.annual_actual_firstpass.service'):
    receipt=DriveArchive('test').save(raw,hashlib.sha256(raw).hexdigest());count=len(drive.data);again=DriveArchive('test').save(raw,hashlib.sha256(raw).hexdigest())
   self.assertGreater(receipt['parts'],1);self.assertTrue(receipt['readback_verified']);self.assertEqual(receipt,again);self.assertEqual(count,len(drive.data))
   index=json.loads(drive.data[receipt['file_id']]);self.assertEqual(index['record_sha256'],hashlib.sha256(raw).hexdigest())
   self.assertTrue(all(len(drive.data[p['file_id']])<=650000 for p in index['parts']))
 def test_changed_drive_readback_is_rejected(self):
  drive=FakeDrive();original=drive.get_media
  drive.get_media=lambda fileId:original(fileId)+b'changed'
  with patch('scripts.annual_actual_firstpass.Drive',return_value=drive),patch('scripts.annual_actual_firstpass.service'):
   with self.assertRaisesRegex(ValueError,'SHA_MISMATCH'):DriveArchive('bad').save(b'{}',hashlib.sha256(b'{}').hexdigest())

if __name__=='__main__':unittest.main()
