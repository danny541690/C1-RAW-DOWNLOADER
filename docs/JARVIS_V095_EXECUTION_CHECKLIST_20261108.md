# JARVIS v0.95 — Remaining Work / Execution Board (2026 first, 2000–2025 later)
Updated 2026-11-08. This is an execution checklist, not a completion certificate.

## P0 — In-flight first
- [x] 15-minute watchdog with no duplicate dispatch; first run succeeded.
- [x] Combined yearly audit and bounded existing November candidate B/S/G checks.
- [x] Add real TWSE/TPEx 2026 OHLCV source-day incremental producer and Drive generation checkpoint.
- [x] Verify first 2026 run 42430514598: 6 weekday slots, 10 successful source-days, 2 failed, 10 new Bronze + 10 Silver + 10 descriptive Gold, Drive cursor committed.
- [x] Persist source-day errors and print each failed unit in Actions logs for next run.
- [ ] Interpret 2 failures (likely non-trading days or API errors; must use actual error receipts, never assume) and classify VERIFIED_MARKET_CLOSED / HTTP_TEMP / SCHEMA_DRIFT / AUTH / REQUIRES_MANUAL.
- [ ] Validate yearly candidate calendar with official holidays and first-publication availability; weekend-only exclusion is insufficient.
- [ ] Establish genuine atomic multi-run writer/fencing against Drive and GitHub duplicate jobs, including deliberate race/restart tests (current generation check is not atomic).
- [ ] Cap source-day work by elapsed time as well as count; ensure cursor only advances after receipt committed, resume partial stage.
- [ ] Persist full task ledger per source/dataset/date, not only a single day offset; inventory candidates from v0.93 with hashes and native schemas.

## P1 — 2026 complete Bronze (six official sources + FinMind gap fallback)
- [ ] TWSE 2026 all documented datasets (not just OHLCV): institutional, margin, lending, valuation, foreign holdings, events.
- [ ] TPEx 2026 all documented datasets: institutional, margin, lending, foreign holdings, valuation, market cap, indices, events.
- [ ] MOPS historical revenue, original disclosed financial quarters, timestamps and revision vintage.
- [ ] TDCC weekly holding distribution, proper week mapping, numeric treatment and source-category guard.
- [ ] TAIFEX daily futures/options and institutional position files.
- [ ] NDC published indicators with release dates / no future data.
- [ ] FinMind free supplementary gap fill only; never silently supersede canonical official sources.
- [ ] Capture strict dataset denominators from official availability; distinguish NOT_PUBLISHED, MARKET_CLOSED, SOURCE_STARTS_LATER, FILE_MISSING, FAILED, VERIFIED.
- [ ] 2026 Jan–Nov source-month inventory and per-dataset/period SHA / CRC / row-count validation; avoid complete-month declarations from filenames.

## P2 — 2026 Silver conversions
- [ ] Per-dataset typed schema adapters, versioned source columns and revision history.
- [ ] Explicit TSE/OTC security IDs and listing dates; emerging board archived only, not analyzed.
- [ ] Correct monetary normalization to 億元; OHLC/nonnumeric, turnover, missingness and units.
- [ ] Source-month comparatives / exact as-of timestamp joins; validation by source daily/weekly/monthly/quarterly.

## P3 — 2026 Gold, PIT and provenance
- [ ] Register all 443 indicator formulas/dependencies/warmup periods; unsupported = DISABLED, never zero.
- [ ] PIT timing of announcements, monthly revenue, quarter filings, institutional holdings and corrected vintages.
- [ ] Bidirectional Gold→Silver→Bronze SHA/file receipt trace and reverse affected-indicator analysis.
- [ ] Recompute affected partitions only; no future leakage or survivorship drift.
- [ ] G0–G5 acceptance, actual verified denominator and explicit exception certificate.

## P4 — Scale out when 2026 G0–G5 passes
- [ ] Automatically queue 2000-01 to 2025-12 by source availability and oldest/latest scanning.
- [ ] Keep verified immutable 0.93 sources as candidate input; no blind copy and no unnecessary refetch.
- [ ] Retain 15-minute monitor and bounded retries, but schedule processing continuously in batches with durable checkpoints.
- [ ] Deliver by-year / by-month / by-source progress tables and error-history rollups, with real run IDs.
- [ ] Publish release only after full PIT/data lineage tests, separately from partial candidate ingestion.

## Completion rules
- Run success != dataset completion.
- 2026 incomplete until all eligible source/dataset/period cells independently pass; 2026-Dec future data isn't considered missing as of Nov 8.
- 2000–2025 does not proceed under a silent release gate bypass.
- Current 2026 production release flags remain false; candidate staging is usable only for QA.
