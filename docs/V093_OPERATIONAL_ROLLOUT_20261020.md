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
