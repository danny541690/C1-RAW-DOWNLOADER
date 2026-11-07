# JARVIS v0.95 R14 | 2026-11-08 execution contract (proposal, not release)

## Scope
2026-01-01 to 2026-11-08 latest published source data; after actual acceptance, 2000-2025 historical backfill. Nov 2026 is partial.

## Required precedence
0. Reuse existing v0.95 verified content (SHA256 and remote readback).
1. Validate and adopt original v0.93/legacy RAW files first. Do NOT redownload qualifying bytes.
2. Download *verified gaps only* from TWSE, TPEx, MOPS, NDC, TDCC, TAIFEX.
3. Fill remaining documented gaps from FinMind FREE where historically available. Record exact provenance. Never treat FinMind as official source.
4. Mark historical unavailable and other unresolved gaps explicitly, never fabricate zeros.

## Incremental three-tier DAG
Partition key: source/dataset/period/contract_version. Bronze object needs native byte SHA256, source lineage and Drive remote readback before COMMITTED. A committed partition immediately unblocks its eligible Silver worker, without a full-year barrier. Silver typed Parquet immediately unlocks only Gold formulas whose full source dependencies, warmup and as-of are valid. Missing data disables just the affected formula. All content immutable and reproducible. Maintain Bronze->Silver->Gold forward and Gold->Silver->Bronze/source reverse lineage, parent SHAs, source version, transform code SHA and formula SHA; invalidate only descendants when upstream changes.

## PIT and release
Use original publication/available_at and corrections vintage for as-of decision cutoff. No later finance report or stock-universe lookahead. Descriptive Gold never passes backtest research. All money presented as 億元 with unit metadata preserved. TSE/OTC only for analysis; emerging stocks stored only.

## Controller design
One controller and bounded parallel worker pools: legacy inventory 4, official Bronze download 2, Silver 3, Gold 2, QA/lineage 2 (tune from real quota and failure rates). Durable queue, immutable Manifest, Checkpoints, CAS/fencing, remote SHA readback, retries capped at 3 and quarantine; per-task restart SKIP for same content and code hashes. Watchdog schedule may recover dead runs but it must not create duplicate writers. GitHub Actions schedule is best-effort, not a guarantee of exact 15-minute intervals. ChatGPT not needed for per-partition wakeups.

## Current blockers / evidence
2026-11-07 Run 42383772658 is a PASS for bounded yearly legacy RAW inventory / two real TWSE candidate day reuse only, NOT a PASS for a complete year or 443 Gold/PIT. Original RAW inventory >=3765 candidates, 62/66 source-month folders, 51/66 nonempty, 24/24 ZIP samples CRC/SHA pass; large folder pagination unfinished. Formal governance/v095/MANIFEST_INDEX.csv remains header-only as checked 2026-11-08. Prior CHECKPOINTS.csv empty; 8 registries pending, 39 dataset contracts candidate. Real cross-runner CAS, actual missing-source T2 new raw writer, full formula DAG and PIT require measured evidence.

**Do not set BULK_COPY_APPROVED or RELEASE_APPROVED true based on workflow green status.**

## Real release sequence
G0 source contract -> G1 one validated legacy partition -> G2 one actual missing source raw write+remote SHA+CAS+restart skip -> G3 one Silver and Gold + two-way provenance + PIT -> G4 six-source bounded canaries -> G5 2026 monthly partitions -> G6 443 formula registry statuses -> G7 publish/trace/PIT -> only then expand to 2000-2025. Failed gates block only dependent partition/metric where safe.

## Full SOP artifact
JARVIS_v095_完整建庫與自動執行SOP_20261108.pdf generated for user in ChatGPT session. Drive upload from this runtime was attempted but failed with `container_session_unavailable`; the new `C1_0.95/60_OPERATIONS_QA` folder was created. Do not claim PDF saved to Drive until actual verification.
