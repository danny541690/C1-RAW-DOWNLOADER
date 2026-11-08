# JARVIS C1 v0.95 | 2026 autonomous build acceptance contract (2026-11-08)

## Scope and non-negotiable controls
Single repo danny541690/C1-RAW-DOWNLOADER; GitHub Actions executes; Google Drive stores source bytes, transformed candidates, receipts and logs. Phase 1 only 2026-01-01 through the latest genuinely published source record. 2000-2025 will NOT be auto-dispatched. Keep BULK_COPY_APPROVED=false and RELEASE_APPROVED=false until separate evidence and formal decision. No look-ahead, no guessed unavailable financial data. Official TWSE/TPEx/MOPS/TDCC/TAIFEX/NDC first; FinMind fallback traceable and limited to approved scope.

## Actual code review 2026-11-08
Six source-specific scheduled workflows are running, but each couples download with some downstream candidate processing. TWSE and TPEx write immutable daily native Bronze, typed OHLCV Silver and descriptive-only Gold with scoped SHA readback. Other sources do not all have approved typed Silver adapters. The GitHub governance/v095/MANIFEST_INDEX.csv and CHECKPOINTS.csv currently hold only headers; remote per-source cursors do exist. 39 dataset contracts remain CANDIDATE_NEEDS_SCHEMA_AND_PIT_VALIDATION, zero production ready. In latest bounded annual inspection 1790 candidate objects and 66 source-month cells were inspected; this does NOT establish 100% data presence. Formal 443 Gold formulas, as-of publication vintage, full lookback and PIT have not been certified. Known source issues: MOPS typed revenue member missing on several raw archives, TDCC missing native manifest exception, TAIFEX 213 format exceptions, NDC 321 observation months not certified vintages.

## Target DAG (18 logical tasks, not 18 production-ready workflows)
D01-D06: independently collect each official source; native immutable SHA and source provenance, verify remote readback and durable checkpoint before acknowledge.
Q01-Q04: independent QA for equity markets, MOPS, TDCC and TAIFEX/NDC separated by dataset adapter; classify five defect types, official session/release calendars and native units.
R01-R02: transient HTTP 429/5xx/network retry max three with backoff+jitter; deterministic parser or schema failure quarantine, retry only after adapter revision. No blocking of unrelated tasks.
S01-S02: typed, versioned Silver on admitted sources, TSE/OTC codes, amounts standardized to 億元 and original units retained, de-duplicate, preserve trade_date/report_period/published_at/available_at/vintage separately.
G01-G02: Gold technical/chip and fundamentals/macro with 443-item (or actual versioned official catalog) formula dependency registry; per indicator code SHA, lookback, no future data. Unavailable inputs => NULL and enabled=false; not zero or estimated.
L01: forward and reverse lineage source request-> Bronze SHA -> Silver SHA/code SHA -> Gold SHA/formula SHA; reverse readback to source original plus PIT, fail dependent metrics only.
C01: durable single-committer Manifest/Checkpoint/error history controller, independent stage percentages and signed release receipt.
Keep old source workflows until validated shadow runs; no overlapping writer per source partition. GitHub concurrency group is NOT durable CAS; atomic fencing/lease and restart collision test needed before source cutover.

## Autonomous operation in 2026
The 2026-only controller checks recent source runs, skips active source writers, dispatches idle overdue source flows in bounded fanout, schedules separate QA if overdue, writes one auditable controller receipt. No forced redownload and no modification to successful partitions. Existing source cursor is authoritative. Do not self-promote when a workflow returns success. Scheduled GitHub cron can be delayed or dropped; use durable state + watchdog rather than relying on cron as guaranteed.
Market calendar denominator must use official eligible trading/release dates, not calendar days or Monday-Friday counts. Per dataset report raw_saved/QA_pass/Silver/Gold_descriptive/Gold_PIT/lineage_pass and quarantined/NOT_APPLICABLE; each percent has numerator and denominator.
Historical valuations, 24-month revenue highs, TTM, Stage3->4 and RS require data warming period and actual release vintage; no 2026 opening-day Gold assertion without preceding historical lookback.

## Release gates
G0 signed dataset schemas/eligibility and release date; G1 all eligible raw Bronze verified; G2 full typed Silver contracts; G3 every enabled Gold indicator independently tested with historical PIT and disabled indicator ledger; G4 full bidirectional SHA and row lineage with readback; G5 cross-runner CAS and replay safety; G6 reconciled denominator and exceptions; G7 user approval before historical expansion. Production year status remains BLOCKED until all gates supported by primary receipts, not just green GitHub jobs. If some original data never existed, use EXCEPTION_COMPLETE with reasons, not a false 100% success.
Keep check of SHA, native bytes and code/version before every incremental update.

## References
Microsoft Fabric medallion: https://learn.microsoft.com/en-us/fabric/onelake/onelake-medallion-lakehouse-architecture
Microsoft Fabric warehouse: https://learn.microsoft.com/en-us/azure/architecture/data-guide/azure-dataops-architecture-design
Microsoft Fabric incremental copy: https://learn.microsoft.com/en-us/fabric/data-factory/incremental-copy-job
GitHub concurrency: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
