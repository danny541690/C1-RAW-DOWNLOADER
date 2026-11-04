"""Isolated JARVIS v0.95 Parquet integration tests. Synthetic fixtures only; no network/Drive/prod writes."""
import datetime
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


def canonical_headers(source, dataset, headers):
    """Normalize positional duplicates without losing domain context."""
    out = []
    seen = {}
    for index, label in enumerate(headers):
        key = str(label).lstrip("\ufeff").strip()
        seen[key] = seen.get(key, 0) + 1
        out.append(f"{source}_{dataset}_c{index:02d}_{key}_{seen[key]}")
    assert len(out) == len(set(out))
    return out


def validate_candidate(meta):
    required = ("source", "dataset", "content_date", "raw_sha", "schema_version")
    if any(not meta.get(x) for x in required):
        return "BLOCKED_METADATA"
    if meta.get("numeric_verified") is not True:
        return "BLOCKED_NUMERIC"
    if meta.get("pit_verified") is not True:
        return "BLOCKED_PIT"
    return "ELIGIBLE"


def parquet_release(rows, meta, folder):
    if validate_candidate(meta) != "ELIGIBLE":
        raise ValueError(validate_candidate(meta))
    year = int(meta["content_date"][:4])
    out = folder / meta["dataset"] / f"year={year}" / "part-000.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), out)
    readback = duckdb.sql(f"SELECT * FROM read_parquet('{out.as_posix()}')").df()
    if len(readback) != len(rows):
        raise ValueError("PARQUET_READBACK_COUNT")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    return out, digest


class IsolatedV095Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.meta = dict(source="TWSE", dataset="margin", content_date="2026-10-22",
                         raw_sha="e" * 64, schema_version="R5",
                         numeric_verified=True, pit_verified=True)
    def tearDown(self):
        self.tmp.cleanup()

    def test_duplicate_official_columns_positional(self):
        names = canonical_headers("TWSE", "margin", ["代號", "買進", "賣出", "買進", "賣出"])
        self.assertEqual(len(set(names)), 5)
        self.assertNotEqual(names[1], names[3])

    def test_parquet_written_readable_duckdb(self):
        rows = [{"security_id": "2330", "date": "2026-10-22", "margin_buy": 120},
                {"security_id": "1101", "date": "2026-10-22", "margin_buy": 0}]
        out, sha = parquet_release(rows, self.meta, self.path)
        self.assertEqual(len(sha), 64)
        self.assertEqual(out.suffix, ".parquet")
        self.assertEqual(duckdb.sql(f"SELECT SUM(margin_buy) FROM '{out.as_posix()}'").fetchall()[0][0], 120)

    def test_unverified_numeric_block(self):
        self.meta["numeric_verified"] = False
        with self.assertRaisesRegex(ValueError, "BLOCKED_NUMERIC"):
            parquet_release([{"security_id": "2330"}], self.meta, self.path)
        self.assertFalse(list(self.path.rglob("*.parquet")))

    def test_unknown_pit_block(self):
        self.meta["pit_verified"] = None
        with self.assertRaisesRegex(ValueError, "BLOCKED_PIT"):
            parquet_release([{"security_id": "2330"}], self.meta, self.path)

    def test_partition_isolation(self):
        rows = [{"security_id": "2330", "date": "2026-10-22", "margin_buy": 12}]
        out, sha = parquet_release(rows, self.meta, self.path)
        unrelated = self.path / "unrelated" / "year=2025" / "part.parquet"
        unrelated.parent.mkdir(parents=True)
        unrelated.write_bytes(b"unchanged")
        parquet_release([{"security_id": "2330", "date": "2026-10-22", "margin_buy": 15}], self.meta, self.path)
        self.assertEqual(unrelated.read_bytes(), b"unchanged")
        self.assertNotEqual(sha, hashlib.sha256(out.read_bytes()).hexdigest())

if __name__ == "__main__":
    unittest.main(verbosity=2)
