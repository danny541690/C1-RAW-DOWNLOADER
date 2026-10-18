import unittest
from scripts.drive_storage import verify_drive_unit
class TestDriveContract(unittest.TestCase):
    def test_receipt_and_readback(self):
        class Fake:
            def __init__(self): self.data={}
            def write_bytes(self,n,d): self.data[n]=d
            def read_bytes(self,n): return self.data[n]
        r=verify_drive_unit(Fake(),"2024-01-unit.json",b"official raw bytes")
        self.assertTrue(r["readback_verified"])
    def test_corruption_is_blocked(self):
        class Corrupt:
            def write_bytes(self,n,d): pass
            def read_bytes(self,n): return b"corrupt"
        with self.assertRaises(ValueError):
            verify_drive_unit(Corrupt(),"2024-01-unit.json",b"original")
