# JARVIS v0.97｜v0.93 RAW 驗收→受控複製→v0.97 Bronze 二次驗收→Silver→Gold｜不可跳關作業契約
Version: 1.0 | Date: 2026-11-10 | Status: SPECIFICATION ONLY — DOES NOT AUTHORIZE AUTOMATIC MIGRATION
Owner intent: user explicitly requires v0.93 original data to be proven correct BEFORE copying into v0.97 Bronze; destination Bronze independently verified BEFORE Silver; Silver proven correct BEFORE Gold. No PIT or Silver schema failures may contaminate v0.93 RAW error tally.

## Immutable precedence
1. v0.93/01_RAW originals are READ-ONLY: NEVER move/delete/overwrite/normalize/rename in place.
2. Present 12-lane R3 history is evidence of issue processing, NOT certifying raw contents, NOT migration. R3 status processed=73146/73146, remaining=0; raw basic candidate=7136; legacy 65991 require evidence reconciliation; blocked=19. Frozen eligible inventory=82273, excluded=976 of 83249. Do not conflate counts or claim those 65991 are corrupt.
3. Review candidate by unique source file ID, SHA256, path, provider, dataset, timestamp and parser/rule version. Missing or unproven means UNKNOWN/BLOCKED, NOT OK. Strict provenance and idempotency.
4. RAW Stage-A checks only provenance/source naming, actual bytes/size/SHA/MD5, archive safety & CRC, basic format parseability, empty/truncated/corrupt, date/filename reasonableness; no PIT, no Silver normalization, no Gold factors. Dataset-aware expectations/temporal range checks belong to Stage-B Bronze or later, not RAW file damage.
5. Source absence may be NOT_YET_PUBLISHED, NOT_APPLICABLE, or MISSING only with evidence-based source/calendar policy; no fabricated missing dates. Existing correct = skip.
6. Stage-A fail/uncertain: isolate in ledger + bounded retries on same object; if confirmed bad, match exact official source/dataset/date and perform new candidate reacquisition (official priority, FinMind only compatible supplemental), preserve original and all SHA. Never substitute unrelated dataset/version. Hard exceptions after at most 3 safe attempts => QUARANTINED_WITH_EVIDENCE, pipeline continues on other files.
7. Transitions are per-file/per-partition gated, not a blanket release: A_PASS + original SHA + evidence + copy manifest required before copy; B_PASS + destination SHA + source-destination lineage before Silver; Silver_PASS + schema/unit/date/code/PIT validation before Gold; Gold_PASS + formula/reproduction/PIT lineage before usable research. Fail closed.
8. No background run claim absent actual workflow run ID and receipt. GitHub Actions may time out; checkpoints and single-writer locks required; no duplicate writers. All activities must have auditable Run IDs.
9. XQ manual data, FinMind, and six official sources must preserve separate source roles. Only TSE/OTC, daily or lower frequency (day/week/month/quarter/year), money normalized to 億元 ONLY in Silver, not in RAW or Bronze. No intraday/trade-by-trade.
10. This document governs future changes to JARVIS v0.97. Prior mistaken PIT/Schema-led NG counts must be reinterpreted, never silently erased.

## Stage A｜v0.93 原始資料正確性檢查 (pre-migration)
A0: Freeze inventory at a timestamp and reconcile 83249 files, 976 excluded non-market controls and 82273 candidate IDs; inventory alone ≠ market calendar completeness. Verify all 12 R2 lanes and R3 receipts, anti-duplicate file IDs, SHA conflicts, known status coverage.
A1: Build independent per-file original-byte verification manifest: source, dataset, symbol or market, source date, published-as-of when available, original Drive ID, full original path, MIME, byte length, MD5 (if available), SHA256 computed, archive members/CRC, parser format, test version/run, raw_status, evidence refs. A passed receipt from R2 must be checked for sufficient SHA/byte-coverage; else PARTIAL, not PASS.
A2: Validate *basic* format only (ZIP/xlsx archive CRC, CSV/text decoding/readability, JSON syntactic parse, XLS/PDF basic structural signature and appropriate bounded reader); no requirement to have Silver schema, numeric accounting, PIT, or Gold.
A3: classify PASS_BASIC / NG_CONFIRMED / MISSING_CONFIRMED / BLOCKED_TOO_LARGE / UNKNOWN_NOT_TESTED / NOT_APPLICABLE / NOT_YET_AVAILABLE / SHA_CONFLICT. Only PASS_BASIC is eligible to proceed; exceptions preserved.
A4: failures: diagnose cause; retry bounded 3 attempts with backoff; official source original-target reacquisition as new candidate when source mapping validated; compare SHA and source periods, verify candidate again; preserve invalid original in quarantine, never overwrite it; nonfixable marked QUARANTINED with failure evidence.
A5: Source-year-month coverage and expected availability calendar are a *separate* coverage report; 82273 is frozen existing-file inventory, not expected 2000–2026 files. Do not say 100% market coverage until source availability audit complete.
A6: Precopy gate: only A_PASS per versioned SHA/ID; anti-stale guard re-fetch metadata or bytes if source modified since approval. Generate APPROVED_COPY_MANIFEST and CHECKPOINT. Explicit reject lists.
A7: "A_PASS" means verified suitable as historical raw original bytes; **not** numeric semantic accuracy, PIT, complete expected data or suitability for backtesting.

