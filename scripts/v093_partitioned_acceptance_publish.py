"""Lossless bounded publication of large followup results.

Each child archive is below the existing acceptance publisher's 10 MB limit.
All source bytes are preserved via UTF-8-safe parts and a SHA-256 manifest.
No RAW sources, checkpoints, or source request attempt counts are changed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

LIMIT = 6_000_000
ALLOWED = {".json", ".md", ".log"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stage(source: Path, destination: Path):
    """Yield stable, bounded directories and file manifest."""
    manifest = {"schema": "JARVIS_LOSSLESS_REPORT_PARTITION_V1", "files": {}}
    entries = []
    for file in sorted(source.rglob("*")):
        if not file.is_file() or file.suffix not in ALLOWED:
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(source.resolve()):
            raise ValueError("REPORT_PATH_BOUNDARY")
        name = str(file.relative_to(source))
        raw = file.read_bytes()
        text = raw.decode("utf-8")
        if len(raw) <= LIMIT:
            parts = [(name, raw)]
        else:
            parts = []
            # Encode each text slice independently, avoiding a broken multibyte character.
            pos = 0
            while pos < len(text):
                step = min(len(text) - pos, 1_200_000)
                chunk = text[pos:pos + step].encode("utf-8")
                part_name = "__original_parts__/" + digest(name.encode()) + "/" + str(len(parts)).zfill(6) + ".md"
                parts.append((part_name, chunk))
                pos += step
            if b"".join(payload for _, payload in parts) != raw:
                raise ValueError("REPORT_PART_ROUNDTRIP")
        manifest["files"][name] = {"sha256": digest(raw), "bytes": len(raw), "parts": [n for n, _ in parts]}
        entries.extend(parts)

    manifest_raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode()
    if len(manifest_raw) >= LIMIT:
        raise ValueError("REPORT_INDEX_TOO_LARGE")
    batches = [[("__report_manifest__.json", manifest_raw)]]
    sizes = [len(manifest_raw)]
    for name, raw in entries:
        if len(raw) > LIMIT:
            raise ValueError("REPORT_SINGLE_PART_TOO_LARGE")
        if sizes[-1] + len(raw) > LIMIT:
            batches.append([])
            sizes.append(0)
        batches[-1].append((name, raw))
        sizes[-1] += len(raw)
    result = []
    for i, batch in enumerate(batches):
        dest = destination / str(i).zfill(5)
        for name, raw in batch:
            p = dest / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        result.append(dest)
    return result, manifest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--job", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--input", type=Path, default=Path("results"))
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="jarvis-followup-parts-") as temp:
        batches, manifest = stage(args.input, Path(temp))
        published = []
        for i, folder in enumerate(batches):
            child_job = f"{args.job}-{i:05d}"
            cmd = [sys.executable, "-m", "scripts.v093_acceptance_publish",
                   "--source", args.source, "--job", child_job,
                   "--status", args.status, "--input", str(folder)]
            # Fail closed: no skip of failed batches; deterministic identities support retry.
            subprocess.run(cmd, check=True)
            receipt = json.loads(Path("publication/receipt.json").read_text())
            published.append({"job": child_job, "record_sha256": receipt["record_sha256"],
                              "drive_receipt": receipt["drive_receipt"]})
        output = {"schema": "JARVIS_PARTITION_PUBLICATION_INDEX_V1",
                  "source": args.source, "job": args.job, "batches": published,
                  "original_files": manifest["files"]}
        out = Path("publication")
        out.mkdir(exist_ok=True)
        (out / "partition_index.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(json.dumps({"batches": len(published), "original_files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
