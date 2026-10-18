# C1 v0.93 — Remaining two production blockers (2026-10-19)

## 1. Full dataset coverage: NOT COMPLETE
Four-source mini E2E passed, but FinMind adapter only downloads 2330 TaiwanStockPrice sample, MOPS only monthly revenue pages, and TWSE/TPEx only bulk daily quote tables. Need explicit dataset inventory, expected ticker/date coverage and adapters for institutional, margin, fundamentals, financial statements, corporate actions, and provenance. No sample may be labeled full market. Do not launch full annual capture before inventory and adapters are implemented.

## 2. Automatic continuation: NOT COMPLETE
Cross-job Drive readback has passed, but no production scheduler that automatically advances months across GitHub jobs and survives cancellation/timeout. Need chunked monthly jobs, idempotent durable progress, source-attempt ledger, single active run, continuation trigger, bounded retries, and end-of-year report. Verify a real interruption and automatic continuation. Manual rerun does not qualify.

## Current GO gate
NO-GO. Prior consolidated 4/4 Jobs PASS validates connectivity and persistence only. No 2024 full-market production download was started by this document.
