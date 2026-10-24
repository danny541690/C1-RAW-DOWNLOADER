# TDCC backlog and checkpoint repair — 2026-10-24

The previous active_date_progress.unresolved was a backlog alias: it included candidates that had never been requested. It did not mean all remaining candidates had failed. At 19:23 Taipei, per-date journals contained 1860 saved + 1 source-empty entries for DESC 20261016; ASC 20251031 contained 1126 saved + 55 source-empty + one request intent in flight. Neither journal had an UNRESOLVED error entry at that read.

V6 adds explicit pending_total, not_attempted, failed, interrupted, retry_exhausted, retry_cooldown and other_unverified counters. The legacy unresolved field stays compatible and is marked as a backlog alias. A request intent may be an active request or an interrupted one; it is not automatically a source failure.

Every changed historical intent/result still writes the authoritative per-date HISTORY journal with remote readback verification. Identical journals are no longer rewritten. Derived CURSOR and STATUS are coalesced to 30 seconds, forced on date changes and orderly exit. Snapshot receipt changes remain immediately durable. Restarts load HISTORY even if the derived cursor predates the latest success. No successful RAW is redownloaded; no attempt cap or historical frontier is reset. Official request pacing, schema/date/security validation, immutable RAW and remote SHA confirmation remain unchanged.

Regression validation: 649 tests passed locally, including write failure/restart, immediate intent/result durability, snapshot checkpoints, date/final flush, no redownload and pending/error distinctions. In a single intent/result pair without a heartbeat, historical control-file writes fall from six to two after initialization; this is not a measured end-to-end throughput claim.

Still open: historical universe is based on current candidates, not certified historical membership; the weekly menu currently starts 2025-10-31 and does not provide 2000-01-01..2025-10-30 through this query. Source-empty is not historical absence certification. Numeric and PIT verification remain false.
