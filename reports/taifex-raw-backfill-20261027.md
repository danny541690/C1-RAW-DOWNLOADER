# TAIFEX RAW backfill — 2026-10-27
## Deployment
Source commit: ba21530ac74738a927d5a7adb67b40a5f92c961f.
741 local tests passed. Cloud validation step passed before entering the worker.
- Schedule 6: latest available date in 2026 backwards to 2013-01-01. Run https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40412322565
- Schedule 6-1: 2000-01-01 forwards to 2012-12-31. Run https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/40412322437

## Changes
Enable explicit --backfill in both production workflows. Remove the recorded-at-start key restriction in this mode so new expected units can run. Reopen prior empty and failed historical requests once for this repair pass, preserve prior evidence and lifetime attempts, retain cooldowns and bounded transport retries. Do not overwrite successfully verified RAW. Continue remote RAW readback, hash and native-format checks. Historical snapshots that cannot be recreated remain open evidence gaps. A source-empty response is not certified historical absence.

## Direct Drive baseline and activation evidence
Report ledgers read at 2026-10-26T22:27 UTC:
| Lane | Expected history request units | Saved units | History units reopened | All reopened items |
|---|---:|---:|---:|---:|
| 6 DESC |1836|1416|420|647|
| 6-1 ASC |1429|471|958|958|

Lane 6 additionally created 2 newly expected requests. All reopened items include requests beyond the canonical history plan; do not add them to history coverage. ASC saved total includes imported DESC records; only 471 belong to its assigned partition.

Both new run IDs are present in production STATUS, backfill_enabled=true. At the cited activation checkpoint source_requests_this_run=0 and saved_this_run=0; this proves preparation, not completed downloads. Both cloud workers were in progress.

## Completion limits
Not certified complete. Neither workflow success nor a fast audit proves complete data. The expected plan is not proof of the whole TAIFEX historical dataset universe. Numerical correctness and historical point-in-time correctness remain distinct from format/date/hash validation. Persist unresolved, unavailable and integrity problems rather than declaring missing data complete. Preserve old snapshot gaps and future-link exclusions.
