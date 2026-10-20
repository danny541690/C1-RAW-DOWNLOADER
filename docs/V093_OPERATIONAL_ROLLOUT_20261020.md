# Operational rollout approved 2026-10-20

User approved the architecture review and phased implementation. This change:

- Keeps the existing reverse-history worker and R3 monthly matrix running.
- Resolves duplicate STANDARD folder names by a durable ID registry. Only a
  unique nonempty alias is selected automatically; ambiguous contents block.
  No folders or raw inputs are moved or deleted.
- Adds R4 native context, type/account, original name and unit retention.
  R3 output remains immutable and unapproved. R4 repairs all sources for the
  known failed July partition and only MOPS/FinMind elsewhere; it does not
  silently combine source generations into a new approved dataset.
- Rejects nonfinite candidate values, incomplete identity and malformed digests.
- Locks the QA dependency set. General legacy live preflights remain available
  by manual dispatch; every source/test commit no longer starts all live probes.
- Adds one serialized operational workflow, an hourly wakeup and a completion
  wakeup after R3. Long R4 repairs defer while R3 remains active. Each repair
  invocation has a time budget and durable per-input receipts.
- Writes `05_CONTROL/OPERATIONS/LATEST.json` and `LATEST.md` plus immutable
  snapshots and a targeted repair queue. Processing and approval stay distinct.
- Runs bounded TWSE/TPEx daily shadow capture with explicit response dates,
  immutable RAW ZIPs, readback verification and unapproved candidate Parquet.
  Market holidays and unproven dates are HOLD, not fabricated zero data.
- Rehearses the September price-feature path without approving a universe,
  units, calendar, corporate-action basis, PIT or independent Golden results.
  Insufficient warmup is NULL. This is not a stock-selection release.
- Adds a serialized expected-release publisher that requires byte-verified,
  generation-bound evidence for every gate. It is not server-side Drive CAS.

Formal release is still BLOCKED until source/unit contracts, historical security
universe, calendar, source revision/PIT rules, independent formula Golden and
full warmup are validated. Code presence and unit-test success do not satisfy
these data gates. No strategy weights or private portfolios are published.

Daily shadow first targets the latest weekday after the 18:00 Asia/Taipei
cutoff, or the preceding weekday before it. Weekdays are candidate query dates,
not a certified trading calendar. Same-day successful bytes are resumed;
automatic historical correction scanning remains a production gate.

The current baseline has one history worker and up to two old R3 workers.
The controller may do a short status/shadow task, but will not start another
long R4 rebuild until the R3 matrix completes. All data remain in Drive.

## Parallel rollout V2

- Keep the historical RAW workflow unchanged, including its single writer and reverse month cursor.
- The operational controller now owns only daily shadow and unified progress publication. It reads V2 repair shards and never writes worker queues. Old V1 queue is retained as a migration checkpoint.
- A separate workflow starts isolated July and financial repair jobs together, each with its own queue and folder registry. The financial queue rotates checkpointed months behind untouched months. A legacy controller still running old code blocks new workers until it exits.
- A third worker prepares TWSE native close history from 2025-09 through 2026-09. Input Parquet bytes must match R3 receipt hashes; small extracted close caches have readback hashes. It computes target September indicators after history preparation. Corporate action basis, calendar, universe and independent market-data Golden remain blocking; this is not a production signal.
- Worker wakeups run at :05/:25/:45. Workflow concurrency permits one batch at a time. Repair budgets are 35 minutes per lane, feature preparation 25 minutes, with checkpoints and a margin before job timeout. A queued wakeup cannot interrupt active work. Scheduler timing is not guaranteed.
- Folder registries are worker-specific and initially seeded from the canonical controller registry. Output ownership is disjoint by month/work type; no worker writes LATEST or an approved pointer.
- Worker completion triggers a short unified status refresh. Reporting stays grouped into data, feature and operational acceptance, with exceptions expanded as needed.
- This rollout adds execution capacity and indicator preparation. Complete stock selection, a two-page investment report and backtesting are still outstanding implementation work. No paid resources or new data subscriptions are enabled.

Validation: one consolidated offline suite passes 114 tests, including migration,
queue ownership, checkpoint fairness, old-writer handoff, numerical window Golden,
no future observation dependence, conflict quarantine and verified cache roundtrip.

### Live follow-up: FinMind monthly slice contract

Live reports confirmed that FinMind_FREE_2026 archives used the downloader's
`rows` envelope, while the parser only consumed `data`/table containers. Added
explicit envelope support with stock-scope and API-response-digest checks. The
native rows and monthly archive lineage remain intact; no unit/PIT approval is
inferred. The parser invalidates FinMind receipt keys only, keeping all previous
bytes and other source receipts. Worker queues requeue structurally completed
months once per parser revision, so an earlier zero-output receipt cannot hide
this repair. Already-running workers finish with their original code; the next
serialized batch applies the new revision without overlapping writers.

The consolidated suite now passes 118 tests. Remaining unresolved items include
market-wide totals without individual security IDs and latest-only snapshots
without proven historical dates; these must not be silently assigned a date or
stock ID merely to reduce the unresolved count.

### Real-data acceptance follow-up

- Read back two live feature caches for 2025-10 (1,043 and 1,046 rows).
  All 2,089 rows matched saved byte hashes, receipt row counts and source digests;
  all dates belonged to the stated month and all extracted prices were finite
  and positive. These are bounded samples, not full-market acceptance.
