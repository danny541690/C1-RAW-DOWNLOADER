# Official database backfill — 2026-10-27

User-authorized lane numbering: 1 RECENT_ASC 2013-01 to 2026-10; 2 RECENT_DESC 2026-10 to 2013-01; 3 EARLY_ASC 2000-01 to 2012-12; 4 EARLY_DESC 2012-12 to 2000-01. Retain lane identities, shared month claims, RAW, cursors and source cooldowns. Renumbering does not restart successful downloads.

Plan revision OFFICIAL_DATABASE_BACKFILL_20261027_V2 reconciles already-visited months via the durable retry queue and preserves the unvisited frontier. New explicit production backfill flag permits one new bounded retry pass for recorded exhausted, attempt/time-limited, source-empty and content-incomplete items. Prior status, attempts, retry cycle and error are archived. Verified unchanged RAW remains skipped. Explicit official period and company/endpoint scope blocks remain visible and are not declared complete. Existing per-point 3 attempts, 5-cycle budget, source throttles and remote readback remain active.

Local full suite: 744 tests passed. Final source commit 63d185e34c6eecee746aae1a96f611f331ffc624. Cloud full-suite gate precedes handoff and repair jobs. Intermediate test-failing source is blocked by the gate; final gate status must be checked before claiming production execution.

No claim of whole database completeness or numerical/PIT certification. Workflow success and visited ranges do not establish full source universe, complete fields, or correct historical values. Unresolved source, row-content, scope, missing RAW and period limitations must remain in OFFICIAL_UNRESOLVED_ITEMS.json. Current goal is repair of TWSE/TPEX/MOPS RAW across the stated partitions; this is not a second-layer transform.
