import tempfile
import unittest
from pathlib import Path
from scripts.v093_partitioned_acceptance_publish import stage, LIMIT


class PartitionedReportTests(unittest.TestCase):
    def test_lossless_large_utf8_and_multiple_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "source"
            source.mkdir()
            raw = ("中文繁體資料\\n" * 650000).encode("utf-8")
            (source / "big.json").write_bytes(raw)
            (source / "small.md").write_text("重要證據", encoding="utf-8")
            folders, manifest = stage(source, root / "parts")
            self.assertGreater(len(folders), 1)
            self.assertEqual(manifest["files"]["big.json"]["bytes"], len(raw))
            parts = [p for f in folders for p in f.rglob("*") if p.is_file()]
            by_name = {str(p.relative_to(p.parents[3])) if False else p.name: p for p in parts}
            reconstructed = b"".join((root / "parts" / str(i).zfill(5) / n).read_bytes()
                for n in manifest["files"]["big.json"]["parts"]
                for i in range(len(folders))
                if (root / "parts" / str(i).zfill(5) / n).exists())
            self.assertEqual(reconstructed, raw)
            self.assertTrue(all(sum(p.stat().st_size for p in f.rglob("*") if p.is_file()) <= LIMIT
                                for f in folders))
            self.assertTrue(any(p.name == "__report_manifest__.json" for p in parts))


if __name__ == "__main__":
    unittest.main()