- Downloaded the immutable real archive
  `FinMind_FREE_2026_B000120_000239_2026-09.zip` (105,143 bytes), SHA-256
  `6ee851dbf6256c7a85068335ed0539925f3034610c0e1faa4cdba7db3e5150bf`.
  Archive hash and all 105 native member hashes matched the saved audit.
- New parser extracted 2,096 original rows and 16,768 numeric cells from all
  105 previously unresolved monthly slices. Stock ID, month and exact native
  record context matched each envelope; unit and PIT approval stayed false.
- Seven stock/date observations for code 1594 violate the OHLC relationship,
  including zero/low-volume records. All 56 numeric cells from those observations
  remain `QUARANTINE_OHLC`, with original values intact. This is a validation
  exception requiring market/source-definition review, not proof of a provider
  error. Do not fix prices, substitute zero, or infer trading status automatically.
- No production release was created by these checks. Current old-code workers
  remain active; the parser upgrade is pending for the next serialized batch.

### Independent formula crosscheck on real prices

The reusable read-only verifier `scripts/v093_price_sql_acceptance.py` compares
Python Decimal feature output against SQLite AVG/COUNT/LAG windows. The real
105-member archive produced 2,073 usable price observations across 105 codes.
All 24,876 formula/null comparisons passed, including 5,457 numeric comparisons;
7 OHLC-conflicting stock/date observations and 16 other nonpositive closes were
excluded. Adding a future observation did not change prior-period results.
This is an independent implementation check, not an independent market-source
Golden, nor trading-calendar/corporate-action/universe/PIT approval.

## Consolidated execution acceptance

Offline Engine Tests is now the single automatic full-suite entry point for
scripts, tests, dependency-lock and workflow changes. The separate governance
suite remains manual for diagnostics. Scheduled repair/features and operational
control no longer install dependencies and run the full suite in an extra
validation job before every batch.

A lightweight standard-library code gate reuses successful main-branch offline
acceptance for either the exact commit or matching Git blob signatures across
scripts, tests, workflow definitions and requirements-qa.lock. Documentation-only
commits can reuse that result. Failed tests, a different branch, changed runtime
inputs, incomplete Git trees or unreadable evidence cannot authorize workers.
Offline suite completion wakes scheduled workers and control automatically;
workers retain their existing serialized concurrency groups and checkpoints.

This removes repeated code regression work, not data checks: each new RAW,
STANDARD and feature batch retains provenance, readback and quarantine checks.
Production approval remains separate and blocked without required evidence.
The consolidated suite passes 124 tests locally, including acceptance reuse and
rejection of stale, failed, wrong-branch and incomplete-tree evidence.

### Cache resume repair

The first resumed feature job stopped at Drive's strict duplicate-name check.
Existing prepared periods and hashes were intact. Cache reads now inspect all
same-name aliases only after that exact duplicate-name error: every alias must
match the recorded byte digest (or all aliases must have identical bytes before
recomputation against the source). Differing bytes remain a blocking exception;
no file is deleted or overwritten. Input digest and cached row count are also
bound to the saved receipt. An identical unreceipted cache must match a fresh
extraction from the source before a receipt is recovered. Worker failures now
write a durable blocked status while preserving prepared-period progress.

The consolidated offline suite passes 126 tests including identical-alias resume
and rejection of conflicting aliases. This patch does not certify cache/source
market completeness or release readiness.

## Independent feature scheduling

Feature history now has its own serialized workflow, so a long financial repair
cannot hold its retry behind the entire repair batch. The parallel repair
workflow contains only the two existing repair lanes. Both reuse the same
successful code acceptance; no extra full-suite test job was introduced.

The feature handoff checks only the two observed pre-split workflow definitions.
It cancels only queued/pending legacy definitions with no jobs, leaving active
RAW and repair jobs intact. An active legacy feature job blocks handoff; an
already finished legacy feature job does not block it behind financial work.
Future feature runs use one dedicated concurrency group. Feature completion
refreshes the existing unified controller. The consolidated suite passes 130
checks including this handoff; data/release approval rules remain unchanged.

## 2024 full-year conversion continuation

User authorized continuing Layer02 conversion for all of 2024 after the current
2025/2026 repair scope completed. Verified current shards: July 1/1 and financial
21/21 structurally processed, still unapproved. Verified RAW/2024 year folder and
TWSE/TPEx/MOPS/FinMind month directories; December contains existing input files.
Directory presence is not proof of complete market/source coverage.

The existing parallel workflow adds a `2024` lane, ordered December to January.
It uses four-source R4 conversion with the new metadata index, throttled aggregate
checkpoints, immediate per-input receipts and unchanged content verification.
The lane owns REPAIR_QUEUE_2024_V2.json and a 2024-specific folder registry. It
cannot migrate or overwrite the completed 2025/2026 queues. Queue key/year/month/
source identity is checked before execution. Existing RAW is read only; no older
project data is migrated and no source redownload is performed by this task.

A month with no convertible input writes a blocked report and raises a durable
input exception instead of being counted complete. Other months can continue.
Missing sources and unresolved items remain explicit; all output is unapproved.
The existing controller now publishes separate 2024 progress out of 12 months.
The consolidated local suite passes 140 tests including year/scope isolation.
