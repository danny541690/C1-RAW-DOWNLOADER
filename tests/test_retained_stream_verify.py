import hashlib,unittest
from scripts.v093_retained_stream_verify import HashSink
class StreamTests(unittest.TestCase):
 def test_many_chunks_hash_exact_bytes_without_whole_file_buffer(self):
  sink=HashSink(20);sink.write(b'abc');sink.write(b'def')
  self.assertEqual(sink.hash.hexdigest(),hashlib.sha256(b'abcdef').hexdigest());self.assertEqual(sink.bytes,6)
 def test_overflow_does_not_include_partial_rejected_chunk(self):
  sink=HashSink(3);sink.write(b'ab')
  with self.assertRaises(ValueError):sink.write(b'cd')
  self.assertEqual(sink.bytes,2)
