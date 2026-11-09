# JARVIS C1 v0.96 — RAW First / P0 Operating Contract

Version scope: independent v0.96; repository `C1-RAW-DOWNLOADER`; initial discovery `2025-01,2026-10`. This is **not** a claim that legacy originals, 443 factors, PIT or source-month coverage have been certified.

## Operating architecture
- Preserve v0.93 original Drive file IDs; do not overwrite, rename or delete.
- `JARVIS_C1_v096/00_CONTROL`: immutable source JSON Manifest and compressed Parquet **metadata index** plus SHA-readback receipts.
- `01_RAW_ORIGINAL`: future optional copy of provenance-preserving original source bytes, **not active in P0**.
- `02_RAW_PARQUET`: future normalized source-data Parquet; **not active in P0**.
- `03_QUARANTINE`: corrupt/schema-unknown source triage; no synthetic missing/zero imputation.
- `04_REPORTS`: later signed coverage and exception receipts.
- `99_FUTURE`: reserved for a separate release of Silver/Gold.

## Three jobs — actual workflow
`.github/workflows/v096-raw-first-p0.yml`:
1. P0 inventory: read legacy 2025 and 2026 month folder metadata without downloading bytes; retain Drive IDs, file size, original names, MIME, MD5 when supplied by Drive. Flag partial listings and unknown types. Create isolated v0.96 namespace, publish immutable source manifest with SHA256 Drive readback.
2. P0 index normalize: transform that **metadata manifest only** into column-oriented ZSTD Parquet, verify Parquet row readback and source file SHA256.
3. P0 audit: reject duplicate IDs, false SHA/PIT assertions, source mutations or fabricated 443 Gold completion.

## Next phase P1 acceptance contract (not implemented yet)
- For each source dataset, define exact native schema and source-date semantics.
- Validate actual original source bytes; record original file SHA256, ZIP member SHA, native date and schema.
- Only then serialize daily+ source rows to Parquet; e.g., TSE/OTC/NDCTDCC/futures rows retain data date, acquired timestamp and native units.
- Preserve genuine zeros versus missing, original security codes and nonstock source categories; apply only standard typed field maps and 億元 conversion where appropriate.
- Write immutable compact Parquet source partitions, upstream file IDs and SHA; no PIT or factor inference.
- Report expected eligibility denominators from verified official data contracts; unknown is not automatically missing.
- Allow a partition re-run only if source SHA or native adapter version changed.
- Keep 0.95 schedules untouched in P0 to avoid deleting or damaging ongoing work. Before 0.96 is designated the primary writer, perform an explicit 0.95 schedule freeze / traffic cutover, retaining source files and history intact.
- Existing 2000–2024 source archives await separate bounded year-root discovery. Do not assume roots or backfill ranges.

## Cost and integrity
Source originals: reference-first, no full duplicative copies during P0. SHA256 over source bytes is required before raw migration can be certified; Drive MD5 metadata alone is not a SHA256. Parquet metadata index is *not* a financial market data partition. 0.96 P0 should consume a few small manifests and short-lived GitHub runner disk only.
