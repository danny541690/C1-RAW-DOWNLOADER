# JARVIS C1 v0.93 — 2024 Annual Automation Go/No-Go Audit
Audit date: 2026-10-18
Gate: **NO-GO for unattended full-market 12-month download**
Evidence: GitHub repository code and existing Actions run results.

## Confirmed completed
- Google Drive OAuth upload and hash-confirmed readback pass (run 39111951187 attempt 4).
- Cross-job Drive checkpoint canary pass (run 39134420625).
- Four-source small historical canaries and 27 offline tests pass in recent preflights. Canary samples are NOT full market.
- 12-month simulation handles failures and deferred queues; does not prove production behavior.

## Critical blockers
1. **ChatGPT trigger unproven**: current GitHub connector does not expose workflow_dispatch. Push trigger works only when a suitably scoped workflow exists and is pushed; annual-plan workflow is dry-run-only.
2. **Production workflow absent**: no .github/workflows/v093-annual-actual-firstpass.yml found in repo during audit; standalone first-pass script is not an automatically deployed workflow.
3. **Inadequate source coverage**: annual_actual_firstpass.py is PARTIAL by design:
   - TWSE STOCK_DAY only ticker 2330 per month, not all listed securities/datasets.
   - FinMind TaiwanStockPrice only ticker 2330, omits other dataset types and market universe.
   - TPEx queries only days 1–7 in each month, including closed days, not full history.
   - MOPS only monthly revenue sii/otc HTML; not all financial reports or PIT announcements.
4. **Data quality**: valid() only checks nonempty/header/table. No robust source-vintage period test, OHLC/numeric checking, historical universe, duplicate data, date publication/PIT logic, content-month correctness. TPEx accepts merely presence of 'tables'; MOPS accepts any HTML containing a table. Never mark QA_VERIFIED.
5. **Retry safety**: first-pass script retries each request at most four times during one process, but loses attempt counters across reruns; thus exceeds lifetime per annual logical unit. Catches generic exceptions without classified source-wide hold, Retry-After or quotas. No backup-source reconciliation pipeline; no provenance-based unit-filling.
6. **Durable checkpoint**: first-pass writes per-unit JSON under _CHECKPOINTS, but excludes durable cumulative attempt counts, source data SHA receipt, timestamp and machine-readable repair queue. If checkpoint write fails after successful raw save, the run terminates instead of isolating/recovering. Existing file accepted by weak structural check and can be treated as valid without matching saved receipt.
7. **Remote structure mismatch**: first-pass saves in 01_RAW/{source}/{YYYY-MM}, not approved 01_RAW/{year}/{source}/{YYYY-MM}; reports in 01_RAW/_REPORTS and checkpoints in 01_RAW/_CHECKPOINTS rather than appropriate 05_CONTROL/07_REPORTS.
8. **Missing required reports**: no durable month-end MONTHLY_PROGRESS.md, MISSING_UNITS.csv, aggregate year report, REPAIR_QUEUE.json, request counts, bytes/elapsed durations, coverage numerator/denominator by dataset.
9. **Continuations**: one-process January→December loop, no safe renewal / lock lease / rescheduling for interrupted GitHub runner. Existing job simulation doesn't satisfy full-year auto-continuation.
10. **Partial responses**: HTTP content size limit 8 MB may cut large datasets; treating any nonempty response as complete unsafe. API licensing/rate caps and per-source point-in-time contracts require verification.
11. **Safety**: OAuth Testing refresh token may expire in ~7 days for full Drive scope. GitHub public repo should contain no private datasets, secrets or hidden strategies.
12. **Production smoke gate**: no live one-month end-to-end audit for all four source datasets with correct Drive folder structure, per-unit receipts and verified per-market coverage.

## Required next steps before GO
1. Author true multi-dataset source contract and historic security universe.
2. Implement source adapters with date, market, schema, numeric and PIT metadata validation.
3. Implement durable per-unit immutable raw storage, SHA receipts, correct year-first layout, control/report folders and month-end gap/repair lists.
4. Implement global bounded retry ledger (4 max per annual logical unit), source circuit breakers, checkpoint/idempotency, and alternative-source provenance.
5. Implement workflow orchestration with self-continuation and concurrency lock. Verify a ChatGPT-supported single-command GitHub trigger instead of assuming dispatch exists.
6. Complete one full live month with 4-source data, independent readbacks and discrepancy reports; ensure no unverified data marked correct.
7. Demonstrate interrupted runner recovery, missed month continuity, valid next-command repair-only behavior, and full 12-month dry simulation.
8. Then launch 2024 production workflow; do not reuse earlier experimental data.
