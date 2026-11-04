"""v0.95 isolated immutable candidate + version pointer QA (synthetic only)."""
import hashlib
import json
import os
import tempfile
import unittest
import uuid
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(root, dataset, year, rows, raw_sha, formula_version="test-v1"):
    root = Path(root)
    if not raw_sha or len(raw_sha) != 64:
        raise ValueError("RAW_SHA_REQUIRED")
    candidate_id = uuid.uuid4().hex
    p = root / "candidates" / dataset / f"year={year}" / (candidate_id + ".parquet")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("xb") as f:
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, f)
    digest = sha256(p)
    actual = duckdb.sql("SELECT COUNT(*) FROM read_parquet(?)", params=[str(p)]).fetchall()[0][0]
    if actual != len(rows) or digest != sha256(p):
        raise AssertionError("READBACK_FAIL")
    return {
        "candidate": str(p.relative_to(root)),
        "sha": digest, "raw_sha": raw_sha,
        "formula_version": formula_version, "rows": len(rows),
        "partition": f"{dataset}/year={year}",
    }


def publish(root, candidate, expected_generation, numeric_pass, pit_pass, fence):
    if not numeric_pass or not pit_pass:
        raise PermissionError("QA_GATE_BLOCKED")
    if fence != "ACTIVE":
        raise PermissionError("STALE_FENCE")
    root = Path(root)
    candidate_path = root / candidate["candidate"]
    if sha256(candidate_path) != candidate["sha"]:
        raise ValueError("CANDIDATE_DIGEST_MISMATCH")
    pointer = root / "release-pointer.json"
    old = json.loads(pointer.read_text()) if pointer.exists() else {"generation": 0, "partitions": {}}
    if old["generation"] != expected_generation:
        raise RuntimeError("STALE_GENERATION")
    newer = json.loads(json.dumps(old))
    newer["generation"] += 1
    newer["partitions"][candidate["partition"]] = candidate
    tmp = root / f".pointer-{uuid.uuid4().hex}.tmp"
    tmp.write_text(json.dumps(newer, sort_keys=True))
    os.replace(tmp, pointer)
    return newer["generation"]


def read_partition(root, partition):
    ptr = json.loads((Path(root) / "release-pointer.json").read_text())
    item = ptr["partitions"][partition]
    path = Path(root) / item["candidate"]
    if sha256(path) != item["sha"]:
        raise ValueError("CORRUPT_RELEASE")
    return duckdb.sql("SELECT * FROM read_parquet(?)", params=[str(path)]).df()


class ImmutableRelease(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.raw_sha = "a" * 64

    def tearDown(self):
        self.tmp.cleanup()

    def candidate(self, buy):
        return stage(self.root, "margin", 2026,
                     [{"security_id": "2330", "date": "2026-10-22", "buy": buy}],
                     self.raw_sha)

    def test_01_different_versions_have_distinct_paths(self):
        a, b = self.candidate(1), self.candidate(2)
        self.assertNotEqual(a["candidate"], b["candidate"])
        self.assertTrue((self.root / a["candidate"]).exists())
        self.assertTrue((self.root / b["candidate"]).exists())

    def test_02_candidate_duckdb_readback(self):
        a = self.candidate(9)
        self.assertEqual(a["rows"], 1)
        self.assertEqual(len(a["sha"]), 64)

    def test_03_publish_requires_qa(self):
        a = self.candidate(1)
        with self.assertRaises(PermissionError):
            publish(self.root, a, 0, False, True, "ACTIVE")
        self.assertFalse((self.root / "release-pointer.json").exists())

    def test_04_publish_requires_pit(self):
        a = self.candidate(1)
        with self.assertRaises(PermissionError):
            publish(self.root, a, 0, True, False, "ACTIVE")

    def test_05_fence(self):
        a = self.candidate(1)
        with self.assertRaises(PermissionError):
            publish(self.root, a, 0, True, True, "EXPIRED")

    def test_06_first_publish(self):
        a = self.candidate(7)
        self.assertEqual(publish(self.root, a, 0, True, True, "ACTIVE"), 1)
        self.assertEqual(int(read_partition(self.root, "margin/year=2026")["buy"].iloc[0]), 7)

    def test_07_stale_generation(self):
        a, b = self.candidate(1), self.candidate(2)
        publish(self.root, a, 0, True, True, "ACTIVE")
        with self.assertRaises(RuntimeError):
            publish(self.root, b, 0, True, True, "ACTIVE")
        self.assertEqual(int(read_partition(self.root, "margin/year=2026")["buy"].iloc[0]), 1)

    def test_08_version_switch_keeps_old_bytes(self):
        a, b = self.candidate(1), self.candidate(2)
        publish(self.root, a, 0, True, True, "ACTIVE")
        publish(self.root, b, 1, True, True, "ACTIVE")
        self.assertEqual(sha256(self.root / a["candidate"]), a["sha"])
        self.assertEqual(int(read_partition(self.root, "margin/year=2026")["buy"].iloc[0]), 2)

    def test_09_corruption_blocks_publish(self):
        a = self.candidate(1)
        (self.root / a["candidate"]).write_bytes(b"damaged")
        with self.assertRaises(ValueError):
            publish(self.root, a, 0, True, True, "ACTIVE")

    def test_10_unrelated_partition_not_replaced(self):
        a = stage(self.root, "margin", 2026, [{"id": 1}], self.raw_sha)
        b = stage(self.root, "prices", 2025, [{"id": 2}], self.raw_sha)
        publish(self.root, a, 0, True, True, "ACTIVE")
        publish(self.root, b, 1, True, True, "ACTIVE")
        self.assertEqual(len(read_partition(self.root, "margin/year=2026")), 1)
        self.assertEqual(len(read_partition(self.root, "prices/year=2025")), 1)

    def test_11_input_hash_lineage(self):
        a = self.candidate(1)
        publish(self.root, a, 0, True, True, "ACTIVE")
        ptr = json.loads((self.root / "release-pointer.json").read_text())
        self.assertEqual(ptr["partitions"]["margin/year=2026"]["raw_sha"], self.raw_sha)

    def test_12_empty_raw_sha_refused(self):
        with self.assertRaises(ValueError):
            stage(self.root, "margin", 2026, [{"id": 1}], "")

if __name__ == "__main__":
    unittest.main(verbosity=2)
