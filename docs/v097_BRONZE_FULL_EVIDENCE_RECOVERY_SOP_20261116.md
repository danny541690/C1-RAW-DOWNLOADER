# JARVIS v0.97 BRONZE READY — 2026-11-13 to 2026-11-16 recovery contract

## Scope and immutable cohort

The seven-source frozen cohort is exactly 74,750 unique original source IDs. The
last complete formal source-release baseline as checked on 2026-11-16 was Run
43841716671: 35,467 READY **for Bronze-to-Silver input only**, 39,283 HOLD.
The same report explicitly says `pit_backtest_release_approved=false`.
Never present its 35,467 as full historical PIT-verified backtesting approval.

A separate full-dataset gate (Run 43841831287) covers 82,273 QA entries,
82,393 B entries and has Silver/Gold blockers. These are a **different scope**,
not additive to or a substitute for the frozen 74,750 source-ID cohort.

## Evidence-based findings from recent incident history

1. The 7,489 exception-ledger failure (Run 43831960194) threw
   `2025_ADMISSIONS_WITHOUT_OFFICIAL_PROOF` because 1,132 special-RAW QA records
   exceeded the main official checkpoint's 1,130 exact matches. This was a
   proof ledger aggregation mismatch, not permission to bypass the gate.
   Run 43837035946 reconciled two *distinct original IDs* using a separate
   official retry receipt and original SHA/day/code/holders/shares checks. The
   other 726 expired official-history dates, 1 query error and 1 unreadable
   response remain properly classified; special securities are segregated
   from TSE/OTC ordinary stocks.
2. V2 parsers and source-specific D gates repeatedly succeeded, but did not
   create verified **all-row, all-field, independent publisher, PIT** evidence.
   The evidence-gap census Run 43839581374 (and 43841383515) showed
   24,429 lacking native V2 checkpoint, 11,248 native-inspected HOLDs lacking
   independent full-file attestation, and 3,606 historical
   format/identity conflicts. These categories are a snapshot, not an
   immutable queue; re-run census on current checkpoints.
3. The seven-source publisher bridge fetches documentation/pages and some
   dated samples. A publisher landing-page SHA or daily close-only witness is
   **not** evidence of an entire dataset's rows and fields.
4. Many old ZIP containers are self-assembled. Original ZIP/member CRC and
   SHA prove immutable bytes and membership, not the claimed original publisher.
   Dataset/date/source identity requires independently verifiable provenance.
5. There were two distinct uses of READY: Bronze-to-Silver input eligibility
   and full published/PIT historic backtest eligibility. They must be
   reported separately and never upgraded by label confusion.
6. Successful GitHub Actions jobs prove task execution, not zero remaining
   HOLD. The `remaining=0` field in some reports refers to an already
   visited cohort, not all 39,283 disputed records.
7. Historical schema cannot be a uniform `TWSE=open/high/low/close/...`
   across all source datasets. Versioned dataset-level schema is required;
   `v097_evidence_contract.py` intentionally refuses to infer historical
   schemas without source evidence.

## Official historical source notes

- TWSE daily close listing is presented starting 2004-02-11:
  https://www.twse.com.tw/zh/trading/historical/mi-index.html
  A05 has a different field set and multiple daily product times:
  https://eshop.twse.com.tw/zh/product/detail/cfec9a1470e448ec91bfde006db361e8
- TPEx current daily close listing begins 2007-07; 2007-01 to -06 is
  published via a distinct historic page:
  https://www.tpex.org.tw/zh-tw/mainboard/trading/info/mi-pricing.html
- TDCC holdings portal retention is one year; historic online query begins
  2008-07; "total shares" has specific inclusion rules. Expired period
  does NOT mean one may fabricate missing official confirmation:
  https://s.tdcc.com.tw/portal/zh/smWeb/qryStock
- TAIFEX daily market downloadable history has yearly ZIPs; after-hours
  trade-date attribution is not the wall-clock calendar day:
  https://www.taifex.com.tw/cht/3/futDailyMarketView
- FinMind v4 dataset and individual data_id must be distinguished. FinMind
  sometimes redistributes Taiwan exchange data, so three feeds need not be
  independent original publishers:
  https://github.com/FinMind/FinMind-MCP/blob/master/knowledge/datasets.md

## Newly implemented code (safe and non-promoting)

- `scripts/v097_evidence_contract.py`:
  exact key/full-column/full-row/numeric comparison, reject missing or
  duplicate keys, reject ambiguous numeric thousands separators and
  look-ahead timestamp. A successful 3-way content digest is *not* proof of
  publisher independence or original-blob lineage.
- `scripts/v097_fullfile_evidence_builder.py`:
  incremental (default 24, workflow 32) per-source actual Bronze byte/SHA
  verification; reuse immutable V2 and existing third-party evidence;
  records precise HOLD reasons in per-source checkpoints and Drive quality
  reports. It does **NOT** manufacture missing official or independent
  historical payloads and does **NOT** sign a release.
- `.github/workflows/v097_bronze_full_evidence_auto.yml`:
  push-only strict smoke tests; tagged manual kickoff and hourly
  half-hourly schedule run seven source-independent builders,
  independently run D and full-file/PIT preflight, perform frozen 74,750
  census, dispatch existing Bronze input release only when idle.

## Critical unresolved engineering before any additional READY

No completed general-purpose official/independent **full historical response
fetcher with source-specific all-field parsers** exists for all seven sources.
It is technically and logically impossible to certify 11,248 records just by
running the orchestrator. Where original primary publication receipts are
unobtainable, retain `HOLD_OFFICIAL_HISTORY_UNAVAILABLE` with documented
attempts instead of setting `all_rows_verified=true`.

The independent signed Release Gate must re-fetch referenced bytes, recompute
their hashes and complete row digests, verify the exact source dataset and
historical schema, verify third-party publication independence, and check PIT.
A self-attested JSON truth flag, even with a syntactically valid SHA string,
is never sufficient.

## Next user command: safe full trigger

The user can instruct ChatGPT:
"立即執行 JARVIS v0.97 BRONZE 全檔證據自動修復。請在
`danny541690/C1-RAW-DOWNLOADER` 新增
`scripts/v097_bronze_full_evidence_run_request.txt`，Commit message
包含 `[BRONZE-FULL]`，確認
`.github/workflows/v097_bronze_full_evidence_auto.yml` 完整模式已觸發，
檢查全部七來源 Job、D Gate/PIT/Release Run ID 和 Google Drive 報告；
只以正式 Release receipt 回報 READY 增減；Silver/Gold 禁止。"

This script marker is trigger-only, not a forged evidence record. If the marker
already exists, update it with a new unique, non-secret command sequence.

## Close criteria

- All 74,750 original IDs have verified and exclusive formal disposition.
- Every source-specific HOLD can be mapped to actual immutable evidence and
  unresolved external proof. Unobtainable history is never fabricated.
- All source/proof/checkpoint/manifest references reconcile; no premature
  claim that a remaining HOLD is READY or that 82,273/82,393 equals 74,750.
- Source bytes immutable; no Silver/Gold calculation or transformation.
