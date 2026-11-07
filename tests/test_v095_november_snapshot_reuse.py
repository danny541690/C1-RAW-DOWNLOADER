"""Live downloader snapshot fallback: fail-closed provenance and filename hash checks."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("nov",Path(__file__).resolve().parents[1]/"scripts/v095_ultimate_r1_november_official.py")
nov=importlib.util.module_from_spec(spec);spec.loader.exec_module(nov)

class FakeFiles:
    def __init__(self,raw):self.raw=raw
    def get_media(self,fileId):return self
    def execute(self):return self.raw
class FakeDrive:
    def __init__(self,raw):self._files=FakeFiles(raw)
    def files(self):return self._files
class SnapshotReuse(unittest.TestCase):
    def setUp(self):
        self.day="2026-11-03";self.source="TWSE";self.raw=b'official-example'
        self.d=FakeDrive(self.raw)
        self.prefix="V095_202611_TWSE_"+self.day+"_"
        self.month={"name":"2026-11","id":"month","mimeType":"application/vnd.google-apps.folder"}
        self.obj={"name":self.prefix+nov.sha(self.raw)[:20]+".json","id":"blob","mimeType":"application/json"}
    def check(self,items):
        def listing(d,parent):
            return [self.month] if parent==nov.SOURCES["TWSE"]["bronze"] else items
        with patch.object(nov,"ls",side_effect=listing),patch.object(nov,"validate",return_value={"rows":1234}),patch.object(nov,"parse",return_value=([0]*400,0)):
            return nov.existing_immutable_official_snapshot(self.d,self.source,self.day,{"category":"prices_indices"})
    def test_hash_verified_snapshot_reused(self):
        r=self.check([self.obj]);self.assertEqual(r[-1],"VERIFIED_IMMUTABLE_SNAPSHOT_NOT_FRESH_HTTP")
    def test_absent_snapshot_requires_live_http(self):
        self.assertIsNone(self.check([]))
    def test_ambiguous_snapshot_never_reused(self):
        self.assertIsNone(self.check([self.obj,self.obj]))
    def test_corrupted_hash_refused(self):
        with self.assertRaisesRegex(ValueError,"SHA_NAME_MISMATCH"):
            self.check([{**self.obj,"name":self.prefix+"f"*20+".json"}])
if __name__=="__main__":unittest.main()
