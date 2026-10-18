import unittest
from scripts.storage_verifier import MemoryStorage, persist_verified

class TestStorageVerifier(unittest.TestCase):
    def test_exact_bytes_readback_receipt(self):
        s=MemoryStorage()
        r=persist_verified(s,"2024/TWSE/2024-01/sample.json",b'{"date":"20240102"}')
        self.assertEqual(r["bytes"],19)
        self.assertEqual(len(r["sha256"]),64)
        self.assertTrue(r["readback_verified"])
    def test_corrupted_readback_rejected(self):
        class Corrupt(MemoryStorage):
            def read_bytes(self,path): return b"corrupted"
        with self.assertRaisesRegex(ValueError,"MISMATCH"):
            persist_verified(Corrupt(),"test",b"correct")
    def test_missing_readback_rejected(self):
        class Missing(MemoryStorage):
            def read_bytes(self,path): raise FileNotFoundError(path)
        with self.assertRaises(FileNotFoundError):
            persist_verified(Missing(),"test",b"hello")
    def test_empty_bytes_not_assumed_missing(self):
        r=persist_verified(MemoryStorage(),"test",b"")
        self.assertEqual(r["bytes"],0)

if __name__=="__main__":
    unittest.main()