## Stage M｜受控複製 v0.93 → v0.97 Bronze
M0: Copy, never move. Destination: ChatGPT資料存取/JARVIS_C1_v097_LIFECYCLE/02_DATA_LAKE/01_BRONZE_ORIGINAL/<source>/<dataset>/<yyyy>/<mm>/... (actual existing folder contract must be inspected; adapt only with explicit versioned mapping). Destination is original bytes, NOT normalized or recomputed.
M1: For each approved original: source_file_id, source_sha256, source_size, evidence_id, approved_manifest_version; idempotency key source_id+sha+target_dataset_path; ensure no collision, target immutable; if exists and hash matches SKIP; if differs HALT_CONFLICT and quarantine candidate, don't overwrite.
M2: Use temporary staging with fresh copy to final/manifest once hash checked; when cloud copy operation is server side verify destination bytes by re-read or strong hash independent of metadata where possible, not merely success API response. One writer per target, bounded concurrency by source.
M3: Write per-file COPY_RECEIPT: original file ID/path/SHA/bytes → destination ID/path/SHA/bytes; timestamp/run; copy attempt and comparison; no valid receipt=NOT_MIGRATED. Interrupted copies restart from checkpoint without duplicates.
M4: A failed individual target must not block unrelated targets. Never promote a quarantined, unknown or partially checked source.
M5: Compare expected approved-copy counts to successful destination receipts + skipped identical + outstanding failures; strict equality conservation and uniqueness.

## Stage B｜v0.97 Bronze destination independent acceptance
B0: Independently enumerate actual files at destination; compare M manifest; prevent foreign/unapproved file contamination.
B1: Read and hash destination bytes; exact SHA and size match original; source provenance exists; archive/format recheck basic integrity (target test), stable source/date/dataset tree, duplicates/gaps classification. Match source IDs, market expected dates when source calendars available; source count and dataset partition completeness separate from raw byte validity.
B2: Validate dataset-level business meaning only if explicitly scoped to Bronze dataset contract, never modify original bytes. Suspicious value/field changes => quality exception and downstream hold, not edit Bronze.
B3: Classification BRONZE_PASS/BRONZE_PARTIAL/BRONZE_NG/BRONZE_BLOCKED. BRONZE_PASS requires exact source↔destination mapping and immutable copy/hash proof. Bronze partially accepted may coexist with source partition exceptions; blocked not passed.
B4: Publish signed/versioned Bronze manifest with 100% reconciliation of eligible copy targets, exceptions and source coverage; only BRONZE_PASS passed onwards.

## Stage C｜Silver normalization AND QA (in v0.97 only)
C0: Input only approved Bronze partitions with exact hashes; deterministic transformations, row lineage.
C1: Normalize dates and publication/effective dates separately; TSE/OTC stock codes, data types, null/NA, dedup by valid business keys, columns, corporate action treatment per dataset; money in 億元, volume units explicit; no raw alteration.
C2: Temporal vintage and PIT at Silver: data may only become visible on actual release/filing/publication timestamp; avoid lookahead, restatements carry vintage; sample PIT tests and negative controls.
C3: Counts/keys, structural and numeric comparisons, date alignment, sum rules where supported; pass only where source-to-silver derivation and column mapping versions explain every retained/removed row. FAILED/UNKNOWN quarantined for Silver only, never retroactively corrupt Bronze.
C4: Release SILVER_PASS per dataset/partition, else hold and log.

## Stage D｜Gold factor creation AND QA (in v0.97 only)
D0: Input Silver_PASS only and parameter/version snapshot; compute 400+ only where prerequisites exist, mark unavailable indicators DISABLED_WITH_REASON, never fabricate data.
D1: Formula/unit/technical-chip-financial valuation correctness, sample back calculations, rolling windows, split-adjustment, trading calendars, PIT.
D2: Bidirectional Bronze↔Silver↔Gold trace for every factor/sample; contradictory evidence blocks the affected feature.
D3: GOLD_PASS only after comparable fixed benchmark, lineage and formula tests; model/backtest release gate is independent.

## Monitoring, reporting and completion
Every run: source/dataset/year/month and lane; total frozen candidates; raw verified PASS/NG/UNKNOWN/BLOCKED; sanctioned copy target/pending/success/hash mismatch; Bronze PASS/partial/blocked; Silver PASS/blocked; Gold enabled/disabled; exceptions and attempts; actual GitHub Run ID and timestamp.
Business stage progress: A verified / candidates, M matched copy / eligible A_PASS, B accepted / copied, C accepted / B input, D accepted / C input. Never combine 73,146 issues processed with 82,273 inventory as one percentage.
Until all earlier gates satisfied, system state is BLOCKED_NOT_CERTIFIED. The requested order is A→M→B→C→D; NO reverse gate, NO skipping.

## Implementation priority from 2026-11-10 audit
P0: Create an independent, NON-MUTATING A-stage reconciliation of 65,991 legacy R3 labels plus 7,136 basic candidates and 19 blocked, reconciling to frozen inventory. Historical R3 checkpoint=complete is not enough.
P1: Finalize and test stage-A raw-only scanner and source-specific safe failure rules, including large files and HTML error pages, with explicit per-file evidence; don't reinterpret missing schema as failed source bytes.
P2: source-calendar completeness and raw QA release manifest.
P3: implement idempotent verified COPY to v0.97 Bronze with dual-SHA lineage receipts, initially small samples.
P4: independently certify Bronze by source partition, then Silver then Gold.
P5: code/unit tests, failure injection, race/restart/checkpoint/duplicate/rollback verification before high concurrency.
All schedules must gate on predecessor receipts and stop on real structural system failures; keep task-level bounded retries and manual exception queue. This SOP is not proof the code presently enforces every stage.
