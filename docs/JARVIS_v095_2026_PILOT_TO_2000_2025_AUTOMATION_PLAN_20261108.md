# JARVIS C1 v0.95 — 2026 pilot → 2000–2025 historical backfill execution specification
Date: 2026-11-08. Status: PLAN / CONTROL MONITOR LIVE; BULK DATA BUILD NOT YET RELEASED.

## Invariants
- One repository, one authoritative controller; 15-minute watchdog only checks health and dispatches the bounded 2026 audit, not bulk ingestion.
- v0.93 is immutable source candidate, v0.95 is independent destination; reuse only after actual byte SHA256, native schema and release-date evidence. Never redownload accepted verified data.
- Six official sources (TWSE, TPEx, MOPS, TDCC, TAIFEX, NDC) primary; FinMind free as gap supplement. FinMind paid optional, not required. Listed/OTC for analysis; emerging-board data retained but excluded from Gold.
- 2026 pilot: 2026-01-01 through source-locally released latest date (dynamic cutoffs); unissued future dates are not missing. Historical after pilot: 2000-01 through 2025-12 (312 months); all-through-2026 current month total 323 months as of Nov 2026.
- Never claim completed merely because workflow conclusion is success; stage and dataset release flags must be signed by evidence.

## Proposed production controller (NOT YET IMPLEMENTED)
1. Durable Source Registry / Dataset Contracts: expected source-specific calendar, first available date, naming, native units, announcements and schema revisions; distinguish NOT_PUBLISHED, SOURCE_UNAVAILABLE, CONTRACT_PENDING, RECOVERABLE_ERROR and VERIFIED_GAP.
2. Immutable v0.93 inventory with paginated Drive listing, no depth-dependent completion; identify exact source-month dataset partition, bytes SHA, format validation (ZIP CRC, CSV encodings/BOM, Excel sheets, PDF parsing isolated).
3. Durable manifest and task ledger: primary key (source, dataset, date/period, vintage, stage, version); task states DISCOVERED→ELIGIBLE→LEASED→DOWNLOADED→BRONZE_VERIFIED→SILVER_VERIFIED→GOLD_CANDIDATE→PIT_AND_LINEAGE_PASSED→RELEASED, plus RETRY and QUARANTINED.
4. CAS single committer, per-partition lease TTL, fencing generation, ownership + Drive SHA256 readback; do not presume GitHub artifact or a local checkpoint is cross-runner persistent. Persist manifest/checkpoints in authoritative Drive/Git state with race tests.
5. Work queue by source/date partition: eligible Bronze sources first, Silver and Gold pipelined per partition after upstream verification; partition-local blocking only.
6. Retry transport errors up to 3 attempts per cycle with bounded exponential backoff+jitter; persistent circuit breaker after 5 cycles; independent queue proceeds; authentication failure/systemic contract failure halts that source, not whole build. Restart from persisted last ACK after GitHub timeout.
7. Silver validation: data types, TSE/OTC mapping, date/time, sign, unit (all monetary aggregates in NT$100m), distinctness, OHLC constraints, stock counts and source aggregation.
8. Gold 443 indicators: executable registry with formulas, dependencies, min-history/rolling-window warmup, availability-as-of and publication/filing timestamps; unavailable prerequisites => DISABLED_MISSING_INPUT, never fabricated values.
9. Bidirectional lineage: all Gold rows point to Silver partition id/hash, Bronze id/hash and native source/version; reverse traversal and deterministic replay. Record data vintage and revisions to avoid look-ahead.
10. Quality G0–G5: source provenance and availability; Bronze bytes/native schema; Silver counts, dates and units; Gold formula and PIT; cross-runner CAS/Drive readback and restart; full coverage denominator and exception certification.
11. Two-phase rollout: 2026 pilot must pass G0–G5 and signed actual data/manifest and restart evidence, only then allow HISTORICAL_BACKFILL_APPROVED; 2000–2025 backfill in historical month work units, newest/oldest priority alternating only where source supports it. Historical source starts later than 2000 must be labeled NOT_YET_AVAILABLE, not counted as failure.
12. Outputs each run: counts eligible/attempted/downloaded/skipped/repaired/quarantined, Bronze/Silver/Gold partition coverage and row counts, PIT PASS/FAIL/BLOCKED, lineage completeness, issue type, cursor, actual Run ID, Drive receipt and SHA. All percentages use verified source-specific denominators, not calendar-month counts alone.

## Known observed blockers as of 2026-11-08
- Formal MANIFEST_INDEX and CHECKPOINTS have 0 rows.
- 39 source dataset contracts have not passed production readiness gate.
- Actual cross-runner CAS/Drive writer and full-year Silver adapters not verified.
- 443 indicator historical PIT and filing-date evidence not certified.
- Earlier v0.93/v0.95 failures: API transport/authorization, pagination/truncation, TPEX nonnumeric price records, TDCC source misclassification and grouping, NDC, Parquet/column drift, Drive SHA and handoff, repeated partial pipeline failure.
- Existing 2026 yearly controller is an AUDIT AND BOUNDED CANDIDATE workflow; source downloads and full Gold production remain locked.

## Current live workflows
- .github/workflows/v095-2026-15m-watchdog.yml runs cron */15 and dispatches the existing 2026 yearly audit only when idle and eligible; success cooldown 60m, failure cooldown 15–360m. It cannot repair a missing production adapter.
- .github/workflows/v095-2026-auto-recovery.yml runs the bounded 2026 evidence audit via push/manual/watchdog. Previous 6h schedule removed.
- Current PHASE1_FLAGS remain BULK_COPY_APPROVED=false and RELEASE_APPROVED=false. Do not unlock without actual tests and explicit release gate.

## Next implementation gates, in order
P0: complete 39 contracts, dataset-specific availability denominators; durable manifest/ACK; Drive CAS and conflict regression.
P1: implement six-source official connectors per approved dataset, with reuse + retries + gap states; prove 2026 Bronze all eligible partitions.
P2: full 2026 Silver typed adapters and QA; add complete Gold dependency/PIT formula catalog; demonstrate reverse lineage and recovered interrupted run.
P3: 2026 full staged acceptance; then enable 2000–2025 historical queue with same mechanisms, keeping release separate from ingestion.
