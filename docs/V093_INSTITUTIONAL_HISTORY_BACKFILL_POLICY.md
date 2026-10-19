# JARVIS C1 v0.93 — Institutional-style maximal historical warehouse
## Objective and cost boundary
Retain every legitimately obtainable historical source record, including delisted issuers and corrected filings, without requiring incomplete early-era chips to be filled. Use public/free bulk archives first; FinMind per-stock queries only for uncovered fields and periods, subject to provider quotas. User's one-hour/day research budget means no routine manual exports or repair loops. Never promise 100% all-market coverage from a dataset's published start.
## Authoritative configuration
`config/history_source_registry.json` contains source-specific starts, uncertainty, access, priorities, checkpoint and immutability policy. `scripts/history_backfill_plan.py --summary-only` produces a no-network work estimate. Its units are dataset-month planning records, **not** API calls or downloaded files. The existing 2024 job is independent and must not be interrupted.
## Bronze / Silver / Gold
Bronze: original response bytes, fetch timestamp, URL, dataset, source, hash, period, stock ID if applicable, source version and response metadata; immutable or versioned. Never silently replace a prior publication.
Silver: normalized types and units, unique identifiers with listing/delisting timelines, schema and numeric checks, source comparisons, effective date vs publication date vs ingestion date, explicit PIT_UNVERIFIED where publication timestamp is unknown.
Gold: indicators and backtest-ready snapshots with as-of cutoff and no lookahead, survivor-bias controls, adjusted vs unadjusted prices distinguished.
## Download and repair policy
- Primary bulk endpoints for TWSE/TPEx; source-specific start dates are discovery leads, not verified API availability.
- Download each month/dataset, save immediately to Drive `01_RAW/{year}/{source}/{YYYY-MM}`, checkpoint separately and log SHA256; successful units not refetched.
- At most four source request attempts per unit across restarts; retries for recoverable errors only; failures deferred, no endless loops. Respect rate limits and terms; paid options only after quantified free coverage and request budget.
- Record separate NOT_LISTED, NOT_YET_PUBLISHED, MARKET_CLOSED, NOT_AVAILABLE_FROM_SOURCE, DEFERRED_MISSING, SOURCE_HOLD, PIT_UNVERIFIED and QA_VERIFIED states.
- Distinguish earliest **published** data from earliest **actually retrievable** record; verify by source/dataset with real responses before marking complete.
- Track revisions, corrections, corporate actions, symbol changes and delistings. Revisions are new versions, not overwrite.
- Incremental daily collection after historical foundation; periodic revision scanning with bounded lookback and evidence-based exceptions.
## Execution order
1. Finish 2024 existing job and its missing reports independently.
2. 2010–2023, then 2025–latest, to support 2010–2026 benchmark study.
3. 1990–2009 where actual records exist; prioritize official bulk archives.
4. Continuous daily incremental updates and scheduled reconciliation.
Priorities determine order, **not exclusion**. Missing financial or institutional fields never block capturing prices.
## Gates before large backfill
Actual date-boundary canary per dataset, universe including delisted tickers, real free-tier quota accounting, storage estimate, PIT version policy, source rights/terms, resume and failure isolation, monthly QA report. A planning manifest alone is not a production downloader.
## Documented historical leads (not verified live coverage)
FinMind TaiwanStockFinancialStatements 1990-03-01; TaiwanStockPrice 1994-10-01. TPEx individual stock daily info page says since 1994/01, bulk daily quotes archive 2003/08; TWSE individual stock-day public page states since 2010-01-04. MOPS dataset-specific start remains unverified.
References:
- https://finmind.github.io/tutor/TaiwanMarket/Fundamental/
- https://finmind.github.io/tutor/TaiwanMarket/Technical/
- https://www.tpex.org.tw/en-us/mainboard/trading/info/stock-pricing.html
- https://www.tpex.org.tw/en-us/mainboard/trading/info/pricing.html
- https://accessibility.twse.com.tw/zh/trading/historical/stock-day.html
