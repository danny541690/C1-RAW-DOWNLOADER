import unittest,urllib.error
from scripts.v093_tdcc_independent import classify_error,SourceEmpty
class ErrorPhaseTests(unittest.TestCase):
 def test_drive_403_is_not_source_backoff(self):
  e=urllib.error.HTTPError('https://googleapis.com',403,'quota',{},None)
  self.assertEqual(classify_error(e,'PERSIST_AND_REMOTE_READBACK'),'STORAGE_OR_READBACK_ERROR')
  self.assertEqual(classify_error(e,'POST_HISTORY_QUERY'),'SOURCE_BACKOFF')
 def test_mismatch_and_format(self):
  self.assertEqual(classify_error(ValueError('existing remote file SHA mismatch'),'PERSIST_AND_REMOTE_READBACK'),'READBACK_MISMATCH')
  self.assertEqual(classify_error(ValueError('HISTORY_RESULT_CODE_NOT_CONFIRMED'),'POST_HISTORY_QUERY'),'FORMAT_OR_VALIDATION_ERROR')
 def test_empty_is_not_transport(self):
  self.assertEqual(classify_error(SourceEmpty('empty'),'POST_HISTORY_QUERY'),'SOURCE_EMPTY_UNCONFIRMED')
